import asyncio
from fastapi import WebSocket

class WebSocketLogManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

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

ws_manager = WebSocketLogManager()
