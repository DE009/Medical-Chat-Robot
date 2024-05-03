import json

import nls


URL = "wss://nls-gateway-cn-shanghai.aliyuncs.com/ws/v1"
TOKEN = "a5aae5ddb27c476e9c2e91f484dffa35"  # 参考https://help.aliyun.com/document_detail/450255.html获取token
APPKEY = "wqgataB0hKgwl4V8"  # 获取Appkey请前往控制台：https://nls-portal.console.aliyun.com/applist


class Asr():
    def __init__(self) -> None:
        """初始化，构建链接对象"""
        self.sr = nls.NlsSpeechTranscriber(
            url=URL,
            token=TOKEN,
            appkey=APPKEY,
            # on_sentence_begin=self.teon_sentence_begin,
            on_sentence_end=self._on_sentence_end,
            on_start=self._on_start,
            # on_result_changed=self.test_on_result_chg,
            # on_completed=self._on_completed,
            on_error=self._on_error,
            # on_close=self.test_on_close,
            # callback_args=[self.__id],
        )
        self.result = ""

    def _on_start(self, message, *args):
        # 每次启动时，清空result，用于记录当前的识别结果。
        self.result = ""

    def _on_sentence_end(self, message, *args):
        # 每次识别完成一个句子，累加到当前结果
        mes = json.loads(message)
        self.result += mes["payload"]["result"]

    # def _on_completed(self, message, *args):
    #     # 识别完成，
    #     # print("on_completed:args=>{} message=>{}".format(args, message))
    #     return
    def _on_error(self, message, *args):
        print("on_error args=>{}".format(args))

    def audio_to_text(self, audio: bytes) -> str:
        """输入音频的二进制对象，返回结果"""
        self.sr.start(
            aformat="pcm",
            enable_intermediate_result=True,
            enable_punctuation_prediction=True,
            enable_inverse_text_normalization=True,
        )
        slices = zip(*(iter(audio),) * 640)
        for i in slices:
            self.sr.send_audio(bytes(i))
            # time.sleep
        self.sr.stop()
        return self.result
