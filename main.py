# main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

# 导入路由
from api import ui, routes
# 导入日志管理（用于 WebSocket）
from module.logmanager import ws_manager

app = FastAPI(title="阴阳师自动化")

# 清除 tasks/tmp 目录下的所有文件
import os
import shutil

if os.path.exists("tasks/tmp"):
    shutil.rmtree("tasks/tmp")
os.makedirs("tasks/tmp")

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 注册路由
app.include_router(ui.router)
app.include_router(routes.router)

# 注册 WebSocket
from fastapi import WebSocket
import json

@app.websocket("/logs")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # 处理前端发来的控制消息
            try:
                msg = json.loads(data)
                if msg.get('type') == 'clear_history':
                    ws_manager.clear_history()
            except json.JSONDecodeError:
                pass
    except:
        ws_manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
