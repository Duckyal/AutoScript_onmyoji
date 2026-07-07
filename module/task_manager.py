# module/task_manager.py
import asyncio
from module.decorators import trigger_stop_signal

# 存储结构: { "device_serial": asyncio.Task }
active_tasks = {}
# 存储结构: { "device_serial": "task_name" }
active_names = {}

def register_task(device_id: str, task: asyncio.Task, task_name: str):
    """注册任务"""
    # 1. 安全检查：如果该设备已有任务，直接报错，不允许覆盖
    if device_id in active_tasks:
        raise ValueError(f"设备 {device_id} 正在运行任务 ({active_names[device_id]})，请先停止后再启动。")
    
    active_tasks[device_id] = task
    active_names[device_id] = task_name
    
    # 2. 定义回调：任务自然结束时自动清理 (作为兜底，防止 finally 没执行)
    def on_done(t):
        # 尝试获取异常（如果有的话），防止协程未获取异常就报错
        try:
            t.result()
        except:
            pass
        # 清理字典
        active_tasks.pop(device_id, None)
        active_names.pop(device_id, None)
    
    task.add_done_callback(on_done)

def cancel_task(device_id: str) -> bool:
    """停止任务"""
    if device_id in active_tasks:
        trigger_stop_signal(device_id)
        return True
    return False

def is_running(device_id: str):
    """查询状态"""
    if device_id in active_tasks:
        # 再次确认任务是否真的还在运行（防止自然结束未及时清理）
        if not active_tasks[device_id].done():
            return True, active_names[device_id]
        else:
            # 如果已结束，清理脏数据
            active_tasks.pop(device_id, None)
            active_names.pop(device_id, None)
    return False, None
