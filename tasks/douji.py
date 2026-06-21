import asyncio
from module.adb import ADB

class DoujiTask:
    def __init__(self, device:ADB, config:dict):
        self.device = device
        self.config = config
        asyncio.run(self.run())

    async def run(self):
        log(f"Running Yuhun Task with config: {self.config}")