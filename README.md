# AutoScript_onmyoji

阴阳师游戏自动化脚本工具，提供现代化 Web 界面管理和 ADB 手机自动化功能。

## 功能特性

- **Web 界面管理**：基于 FastAPI 的现代化 Web 界面，支持实时日志查看和任务管理
- **开发控制台**：集成 scrcpy 投屏功能，支持实时查看设备屏幕、远程操作、拉框截图
- **内置任务**：支持御魂、斗技、突破、英杰、活动等游戏任务自动化
- **OCR 识别**：集成 RapidOCR 进行图像文字识别，支持找图和找字功能
- **图像处理**：使用 OpenCV 进行图像分析和模板匹配
- **实时日志**：WebSocket 实时日志传输和终端样式显示
- **ADB 集成**：通过 ADB 连接 Android 设备进行自动化操作
- **可中断任务**：支持优雅停止运行中的任务

## 安装步骤

### 环境要求

- Python 3.10+
- Android 设备（支持 ADB 连接）
- ADB 工具（建议安装完整的 Android SDK Platform Tools）

### 使用 uv 安装（推荐）

```bash
git clone https://github.com/Duckyal/AutoScript_onmyoji.git
cd AutoScript_onmyoji

# 初始化虚拟环境并安装依赖
uv sync
```

### 使用 pip 安装

```bash
git clone https://github.com/Duckyal/AutoScript_onmyoji.git
cd AutoScript_onmyoji

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate    # Windows

# 安装依赖
pip install -r requirements.txt
```

### 安装 ADB

```bash
# Ubuntu/Debian
sudo apt install adb

# Arch Linux
sudo pacman -S android-tools

# macOS (Homebrew)
brew install android-platform-tools

# Windows
# 下载 https://developer.android.com/studio/releases/platform-tools
# 解压后添加到 PATH
```

## 使用方法

### 启动服务

```bash
# 使用 uv
uv run python main.py

# 或直接运行
python main.py
```

服务将在 `http://0.0.0.0:8000` 启动。

### 连接设备

1. 确保 Android 设备已开启 **USB 调试**
2. 通过 USB 或网络连接设备：

```bash
# USB 连接
adb devices

# 网络连接（需先通过 USB 连接一次）
adb tcpip 5555
adb connect <设备IP>:5555
```

### 执行任务

#### 设备页

在首页输入设备序列号后进入设备页，选择任务类型并配置参数：

- **御魂**：自动执行御魂副本，支持选择层数、次数、组队模式
- **斗技**：自动斗技场对战，支持到达名仕或荣誉点满自动停止
- **突破**：自动式神突破，支持个人突破和寮突破
- **英杰**：自动挑战英杰副本
- **活动**：自动执行活动任务

#### 开发控制台

点击"开发页"进入开发控制台，支持：

- **实时投屏**：查看设备屏幕实时画面
- **远程操作**：鼠标点击、拖拽控制设备
- **拉框截图**：框选屏幕区域并保存截图
- **找图功能**：上传图片进行模板匹配
- **找字功能**：OCR 文字识别

## 项目结构

```
AutoScript_onmyoji/
├── main.py                 # 主程序入口（FastAPI 服务）
├── requirements.txt        # Python 依赖
├── sync_frontend.sh        # 前端同步脚本（推送到 github.io）
├── .gitignore              # Git 忽略配置
├── api/                    # API 路由
│   ├── routes.py           # 核心 API 路由（任务、截图、OCR 等）
│   └── ui.py               # UI 页面路由
├── module/                 # 核心模块
│   ├── adb.py              # ADB 设备管理（截图、点击、找图、找字）
│   ├── adb_stream.py       # scrcpy 视频流管理
│   ├── decorators.py       # 装饰器工具（停止信号、可中断 sleep）
│   ├── logmanager.py       # WebSocket 日志管理器
│   └── task_manager.py     # 任务管理器（协程管理、状态查询）
├── static/                 # 静态资源（前端页面）
│   ├── css/                # 样式文件
│   ├── js/                 # JavaScript 文件
│   │   ├── dev/            # 开发控制台脚本
│   │   ├── home/           # 主页脚本
│   │   └── index/          # 首页脚本
│   ├── dev.html            # 开发控制台页面
│   ├── home.html           # 设备页
│   └── index.html          # 首页（设备选择）
└── tasks/                  # 任务脚本
    ├── yuhun.py            # 御魂任务
    ├── douji.py            # 斗技任务
    ├── tupo.py             # 突破任务
    ├── yinjie.py           # 英杰任务
    ├── huodong.py          # 活动任务
    └── 斗技图片/           # 斗技任务图片资源
        └── ...
```

## API 接口

### 任务管理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/start` | POST | 启动任务 |
| `/api/stop_task` | POST | 停止任务 |
| `/api/task_status` | GET | 查询任务状态 |

### 图像处理

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/find_image` | POST | 找图（模板匹配） |
| `/api/ocr_text` | POST | 找字（OCR 识别） |
| `/api/save_screenshot` | POST | 保存截图 |

### 设备信息

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/device_resolution` | GET | 获取设备分辨率 |
| `/api/adb_devices` | GET | 获取连接的设备列表 |

### 视频流

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/stream` | GET | 获取 scrcpy 视频流 |
| `/api/start_stream` | POST | 启动视频流 |
| `/api/stop_stream` | POST | 停止视频流 |

## 开发说明

### 添加新任务

1. 在 `tasks/` 目录创建新的任务文件
2. 实现 `Task_xxx` 类，包含 `run()` 方法
3. 在 `main.py` 中注册任务路由

### 自定义脚本规范

自定义脚本需要符合以下规范：

- 脚本文件应为 `.py` 文件
- 创建任务类，接收 `device`（ADB 实例）和 `config`（配置字典）参数
- 在 `run()` 方法中实现任务逻辑
- 使用 `self.op.sleep()` 替代 `time.sleep()`（支持中断）
- 使用 `self.op.log()` 进行日志输出

### 前端同步

修改前端后同步到 GitHub Pages：

```bash
./sync_frontend.sh
```

## 注意事项

- 请确保 ADB 连接稳定
- 游戏版本更新可能影响脚本兼容性
- 使用自动化脚本时请遵守游戏规则
- 建议在测试环境先验证脚本功能
- 截图默认保存到系统下载目录

## 许可证

本项目采用 MIT 许可证。
