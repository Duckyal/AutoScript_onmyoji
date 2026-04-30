from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from module.log import log


app = FastAPI()
# 让 FastAPI 自动识别 static 目录下所有的 css/js 文件
app.mount("/static", StaticFiles(directory="static"), name="static")
# 指定存放 HTML 模板的文件夹
templates = Jinja2Templates(directory="templates")


# ui接口
@app.get("/")
async def get_ui(request: Request):
    # 将变量传入 HTML 模板
    return templates.TemplateResponse("index.html", {"request": request, "script_name": "阴阳师脚本"})


# 日志传输接口
from fastapi import WebSocket
from module.log_manager import ws_manager

@app.websocket("/logs")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # 只是保持连接，不需要接收前端发来的消息
            await websocket.receive_text()
    except Exception:
        ws_manager.disconnect(websocket)


# 启动任务接口
import shutil, os
from fastapi import UploadFile, Form
from tasks import custom

@app.post("/start")
async def run_task(request: Request):
    content_type = request.headers.get("content-type", "")
    # 执行自定义py任务
    if "multipart/form-data" in content_type:
        form = await request.form()
        # 提取文本参数
        process = form.get("process")
        # 用 UploadFile 类型接收文件
        py_file: UploadFile = form.get("file")
        if not py_file:
            return {"status": "error", "message": "未收到文件"}
        # 清除临时文件
        shutil.rmtree("tmp", ignore_errors=True)
        # 保存到本地
        upload_dir = "tmp"
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, py_file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(py_file.file, f)
        log(f'收到自定义脚本: {py_file.filename}，进程: {process}')
        custom.run(py_file.filename)
    # 执行预制任务
    else:
        data = await request.json()
        log(data)

        task_name = data.get("taskName")
        config    = data.get("config", {})
        process   = data.get("process", {})
        log(f"收到内置任务: {task_name}，进程: {process}", "info")
        log(f"配置: {config}", "info")

        # TODO: 根据任务类型分发
        # if data["task"] == "yuhun": ...
        # if data["task"] == "douji": ...

        return {"status": "success", "message": f"内置任务 [{task_name}] 已启动"}
    

# 

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)