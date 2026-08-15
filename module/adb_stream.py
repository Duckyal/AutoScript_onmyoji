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
        # 多设备结构：以 device_id 为键
        self.frames: dict[str, np.ndarray] = {}
        self.frame_locks: dict[str, Lock] = {}
        self.runnings: dict[str, bool] = {}
        self.statuses: dict[str, dict] = {}
        self.screenshot_interval = 0.05  # 全局共享

    def _ensure_device(self, device_name: str):
        """确保设备条目已初始化"""
        if device_name not in self.frames:
            self.frames[device_name] = None
            self.frame_locks[device_name] = Lock()
            self.runnings[device_name] = False
            self.statuses[device_name] = {
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
        self._ensure_device(device_name)
        if self.runnings[device_name]:
            return

        self.runnings[device_name] = True
        self.statuses[device_name] = {"connected": False, "message": "正在初始化...", "retry_count": 0}

        def worker():
            retry_count = 0
            device = None
            consecutive_failures = 0
            max_consecutive_failures = 3

            while self.runnings.get(device_name, False):
                try:
                    self.statuses[device_name]["message"] = f"正在连接 (尝试 {retry_count + 1})..."

                    if device is None:
                        from module.adb import ADB
                        device = ADB(device_name)

                    self.statuses[device_name]["message"] = "正在获取屏幕..."

                    while self.runnings.get(device_name, False):
                        try:
                            frame = device.获取截图()

                            if frame is not None:
                                with self.frame_locks[device_name]:
                                    self.frames[device_name] = frame.copy()
                                self.statuses[device_name]["connected"] = True
                                self.statuses[device_name]["message"] = "已连接"
                                self.statuses[device_name]["retry_count"] = 0
                                consecutive_failures = 0
                            else:
                                consecutive_failures += 1
                                if consecutive_failures >= max_consecutive_failures:
                                    self.statuses[device_name]["connected"] = False
                                    self.statuses[device_name]["message"] = "截图连续为空"
                                else:
                                    self.statuses[device_name]["message"] = f"截图为空 ({consecutive_failures}/{max_consecutive_failures})"

                        except Exception as capture_err:
                            consecutive_failures += 1
                            print(f"[DEBUG] [{device_name}] 截图失败: {capture_err}")
                            if consecutive_failures >= max_consecutive_failures:
                                self.statuses[device_name]["connected"] = False
                                self.statuses[device_name]["message"] = f"截图失败: {str(capture_err)[:20]}"
                                break
                            else:
                                self.statuses[device_name]["message"] = f"获取中 ({consecutive_failures}/{max_consecutive_failures})"
                                time.sleep(0.5)
                                continue

                        time.sleep(self.screenshot_interval)

                except Exception as e:
                    print(f"[DEBUG] [{device_name}] 流断开: {e}")
                    self.statuses[device_name]["connected"] = False
                    self.statuses[device_name]["message"] = f"连接断开: {str(e)[:20]}"

                    retry_count += 1
                    self.statuses[device_name]["retry_count"] = retry_count
                    consecutive_failures = 0

                    if retry_count > 10:
                        self.statuses[device_name]["message"] = "连接失败，已停止"
                        break

                    backoff = min(5, 2 ** (retry_count - 1))
                    self.statuses[device_name]["message"] = f"{backoff}秒后重连..."
                    time.sleep(backoff)

            self.runnings[device_name] = False
            self.statuses[device_name]["connected"] = False
            self.statuses[device_name]["message"] = "流已停止"

        t = threading.Thread(target=worker, daemon=True)
        t.start()

    def get_frame_jpeg(self, device_name: str) -> bytes:
        self._ensure_device(device_name)
        with self.frame_locks[device_name]:
            if self.frames[device_name] is None:
                return self._generate_placeholder_image(self.statuses[device_name]["message"])
            frame = self.frames[device_name].copy()

        frame_bgr = self._frame_to_bgr(frame)
        _, jpeg_buffer = cv2.imencode('.jpg', frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return jpeg_buffer.tobytes()

    def get_status(self, device_name: str = None):
        # 兼容无参数调用：返回第一个设备的状态或全局默认
        if device_name is None:
            if self.statuses:
                device_name = next(iter(self.statuses))
            else:
                return {"connected": False, "message": "未初始化", "retry_count": 0, "screenshot_interval": self.screenshot_interval}

        self._ensure_device(device_name)
        status = self.statuses[device_name].copy()
        status["screenshot_interval"] = self.screenshot_interval
        return status

    def set_screenshot_interval(self, interval: float):
        self.screenshot_interval = max(0.01, min(interval, 0.15))

    def stop(self, device_name: str):
        """停止指定设备的流"""
        self._ensure_device(device_name)
        self.runnings[device_name] = False

stream_manager = StreamManager()
