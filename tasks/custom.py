import asyncio
from module.log import log

async def run_script(file_name: str):
    """执行用户的 .py 脚本，把脚本的 print 输出推送到前端"""
    log(f"===== 开始执行 {file_name} =====", "info")

    process = await asyncio.create_subprocess_exec(
        "python", "-m", f"tmp.{file_name}",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # 实时逐行读取输出，每行都推送到前端
    while True:
        line = await process.stdout.readline()
        if not line:
            break
        text = line.decode("utf-8", errors="ignore").strip()
        if text:
            log(text, "info", source="script")  # 标记来源为 script

    # 读取错误输出
    err = await process.stderr.read()
    if err:
        error_text = err.decode("utf-8", errors="ignore").strip()
        if error_text:
            log(error_text, "error", source="script")

    await process.wait()
    log(f"===== 脚本执行完毕 =====", "info")

def run(file_name):
    """给外部调用的同步入口"""
    asyncio.create_task(run_script(file_name))