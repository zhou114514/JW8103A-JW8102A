#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
嘉慧功率计控制程序 - 主控制界面模块

本模块实现了功率计的主控制界面，包含以下核心功能：
    - 串口连接与管理：自动检测可用端口，连接FTDI设备
    - 功率数据采集：实时读取4通道光功率数据（约100Hz采样率）
    - 数据显示：LCD显示当前值、最大值、最小值，以及实时曲线图
    - 数据记录：将功率数据保存为CSV文件
    - TCP服务器/客户端：支持远程控制和数据共享
    - 局域网发现：自动发现局域网内的其他功率计控制软件
    - 自动化接口：提供自动化测试系统的控制接口

类:
    JW8103A_Control: 主窗口控制类，继承自QMainWindow

依赖:
    - PyQt5: GUI框架
    - pyserial: 串口通信
    - pandas: 数据处理和CSV导出
    - pyqtgraph: 实时曲线绘图
"""

from Ui_JW8103A_Control import Ui_MainWindow
import serial
import serial.tools.list_ports
import time
import datetime
import os
import threading
import json
import socket
import pandas as pd
from queue import Queue
from JW8103A import JW8103A
from tool import *
from TCPClient import TCPClient
from TCPServer import TCPServer
from MyPlot import MyPlot
from LatencyTimerSet import *
from LAN_Search import *

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, Qt

VERSION = "Unknown" if not os.path.exists("更新内容.csv") or \
                       pd.read_csv("更新内容.csv", header=None, index_col=None).iloc[-1, 0] is None \
    else pd.read_csv("更新内容.csv", header=None, index_col=None).iloc[-1, 0]


def showAbout(self):
    # 读取 CSV 文件
    df = pd.read_csv("更新内容.csv", header=None, names=["版本号", "更新内容"])
    # 将 DataFrame 转换为 HTML 表格字符串
    html_table = df.to_html(index=False, border=1)
    # 创建关于窗口
    aboutWin = QtWidgets.QDialog(self)
    aboutWin.setWindowTitle("关于")
    aboutWin.resize(400, 300)
    aboutWin.setStyleSheet("background-color: #FFFFFF;color: #000000;font: 12pt \"微软雅黑\";")
    # 创建 QTextEdit 控件
    aboutText = QtWidgets.QTextEdit(aboutWin)
    aboutText.setReadOnly(True)
    aboutText.setHtml(html_table)  # 设置 HTML 内容
    # 使用布局管理器
    layout = QtWidgets.QVBoxLayout(aboutWin)
    layout.addWidget(aboutText)  # 将 QTextEdit 添加到布局中
    # 设置布局的边距（可选）
    layout.setContentsMargins(10, 10, 10, 10)
    # 显示窗口
    aboutWin.show()


class JW8103A_Control(QtWidgets.QMainWindow, Ui_MainWindow):
    """
    嘉慧功率计主控制窗口类
    
    该类实现了功率计控制软件的主要功能，包括：
    - 设备连接管理（串口/TCP）
    - 实时功率数据采集与显示
    - 数据记录与导出
    - TCP服务器（供远程客户端连接）
    - 自动化控制接口
    
    信号:
        value_update (list): 用于更新UI显示的功率值信号
        value_save (list): 用于保存功率数据的信号
        
    属性:
        ser: 串口对象
        JW: JW8103A设备实例
        TCPServer: TCP服务器实例（供其他客户端连接）
        TCPClient: TCP客户端实例（连接其他服务器）
        AutoServer: 自动化控制服务器（端口1235）
    """
    
    # Qt信号定义
    value_update = pyqtSignal(list)  # 功率值更新信号，传递4通道功率列表
    value_save = pyqtSignal(list)    # 功率值保存信号

    def __init__(self, parent=None):
        super(JW8103A_Control, self).__init__(parent)
        self.setupUi(self)
        self.setWindowTitle(f"嘉慧功率计控制程序 {VERSION}")
        self.version.setText(f"版本：{VERSION}")
        self.init_config()
        self.conifg = read_config()

        self.ser = serial.Serial()
        self.JW = None
        self.Com_Dict = {}
        self.Record_Thread = None
        self.start_record = False
        self.startTime = None
        self.stopped = True
        self.stopRecord = False

        self.data_source = "Port"

        self.TCPServer = None
        self.TCPClient = None

        self.hostip = socket.gethostbyname(socket.gethostname())
        self.host_ip.setText(self.hostip)
        self.hostport = 1234

        self.autoip = self.conifg["Auto"]["address"] if self.conifg["Auto"]["address"] else socket.gethostbyname(socket.gethostname())
        self.autoport = self.conifg["Auto"]["port"] if self.conifg["Auto"]["port"] else 10005
        self.address = "127.0.0.1"
        self.port = 1234
        self.AutoServer = TCPServer(addr=self.autoip, port=self.autoport, func=self.Auto_server_rec)
        self.AutoServer.start()

        self.ClientQ = Queue()
        self.CH_Value_dict = {0: self.CH1_Value, 1: self.CH2_Value, 2: self.CH3_Value, 3: self.CH4_Value}
        self.CH_max_dict = {0: self.CH1_max, 1: self.CH2_max, 2: self.CH3_max, 3: self.CH4_max}
        self.CH_min_dict = {0: self.CH1_min, 1: self.CH2_min, 2: self.CH3_min, 3: self.CH4_min}
        self.Value_record = {0: {"max": -60, "min": None, "value": 0}, 1: {"max": -60, "min": None, "value": 0},
                             2: {"max": -60, "min": None, "value": 0}, 3: {"max": -60, "min": None, "value": 0}}
        self.CH_Wave_dict = {0: self.CH1_wave, 1: self.CH2_wave, 2: self.CH3_wave, 3: self.CH4_wave}
        self.CH_Twave_dict = {0: self.CH1Twave, 1: self.CH2Twave, 2: self.CH3Twave, 3: self.CH4Twave}
        self.CH_PlotLayout_dict = {0: self.CH1_Plot_layout, 1: self.CH2_Plot_layout, 2: self.CH3_Plot_layout,
                                   3: self.CH4_Plot_layout}
        self.CH_name_dict = {0: self.CH1_name, 1: self.CH2_name, 2: self.CH3_name, 3: self.CH4_name}
        self.CH_Plot_dict = {0: None, 1: None, 2: None, 3: None}

        for i in range(4):
            self.CH_Plot_dict[i] = MyPlot({"功率": [0]})
            self.CH_PlotLayout_dict[i].addWidget(self.CH_Plot_dict[i])

        self.startIndex = 0  # 开始记录的数据下标
        self.setCHwave_dict = {0: self.setCH1wave, 1: self.setCH2wave, 2: self.setCH3wave, 3: self.setCH4wave}
        self.portInfo.setReadOnly(True)
        self.value_update.connect(self.update_value)
        self.value_save.connect(self.save_value)
        self.Power_Buffer = []
        self.CheckPort_callback()

        self.init_btn()

    def init_config(self):
        """初始化配置"""
        if not os.path.exists("config.ini"):
            with open("config.ini", "w") as f:
                f.write("[Port]\nname = COM1\n")
                f.write("[TCP]\naddress = 127.0.0.1\nport = 1234\n")
                f.write("[Auto]\naddress = 127.0.0.1\nport = 10005\n")
            

    def init_btn(self):
        """初始化界面按钮的信号与槽连接"""
        self.version.clicked.connect(lambda: showAbout(self))

        self.openPort.clicked.connect(lambda : self.PortOpen_callback(True))
        self.closePort.clicked.connect(self.PortClose_callback)
        self.ComCheck.clicked.connect(self.CheckPort_callback)

        self.scanServer.clicked.connect(self.ScanServer_callback)
        self.serverList.activated.connect(self.ServerSelect_callback)
        self.TCPconnect.clicked.connect(self.TCPConnect_callback)
        self.TCPdisconnect.clicked.connect(self.TCPDisconnect_callback)

        self.Com.currentTextChanged.connect(self.CurrentPort_callback)

        self.Connect.clicked.connect(self.Connect_JW)
        self.Disconnect.clicked.connect(lambda: self.Disconnect_JW(True))
        self.Clean.clicked.connect(self.Clean_callback)
        self.startRecordBtn.clicked.connect(self.start_record_callback)
        self.stopRecordBtn.clicked.connect(self.stop_record_callback)
        self.startRecordBtn.setEnabled(False)
        self.stopRecordBtn.setEnabled(False)
        self.RestartHost.clicked.connect(self.RestartHost_callback)
        self.RestartHost.setEnabled(False)

        for i in range(4):
            self.setCHwave_dict[i].clicked.connect(lambda state, CH=i + 1: self.Set_Wavelength(CH))

        if self.conifg:
            if "Port" in self.conifg:
                self.Com.setCurrentText(self.conifg["Port"]["name"])
            if "TCP" in self.conifg:
                self.IPaddress.setText(self.conifg["TCP"]["address"])
                self.IPport.setText(self.conifg["TCP"]["port"])

        self.btn_group_enable(False)

    def btn_group_enable(self, enable: bool):
        """启用或禁用设备操作按钮组
        
        Args:
            enable: True启用按钮组，False禁用按钮组
        """
        self.Connect.setEnabled(enable)
        self.Disconnect.setEnabled(enable)
        self.Clean.setEnabled(enable)
        self.setCH1wave.setEnabled(enable)
        self.setCH2wave.setEnabled(enable)
        self.setCH3wave.setEnabled(enable)
        self.setCH4wave.setEnabled(enable)

    def PortOpen_callback(self, alert=True):
        """打开串口回调函数
        
        打开选中的串口，并启动TCP服务器和局域网发现服务。
        会自动设置FTDI芯片的LatencyTimer为1ms以提高通信速率。
        
        Args:
            alert: 是否显示警告对话框
            
        Returns:
            bool: 打开成功返回True，失败返回False
        """
        if not check_is_FTDI_port(self.Com.currentText()):
            if alert:
                QMessageBox.warning(self, "警告", "请选择正确的端口！", QMessageBox.Yes)
            return False
        else:
            SetLatencyTimer(self.Com.currentText(), 1)
        self.ser.port = self.Com.currentText()
        self.ser.baudrate = 115200
        try:
            self.data_source = "Port"
            self.ser.open()
            self.updateInfo("端口打开成功！")
            edit_config("Port", "name", self.ser.port)
            self.hostport = int(self.host_port.text()) if self.host_port.text().isdigit() and int(
                self.host_port.text()) > 0 and int(self.host_port.text()) < 65536 else 1234
            self.TCPServer = TCPServer(addr=self.hostip, port=self.hostport, func=self.Server_update_device_rec)
            self.TCPServer.ready_signal.connect(self.Server_ready_callback)
            self.TCPServer.start()
            discovery_thread = threading.Thread(target=LAN_Search.start_discovery_server, args=(self.hostport, "JW8103A_Control", ))
            discovery_thread.daemon = True
            discovery_thread.start()
            self.btn_group_enable(True)
            return True
        except Exception as e:
            self.updateInfo(f"端口打开失败！{e}")
            return False

    def Server_ready_callback(self, isReady, info):
        if isReady:
            self.updateInfo(f"TCP服务器启动成功！{info}")
            self.RestartHost.setEnabled(False)
        else:
            self.updateInfo(f"TCP服务器启动失败！{info}")
            self.RestartHost.setEnabled(True)

    def RestartHost_callback(self):
        self.hostport = int(self.host_port.text()) if self.host_port.text().isdigit() and int(
            self.host_port.text()) > 0 and int(self.host_port.text()) < 65536 else 1234
        self.TCPServer = TCPServer(port=self.hostport, func=self.Server_update_device_rec)
        self.TCPServer.ready_signal.connect(self.Server_ready_callback)
        self.TCPServer.start()

    def PortClose_callback(self):
        self.Disconnect_JW(False)
        self.ser.close()
        if self.TCPServer is not None:
            self.TCPServer.close_tcp_server()
        self.btn_group_enable(False)
        self.updateInfo("端口关闭成功！")

    def ScanServer_callback(self):
        threading.Thread(target=self.scanT).start()

    def scanT(self):
        servers = LAN_Search.discover_services(timeout=5)
        for serverName, serverAddress, serverPort in servers:
            if serverName == "JW8103A_Control":
                self.updateInfo(f"发现服务器：{serverName}，地址：{serverAddress}，端口：{serverPort}")
                self.serverList.addItem(f"{serverName},{serverAddress},{serverPort}")

    def ServerSelect_callback(self):
        if self.serverList.currentIndex() == -1:
            return
        server = self.serverList.currentText().split(",")
        self.address = server[1]
        self.port = int(server[2])
        self.IPaddress.setText(self.address)
        self.IPport.setText(str(self.port))

    def TCPConnect_callback(self):
        if self.IPaddress.text() == "":
            self.updateInfo("请输入IP地址！")
            return
        if self.IPport.text() == "":
            self.updateInfo("请输入端口号！")
            return
        self.address = self.IPaddress.text()
        self.port = int(self.IPport.text())
        try:
            self.data_source = "TCP"
            self.TCPClient = TCPClient(self.address, self.port, func=lambda x: self.ClientQ.put(json.loads(x)))
            self.TCPClient.start()
            self.TCPClient.connectedSignal.connect(self.connect_sig)
            self.updateInfo("TCP连接成功！")
            edit_config("TCP", "address", self.address)
            edit_config("TCP", "port", str(self.port))
            self.btn_group_enable(True)
        except:
            self.updateInfo("TCP连接失败！")

    def connect_sig(self, sig, info):
        if sig == "NO":
            self.TCPDisconnect_callback()
            self.updateInfo(f"TCP连接断开！{info}")

    def TCPDisconnect_callback(self):
        self.Disconnect_JW(False)
        self.TCPClient.connectedSignal.disconnect()
        self.TCPClient.stop()
        self.updateInfo("TCP断开连接成功！")
        self.btn_group_enable(False)

    def CheckPort_callback(self):
        self.Com.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.Com_Dict["%s" % port[0]] = "%s" % port[1]
            self.Com.addItem(port[0])

    def CurrentPort_callback(self):
        port = self.Com.currentText()
        if port in self.Com_Dict:
            self.ComName.setText(self.Com_Dict[port])
        else:
            self.ComName.setText("")

    def Base_value(self):
        Wavelist = self.JW.Read_User_Wavelength()
        for i in range(len(Wavelist)):
            Wavelist[i] = str(Wavelist[i]) + "nm"
        for i in range(4):
            self.CH_Twave_dict[i].clear()
            self.CH_Twave_dict[i].addItems(Wavelist)
        result = self.JW.Read_Screen_Data()
        if result not in [[], None]:
            for i in range(4):
                self.CH_Wave_dict[i].setText("波长" + result[f"CH{i + 1}"]["Wavelength"] + "nm")

    def Connect_JW(self, alert=True):
        if self.data_source == "Port":
            if self.JW is not None:
                self.updateInfo("已连接！")
                return True
            self.JW = JW8103A(self.ser)
            a = self.JW.Connect()
            if a:
                try:
                    # self.Base_value()
                    self.Record_Thread = threading.Thread(target=self.PowerRecord)
                    self.Record_Thread.start()
                except Exception as e:
                    if alert:
                        self.updateInfo(f"连接失败！{e}")
                    QMessageBox.warning(self, "警告", f"连接失败！{e}", QMessageBox.Yes)
                    return False
                self.Connect.setEnabled(False)
                self.Disconnect.setEnabled(True)
                self.startRecordBtn.setEnabled(True)
                self.updateInfo("连接成功！")
                if alert:
                    QMessageBox.information(self, "提示", "连接成功！", QMessageBox.Yes)
                return True
            else:

                self.updateInfo("连接失败！")
                if alert:
                    QMessageBox.warning(self, "警告", "连接失败！", QMessageBox.Yes)
                return False
        elif self.data_source == "TCP":
            self.TCPClient.send(json.dumps({"cmd": "Connect"}))
            result = self.ClientQ.get(block=True, timeout=1)
            if result["isSuccess"]:
                self.updateInfo("连接成功！")
                self.Record_Thread = threading.Thread(target=self.PowerRecord)
                self.Record_Thread.start()
                if alert:
                    QMessageBox.information(self, "提示", "连接成功！", QMessageBox.Yes)
                self.Connect.setEnabled(False)
                self.Disconnect.setEnabled(True)
                return True
            else:
                self.updateInfo("连接失败！")
                if alert:
                    QMessageBox.warning(self, "警告", "连接失败！", QMessageBox.Yes)
                return False

    def Server_update_device_rec(self, data):
        """TCP服务器数据接收处理函数
        
        处理来自TCP客户端的控制命令，支持的命令包括：
        - Connect/ConnectDevice: 连接功率计设备
        - Disconnect: 断开设备连接
        - Set_Wavelength: 设置通道波长
        - Read_User_Power/GetPower: 读取功率值
        
        Args:
            data: JSON格式的命令字符串
            
        Returns:
            str: JSON格式的响应数据
        """
        data = json.loads(data)
        if data["cmd"] == "Connect":
            a = self.Connect_JW()
            return self.make_pack(a, "", "")
        elif data["cmd"] == "Disconnect":
            self.Disconnect_JW(False)
            return self.make_pack(True, "", "")
        elif data["cmd"] == "Set_Wavelength":
            CH = int(data["params"]["CH"])
            Wavelength = int(data["params"]["Wavelength"])
            a = self.JW.User_Wavelength(CH, Wavelength)
            return self.make_pack(a, "", "")
        elif data["cmd"] == "Read_User_Power":
            return self.make_pack(True, self.Power_Buffer, "")
        elif data["cmd"] == "ConnectDevice":
            a = self.Connect_JW()
            return self.make_pack(a, "", "")
        elif data["cmd"] == "GetPower":
            value = self.Power_Buffer
            return self.make_pack(True, value, "")
        else:
            return self.make_pack(False, "", "Unknown command!")

    def Auto_server_rec(self, data):
        """自动化控制服务器数据接收处理函数
        
        处理来自自动化测试系统的控制命令（端口1235），支持的命令包括：
        - GetPower: 获取4通道功率值（包含当前值、最大值、最小值）
        - RecordCon: 控制数据记录的开始/停止
        - ConnectDevice: 打开串口并连接设备
        - check: 获取软件版本号
        
        Args:
            data: JSON格式的命令字符串，格式为 {"opcode": "命令", "parameter": {...}}
            
        Returns:
            str: JSON格式的响应数据
        """
        data = json.loads(data)
        if data['opcode'] == "GetPower":
            res_dict = {"CH1": {
                            "Power": self.Value_record[0]["value"],
                            "Max": self.Value_record[0]["max"],
                            "Min": self.Value_record[0]["min"]
                        }, 
                        "CH2": {
                            "Power": self.Value_record[1]["value"],
                            "Max": self.Value_record[1]["max"],
                            "Min": self.Value_record[1]["min"]
                        },
                        "CH3": {
                            "Power": self.Value_record[2]["value"],
                            "Max": self.Value_record[2]["max"],
                            "Min": self.Value_record[2]["min"]
                        },
                        "CH4": {
                            "Power": self.Value_record[3]["value"],
                            "Max": self.Value_record[3]["max"],
                            "Min": self.Value_record[3]["min"]
                        }
                    }
            return self.make_pack(True, res_dict, "Null")
        elif data['opcode'] == 'RecordCon':
            if data['parameter']['Con'] == 'Start':
                success = self.start_record_callback()
                error_msg = ""
                if not success:
                    error_msg = "开启记录错误!"
                return self.make_pack(success, '', error_msg)
            elif data['parameter']['Con'] == 'Stop':
                success = self.stop_record_callback()
                error_msg = ""
                if not success:
                    error_msg = "关闭记录错误!"
                return self.make_pack(success, '', error_msg)
            else:
                return self.make_pack(False, '', f'command not supported:{data}')
        elif data['opcode'] == 'ConnectDevice':
            # 自动化连接的时候串口还没有打开，所以还要先打开串口
            a = self.PortOpen_callback(alert=False)
            b = False
            time.sleep(0.01)
            if a:
                b = self.Connect_JW(alert=False)
            error_msg = ""
            if not a or not b:
                error_msg = "连接设备错误!"
            return self.make_pack(a & b, "", error_msg)
        elif data['opcode'] == 'check':
            return self.make_pack(True, VERSION, 'Null')
        else:
            return self.make_pack(False, "", "Unknown command!")

    def make_pack(self, isSuccess, Value, ErrorMessage):
        data = {"isSuccess": isSuccess, "Value": Value, "ErrorMessage": ErrorMessage}
        return json.dumps(data)

    def Disconnect_JW(self, need_Box=True):
        self.JW = None
        self.stopRecord = True
        if self.Record_Thread is not None:
            self.Record_Thread.join()
        self.Connect.setEnabled(True)
        self.Disconnect.setEnabled(False)
        self.startRecordBtn.setEnabled(False)
        self.stopRecordBtn.setEnabled(False)
        self.stopRecord = False
        if need_Box:
            QMessageBox.information(self, "提示", "断开连接成功！", QMessageBox.Yes)

    def PowerRecord(self):
        """功率数据采集线程函数
        
        持续从设备读取功率数据，约100Hz采样率（9ms间隔）。
        每10次采样更新一次UI显示（约10Hz刷新率）。
        如果正在记录，会同时发送数据保存信号。
        
        注意:
            此函数运行在独立线程中，通过Qt信号与主线程通信。
        """
        if not os.path.exists("./Record"):
            os.mkdir("./Record")
        counter = 0
        self.last_time = 0
        while True:
            try:
                now = int(round(time.time() * 1000))
                # if (now - aa) >= 1000:
                #     aa = now
                #     print(f"PowerRecord: {a}次/秒")
                #     a = 0
                if (now - self.last_time) >= 9:  # 9ms更新一次，100Hz
                    counter += 1
                    # a = a + 1
                    if self.stopRecord:
                        break
                    result = []
                    if self.data_source == "Port":  # 串口链接功率计的状态
                        result = self.JW.Read_User_Power()
                    elif self.data_source == "TCP":  # 使用TCP链接连接了功率计的主机的状态
                        self.TCPClient.send(json.dumps({"cmd": "Read_User_Power"}))
                        result = self.ClientQ.get(block=True, timeout=1)
                        result = result["Value"]
                    if result not in [[], None]:
                        self.Power_Buffer = result
                        if counter % 10 == 0:
                            counter = 0
                            self.value_update.emit(result)
                    if self.start_record:
                        self.value_save.emit(result)  # 更改为在按下停止记录后才开始保存
                    self.last_time = now
            except Exception as e:
                print(f"PowerRecord Error: {e}")

    def update_value(self, value: list):
        for i in range(4):
            self.CH_Value_dict[i].display(str(value[i]))
            self.Value_record[i]["value"] = value[i]
            if value[i] > self.Value_record[i]["max"]:
                self.Value_record[i]["max"] = value[i]
            if self.Value_record[i]["min"] is None:
                self.Value_record[i]["min"] = value[i]
            elif self.Value_record[i]["min"] is not None and value[i] < self.Value_record[i]["min"]:
                self.Value_record[i]["min"] = value[i]

            self.CH_max_dict[i].display(str(self.Value_record[i]["max"]))
            self.CH_min_dict[i].display(str(self.Value_record[i]["min"]))
            if not self.stopped:
                self.CH_Plot_dict[i].update_signal.emit({'功率': self.CH_Value_dict[i].value()})

    def start_record_callback(self):
        if self.start_record:
            print("已经开始记录，请勿重复开始！")
            return False
        self.start_record = True
        self.stopped = False
        self.startTime = time.strftime('%Y-%m-%d %H-%M-%S')
        self.startRecordBtn.setEnabled(False)
        self.stopRecordBtn.setEnabled(True)
        self.updateInfo("开始记录！")
        self.Clean_callback()
        return True

    def stop_record_callback(self):
        if not self.start_record:
            print("还未开始记录！")
            return False
        self.start_record = False
        self.stopped = True
        self.startRecordBtn.setEnabled(True)
        self.stopRecordBtn.setEnabled(False)
        self.updateInfo("停止记录！")
        # 停止图像更新

        # 更改文件名
        try:
            os.rename(f"./Record/PowerRecord_{self.startTime}.csv",
                      f"./Record/PowerRecord_{self.startTime}_{time.strftime('%Y-%m-%d %H-%M-%S')}.csv")
        except FileNotFoundError:
            print(f"错误：找不到文件 ./Record/PowerRecord_{self.startTime}.csv")
            return False
        except PermissionError:
            print("错误：没有权限更改文件名")
            return False
        except OSError as e:
            print(f"错误：无法重命名文件 - {e}")
            return False
        return True

    def save_value(self, value: list):
        if not os.path.exists(f"./Record/PowerRecord_{self.startTime}.csv"):
            with open(f"./Record/PowerRecord_{self.startTime}.csv", "w", encoding="gbk") as f:
                f.write(f"时间,{self.CH1_name.text()},{self.CH2_name.text()},{self.CH3_name.text()},{self.CH4_name.text()}\n")
        with open(f"./Record/PowerRecord_{self.startTime}.csv", "a") as f:
            f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + "," + str(value[0]) + "," + str(value[1]) + "," + str(value[2]) + "," + str(value[3]) + "\n")

    def Set_Wavelength(self, CH: int):
        a = self.JW.User_Wavelength(CH, self.CH_Twave_dict[CH - 1].currentIndex() + 1)
        if a:
            self.CH_Wave_dict[CH - 1].setText("波长" + self.CH_Twave_dict[CH - 1].currentText())
            self.updateInfo(f"CH{CH}波长设置成功！")
            print(f"CH{CH}波长设置成功！")
        else:
            self.updateInfo(f"CH{CH}波长设置失败！")
            print(f"CH{CH}波长设置失败！")

    def Clean_callback(self):
        for i in range(4):
            self.CH_Value_dict[i].display("0")
            self.CH_max_dict[i].display("0")
            self.CH_min_dict[i].display("0")
            self.Value_record[i]["value"] = 0
            self.Value_record[i]["max"] = -60
            self.Value_record[i]["min"] = 0
            self.CH_Plot_dict[i].clearData()

    def updateInfo(self, info):
        if self.data_source == "Port":
            self.portInfo.append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " " + info)
            self.portInfo.append("\n")
            self.portInfo.moveCursor(QtGui.QTextCursor.End)
        elif self.data_source == "TCP":
            self.TCPInfo.append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " " + info)
            self.TCPInfo.append("\n")
            self.TCPInfo.moveCursor(QtGui.QTextCursor.End)

    def closeEvent(self, event):
        reply = QtWidgets.QMessageBox.question(self,
                                               '嘉慧功率计',
                                               "是否要退出程序？",
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            event.accept()
            if self.data_source == "Port":
                self.PortClose_callback()
            elif self.data_source == "TCP":
                self.TCPDisconnect_callback()
            os._exit(0)

        else:
            event.ignore()
