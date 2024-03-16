# -*- coding: utf-8 -*-
from communication import Communication
class NaoCommunication(Communication, object):
    def __init__(self):
        super(NaoCommunication,self).__init__()
    def connect_to_server(self, address,port):
        """向指定的IP和端口发起链接"""
        self.sock.connect((address,port))
        print("Connected to server:", address)


    def send_to_pc(self, audio):
        # 发送给PC
        self.send_bytes(audio)
        
    def recv_from_pc(self):
        # 等待pc返回值
        response = self.recv_string()
        return response
    
