from module.adb import ADB


class Task_yuling:
    def __init__(self, device:ADB, config:dict):
        self.op = device
        self.config = config
        self.state = "N"
    
    def run(self):
        boss = self.config["boss"]+"_1920x1080.png"
        layer = self.config["layer"]+"_1920x1080.png"
        self.op.图片预加载(f"tasks/御灵图片/{boss}", f"tasks/御灵图片/{layer}", "tasks/御灵图片/未锁定_1920x1080.png", "tasks/御灵图片/御灵_1920x1080.png")
        while True:
            self.op.sleep(1)
            result = self.op.找图()
            if result is None:
                break
            if "御灵_1920x1080.png" in result:
                self.op.点击(*result["御灵_1920x1080.png"])
                continue
            if boss in result:
                self.op.点击(*result[boss])
                self.op.sleep(1)
            if layer in result:
                self.op.点击(*result[layer])
                self.op.sleep(1)
            if "未锁定_1920x1080.png" in result:
                self.op.点击(*result["未锁定_1920x1080.png"])
                self.op.sleep(1)
        
        count = 0
        end = (int(self.op.width*3/5), int(self.op.height*9/10), int(self.op.height*1/10))
        self.op.图片预加载("tasks/御灵图片/奖励_1920x1080.png", "tasks/御灵图片/挑战_1920x1080.png")
        while True:
            self.op.sleep(0.5)
            result = self.op.找图()
            if result is None:
                self.op.sleep(5)
                continue
            elif "奖励_1920x1080.png" in result:
                self.op.点击(*end)
                self.op.sleep(1)
                if self.state == "N":
                    count += 1
                    self.state = "Y"
            elif "挑战_1920x1080.png" in result:
                self.op.点击(*result["挑战_1920x1080.png"])
                self.op.sleep(1)
                self.state = "N"
            if count >= self.config["count"] and self.config["count"] != 0:
                self.op.log("已完成{count}次{boss}{layer}的挑战".format(count=count, boss=self.config["boss"], layer=self.config["layer"]))
                break
