import subprocess
from typing import List, Tuple

def check_adb(device: str) -> Tuple[bool, str]:
    try:
        if ":" in device:
            result = subprocess.run(
                ['adb', 'connect', device],
                capture_output=True, text=True, timeout=5
            )
            output = result.stdout + result.stderr
            if 'connected' in output or 'already connected' in output:
                return True, "连接成功"
            return False, output.strip() or "连接失败"
        else:
            result = subprocess.run(
                ['adb', '-s', device, 'get-state'],
                capture_output=True, text=True, timeout=5
            )
            if 'device' in result.stdout:
                return True, "设备在线"
            return False, "设备未连接或离线"
    except subprocess.TimeoutExpired:
        return False, "adb 命令超时"
    except FileNotFoundError:
        return False, "未找到 adb，请检查环境变量"
    except Exception as e:
        return False, str(e)

def get_devices() -> List[str]:
    try:
        result = subprocess.run(
            ['adb', 'devices'], capture_output=True, text=True, check=True
        )
        lines = result.stdout.strip().split('\n')
        devices = []
        for line in lines[1:]:
            if line.strip():
                parts = line.split('\t')
                if len(parts) >= 2 and parts[1].strip() == 'device':
                    devices.append(parts[0].strip())
        return devices
    except FileNotFoundError:
        print("未找到 adb 命令")
        return []
    except Exception as e:
        print(f"获取设备失败: {e}")
        return []


import time
import threading
import numpy as np
import cv2
from threading import Lock
from typing import Optional

class StreamManager:
    def __init__(self):
        self.current_frame: Optional[np.ndarray] = None
        self.frame_lock = Lock()
        self.current_device: Optional[str] = None
        self.running = False
        self.screenshot_interval = 0.05
        
        self.status = {
            "connected": False,
            "message": "未初始化",
            "retry_count": 0
        }

    @staticmethod
    def _generate_placeholder_image(text="连接中..."):
        img = np.zeros((720, 1080, 3), np.uint8)
        img[:] = (50, 50, 50)
        
        font = cv2.FONT_HERSHEY_SIMPLEX
        text_size = cv2.getTextSize(text, font, 1.5, 2)[0]
        text_x = (1080 - text_size[0]) // 2
        text_y = (720 + text_size[1]) // 2
        
        cv2.putText(img, text, (text_x, text_y), font, 1.5, (255, 255, 255), 2, cv2.LINE_AA)
        
        _, buffer = cv2.imencode('.jpg', img)
        return buffer.tobytes()

    @staticmethod
    def _frame_to_bgr(frame: np.ndarray) -> np.ndarray:
        if len(frame.shape) == 3 and frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        return frame

    def start(self, device_name: str):
        if self.current_device == device_name and self.running:
            return

        self.running = True
        self.current_device = device_name
        self.status = {"connected": False, "message": "正在初始化...", "retry_count": 0}

        def worker():
            retry_count = 0
            device = None
            consecutive_failures = 0
            max_consecutive_failures = 3
            
            while self.running and self.current_device == device_name:
                try:
                    self.status["message"] = f"正在连接 (尝试 {retry_count + 1})..."
                    
                    if device is None:
                        from module.adb import ADB
                        device = ADB(device_name)
                    
                    self.status["message"] = "正在获取屏幕..."
                    
                    while self.running and self.current_device == device_name:
                        try:
                            frame = device.获取截图()
                            
                            if frame is not None:
                                with self.frame_lock:
                                    self.current_frame = frame.copy()
                                self.status["connected"] = True
                                self.status["message"] = "已连接"
                                self.status["retry_count"] = 0
                                consecutive_failures = 0
                            else:
                                consecutive_failures += 1
                                if consecutive_failures >= max_consecutive_failures:
                                    self.status["connected"] = False
                                    self.status["message"] = "截图连续为空"
                                else:
                                    self.status["message"] = f"截图为空 ({consecutive_failures}/{max_consecutive_failures})"
                            
                        except Exception as capture_err:
                            consecutive_failures += 1
                            print(f"[DEBUG] 截图失败: {capture_err}")
                            if consecutive_failures >= max_consecutive_failures:
                                self.status["connected"] = False
                                self.status["message"] = f"截图失败: {str(capture_err)[:20]}"
                                break
                            else:
                                self.status["message"] = f"获取中 ({consecutive_failures}/{max_consecutive_failures})"
                                time.sleep(0.5)
                                continue
                        
                        time.sleep(self.screenshot_interval)
                    
                except Exception as e:
                    print(f"[DEBUG] 流断开: {e}")
                    self.status["connected"] = False
                    self.status["message"] = f"连接断开: {str(e)[:20]}"
                    
                    retry_count += 1
                    self.status["retry_count"] = retry_count
                    consecutive_failures = 0
                    
                    if retry_count > 10:
                        self.status["message"] = "连接失败，已停止"
                        break
                    
                    backoff = min(5, 2 ** (retry_count - 1))
                    self.status["message"] = f"{backoff}秒后重连..."
                    time.sleep(backoff)
            
            self.running = False
            self.status["connected"] = False
            self.status["message"] = "流已停止"

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def get_frame_jpeg(self) -> bytes:
        with self.frame_lock:
            if self.current_frame is None:
                return self._generate_placeholder_image(self.status["message"])
            frame = self.current_frame.copy()

        frame_bgr = self._frame_to_bgr(frame)
        _, jpeg_buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return jpeg_buffer.tobytes()

    def get_status(self):
        status = self.status.copy()
        status["screenshot_interval"] = self.screenshot_interval
        return status

    def set_screenshot_interval(self, interval: float):
        self.screenshot_interval = max(0.01, min(interval, 0.15))

stream_manager = StreamManager()
