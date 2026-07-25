# api/routes.py
from fastapi import APIRouter, Request, Form, File, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse, Response
import asyncio
import time
import os
import platformdirs

router = APIRouter()

# --- 导入模块 ---
from module import adb_stream
from module.logmanager import ws_manager
from module import task_manager
from module.adb import ADB  # 你原有的 ADB 类

# --- 设备与流 ---
@router.get("/api/get_devices")
async def api_get_devices():
    return {"devices": adb_stream.get_devices()}

@router.get("/api/stream_status")
def get_stream_status():
    """返回当前视频流的连接状态"""
    return JSONResponse(content=adb_stream.stream_manager.get_status())

@router.post("/api/set_stream_interval")
async def set_stream_interval(request: Request):
    """设置截图间隔（秒），范围0.01-0.6"""
    data = await request.json()
    interval = data.get("interval", 0.3)
    adb_stream.stream_manager.set_screenshot_interval(interval)
    return {"success": True, "message": f"截图间隔已设置为 {interval:.2f} 秒"}

@router.get("/api/device_resolution")
def get_device_resolution(device_name: str):
    """获取设备的物理分辨率"""
    import subprocess
    try:
        result = subprocess.run(
            ["adb", "-s", device_name, "shell", "wm", "size"],
            capture_output=True, text=True, timeout=2
        )
        output = result.stdout.strip()
        if 'Physical size:' in output:
            size_str = output.split('Physical size:')[1].strip()
            w, h = map(int, size_str.split('x'))
            return {"success": True, "width": w, "height": h}
        elif 'size:' in output:
            size_str = output.split('size:')[1].strip()
            w, h = map(int, size_str.split('x'))
            return {"success": True, "width": w, "height": h}
        return {"success": False, "message": "无法获取分辨率"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.get("/api/start_stream")
def start_stream(device_name: str):
    adb_stream.stream_manager.start(device_name)
    return {"success": True, "message": "流正在启动..."}

@router.get("/api/stream")
def video_stream():
    def generate():
        timeout_count = 0
        max_timeout = 10
        while True:
            try:
                frame_bytes = adb_stream.stream_manager.get_frame_jpeg()
                timeout_count = 0
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n\r\n')
            except ValueError:
                timeout_count += 1
                if timeout_count >= max_timeout:
                    break
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + b'' + b'\r\n\r\n')
            except Exception as e:
                print(f"[STREAM ERROR] {e}")
                timeout_count += 1
                if timeout_count >= max_timeout:
                    break
                time.sleep(0.5)
            time.sleep(0.033)
    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")

@router.get("/api/current_frame")
def get_current_frame(device_name: str):
    try:
        jpeg_bytes = adb_stream.stream_manager.get_frame_jpeg()
        return Response(content=jpeg_bytes, media_type="image/jpeg")
    except ValueError:
        return JSONResponse(status_code=400, content={"success": False, "message": "画面未加载"})

# --- 控制与输入 ---
@router.post("/api/input")
async def handle_input(
    device_name: str = Form(...), action: str = Form(...),
    x1: int = Form(...), y1: int = Form(...),
    x2: int = Form(0), y2: int = Form(0), duration: int = Form(0)
):
    # 这里也可以调用 module/adb.py 里的类方法，看你喜好
    try:
        device = ADB(device_name)
        if action == "tap":
            device.adb_shell(f"input tap {x1} {y1}")
        elif action == "swipe":
            device.adb_shell(f"input swipe {x1} {y1} {x2} {y2} {duration}")
        elif action == "longpress":
            device.adb_shell(f"input swipe {x1} {y1} {x1} {y1} {duration}")         
        return {"success": True, "message": "操作已发送"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

# --- 保存截图 ---
@router.post("/api/save_screenshot")
async def save_screenshot(
    folder_path: str = Form(''),
    file_name: str = Form(''),
    screen_width: str = Form(''),
    screen_height: str = Form(''),
    image: UploadFile = File(...)
):
    try:
        if not folder_path: 
            folder_path = platformdirs.user_downloads_dir()
        if not os.path.exists(folder_path): 
            os.makedirs(folder_path, exist_ok=True)
        
        # 生成文件名：{用户输入}_{屏幕宽度}x{屏幕高度}.png
        # 如果用户未输入文件名，使用时间戳
        base_name = file_name if file_name else f"screenshot_{int(time.time())}"
        
        # 如果提供了屏幕尺寸，添加到文件名中
        if screen_width and screen_height:
            final_name = f"{base_name}_{screen_width}x{screen_height}.png"
        else:
            final_name = f"{base_name}.png"
        
        filepath = os.path.join(folder_path, final_name)

        with open(filepath, "wb") as buffer:
            buffer.write(await image.read())
        return {"success": True, "message": "保存截屏成功", "path": filepath}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})


