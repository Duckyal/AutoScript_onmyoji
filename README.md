# AutoScript_onmyoji

阴阳师游戏自动化脚本工具，提供现代化 Web 界面管理和 ADB 手机自动化功能。

## 功能特性

- **Web 界面管理**：基于 FastAPI 的现代化 Web 界面，支持实时日志查看和任务管理
- **开发控制台**：集成 uiautomator2 投屏功能，支持实时查看设备屏幕、远程操作、拉框截图、找图找字、可调帧率
- **内置任务**：支持御魂、御灵、斗技、突破、英杰、活动、K28 等游戏任务自动化
- **OCR 识别**：集成 RapidOCR 进行图像文字识别，支持正则匹配和局部区域识别
- **图像处理**：使用 OpenCV 进行图像分析和模板匹配，支持角优先度选择
- **实时日志**：WebSocket 实时日志传输和终端样式显示
- **ADB 集成**：通过 ADB 连接 Android 设备进行自动化操作
- **可中断任务**：支持优雅停止运行中的任务
- **多设备支持**：支持同时连接多个设备

## 安装步骤

### 环境要求

- Python 3.10~3.13（**不支持 3.14**，多数依赖尚无预编译 wheel）
- Android 设备（支持 ADB 连接）
- ADB 工具（建议安装完整的 Android SDK Platform Tools）

### 安装 uv（推荐）

uv 是一个快速的 Python 包管理器，建议使用 uv 管理虚拟环境和依赖：

```bash
# Linux/Mac
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
irm https://astral.sh/uv/install.ps1 | iex

# 验证安装
uv --version
```

### 使用 uv（推荐，开箱即用）

```bash
# 1. 克隆项目
git clone https://github.com/Duckyal/AutoScript_onmyoji.git
cd AutoScript_onmyoji

# 2. 直接运行（首次自动创建 .venv 并安装依赖）
uv run python main.py
```

首次运行时 uv 会根据 `pyproject.toml` 自动完成：
- 创建 `.venv` 虚拟环境
- 安装所有依赖到虚拟环境
- 启动程序

后续运行直接秒启动，无需重复安装。

### 使用 pip 创建虚拟环境并安装依赖

如果你不使用 uv，可以使用标准的 pip 方式：

```bash
# 1. 克隆项目
git clone https://github.com/Duckyal/AutoScript_onmyoji.git
cd AutoScript_onmyoji

# 2. 创建虚拟环境
python -m venv .venv

# 3. 激活虚拟环境
# Linux/Mac
source .venv/bin/activate
# Windows Command Prompt
.venv\Scripts\activate.bat
# Windows PowerShell
.venv\Scripts\Activate.ps1

# 4. 安装依赖
pip install -r requirements.txt

# 5. 验证安装（可选）
pip list
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
# 前往 [AndroidDevelopers](https://developer.android.google.cn/tools/releases/platform-tools?hl=zh-cn) 下载[platform-tools](https://googledownloads.cn/android/repository/platform-tools-latest-windows.zip)
# 解压后添加到 PATH
```

### 验证安装

安装完成后可以验证关键工具是否可用：

```bash
# 验证 Python
python --version

# 验证 ADB
adb version

# 验证 uv 项目依赖（首次会自动创建虚拟环境并安装依赖）
uv run python -c "import fastapi; print('FastAPI:', fastapi.__version__)"
```

## 使用方法

### 启动服务

```bash
uv run python main.py
# 或
python main.py
```

服务将在 `http://localhost:8000` 启动（可搭配内网穿透工具异网操控本地脚本运行）。

### 连接设备

1. 确保 Android 设备已开启 **USB 调试**
2. 通过 USB 或网络连接设备：

```bash
adb devices
adb tcpip 5555
adb connect <设备IP>:5555
```

### 执行任务

#### 设备页

在首页输入设备序列号后进入设备页，选择任务类型并配置参数：

- **御魂**：自动执行御魂副本，支持选择层数、次数、组队模式（暂不支持）
- **御灵**：自动执行御灵副本，支持选择层数、次数、组队模式
- **斗技**：自动斗技场对战，支持到达名仕或荣誉点满自动停止
- **突破**：自动式神突破，支持个人突破和寮突破
- **英杰**：自动挑战英杰副本（仅支持部分功能）
- **活动**：自动执行活动任务（仅支持部分功能）
- **K28**：自动执行探索副本，支持突破券满自动切换突破任务

#### 开发控制台

点击"开发页"进入开发控制台，支持：

- **实时投屏**：查看设备屏幕实时画面
- **远程操作**：鼠标点击、长按、拖拽控制设备
- **拉框截图**：框选屏幕区域并保存截图
- **找图功能**：上传图片进行模板匹配，支持角优先度
- **找字功能**：OCR 文字识别，支持正则匹配

## 项目结构

