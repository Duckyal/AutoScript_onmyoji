from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
import subprocess
import requests
import time


app = FastAPI()
# 让 FastAPI 自动识别 static 目录下所有的 css/js 文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# ==========================ui接口===================================
@app.get("/")
async def index(request: Request):
    # 接收 device_name，默认为空字符串
    return Jinja2Templates(directory="static").TemplateResponse("index.html", {
        "request": request,
        "time_now": time.time()
    })

@app.get("/home")
async def home(request: Request, device: str):
    # 进页时校验设备
    device_ok, device_msg = check_adb(device)

    # 渲染home页面
    return Jinja2Templates(directory="static").TemplateResponse("home.html", {
        "request": request,
        "time_now": time.time(),
        "device": device,
        "device_ok": device_ok,       # adb是否通过校验
        "device_msg": device_msg,     # 未通过时的提示文案
    })

@app.get("/dev")
async def dev(request: Request, device: str):
    # 进页时校验设备
    device_ok, device_msg = check_adb(device)

    # 渲染home页面
    return Jinja2Templates(directory="static").TemplateResponse("dev.html", {
        "request": request,
        "time_now": time.time(),
        "device": device,
        "device_ok": device_ok,       # adb是否通过校验
        "device_msg": device_msg,     # 未通过时的提示文案
    })

# 校验设备是否在线
def check_adb(device):
    try:
        if ":" in device:
            result = subprocess.run(['adb', 'connect', device],
                                    capture_output=True, text=True, timeout=5)
            output = result.stdout + result.stderr
            if 'connected' in output or 'already connected' in output:
                return True, "连接成功"
            return False, output.strip() or "连接失败"
        else:
            result = subprocess.run(['adb', '-s', device, 'get-state'],
                                    capture_output=True, text=True, timeout=5)
            if 'device' in result.stdout:
                return True, "设备在线"
            return False, "设备未连接或离线"
    except subprocess.TimeoutExpired:
        return False, "adb 命令超时"
    except FileNotFoundError:
        return False, "未找到 adb，请检查环境变量"
    except Exception as e:
        return False, str(e)

