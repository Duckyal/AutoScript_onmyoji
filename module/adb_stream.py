# adb辅助方法
import subprocess
from typing import List, Tuple

def check_adb(device: str) -> Tuple[bool, str]:
    """校验设备是否在线，返回 (ok, message)"""
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
    """获取在线设备列表"""
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


# scrcpy视频流封装（使用外置scrcpy命令行工具）
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
        self.scrcpy_process = None
        self.current_device: Optional[str] = None
        
        self.status = {
            "connected": False,
            "message": "未初始化",
            "retry_count": 0
        }

    @staticmethod
    def _generate_placeholder_image(text="连接中..."):
        """生成带有提示文字的灰色占位图"""
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

    def _stop_process(self):
        """停止scrcpy进程"""
        if self.scrcpy_process is not None:
            try:
                self.scrcpy_process.terminate()
                self.scrcpy_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.scrcpy_process.kill()
            except Exception:
                pass
            self.scrcpy_process = None

    def start(self, device_name: str):
        if self.current_device == device_name and self.scrcpy_process is not None:
            return

        self._stop_process()

        self.current_device = device_name
        self.status = {"connected": False, "message": "正在初始化...", "retry_count": 0}

        def worker():
            retry_count = 0
            while self.current_device == device_name:
                try:
                    self.status["message"] = f"正在连接 (尝试 {retry_count + 1})..."
                    
                    cmd = [
                        'scrcpy',
                        '--tcpip',
                        '-s', device_name,
                        '--max-size', '0',
                        '--bit-rate', '8M',
                        '--max-fps', '60',
                        '--no-audio',
                        '--no-control',
                        '--stay-awake',
                        '--raw',
                    ]
                    
                    self.scrcpy_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=0,
                    )
                    
                    pipe = self.scrcpy_process.stdout
                    frame_buffer = bytearray()
                    
                    while self.current_device == device_name:
                        data = pipe.read(4096)
                        if not data:
                            break
                        frame_buffer.extend(data)
                        
                        while len(frame_buffer) > 4:
                            if frame_buffer[0:4] == b'\x00\x00\x00\x01':
                                frame_size_end = frame_buffer.find(b'\x00\x00\x00\x01', 4)
                                if frame_size_end == -1:
                                    break
                                
                                frame_data = bytes(frame_buffer[:frame_size_end])
                                frame_buffer = frame_buffer[frame_size_end:]
                                
                                try:
                                    frame = cv2.imdecode(np.frombuffer(frame_data, np.uint8), cv2.IMREAD_COLOR)
                                    if frame is not None:
                                        with self.frame_lock:
                                            self.current_frame = frame.copy()
                                        self.status["connected"] = True
                                        self.status["message"] = "已连接"
                                        self.status["retry_count"] = 0
                                except Exception:
                                    pass
                            else:
                                frame_buffer = frame_buffer[1:]
                    
                except Exception as e:
                    print(f"Scrcpy 流断开: {e}")
                    self.status["connected"] = False
                    self.status["message"] = f"连接断开: {str(e)[:20]}"
                    
                    retry_count += 1
                    self.status["retry_count"] = retry_count
                    
                    if retry_count > 10:
                        self.status["message"] = "连接失败，已停止"
                        break
                    
                    self.status["message"] = f"5秒后重连..."
                    time.sleep(5)
                
                finally:
                    self._stop_process()
            
            self.status["connected"] = False
            self.status["message"] = "流已停止"

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def get_frame_jpeg(self) -> bytes:
        """获取当前帧，如果无画面则返回带文字的占位图"""
        with self.frame_lock:
            if self.current_frame is None:
                return self._generate_placeholder_image(self.status["message"])
            frame = self.current_frame.copy()

        frame_bgr = self._frame_to_bgr(frame)
        _, jpeg_buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return jpeg_buffer.tobytes()

    def get_status(self):
        """获取当前流状态"""
        return self.status

stream_manager = StreamManager()
