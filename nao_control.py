
# -*- coding: utf-8 -*-
import functools
import json
import time
from naoqi import qi

from communication import Communication

PC_IP="192.168.43.60"
PC_PORT=5555
class NaoControl():
    def __init__(self):
        # 初始化通信模块
        self.comm=Communication()
        self.comm.connect_to_server(PC_IP,PC_PORT)

        self.ses=qi.Session()
        self.ses.connect("tcp://localhost:9559")
        #初始化模块
        self.mem=self.ses.service("ALMemory")
        # self.mot=self.ses.service("ALMotion")

        self.tts=self.ses.service("ALTextToSpeech")
        self.ani_tts=self.ses.service("ALAnimatedSpeech")
        # self.motion=Motion(self.mot)
        self.tts.setLanguage("Chinese")

        # 获取ALAudioDevice服务
        self.audio_service = self.ses.service("ALAudioDevice")
        self.audio_recorder= self.ses.service("ALAudioRecorder")
        #启动声音大小计算。
        self.audio_service.enableEnergyComputation()

        self.front=self.mem.subscriber("FrontTactilTouched")
        self.con_front=self.front.signal.connect(functools.partial(self.FrontTouched,"FrontTactilTouched"))

        # 设置listening的自主动作
        self.listen_move=self.ses.service("ALListeningMovement")
        self.listen_move.setEnabled(True)

        # 配置LED
        self.led =self.ses.service("ALLeds")


        #当前正在对话的标志位
        self.chating=False

    def speech(self, text):
        # 将输入的字符串，语音播报。
        # self.tts.say(text)
        self.ani_tts.say(text)
    def record(self):
        # 开始录音，直到一段时间内，声音低于阈值。
        # 设置音频参数
        sample_rate = 16000  # 采样率
        channels = [1, 0, 0, 0]  # 只使用左声道
        deinterleaved = True  # 是否交错存储

        def read_file(file):
            with open(file, "rb") as f:
                data=f.read()
            return data
        audio_file="/home/nao/medic_chatbot/record.wav"
        self.audio_recorder.stopMicrophonesRecording()
        self.audio_recorder.startMicrophonesRecording(audio_file,"wav",16000,(1,0,0,0))
        # 若声音持续小于2000超过1.5秒？就停止录音
        silence_time=0
        while True:
            if self.audio_service.getFrontMicEnergy() < 2000:
                silence_time += 1  # 增加静音时间，单位为秒
                if silence_time >= 3:  # 如果静音时间超过1.5秒，则停止录音
                    break
                # time.sleep(0.1)
                self.led.rotateEyes(0xFF,0.5,0.5)
            else:
                # 若期间有高于2000的，则从零继续开始计数。
                silence_time =0
        self.audio_recorder.stopMicrophonesRecording()
            

        # 读取录音文件的内容，返回字节对象值。
        data=read_file(audio_file)
        return data
    def FrontTouched(self,event,value):
        # 通过摸头的回调函数，开始对话
        print  event,value
        if value==1 and self.chating==False:    # 此时无人在对话
            self.chat()
    def thinking_led(self):
        # 所有等待时，都执行这个函数，直到收到返回值。
        pass
    def chat(self):
        while True:
            # 进入chat获取标值
            self.chating=True
            audio=self.record()
            # 发送音频，等待用户回答的str。
            self.comm.send_audio(audio)
            output = self.comm.recv_dict()
            print(output)
            # self.tts(output)
            output = json.loads(output)
            print(output[u'text'].encode('utf-8'))
            self.speech(output[u'text'].encode('utf-8'))
            print("说完了")
            if output['end_chat']:
                # 若结束当前对话，则结束当前对话循环，重新等待摸头。
                self.chating=False  # 退出chat释放标值
                break
    
    def daemon(self):
        while True:
            time.sleep(1)
