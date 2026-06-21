import asyncio
from fastapi import WebSocket

class WebSocketLogManager:
    def __init__(self, source: str = "server"):
        '''source: server（后端业务日志）/ 进程名（py脚本日志）'''
        self.active_connections: list[WebSocket] = []
        self.source = source

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    def broadcast(self, message: str, level: str = "info", source: str = "server"):
        data = {"message": message, "level": level, "source": source}
        for connection in self.active_connections:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(connection.send_json(data))
            except RuntimeError:
                # 没有运行中的事件循环时，降级为同步打印
                print(f"[{level.upper()}] {message}")
            except Exception:
                pass

    def log(self, message: str, level: str = "info"):
        """
        专用的日志函数，会同时输出到本地终端 + 推送到前端 WebSocket
        - message: 日志内容
        - level: info / success / warning / error
        - source: server（后端业务日志）/ 进程名（py脚本日志）
        """
        # 本地终端也打印一份（方便你本地调试）
        print(f"[{level.upper()}] {message}")
        
        # 推送到前端
        self.broadcast(message, level, self.source)