```
AutoScript_onmyoji/
├── main.py                 # 主程序入口（FastAPI 服务）
├── pyproject.toml          # 项目元信息和依赖声明（uv 使用）
├── requirements.txt        # Python 依赖（pip 使用）
├── README.md               # 项目介绍
├── .gitignore              # Git 忽略配置
├── api/                    # API 路由
│   ├── routes.py           # 核心 API 路由（任务、截图、OCR、视频流）
│   └── ui.py               # UI 页面路由
├── module/                 # 核心模块
│   ├── adb.py              # ADB 设备管理（截图、点击、找图、找字）
│   ├── adb_stream.py       # uiautomator2 视频流管理（截屏方式）
│   ├── decorators.py       # 装饰器工具（停止信号、可中断 sleep）
│   ├── logmanager.py       # WebSocket 日志管理器
│   └── task_manager.py     # 任务管理器（协程管理、状态查询）
├── static/                 # 静态资源（前端页面）
│   ├── css/                # 样式文件
│   ├── js/                 # JavaScript 文件
│   ├── dev.html            # 开发控制台页面
│   ├── home.html           # 设备页
│   └── index.html          # 首页（设备选择）
└── tasks/                  # 任务脚本
    ├── yuhun.py            # 御魂任务
    ├── yuling.py           # 御灵任务
    ├── douji.py            # 斗技任务
    ├── tupo.py             # 突破任务
    ├── yinjie.py           # 英杰任务
    ├── huodong.py          # 活动任务
    ├── k28.py              # K28 任务
    └── 图片资源目录/        # 各任务图片模板
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
| `/api/stream` | GET | 获取视频流（MJPEG 格式） |
| `/api/start_stream` | GET | 启动视频流 |
| `/api/stream_status` | GET | 获取流状态 |
| `/api/set_stream_interval` | POST | 设置截图间隔（控制帧率） |

### 输入控制

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/input` | POST | 点击/滑动/长按操作 |

## 开发说明

### 添加新任务

在 `home.html` 中添加新任务需要遵循以下规范：

#### 1. 创建任务脚本

在 `tasks/` 目录创建新的任务文件（如 `xxx.py`），实现 `Task_xxx` 类：

```python
from module.adb import ADB

class Task_xxx:
    def __init__(self, device: ADB, config: dict):
        self.op = device      # ADB 设备实例
        self.config = config  # 配置字典
        
    def run(self):
        # 预加载模板图片
        self.op.图片预加载(
            "tasks/xxx图片/按钮1_1920x1080.png",
            "tasks/xxx图片/按钮2_1920x1080.png"
        )
        
        while True:
            self.op.sleep(1)
            result = self.op.找图()
            if result is None or not result:
                continue
                
            if "按钮1_1920x1080.png" in result:
                self.op.点击(*result["按钮1_1920x1080.png"])
            elif "按钮2_1920x1080.png" in result:
                self.op.点击(*result["按钮2_1920x1080.png"])
```

#### 2. 创建图片资源目录

在 `tasks/` 目录下创建对应的图片文件夹（如 `xxx图片/`），放置模板图片。图片命名规范：

```
{图片描述}_{屏幕宽度}x{屏幕高度}.png
例如：按钮1_1920x1080.png
```

屏幕参数会被找图模块自动读取，用于分辨率适配。

#### 3. 在 home.html 中添加任务配置面板

在 `static/home.html` 的 `content-main` 区域添加任务配置面板：

```html
<!-- xxx配置 -->
<div class="task-panel" id="panel-xxx" style="display: none;" data-name="任务名称">
  <h3 class="task-panel__title">任务配置</h3>
  <div class="form-group">
    <label class="form-label" for="param1">数字参数</label>
    <input class="form-input" type="text" id="param1" name="param1" value="默认值">
    
    <label class="form-label" for="param2">选项参数</label>
    <select class="form-select" id="param2" name="param2">
      <option value="option1">选项1</option>
      <option value="option2">选项2</option>
    </select>
    
    <label class="form-label" for="mode">更多日志</label>
    <select class="form-select" id="mode" name="mode">
      <option value="less">否</option>
      <option value="more">是</option>
    </select>
  </div>
</div>
```

**配置要点**：
- 每个任务面板必须有唯一的 `id`，格式为 `panel-{任务名}`（如 `panel-xxx`），与任务脚本文件名保持一致
- 每个任务面板必须有 `data-name` 属性，用于在任务列表中显示任务名称
- 表单元素必须有唯一的 `name` 属性，用于提交任务时传递参数
- 表单元素必须由 `<div class="form-group">` 包裹
- 除第一个任务面板外，其他面板应通过 `style="display: none;"` 隐藏

#### 4. 任务配置参数

所有表单参数会通过 POST 请求发送到 `/start` 接口，在任务类的 `config` 参数中获取：

```python
# 前端配置
# <input name="count" value="100">
# <select name="mode"><option value="less">否</option></select>

# 后端获取
count = self.config.get("count", 100)
mode = self.config.get("mode", "less")
```

#### 5. 任务脚本规范

