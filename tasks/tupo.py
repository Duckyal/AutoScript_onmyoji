import asyncio
from module.log import log
from module.adb import ADB

class TupoTask:
    def __init__(self, device:ADB, config:dict):
        self.device = device
        self.config = config
        asyncio.run(self.run())
    
    async def run(self):
        log(f"Running Yuhun Task with config: {self.config}")