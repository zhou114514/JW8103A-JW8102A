# 嘉慧功率计控制软件

[![License: MPL 2.0](https://img.shields.io/badge/License-MPL_2.0-brightgreen.svg)](https://opensource.org/licenses/MPL-2.0)

嘉慧光电 JW8103A/JW8102A 光功率计控制程序，基于 PyQt5 开发的桌面应用程序。

## 功能特性

### 核心功能
- **4通道功率测量**：同时读取并显示4个通道的光功率值
- **实时数据显示**：LCD数显当前值、最大值、最小值
- **实时曲线图**：动态显示功率变化趋势
- **波长设置**：支持设置测量波长（850nm - 1625nm）
- **数据记录**：将测量数据保存为CSV文件

### 网络功能
- **TCP服务器**：允许远程客户端连接获取功率数据
- **TCP客户端**：连接其他功率计服务器进行数据共享
- **局域网发现**：自动发现局域网内的其他控制软件
- **自动化接口**：提供自动化测试系统的控制接口（端口1235）

### 硬件支持
- 支持 JW8103A、JW8102A 系列光功率计
- 使用 FTDI USB转串口芯片
- 自动配置FTDI芯片延迟定时器以提高通信效率

## 系统要求

- **操作系统**：Windows 10/11
- **Python版本**：Python 3.8+
- **硬件要求**：嘉慧 JW8103A 或 JW8102A 光功率计

## 安装依赖

```bash
pip install PyQt5 pyserial pandas pyqtgraph numpy bitstring
```

或使用requirements.txt（如有）：

```bash
pip install -r requirements.txt
```

## 运行程序

```bash
python 嘉慧功率计.py
```

## 项目结构

```
嘉慧功率计/
├── 嘉慧功率计.py          # 主入口文件
├── JW8103A_Control.py     # 主控制界面
├── JW8103A.py             # 设备通信协议
├── TCPClient.py           # TCP客户端
├── TCPServer.py           # TCP服务器
├── MyPlot.py              # 实时曲线绑图组件
├── LAN_Search.py          # 局域网服务发现
├── LatencyTimerSet.py     # FTDI延迟定时器设置
├── tool.py                # 配置文件工具
├── Ui_JW8103A_Control.py  # UI界面（Qt Designer生成）
├── JW8103A_Control.ui     # Qt Designer界面文件
├── config.ini             # 配置文件
├── 更新内容.csv           # 版本更新日志
├── logo_llgt.ico          # 程序图标
├── 嘉慧功率计.spec        # PyInstaller打包配置
└── Record/                # 数据记录目录
```

## 使用说明

### 串口连接
1. 连接功率计到电脑USB端口
2. 点击"检查端口"刷新可用端口列表
3. 选择正确的COM端口（需为FTDI端口）
4. 点击"打开端口"
5. 点击"连接"与功率计建立通信

### 数据记录
1. 连接设备后，点击"开始记录"按钮
2. 数据将实时保存到 `Record/` 目录
3. 点击"停止记录"结束记录
4. 文件名格式：`PowerRecord_开始时间_结束时间.csv`

### 远程连接
1. 串口连接的主机会自动启动TCP服务器
2. 其他客户端可通过"扫描服务器"发现可用服务
3. 选择服务器后点击"TCP连接"进行远程连接

### 自动化接口

程序启动后会在端口 1235 监听自动化控制命令：

```json
// 获取功率值
{"opcode": "GetPower", "parameter": {}}

// 开始记录
{"opcode": "RecordCon", "parameter": {"Con": "Start"}}

// 停止记录
{"opcode": "RecordCon", "parameter": {"Con": "Stop"}}

// 连接设备
{"opcode": "ConnectDevice", "parameter": {}}

// 检查版本
{"opcode": "check", "parameter": {}}
```

响应格式：
```json
{
  "isSuccess": true,
  "Value": {...},
  "ErrorMessage": ""
}
```

## 通信协议

详细协议说明请参考《嘉慧功率计JW8102A_JW8103A 用户通信协议V23.05.06.pdf》

协议帧格式：
```
帧头(0x7B) + 地址 + 长度 + 命令(2字节) + 数据 + 校验 + 帧尾(0x7D)
```

## 版本历史

| 版本 | 更新内容 |
|------|----------|
| v1.0.3 | 增加自动搜索局域网服务功能，修正最大最小值更新逻辑 |
| v1.0.2 | 增加自定义通道名称功能，数据记录表头自动跟随 |
| v1.0.1 | 修改保存数据分段方法，增加功率变化折线图，增加串口识别和FTDI延时器自动配置 |
| v1.0.0 | 正式版本，双设备监看，远程控制支持 |

## 打包发布

使用 PyInstaller 打包为可执行文件：

```bash
pyinstaller 嘉慧功率计.spec
```

打包后的程序位于 `dist/嘉慧功率计vX.X.X/` 目录。

## 许可证

本项目采用 [Mozilla Public License 2.0 (MPL-2.0)](https://opensource.org/licenses/MPL-2.0) 许可证。

### MPL 2.0 许可证要点

- ✅ **商业使用**：可以用于商业目的
- ✅ **修改**：可以修改源代码
- ✅ **分发**：可以分发软件
- ✅ **专利使用**：提供专利授权
- ✅ **私人使用**：可以私人使用
- ⚠️ **公开源代码**：修改的文件必须公开源代码（基于文件级别的 copyleft）
- ⚠️ **许可证和版权声明**：必须包含许可证和版权声明

详细内容请参阅 [LICENSE](LICENSE) 文件。

## 联系方式



