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


# =============================================================================================
#                                       scrcpy 视频流
# =============================================================================================
import os
import struct
import socket
import queue as _queue
import hashlib


class ScrcpyStream:
    """单个设备的 scrcpy H.264 视频流"""

    def __init__(self, device_name: str, jar_path: str):
        self.device_name = device_name
        self.jar_path = jar_path
        self.running = False
        self.server_proc = None
        self.video_socket: socket.socket | None = None
        self.control_socket: socket.socket | None = None  # v1.20 协议需要二次连接
        self.forward_port = 0
        self.device_info = {}  # name, width, height
        self._clients: list[_queue.Queue] = []
        self._lock = threading.Lock()
        self._reader_thread = None

    def _get_forward_port(self) -> int:
        """根据设备名生成一个稳定的端口号"""
        h = hashlib.md5(self.device_name.encode()).hexdigest()
        return 20000 + int(h[:4], 16) % 30000

    def start(self):
        if self.running:
            return True
        try:
            port = self._get_forward_port()
            self.forward_port = port

            # 0. 清理设备上残留的 scrcpy server 进程
            #    否则旧 server 仍占用 localabstract:scrcpy, 新 server 绑定失败立即退出,
            #    导致 dummy byte 返回 EOF (b'').
            try:
                subprocess.run(
                    ['adb', '-s', self.device_name, 'shell', 'pkill', '-f', 'scrcpy-server.jar'],
                    capture_output=True, timeout=3
                )
            except Exception:
                pass

            # 1. push jar
            subprocess.run(
                ['adb', '-s', self.device_name, 'push', self.jar_path, '/data/local/tmp/scrcpy-server.jar'],
                capture_output=True, timeout=15
            )

            # 2. adb forward
            subprocess.run(
                ['adb', '-s', self.device_name, 'forward', f'tcp:{port}', 'localabstract:scrcpy'],
                capture_output=True, timeout=5
            )

            # 3. start server (v1.20 protocol, control=false)
            #    注意: stdout/stderr 必须用 DEVNULL, 不能用 PIPE!
            #    scrcpy server 会输出大量日志, pipe buffer (64KB) 满后
            #    server 会阻塞, 导致 socket 通信卡死, dummy byte 返回 EOF.
            cmd = [
                'adb', '-s', self.device_name, 'shell',
                'CLASSPATH=/data/local/tmp/scrcpy-server.jar',
                'app_process', '/', 'com.genymobile.scrcpy.Server',
                '1.20',           # version
                'info',           # log level
                '0',              # max width (0=unlimited)
                '8000000',        # bitrate
                '0',              # max fps (0=unlimited)
                '-1',             # lock screen orientation (unlocked)
                'true',           # tunnel forward
                '-',              # crop
                'false',          # send frame rate
                'false',          # control enabled (DISABLED)
                '0',              # display id
                'false',          # show touches
                'true',           # stay awake
                '-',              # codec options
                '-',              # encoder name
                'false',          # power off screen after close
            ]
            self.server_proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

            # 给 server 充分启动时间 (redroid 上 ~500ms, 真机更快)
            # 如果不 sleep, retry 循环可能连接太快, server 还在初始化,
            # 导致 dummy byte 返回 EOF.
            time.sleep(0.8)

            # 4. connect to video socket (retry until server is ready)
            #    v1.20 协议: tunnel_forward 模式下, server 监听 localabstract:scrcpy,
            #    客户端必须连接两次 (video + control), 即使 control_enabled=false.
            #    只连一次会导致 server 卡在等待第二个连接, 最终触发 CleanUp 退出.
            for _ in range(30):
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2)
                    s.connect(('127.0.0.1', port))
                    self.video_socket = s
                    break
                except (ConnectionRefusedError, socket.timeout):
                    time.sleep(0.1)
            else:
                raise ConnectionError("无法连接 scrcpy server (video socket)")

            # 4.1 连接 control socket (v1.20 协议要求, 即使 control=false)
            time.sleep(0.15)  # 给 server 时间接受第一个连接
            try:
                cs = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                cs.settimeout(2)
                cs.connect(('127.0.0.1', port))
                self.control_socket = cs
            except (ConnectionRefusedError, socket.timeout):
                # 某些设备/版本可能不需要, 忽略错误
                pass

            # 5. read protocol header
            # dummy byte
            dummy = self.video_socket.recv(1)
            if not dummy or dummy != b'\x00':
                raise ConnectionError(f"dummy byte 异常: {dummy!r}")

            # device name (64 bytes)
            name_bytes = self._recv_exact(64)
            self.device_info['name'] = name_bytes.decode('utf-8').rstrip('\x00')

            # resolution (4 bytes: uint16 width, uint16 height, big-endian)
            res_bytes = self._recv_exact(4)
            w, h = struct.unpack('>HH', res_bytes)
            self.device_info['width'] = w
            self.device_info['height'] = h

            self.video_socket.setblocking(False)
            self.running = True

            # 6. start reader thread
            self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._reader_thread.start()
            return True

        except Exception as e:
            self.running = False
            self._cleanup()
            raise

    def _recv_exact(self, n: int) -> bytes:
        """从 socket 精确读取 n 个字节"""
        buf = b''
        while len(buf) < n:
            if not self.video_socket:
                raise ConnectionError("socket 已关闭")
            chunk = self.video_socket.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("socket 已断开")
            buf += chunk
        return buf

    def _read_loop(self):
        """后台线程：读取 H.264 数据并广播给所有 WebSocket 客户端"""
        while self.running and self.video_socket:
            try:
                data = self.video_socket.recv(0x10000)  # 64KB chunks
                if not data:
                    break
                with self._lock:
                    dead = []
                    for q in self._clients:
                        try:
                            q.put_nowait(data)
                        except _queue.Full:
                            dead.append(q)  # 客户端太慢，丢弃
                    for q in dead:
                        self._clients.remove(q)
            except BlockingIOError:
                time.sleep(0.005)
            except OSError:
                break

        self.running = False
        self._cleanup()

    def add_client(self) -> _queue.Queue:
        """添加一个 WebSocket 客户端，返回一个数据队列"""
        q: _queue.Queue = _queue.Queue(maxsize=300)
        with self._lock:
            self._clients.append(q)
        return q

    def remove_client(self, q: _queue.Queue):
        """移除一个客户端，如果没有客户端了就停止流"""
        with self._lock:
            if q in self._clients:
                self._clients.remove(q)
            if not self._clients:
                self.stop()

    def stop(self):
        self.running = False
        self._cleanup()

    def _cleanup(self):
        if self.video_socket:
            try:
                self.video_socket.close()
            except Exception:
                pass
            self.video_socket = None
        if self.control_socket:
            try:
                self.control_socket.close()
            except Exception:
                pass
            self.control_socket = None
        if self.server_proc:
            try:
                self.server_proc.terminate()
                self.server_proc.wait(timeout=3)
            except Exception:
                try:
                    self.server_proc.kill()
                except Exception:
                    pass
            self.server_proc = None
        try:
            subprocess.run(
                ['adb', '-s', self.device_name, 'forward', '--remove', f'tcp:{self.forward_port}'],
                capture_output=True, timeout=3
            )
        except Exception:
            pass
        # 同时清理设备上残留的 scrcpy server 进程
        try:
            subprocess.run(
                ['adb', '-s', self.device_name, 'shell', 'pkill', '-f', 'scrcpy-server.jar'],
                capture_output=True, timeout=3
            )
        except Exception:
            pass

    def get_status(self):
        return {
            "running": self.running,
            "device_info": self.device_info,
            "client_count": len(self._clients),
        }


class ScrcpyStreamManager:
    """管理多设备的 scrcpy 视频流"""

    def __init__(self):
        self.jar_path = os.path.join(os.path.dirname(__file__), 'scrcpy-server.jar')
        self.streams: dict[str, ScrcpyStream] = {}

    def _ensure(self, device_name: str) -> ScrcpyStream:
        if device_name not in self.streams:
            self.streams[device_name] = ScrcpyStream(device_name, self.jar_path)
        return self.streams[device_name]

    def start(self, device_name: str):
        s = self._ensure(device_name)
        if not s.running:
            s.start()
        return s

    def stop(self, device_name: str):
        if device_name in self.streams:
            self.streams[device_name].stop()

    def get_status(self, device_name: str):
        if device_name not in self.streams:
            return {"running": False, "device_info": {}, "client_count": 0}
        return self.streams[device_name].get_status()


scrcpy_manager = ScrcpyStreamManager()
