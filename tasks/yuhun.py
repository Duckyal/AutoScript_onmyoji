import asyncio
from module.adb import ADB

class YuhunTask:
    def __init__(self, device:ADB, config:dict):
        self.device = device
        self.config = config
        asyncio.run(self.run())
    
    async def run(self):
        self.device.log(f"Running Yuhun Task with config: {self.config}")
        self.device.找字()
