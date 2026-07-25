import asyncio
from fastapi import WebSocket

class WebSocketLogManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        # 保存主线程的事件循环引用
        self.loop = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        # connect 是在主线程执行的，这里可以获取到真正的主循环
        if not self.loop:
            self.loop = asyncio.get_running_loop()

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    def broadcast(self, message: str, level: str = "info", source: str = None): # type: ignore
        data = {
            "message": message, 
            "level": level,
            "source": source  # 加上设备ID，前端可以用来区分
        }
        
        # 如果还没有客户端连进来（loop 为空），或者还没启动，没法发 WebSocket
        if not self.loop:
            print(f"[WS_UNAVAILABLE] {message}")
            return

        for connection in self.active_connections:
            try:
                # 使用 run_coroutine_threadsafe
                # 这行代码的作用是：在子线程里，给主线程的 loop 提交一个任务
                # 主线程会在空闲时执行 connection.send_json(data)
                asyncio.run_coroutine_threadsafe(
                    connection.send_json(data), 
                    self.loop
                )
            except RuntimeError:
                print(f"[{level.upper()}] {message}")
            except Exception:
                pass

    def log(self, message: object, level: str = "info", source: str = ''):
        """
        专用的日志函数，会同时输出到本地终端 + 推送到前端 WebSocket
        - message: 日志内容
        - level: info / success / warning / error
        - device_id: 设备ID (可选)
        """
        # 本地终端也打印一份（方便你本地调试）
        print(f"[{level.upper()}] [{source if source else ''}] {message}")
        
        # 推送到前端
        self.broadcast(str(message), level, source)


ws_manager = WebSocketLogManager()
