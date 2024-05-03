from communication import Communication
from asr import Asr
import json


class PCCommunication(Communication):
    def __init__(
        self,
    ) -> None:
        super().__init__()
        self.asr = Asr()
        # 初始化控制信号格式
        self.ctrl_sign_template = {"text": "", "end_chat": False, "action_ctrl": ""}

    def send_ctrl_sign(self, text, end_chat=False, action=""):
        # 发送控制型号
        self.ctrl_sign_template["text"] = text
        self.ctrl_sign_template["end_chat"] = end_chat
        self.ctrl_sign_template["action_ctrl"] = action
        self.send_dict(json.dumps(self.ctrl_sign_template))

    def recv_audio_to_text(self):
        # 接受audio，直接转换为text返回。
        audio = self._recv_bytes()
        # print(audio)
        print("收到音频")
        print("进入ASR")
        text = self.asr.audio_to_text(audio)
        return text
