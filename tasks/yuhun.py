from module.adb import ADB

class Task_yuhun:
    def __init__(self, device:ADB, config:dict):
        self.op = device
        self.config = config
        self.结束点击 = (int(self.op.width*4/5), int(self.op.height*4/5), int(self.op.height*1/10))
        self.state = "N"
    
    def run(self):
        type = self.config.get("type")
    
        if type == "八岐大蛇":
            self.八岐大蛇()
        elif type == "业原火":
            self.业原火()

    def 八岐大蛇(self):
        team = self.config.get("team")
        count = int(self.config.get("count"))
        num = 0
        if team == "leader":
            self.op.图片预加载("tasks/御魂图片/八岐大蛇/胜利_960x540.png", "tasks/御魂图片/八岐大蛇/结束_960x540.png", "tasks/御魂图片/八岐大蛇/挑战_960x540.png",
                          "tasks/御魂图片/八岐大蛇/拒绝悬赏_1920x1080.png")
            while True:
                self.op.sleep(1)
                result = self.op.找图()
                if not result:
                    self.op.sleep(2)
                elif "拒绝悬赏_1920x1080.png" in result:
                    self.op.点击(*result["拒绝悬赏_1920x1080.png"])
                elif "挑战_960x540.png" in result:
                    self.op.点击(*result["挑战_960x540.png"])
                elif "胜利_960x540.png" in result:
                    self.op.点击(*self.结束点击)
                    self.state = "N"
                elif "结束_960x540.png" in result:
                    self.op.点击(*self.结束点击)
                    if self.state == "N":
                        self.state = "Y"
                        num += 1
                    self.op.log(f"已挑战{num}次")
                    if num >= count and count != 0:
                        self.op.log("完成御魂任务")
                        break
        else:
            self.op.图片预加载("tasks/御魂图片/八岐大蛇/胜利_960x540.png", "tasks/御魂图片/八岐大蛇/结束_960x540.png", "tasks/御魂图片/八岐大蛇/拒绝悬赏_1920x1080.png")
            while True:
                self.op.sleep(1)
                result = self.op.找图()
                if not result:
                    self.op.sleep(2)
                elif "拒绝悬赏_1920x1080.png" in result:
                    self.op.点击(*result["拒绝悬赏_1920x1080.png"])
                elif "胜利_960x540.png" in result:
                    self.op.点击(*self.结束点击)
                    self.state = "N"
                elif "结束_960x540.png" in result:
                    self.op.点击(*self.结束点击)
                    if self.state == "N":
                        self.state = "Y"
                        num += 1
                    self.op.log(f"已挑战{num}次")
                    if num >= count and count != 0:
                        self.op.log("完成御魂任务")
                        break

    def 业原火(self):
        count = 0
        self.op.图片预加载("tasks/御魂图片/业原火/未锁定_1920x1080.png", "tasks/御魂图片/业原火/挑战_1920x1080.png", "tasks/御魂图片/业原火/胜利_1920x1080.png", "tasks/御魂图片/业原火/失败_1920x1080.png")
        while True:
            self.op.sleep(0.5)
            result = self.op.找图()
            if not result:
                self.op.sleep(3)
                continue
            if "未锁定_1920x1080.png" in result:
                self.op.点击(*result["未锁定_1920x1080.png"])
                self.op.sleep(0.5)
            if "挑战_1920x1080.png" in result:
                self.op.点击(*result["挑战_1920x1080.png"])
                self.state = "N"
                self.op.sleep(0.5)
            elif "胜利_1920x1080.png" in result:
                self.op.点击(*self.结束点击)
                if self.state == "N":
                    count += 1
                    self.state = "Y"
                self.op.log(f"已完成{count}次")
                self.op.sleep(0.5)
            elif "失败_1920x1080.png" in result:
                from module.decorators import TaskStoppedException
                raise TaskStoppedException("任务失败:可能阵容式神未搭配御魂")

            if self.config.get("count") != 0:
                if count >= int(self.config.get("count", 100)):
                    self.op.log("业原火任务完成")
                    break