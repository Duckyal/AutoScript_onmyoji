# AutoScript_onmyoji

阴阳师游戏自动化脚本工具，提供Web界面管理和ADB手机自动化功能。

## 功能特性

- **Web界面管理**：基于FastAPI的现代化Web界面，支持实时日志查看
- **内置任务**：支持御魂、斗技、突破等游戏任务自动化
- **自定义脚本**：支持上传和执行自定义Python脚本
- **多进程管理**：支持同时运行多个脚本进程
- **实时日志**：WebSocket实时日志传输和显示
- **ADB集成**：通过ADB连接Android设备进行自动化操作
- **OCR识别**：集成RapidOCR进行图像文字识别
- **图像处理**：使用OpenCV进行图像分析和处理

## 安装步骤

### 环境要求

- Python 3.8+
- Android设备（支持ADB连接）
- ADB工具

### 安装依赖

1. 克隆项目：
```bash
git clone <repository-url>
cd AutoScript_onmyoji
```

2. 安装Python依赖：
```bash
pip install -r requirements.txt
```

3. 安装ADB工具（如果尚未安装）：
```bash
# Windows
# 下载ADB工具并添加到PATH环境变量
# 或使用scrcpy等工具
```

## 使用方法

### 启动服务

运行主程序启动Web服务：

```bash
python main.py
```

服务将在 `http://localhost:8000` 启动。

### 连接设备

1. 确保Android设备已开启USB调试
2. 使用ADB连接设备：
```bash
adb devices  # 查看连接的设备
```

### 执行任务

#### 内置任务

在Web界面中选择以下内置任务：

- **御魂 (yuhun)**：自动执行御魂副本
- **斗技 (douji)**：自动斗技场对战
- **突破 (tupo)**：自动式神突破

配置相应参数后点击"启动"按钮。

#### 自定义脚本

1. 编写Python脚本（参考 `tasks/` 目录下的示例）
2. 在Web界面上传脚本文件
3. 选择进程并启动执行

## 项目结构

```
AutoScript_onmyoji/
├── main.py                 # 主程序入口
├── requirements.txt        # Python依赖
├── module/                 # 核心模块
│   ├── adb.py             # ADB设备管理
│   ├── decorators.py      # 装饰器工具
│   ├── log.py             # 日志工具
│   └── log_manager.py     # 日志管理器
├── static/                 # 静态资源
│   ├── css/               # 样式文件
│   └── js/                # JavaScript文件
├── tasks/                  # 任务脚本
│   ├── yuhun.py           # 御魂任务
│   ├── douji.py           # 斗技任务
│   ├── tupo.py            # 突破任务
│   └── custom.py          # 自定义脚本执行器
├── templates/              # HTML模板
│   └── index.html         # 主页面
└── tmp/                   # 临时文件目录
```

## 开发说明

### 添加新任务

1. 在 `tasks/` 目录创建新的任务文件
2. 实现任务类，继承基础任务逻辑
3. 在 `main.py` 中添加任务路由

### 自定义脚本规范

自定义脚本需要符合以下规范：

- 脚本文件应为 `.py` 文件
- 主要逻辑应封装在函数或类中
- 使用 `module.log` 进行日志输出
- 支持异步执行

## 注意事项

- 请确保ADB连接稳定
- 游戏版本更新可能影响脚本兼容性
- 使用自动化脚本时请遵守游戏规则
- 建议在测试环境先验证脚本功能

## 许可证

本项目采用 MIT 许可证。
