from module.adb import ADB

class Task_tupo:
    def __init__(self, device:ADB, config:dict):
        self.op = device
        self.config = config

    def run(self):
        if self.config.get("type") == "kekkai":
            self.run_kekkai()
        else:
            self.run_ryou()
    
    def run_kekkai(self):
        self.op.log(f"准备运行个人突破")

    def run_ryou(self):
        self.op.log(f"开始运行寮突破")