- 创建任务类，接收 `device`（ADB 实例）和 `config`（配置字典）参数
- 在 `run()` 方法中实现任务逻辑
- 使用 `self.op.sleep()` 替代 `time.sleep()`（支持中断）
- 使用 `self.op.log()` 进行日志输出
- 使用 `self.op.图片预加载()` 预加载模板图片
- 使用 `self.op.找图()` 和 `self.op.找字()` 进行图像和文字识别
- 使用 `self.op.点击()`、`self.op.长按()`、`self.op.滑动()` 进行设备操作

### 开发控制台（dev.html）使用说明

开发控制台提供实时投屏、远程操作和图像识别功能，用于调试和测试。

#### 主要功能

##### 1. 实时投屏

- 左侧显示设备屏幕实时画面（MJPEG 视频流）
- 支持点击、长按、滑动等远程操作
- 支持触摸屏手势（滑动和长按）

##### 2. 模式与保存设置

- **拉框截图模式**：勾选后可在视频流上框选区域，中键切换
- **截图间隔**：设置视频流帧率（1-60 毫秒，对应约 16-1000 fps）
- **指定保存文件夹路径**：设置截图保存位置，默认下载目录
- **保存文件名**：输入文件名（不带后缀），后台自动添加屏幕参数和后缀

##### 3. 区域参数

支持设置找图找字的区域坐标（-1 表示全屏，支持小数比）：
- `x1, y1`：区域左上角坐标
- `x2, y2`：区域右下角坐标
- 可通过拉框截图自动填充区域参数

##### 4. 图像识别

**找图参数**：
- **相似度**：0-1，默认 0.90，值越高匹配越严格
- **角优先度**：左上角(tl)、右上角(tr)、左下角(bl)、右下角(br)

**找字参数**：
- **目标文本**：要识别的文本，支持正则表达式
- **使用正则匹配**：开启后支持正则表达式匹配

##### 5. 操作按钮

- **上传本地图片**：上传本地图片用于找图/找字识别
- **保存**：保存当前截图（支持拉框区域截图）
- **找图**：使用上传的图片或框选区域进行模板匹配
- **找字 (OCR)**：对当前截图或框选区域进行文字识别
- **隐藏工具栏**：隐藏右侧工具栏，全屏显示视频流

#### 使用示例

**截图保存**：
1. 输入保存文件路径（可选，默认电脑的下载目录）
2. 输入保存文件名（如 `my_shot`）
3. 框选区域或手动输入截图区域
4. 点击"保存"按钮
5. 截图将保存为 `my_shot_1920x1080.png`（自动添加屏幕参数）

**找图识别**：
1. 上传本地图片或使用框选区域或手动输入框选区域作为模板
2. 设置相似度和角优先度
3. 点击"找图"按钮
4. 识别结果显示在文本框中

**找字识别**：
1. 上传本地图片或使用框选区域或手动输入框选区域作为模板
2. 设置目标文本（支持正则，如 `\d+/30`）
3. 点击"找字 (OCR)"按钮
4. 识别结果显示在文本框中

### 找图角优先度

找图方法支持四个角优先度：

```python
self.op.找图(priority_corner='tl')  # 左上角（默认）
self.op.找图(priority_corner='tr') # 右上角
self.op.找图(priority_corner='bl') # 左下角
self.op.找图(priority_corner='br') # 右下角
```

### 找字正则匹配

```python
result = self.op.找字(target_txt=r"\d+/\d+", use_regex=True)
if result:
    for text in result:
        match = re.search(r"(\d+)/(\d+)", text)
        if match:
            a, b = match.groups()
```

### 图片文件名规范

模板图片文件名应包含屏幕分辨率信息：

```
{图片描述}_{宽度}x{高度}.png
例如：按钮_1920x1080.png
```

找图模块会自动从文件名提取屏幕参数，用于优化分辨率适配。

### 分辨率适配

找图模块支持自动分辨率适配：
- 从模板文件名提取基准分辨率（如 1920x1080）
- 根据当前截图分辨率计算缩放因子
- 支持非均匀拉伸（尽可能适配各种屏幕比例，超宽屏不支持）
- 智能双向匹配：放大截图或缩小模板，保持细节完整

## 注意事项

- 请确保 ADB 连接稳定
- 游戏版本更新可能影响脚本兼容性
- 使用自动化脚本时请遵守游戏规则
- 建议在测试环境先验证脚本功能
- 截图默认保存到系统下载目录
- 支持 Windows、Linux、macOS 多平台
- Windows运行时可能缺少动态链接库，需要安装[Visual C++ 运行库](https://aka.ms/vs/17/release/vc_redist.x64.exe)

### 版本兼容性

本项目使用的 `starlette >= 1.3.0` 版本对 `TemplateResponse` 方法签名进行了变更：

```python
# 旧版本 (< 1.3.0)
templates.TemplateResponse(name, context)

# 新版本 (>= 1.3.0)
templates.TemplateResponse(request, name, context)
```

代码已适配新版本签名，如果需要使用旧版本 Starlette，请修改 `api/ui.py` 中的 `TemplateResponse` 调用方式。

## 许可证

MIT License
