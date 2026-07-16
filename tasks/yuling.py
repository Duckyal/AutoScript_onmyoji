from module.adb import ADB


class Task_yuling:
    def __init__(self, device:ADB, config:dict):
        self.op = device
        self.config = config
    
    def run(self):
        boss = self.config["boss"]+".png"
        layer = self.config["layer"]+".png"
        self.op.图片预加载(f"tasks/御灵图片/{boss}", f"tasks/御灵图片/{layer}", "tasks/御灵图片/未锁定.png", "tasks/御灵图片/御灵.png")
        while True:
            self.op.sleep(1)
            result = self.op.找图()
            if result is None:
                break
            if "御灵.png" in result:
                self.op.点击(*result["御灵.png"])
                continue
            if boss in result:
                self.op.点击(*result[boss])
                self.op.sleep(1)
            if layer in result:
                self.op.点击(*result[layer])
                self.op.sleep(1)
            if "未锁定.png" in result:
                self.op.点击(*result["未锁定.png"])
                self.op.sleep(1)
        
        count = 0
        end = (int(self.op.height*3/5), int(self.op.width*9/10), int(self.op.width*1/10))
        self.op.图片预加载("tasks/御灵图片/奖励.png", "tasks/御灵图片/挑战.png")
        while True:
            result = self.op.找图()
            if result is None:
                self.op.sleep(5)
                continue
            elif "奖励.png" in result:
                self.op.点击(*end)
                self.op.sleep(1)
                count += 1
            elif "挑战.png" in result:
                self.op.点击(*result["挑战.png"])
                self.op.sleep(1)
            if count >= self.config["count"] and self.config["count"] != 0:
                self.op.log("已完成{count}次{boss}{layer}的挑战".format(count=count, boss=self.config["boss"], layer=self.config["layer"]))
                break
