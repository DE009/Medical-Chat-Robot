from elastic_search import Elastic
import json
import os

import langchain
from langchain_core.prompts import PromptTemplate
from langchain.tools import tool
from langchain_core.output_parsers import StrOutputParser
from langchain_community.embeddings.dashscope import DashScopeEmbeddings
from langchain.memory import ConversationBufferMemory
from langchain_community.llms import Tongyi
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.agents import AgentExecutor, create_react_agent
from langchain.pydantic_v1 import BaseModel, Field

from langchain_community.tools import DuckDuckGoSearchRun
from langchain_community.tools import DuckDuckGoSearchResults

from langchain_core.runnables import RunnableLambda
from langchain_core.runnables import RunnablePassthrough
from operator import itemgetter

els_url = "https://118.178.196.244:9200"
els_key = "Z1FnVVdZMEJnLUNkTWFrdXdfdk46YVBjdEtyVHhTek90VTloSUV3LUNIZw=="
os.environ["DASHSCOPE_API_KEY"] = "sk-a34e3a056413489f8e3300bef0a1a6f8"

es = Elastic(els_url, els_key)


class Tools:
    # 工具类，包含所有需要的tools

    # 默认self是传入的对象本身。而@tool修饰后，就没有默认传毒对象了。所以，这里不用写self，直接执行。
    # 当然，这样的话，也就相当于一个类方法了。和对象没有关系。不过无所谓，这里tool本来就是为了逻辑清晰而用的。
    @tool
    def search_indication(indication: str) -> list[dict[str:str]]:
        """search with indication of patient and return top 10 relative medicine."""
        result = es.base_search("indication", key_word=indication)
        return [
            {
                "indication": hit["_source"]["indication"],
                "medication_name": hit["_source"]["medication_name"],
            }
            for hit in result["hits"]["hits"]
        ]

    def search_manual(self, medication_name: str) -> list[dict[str:str]]:
        result = es.base_search("medication_name", key_word=medication_name)
        if result['hits']['total']['value']:
            return [
                {
                    "manual": hit["_source"]["manual"],
                    "medication_name": hit["_source"]["medication_name"],
                }
                for hit in result["hits"]["hits"]
            ]
        else:
            return False

    @tool
    def ask_human(question: str):
        """ask patients for the information they need to help you diagnose"""
        answer = input(question)
        return answer


