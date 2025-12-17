#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
TCP服务器模块

本模块实现了一个基于PyQt5 QThread的多客户端TCP服务器。
用于向远程客户端提供功率计数据访问和控制接口。

主要功能:
    - 多客户端并发连接支持
    - 基于换行符的消息分帧
    - 自定义请求处理回调
    - 优雅的服务器关闭机制

类:
    TCPServer: TCP服务器线程类
    
使用示例:
    >>> def handle_request(data):
    ...     return '{"result": "ok"}'
    >>> server = TCPServer(port=1234, func=handle_request)
    >>> server.ready_signal.connect(on_ready)
    >>> server.start()
"""

import sys
import socket
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QLineEdit, QTextEdit
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import threading
from queue import Queue
import json


class TCPServer(QThread):
    """
    TCP服务器线程类
    
    基于PyQt5 QThread实现的多客户端TCP服务器，每个客户端连接
    创建独立线程处理，支持并发请求。
    
    信号:
        cmd_send_signal: 命令发送信号
        ready_signal: 服务器就绪信号，参数为(是否成功, 信息描述)
        
    属性:
        host: 服务器绑定的IP地址
        port: 服务器监听端口
        func: 请求处理回调函数，接收请求数据返回响应数据
        client_sockets: 已连接的客户端socket列表
    """
    
    # Qt信号定义
    cmd_send_signal = pyqtSignal([str, str])    # 命令发送信号
    ready_signal = pyqtSignal([bool, str])       # 服务器就绪信号

    def __init__(self, addr:str=None, port=8888, func=lambda x: print(x)):
        """
        初始化TCP服务器
        
        Args:
            addr: 服务器绑定地址，默认为本机IP
            port: 监听端口，默认8888
            func: 请求处理回调函数，接收请求字符串，返回响应字符串
        """
        super(TCPServer, self).__init__()
        self.host = addr if addr else socket.gethostbyname(socket.gethostname())
        self.port = int(port)
        self.func = func
        self.recQueues = {}
        
        # 服务器运行状态标志
        self._is_running = True
        self.server_socket = None
        self.client_threads = {}   # 客户端线程字典 {addr: thread}
        self.client_sockets = []   # 客户端socket列表

    def handle_client_connection(self, client_socket, addr):
        """处理客户端连接"""
        try:
            buffer = b""
            while self._is_running:
                try:
                    client_socket.settimeout(1)  # 设置超时以便定期检查关闭标志
                    data = client_socket.recv(1024)
                    if not data:  # 连接关闭
                        break
                    
                    # print(f"接收到来自{addr}的数据: {data.decode('utf-8')}")
                    buffer += data
                    
                    if b'\n' in buffer:
                        messages = buffer.split(b'\n')
                        for message in messages[:-1]:
                            a = self.func(message.decode('utf-8'))
                            self.send(client_socket, a)  
                        buffer = messages[-1]
                        
                except socket.timeout:
                    continue  # 超时后继续循环以检查关闭标志
                except Exception as e:
                    print(f"{addr}:客户端连接异常: {e}")
                    break
                    
            # 处理剩余未处理的消息
            if buffer:
                self.server_handler(client_socket, buffer)
                
        finally:
            print(f"关闭来自{addr}的连接")
            self.cleanup_client(client_socket, addr)

    def server_handler(self, client_socket, buffer):
        """处理客户端数据"""
        try:
            data = buffer.decode('utf-8')
            if data:
                a = self.func(data)
                self.send(client_socket, a)
        except Exception as e:
            print(f"处理客户端数据时出错: {e}")

    def cleanup_client(self, client_socket, addr):
        """清理客户端资源"""
        try:
            if client_socket in self.client_sockets:
                self.client_sockets.remove(client_socket)
            if addr in self.client_threads:
                del self.client_threads[addr]
            client_socket.shutdown(socket.SHUT_RDWR)
            client_socket.close()
        except Exception as e:
            print(f"清理客户端{addr}资源时出错: {e}")

    def run(self):
        """
        启动TCP服务器主循环
        
        创建服务器socket，监听指定端口，接受客户端连接。
        每个客户端连接创建独立的处理线程。
        """
        print("启动TCP服务器")
        print(f"本机IP地址: {self.host}")
        print(f"端口号: {self.port}")

        # 检查端口是否被占用
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex((self.host, self.port))
            if result == 0:
                print(f"端口{self.port}已被占用，请更换端口")
                self.ready_signal.emit(False, "端口已被占用，请更换端口")
                return

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('', self.port))
        self.server_socket.settimeout(1)  # 设置超时以便定期检查关闭标志
        self.server_socket.listen(5)
        print(f"服务器正在{self.host}:{self.port}上监听...")
        self.ready_signal.emit(True, f"服务器正在{self.host}:{self.port}上监听...")

        self._is_running = True
        
        try:
            while self._is_running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    print(f"接受到来自{addr}的连接")
                    
                    # 存储客户端socket
                    self.client_sockets.append(client_socket)
                    
                    # 为每个客户端连接创建一个单独的线程来处理
                    client_thread = threading.Thread(
                        target=self.handle_client_connection, 
                        args=(client_socket, addr),
                        daemon=True
                    )
                    self.client_threads[addr] = client_thread
                    client_thread.start()
                    
                except socket.timeout:
                    continue  # 超时后继续循环以检查关闭标志
                except Exception as e:
                    print(f"连接异常: {e}")
        finally:
            self.cleanup_server()

    def cleanup_server(self):
        """清理服务器资源"""
        print("正在关闭服务器...")
        
        # 关闭所有客户端连接
        for client_socket in self.client_sockets[:]:  # 使用副本遍历
            try:
                client_socket.shutdown(socket.SHUT_RDWR)
                client_socket.close()
            except Exception as e:
                print(f"关闭客户端socket时出错: {e}")
        
        # 清空客户端列表
        self.client_sockets.clear()
        self.client_threads.clear()
        
        # 关闭服务器socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception as e:
                print(f"关闭服务器socket时出错: {e}")
            finally:
                self.server_socket = None
        
        print("服务器已关闭")

    def close_tcp_server(self):
        """关闭TCP服务器"""
        print("正在请求关闭TCP服务器...")
        self._is_running = False
        
        # 如果服务器socket阻塞在accept()，需要先关闭它
        if self.server_socket:
            try:
                # 创建一个临时socket连接到服务器以解除accept()阻塞
                temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                temp_socket.connect((self.host, self.port))
                temp_socket.close()
            except Exception as e:
                print(f"创建临时连接时出错: {e}")

    def send(self, client_socket, data):
        """向客户端发送数据"""
        try:
            data = data + "\n"
            # print(f"向{client_socket.getpeername()}发送数据: {data}")
            client_socket.sendall(data.encode('utf-8'))
        except Exception as e:
            print(f"向{client_socket.getpeername()}发送数据异常: {e}")

# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     server = TCPServer()
#     server.start()
#     re = server.check_login_log(datetime.datetime(2025, 1, 14, 9, 30, 14), datetime.datetime(2025, 1, 14, 9, 30, 18), 4)
#     print(re)
#     sys.exit(app.exec_())