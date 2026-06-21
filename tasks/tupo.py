import asyncio
from module.adb import ADB
import time
import re
import random

class TupoTask:
    def __init__(self, device:ADB, config:dict):
        self.op = device
        self.config = config
        if config.type == "kekkai":
            asyncio.run(self.run_kekkai())
        else:
            asyncio.run(self.run_ryou())
    
    async def run_kekkai(self):
        self.op.log(f"准备运行个人突破")

    async def run_ryou(self):
        self.op.log(f"开始运行寮突破")