class ChatBot:
    def __init__(self, debug=False) -> None:
        # debug
        if debug:
            langchain.debug = True
        # 上下文记忆（ChatBot对象的一个有状态变量。其他都是构建函数。还有一个retriever_cache是有状态的。其他都是执行）
        self.memory = ConversationBufferMemory(
            return_messages=True, memory_key="chat_history"
        )
        self.prompts = self._prompt_init("./prompts.json")
        self.llm = Tongyi(model_name="qwen-72b-chat", temperature=0.5)

        self.tools = Tools()

        # 构建三个agent
        self.diagnose_agent = self._agent_init(
            prompt=PromptTemplate.from_template(
                self.prompts["diagnose_prompt"] + self.prompts["react_base_prompt"]
            ),
            tools=[self.tools.ask_human],
        )
        self.medication_agent = self._agent_init(
            prompt=PromptTemplate.from_template(
                self.prompts["medication_prompt"] + self.prompts["react_base_prompt"]
            ),
            tools=[self.tools.search_indication],
        )
        self.other_agent = self._agent_init(
            prompt=PromptTemplate.from_template(
                self.prompts["other_prompt"] + self.prompts["react_base_prompt"]
            ),
            tools=[DuckDuckGoSearchResults()],
        )
        # 构建chain
        self.rag_chain = self._rag_chain_init()

        self.router_chain = self._router_chain_init()

        self.contextualize_q_chain = self._contextualize_q_chain_init()

        self.full_chain = self._init_full_chain()

    def _prompt_init(self, file):
        prompts = {}
        with open(file, "r") as f:
            prompts = json.load(f)
        return prompts

    def _agent_init(self, prompt, tools):
        # 构建agent函数。
        # 注：agent对象本身不维护memory了。避免输入格式的问题。但是agent，可以通过prompt构建时，模板从输入的dict中，获取到chat_history这个key的value，并放入template，实现memory。从而避免了输入格式冲突，同时保留了memory的功能。
        # Construct the ReAct agent
        agent = create_react_agent(self.llm, tools, prompt)
        # Create an agent executor by passing in the agent and tools
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        return agent_executor

    def _contextualize_q_chain_init(self):
        # 构建上下文联系chain
        # 联系上下文，重写用户问题，包含上下文信息。提升LLM召回能力，（避免因长上下文导致的LLM召回能力下降，无法正确结合上下文理解用户问题）
        contextualize_q_prompt = PromptTemplate.from_template(
            self.prompts["contextualize_q_system_prompt"]
        )
        return contextualize_q_prompt | self.llm | StrOutputParser()

    def _rag_chain_init(self):
        # 构建rag chain，根据输入的问题。构建找到说明书，构建vector，然后进行rag回答用户问题。
        embeddings = DashScopeEmbeddings(
            model="text-embedding-v2",
        )
        extract_med_name_chain = (
            PromptTemplate.from_template(self.prompts["extract_med_name_prompt"])
            | self.llm
            | StrOutputParser()
        )
        # 构建rag的vectorstore对象。并存在cache中，避免重复查找说明书和构建vectorstore，提升效率。
        # key:medication_name; Value: 对应说明书经过切分、embeddin后的VectorStore对象
        retriever_cache = {}

        def create_retriever(medication_name: str):
            # 创建retriever
            # 若有cache，则直接返回；不重复构建
            if medication_name in retriever_cache:
                return retriever_cache[medication_name]
            else:
                # 若无cache。
                # 1. 搜索药物对应的说明书；2. 按照chunk_size，切分为文本块；3.通过embedding模型，构建vectorstore对象。4. 返回retriever对象。
                print(medication_name)
                manual = self.tools.search_manual(medication_name)
                print(manual)
                if manual:  #是否有搜索结果，有，做retriever，无，则返回string信息告诉LLM。
                    text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=512, chunk_overlap=200
                    )
                    splits = text_splitter.split_text(manual[0]['manual'])  # 取检索到的第一个说明书，构建retriever
                    vectorstore = FAISS.from_texts(splits, embedding=embeddings)
                    # 将当前药物加入cache
                    retriever_cache[medication_name] = vectorstore.as_retriever()
                    return retriever_cache[medication_name]
                else:   # 若没搜索到结果，则告知LLM没有结果，以及可能的问题所在。
                    return "抱歉，没有相关的药物。可能是用户问题不清晰，或者当前药物库中没有该药物，抱歉。"      

        return (
            #     {"input":itemgetter("input")}|
            RunnablePassthrough.assign(
                context=extract_med_name_chain | RunnableLambda(create_retriever)
            )
            | PromptTemplate.from_template(self.prompts["rag_prompt"])
            | self.llm
            | StrOutputParser()
        )

    def _router_chain_init(self):
        return (
            PromptTemplate.from_template(self.prompts["router_prompt"])
            | self.llm
            | StrOutputParser()
        )

    def _init_full_chain(self):
        def contextualized_question(input: dict):
            if input.get("chat_history"):
                return self.contextualize_q_chain
            else:
                return input["input"]

        def router(info):
            if "药物推荐" in info["topic"]:
                return self.medication_agent
            elif "诊断" in info["topic"]:
                return self.diagnose_agent
            elif "药物详细内容" in info["topic"]:
                return self.rag_chain
            elif "其他内容" in info["topic"]:
                return self.other_agent
            elif "结束对话" in info["topic"]:
                return False

        return (
            # router chain，分流，结果进入topic。通过
            {"topic": self.router_chain, "input": lambda x: x["input"]}
            |
            # 将memory passthrough到上下文中。
            RunnablePassthrough.assign(
                chat_history=RunnableLambda(self.memory.load_memory_variables)
                | itemgetter("chat_history")
            )
            | RunnablePassthrough.assign(input=contextualized_question)
            | RunnableLambda(router)
        )

    # def chat_tempo(self):
    #     while True:
    #         input_str = input(":")
    #         # 这里必须吧input做成dict的格式，因为输入时，通过lambda表达式获取的。可以正常运行，这里暂时先就不改了。
    #         # 算了，不管了，反正chain之间，passthrough的数据格式，统一用dict。prompttemplate中用{key}获取即可。
    #         inputs = {"input": input_str}
    #         if input_str != "q":
    #             response = self.full_chain.invoke(inputs)
    #             if response == False:
    #                 # 若返回的结果是False，代表用户问题被分流到结束对话。
    #                 # 清空历史记录，返回“再见，期待与你下次相见“
    #                 self.memory.clear()
    #                 print("再见，期待下次再见。")
    #             else:
    #                 # 若为正常内容，保存本次历史。
    #                 self.memory.save_context(
    #                     inputs,
    #                     {
    #                         "output": (
    #                             response
    #                             if isinstance(response, str)
    #                             else response["output"]
    #                         )
    #                     },  # 由于agent和chain的输出格式不同，所以，这里做了判断。agent输出为dict。chain直接输出str。因为outparse不同，一个是reactagent，一个stroutputparse
    #                 )
    #                 print(response)
    #         else:
    #             break

    def chat(self, input_str):
        '''根据用户问题，经过fullchaiin，返回一个答案，并保存memory'''
        input_dict = {"input": input_str}
        response = self.full_chain.invoke(input_dict)
        if response == False:
            self.memory.clear()
            return "再见，期待下次再见。"
        else:
            # 若为正常内容，保存本次历史。返回回答。
            # 由于agent和chain的输出格式不同，所以，这里做了判断。agent输出为dict。chain直接输出str。因为outparse不同，一个是reactagent，一个stroutputparse
            output = response if isinstance(response, str) else response["output"]
            self.memory.save_context(
                input_dict,
                {"output": output},
            )
            return output


chat = ChatBot(debug=True)
chat.full_chain.get_graph().print_ascii()
while True:
    input_str=input(":")
    if input_str=="q":
        break
    else:
        res=chat.chat(input_str)
        print(res)

