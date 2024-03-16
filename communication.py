# -*- coding: utf-8 -*-


import socket
import json


class Communication:
    """communcation类，完成socket链接建立，收发，等通信功能，收发bytes，string，dict数据"""

    def __init__(self):
        """初始化socket"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self, address, port):
        """链接函数"""
        self.sock.connect(address, port)

    def start_listening(self, ip, port):
        """开始在指定的IP和端口上监听，并在建立链接后持续维护链接对象。"""
        self.sock.bind((ip, port))
        self.sock.listen(1)
        print("Server listening on port", port)
        # 这里链接返回client_socket，之后，向client发送数据，只要用client_socket即可。
        # 而原本的self.sock可用于继续等待新的链接。
        self.client_socket, self.client_address = self.sock.accept()
        self.sock = self.client_socket
        print("Connected to:", self.client_address)

    def connect_to_server(self, address, port):
        """向指定的IP和端口发起链接"""
        self.sock.connect((address, port))
        print("Connected to server:", address)

    def _send_bytes(self, data):
        """发送raw data函数"""
        # 配置包的头尾，封装数据的长度，接受时，循环接受，直到接受的长度=封装数据的长度，然后返回。避免从buffer中多拿数据的问题（即tcp粘包问题，取当前数据的时候，取到了下一个包的数据
        header = "{:<10}".format(
            len(data)
        )  # 保证包头大小固定为10，方便接受，同时限制了data的长度不能超过10位10进制数的字节两
        header = header.encode("utf-8")
        self.sock.sendall(header)
        self.sock.sendall(data)

    def _recv_bytes(self):
        """接受raw data 函数，一次接受1024直到接受完成"""
        # 接收头部信息，取得数据大小。然后接受数据大小的数据
        header = self.sock.recv(10)
        data_size = int(header.strip())
        print(data_size)
        # 接收数据
        recived_data = b""
        while len(recived_data) < data_size:
            remaining_lenght = data_size - len(recived_data)
            #  # 循环接受数据包，直到数据长度和包头内的一致。最大读1024个byte避免出现性能问题。
            recived_data += self.sock.recv(min(remaining_lenght, 1024))
        return recived_data

    def _send_string(self, message):
        """发送string对象。需要先编码为byte对象"""
        self._send_bytes(message.encode("utf-8"))

    def _recv_string(self):
        """接受string对象，同理也需要解码"""
        data = self._recv_bytes()
        return data.decode("utf-8")

    def send_dict(self, data):
        """发送格式化数据，这里dump出的就是str类型的json数据"""
        json_data = json.dumps(data)
        self._send_string(json_data)

    def recv_dict(self):
        """接受格式化数据，并用json loads，从string load 为 dict"""
        json_data = self._recv_string()
        return json.loads(json_data)

    def send_audio(self, audio):
        """发audio"""
        self._send_bytes(audio)

    def recv_audio(self):
        """收audio"""
        data = self._recv_bytes()
        return data