# 获取 adb devices 的辅助函数
@app.get("/api/get_devices")
async def api_get_devices():
    try:
        # 执行 adb devices 命令
        result = subprocess.run(['adb', 'devices'], capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split('\n')
        # 解析输出 (跳过第一行 "List of devices attached")
        devices = []
        for line in lines[1:]:
            if line.strip():
                # 输出格式类似: "192.168.1.100:5555    device"
                parts = line.split('\t')
                if len(parts) >= 2 and parts[1].strip() == 'device':
                    devices.append(parts[0].strip())
        return {"devices": devices}
    except FileNotFoundError:
        print("未找到 adb 命令，请确保 adb 已加入环境变量")
        return {"devices": []}
    except Exception as e:
        print(f"获取设备失败: {e}")
        return {"devices": []}

# 获取index页面背景图
@app.get("/api/latest_wallpaper")
def latest_wallpaper():
    url = 'https://yys.163.com/media/picture.html'
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    html = requests.get(url, headers=headers, timeout=10).text

    import re
    # 优先横版高清
    m = (re.search(r'https://yys\.res\.netease\.com[^"\'\s]*?1920x1080\.jpg' , html)
         or re.search(r'https://yys\.res\.netease\.com[^"\'\s]*?\.jpg' , html))
    return {"url": m.group(0) if m else ""}




# ==================== Scrcpy 全局流管理 ====================
from fastapi.responses import StreamingResponse, JSONResponse
from threading import Lock
import scrcpy
import cv2
import subprocess
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import Response

# 全局变量存放当前设备的最新一帧画面
current_frame = None
frame_lock = Lock()
current_client = None
current_device = None


def frame_to_bgr(frame):
    """统一处理颜色通道，解决颜色反转问题"""
    if len(frame.shape) == 3 and frame.shape[2] == 4:
        # 如果是 4 通道，转成 3 通道 BGR
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    return frame


def start_scrcpy_stream(device_name: str):
    """启动 Scrcpy 客户端，持续接收视频流（带自动重连）"""
    global current_frame, current_client, current_device
    
    if current_device == device_name and current_client is not None:
        return

    if current_client is not None:
        current_client.stop()
        current_client = None

    current_device = device_name
    
    # ADB 设备检查
    try:
        print(f"正在检查 ADB 设备列表，查找 {device_name}...")
        result = subprocess.run(["adb", "devices"], capture_output=True, text=True, timeout=3)
        print(result.stdout)
        if device_name not in result.stdout:
            print("警告: adb devices 中未找到该设备！")
    except Exception as e:
        print("执行 adb devices 失败:", e)

    def stream_worker():
        """独立线程：负责拉流，断开后自动重连"""
        global current_frame, current_client
        
        def on_frame(frame):
            global current_frame
            if frame is not None:
                with frame_lock:
                    current_frame = frame.copy()

        retry_count = 0
        while current_device == device_name:
            try:
                print(f"启动 Scrcpy (第 {retry_count + 1} 次)，设备: {device_name}")
                client = scrcpy.Client(
                    device=device_name,
                    bitrate=2000000,   # 降低码率到 2Mbps，适合无线传输
                    max_width=1280,    # 限制分辨率，减少带宽压力
                )
                current_client = client
                client.add_listener(scrcpy.EVENT_FRAME, on_frame)
                client.start()  # 阻塞运行，断开后会抛异常
                retry_count = 0  # 正常结束则重置计数
            except Exception as e:
                print(f"Scrcpy 流断开: {e}")
                retry_count += 1
                if retry_count > 30:
                    print("重连次数过多，停止尝试。")
                    break
                # 递增等待时间，避免疯狂重连
                wait_time = min(3 * retry_count, 15)
                print(f"{wait_time} 秒后自动重连...")
                time.sleep(wait_time)

    # 在独立线程中运行，不阻塞主线程
    import threading
    t = threading.Thread(target=stream_worker, daemon=True)
    t.start()
    print(f"Scrcpy 视频流线程已启动，设备: {device_name}")


def get_current_frame_jpeg():
    """获取当前帧的 JPEG 字节"""
    with frame_lock:
        if current_frame is None:
            return None
        frame = current_frame.copy()
        
    frame_bgr = frame_to_bgr(frame)
    _, jpeg_buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return jpeg_buffer.tobytes()


# ==================== 视频流与控制接口 ====================

@app.get("/api/start_stream")
def start_stream(device_name: str):
    """前端页面加载时调用，通知后端开始拉流"""
    start_scrcpy_stream(device_name)
    return {"success": True, "message": "流正在启动..."}

@app.get("/api/stream")
def video_stream():
    """生成 MJPEG 流给前端 <img> 标签使用"""
    def generate():
        while True:
            frame_bytes = get_current_frame_jpeg()
            if frame_bytes:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n\r\n')
            time.sleep(0.033) # 约 30 fps
    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/api/current_frame")
def get_current_frame(device_name: str):
    """返回内存中当前帧的 JPEG 字节流，供前端截图裁剪用"""
    jpeg_bytes = get_current_frame_jpeg()
    if jpeg_bytes is None:
        return JSONResponse(status_code=400, content={"success": False, "message": "画面未加载"})
    return Response(content=jpeg_bytes, media_type="image/jpeg")

@app.post("/api/input")
async def handle_input(
    device_name: str = Form(...), 
    action: str = Form(...), 
    x1: int = Form(...), 
    y1: int = Form(...), 
    x2: int = Form(0), 
    y2: int = Form(0), 
    duration: int = Form(0)
):
    """接收前端的触控指令，通过 ADB 发给手机"""
    try:
        if action == "tap":
            subprocess.run(["adb", "-s", device_name, "shell", "input", "tap", str(x1), str(y1)], timeout=2)
        elif action == "swipe":
            subprocess.run(["adb", "-s", device_name, "shell", "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration)], timeout=2)
        return {"success": True, "message": "操作已发送"}
    except subprocess.TimeoutExpired:
        return JSONResponse(status_code=408, content={"success": False, "message": "ADB 操作超时"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})


# ==================== 截图接口 ====================

@app.post("/api/screenshot")
async def save_screenshot(
    device_name: str = Form(...), 
    folder_path: str = Form(...),
    file_name: str = Form(...),
    image: UploadFile = File(...)
):
    """接收前端裁剪好的图片文件并保存到指定路径"""
    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)
        
        if not file_name:
            file_name = "screenshot.png"
            
        filepath = os.path.join(folder_path, file_name)
        with open(filepath, "wb") as buffer:
            buffer.write(await image.read())
            
        return {"success": True, "message": "截屏成功", "path": filepath}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

# ===================== 选择目录接口 =====================
import tkinter as tk
from tkinter import filedialog


@app.get("/api/pick_folder")
def pick_folder():
    """弹出系统原生文件夹选择框"""
    try:
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)  # 保证窗口在最前
        folder_path = filedialog.askdirectory(title="选择截图保存文件夹")
        root.destroy()
        return {"success": True, "path": folder_path}
    except Exception as e:
        return {"success": False, "message": str(e)}





# =====================日志传输接口=======================
from fastapi import WebSocket
from module.log import WebSocketLogManager

ws_manager = WebSocketLogManager()

@app.websocket("/logs")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # 只是保持连接，不需要接收前端发来的消息
            await websocket.receive_text()
    except Exception:
        ws_manager.disconnect(websocket)


# =======================启动任务接口==============================
import shutil, os
import datetime
from fastapi import UploadFile, Form
from tasks import custom
import asyncio

@app.post("/start")
async def run_task(request: Request):
    content_type = request.headers.get("content-type", "")

    data = await request.json()
    device = data.get("base", {})["device"]
    # 执行自定义py任务
    if "multipart/form-data" in content_type:
        form = await request.form()
        # 用 UploadFile 类型接收文件
        py_file: UploadFile = form.get("file") # type: ignore
        if not py_file:
            log("未收到py文件")
        # 清除临时文件
        shutil.rmtree("tmp", ignore_errors=True)
        # 保存到本地
        upload_dir = "tmp"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, py_file.filename) # type: ignore
        with open(file_path, "wb") as f:
            shutil.copyfileobj(py_file.file, f)
        ws_manager.log(f'收到自定义脚本: {py_file.filename}')
        asyncio.create_task(asyncio.to_thread(custom.run, py_file.filename, device))
    # 执行预制任务
    else:
        task_name = data.get("task")
        config = data.get("config", {})
        base = data.get("base", {})
        ws_manager.log(f"收到内置任务: {task_name}，设备信息: {base}，任务配置: {config}", "info")

        # 根据任务类型分发
        from module.adb import ADB
        from tasks import yuhun, douji, tupo

        device = ADB(base["device"], base["mode"]) if base["device"]!="" else ADB(mode=base["mode"])
        task_class = None
        if task_name == "yuhun":
            task_class = yuhun.YuhunTask
        elif task_name == "douji":
            task_class = douji.DoujiTask
        elif task_name == "tupo":
            task_class = tupo.TupoTask

        asyncio.create_task(asyncio.to_thread(task_class, device, config)) # type: ignore



if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)