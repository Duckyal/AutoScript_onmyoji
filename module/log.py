from module.log_manager import ws_manager

def log(message: str, level: str = "info", source: str = "server"):
    """
    专用的日志函数，会同时输出到本地终端 + 推送到前端 WebSocket
    - message: 日志内容
    - level: info / success / warning / error
    - source: server（后端业务日志）/ script（py脚本日志）
    """
    # 本地终端也打印一份（方便你本地调试）
    print(f"[{level.upper()}] {message}")
    
    # 推送到前端
    ws_manager.broadcast(message, level, source)
