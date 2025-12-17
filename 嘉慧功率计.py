#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
嘉慧功率计控制程序 - 主入口模块

本程序用于控制嘉慧光电JW8103A/JW8102A系列光功率计。
提供串口通信、4通道功率实时显示、数据记录、TCP远程控制等功能。

使用方法:
    直接运行此文件启动应用程序:
    $ python 嘉慧功率计.py

依赖:
    - PyQt5: GUI框架
    - pyserial: 串口通信
    - pandas: 数据处理
    - pyqtgraph: 实时绘图

作者: 嘉慧光电
"""

from PyQt5 import QtWidgets, QtCore
import multiprocessing
import sys
from JW8103A_Control import JW8103A_Control


if __name__ == '__main__':
    # 在Windows平台上使用multiprocessing打包为exe时需要调用freeze_support
    multiprocessing.freeze_support()

    # 启用高DPI缩放，确保在高分辨率屏幕上界面正常显示
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)

    # 创建Qt应用程序实例
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建并显示主窗口
    mainWind = JW8103A_Control()
    mainWind.show()

    # 进入Qt事件循环
    sys.exit(app.exec_())
