from module.adb import ADB

class Task_yuhun:
    def __init__(self, device:ADB, config:dict):
        self.op = device
        self.config = config
    
    def run(self):
        self.op.log(f"Running Yuhun Task with config: {self.config}")
        self.op.找字()