# --- 任务执行 ---
from module.decorators import register_stop_signal, cleanup_stop_signal, TaskStoppedException

@router.post("/start")
async def run_task(request: Request):
    data = await request.json()

    task_name = data.get("task")
    device_id = data.get("device")
    config = data.get("config", {})
    mode = config.get("mode", "less")
    
    if not device_id:
        return JSONResponse(status_code=400, content={"success": False, "message": "设备ID不能为空"})

    try:
        # 动态导入任务类
        import importlib
        module = importlib.import_module(f'tasks.{task_name}')
        TaskClass = getattr(module, f'Task_{task_name}')
        
        # 创建设备对象
        device = ADB(device_id, mode)
        
        # 注册停止信号 (必须)
        register_stop_signal(device_id)
        
        # 实例化任务
        task_instance = TaskClass(device, config)

        # 定义任务包装器
        async def task_wrapper():
            try:
                await asyncio.to_thread(task_instance.run)
         
            except TaskStoppedException:
                ws_manager.log(f"任务 {device_id} 已被终止", "success")
                
            except asyncio.CancelledError:
                ws_manager.log(f"任务 {device_id} 被取消", "warning")
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                ws_manager.log(f"任务异常: {e}", "error")
                
            finally:
                # 【关键清理】
                cleanup_stop_signal(device_id)
                task_manager.active_tasks.pop(device_id, None)
                task_manager.active_names.pop(device_id, None)
        
        # 创建并注册 asyncio 任务
        task_obj = asyncio.create_task(task_wrapper())
        task_manager.register_task(device_id, task_obj, task_name)
        
        return {"success": True, "message": "任务已开始"}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500, 
            content={"success": False, "message": f"启动失败: {str(e)}"}
        )

# --- 任务状态查询 ---
@router.get("/api/task_status")
def get_task_status(device: str):
    is_running, name = task_manager.is_running(device)
    return {
        "running": is_running,
        "task_name": name
    }

# --- 停止任务 ---
from module.decorators import trigger_stop_signal

@router.post("/api/stop_task")
async def stop_task_api(request: Request):
    body = await request.json()
    device_id = body.get("device")
    
    if not device_id:
        return {"success": False, "message": "缺少设备ID"}
    
    # 触发停止信号（用于优雅停止，让代码清理资源）
    trigger_stop_signal(device_id)
    
    return {"success": True, "message": "终止指令已发送"}

# ---- 找图/找字接口 ----
@router.post("/api/find_image")
async def find_image(
    device_name: str = Form(''),
    image: UploadFile = File(None),
    sim: float = Form(0.90),
    priority_corner: str = Form('tl'),
    x1: str = Form('-1'),
    y1: str = Form('-1'),
    x2: str = Form('-1'),
    y2: str = Form('-1')
):
    try:
        x1_val = float(x1) if '.' in x1 else int(x1)
        y1_val = float(y1) if '.' in y1 else int(y1)
        x2_val = float(x2) if '.' in x2 else int(x2)
        y2_val = float(y2) if '.' in y2 else int(y2)
    except ValueError:
        x1_val = y1_val = x2_val = y2_val = -1
    
    device = ADB(device_name)
    
    if image and image.filename:
        img_bytes = await image.read()
        device.图片预加载(img_bytes)
    else:
        main_img = device.获取截图(x1_val, y1_val, x2_val, y2_val)
        device.图片预加载(main_img)
    
    result = device.找图(sim=sim, priority_corner=priority_corner, x1=x1_val, y1=y1_val, x2=x2_val, y2=y2_val)
    print(result)
    return {"result": str(result)}

@router.post("/api/ocr_text")
async def ocr_text(
    device_name: str = Form(''),
    image: UploadFile = File(None),
    target_txt: str = Form(''),
    use_regex: bool = Form(False),
    x1: str = Form('-1'),
    y1: str = Form('-1'),
    x2: str = Form('-1'),
    y2: str = Form('-1')
):
    try:
        x1_val = float(x1) if '.' in x1 else int(x1)
        y1_val = float(y1) if '.' in y1 else int(y1)
        x2_val = float(x2) if '.' in x2 else int(x2)
        y2_val = float(y2) if '.' in y2 else int(y2)
    except ValueError:
        x1_val = y1_val = x2_val = y2_val = -1
    
    device = ADB(device_name)
    
    if image and image.filename:
        img_bytes = await image.read()
        result = device.找字(Specified_image=img_bytes, target_txt=target_txt, use_regex=use_regex, x1=x1_val, y1=y1_val, x2=x2_val, y2=y2_val)
    else:
        result = device.找字(target_txt=target_txt, use_regex=use_regex, x1=x1_val, y1=y1_val, x2=x2_val, y2=y2_val)
    
    print(result)
    return {"result": str(result)}