from elasticsearch import Elasticsearch

from langchain.tools import tool


class Elastic:
    def __init__(self, url, api_key) -> None:
        self.es_conn = Elasticsearch(
            [url],
            verify_certs=False,
            api_key=api_key,
        )

    def base_search(self, search_field: str, key_word: str, size: int = 10):
        query = {
            "size": size,
            "query": {
                "query_string": {
                    "query": search_field + ":" + key_word.replace('"\n', "")
                }
            },
            #    "explain": True
        }
        print(query)
        result = self.es_conn.search(index="pharm_iksmart", body=query)
        return result
