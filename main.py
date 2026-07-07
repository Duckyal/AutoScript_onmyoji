# main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

# 导入路由
from api import ui, routes
# 导入日志管理（用于 WebSocket）
from module.logmanager import ws_manager

app = FastAPI(title="阴阳师自动化")

# 静态文件
app.mount("/static", StaticFiles(directory="static"), name="static")

# 注册路由
app.include_router(ui.router)
app.include_router(routes.router)

# 注册 WebSocket
from fastapi import WebSocket
@app.websocket("/logs")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True: await websocket.receive_text()
    except: ws_manager.disconnect(websocket)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
