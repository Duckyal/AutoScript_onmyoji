from module.adb import ADB


class Task_k28:
    def __init__(self, device:ADB, config:dict):
        self.op = device
        self.config = config

            
    def run(self):
        end = (int(self.op.height*3/5), int(self.op.width*9/10), int(self.op.width*1/10))
        self.op.图片预加载("tasks/k28图片/k28_1920x1080.png", "tasks/k28图片/退出_1920x1080.png", "tasks/k28图片/确认退出_1920x1080.png")
        while True:
            self.op.sleep(1)
            result = self.op.找图()
            if "k28_1920x1080.png" in result:
                break
            elif "确认退出_1920x1080.png" in result:
                self.op.点击(*result["确认退出_1920x1080.png"])
            elif "退出_1920x1080.png" in result:
                self.op.点击(*result["退出_1920x1080.png"])

        imgs = ('tasks/k28图片/k28_1920x1080.png', "tasks/k28图片/探索_1920x1080.png", "tasks/k28图片/自动轮换_1920x1080.png",
                "tasks/k28图片/轮换设置_1920x1080.png", "tasks/k28图片/小怪_1920x1080.png", "tasks/k28图片/大怪_1920x1080.png", 
                "tasks/k28图片/奖励_1920x1080.png", "tasks/k28图片/失败_1920x1080.png", "tasks/k28图片/通关奖励_1920x1080.png", 
                "tasks/k28图片/结界突破_1920x1080.png", "tasks/k28图片/掉落宝箱_1920x1080.png", "tasks/k28图片/退出_1920x1080.png")
        self.op.图片预加载(*imgs)
        state = 0
        while True:
            self.op.check_stop()
            result = self.op.找图(priority_corner="br")
            if "k28_1920x1080.png" in result and "结界突破_1920x1080.png" in result:
                if self.config["count"] != 0:   # 有突破券上限
                    result_txt = self.op.找字(x1=0.5, x2=0.7, y2=0.2, target_txt=r".*\d+/30.*", use_regex=True)
                    if result_txt:
                        import re
                        match = re.search(r"(\d+)/30", result_txt[0])
                        if match:
                            a = match.group(1)
                            print(a, result_txt)
                            if int(a) >= int(self.config["count"]):
                                self.op.log("突破券已达{count}上限，运行突破任务".format(count=a))
                                self.op.点击(*result["结界突破_1920x1080.png"])
                                from tasks.tupo import Task_tupo
                                Task_tupo(self.op, self.config).refresh_kekkai()
                                self.op.图片预加载(*imgs)
                                state = 0
                            else:
                                self.op.点击(*result["k28_1920x1080.png"])
                        else:
                            self.op.点击(*result["k28_1920x1080.png"])
            elif "探索_1920x1080.png" in result:
                self.op.点击(*result["探索_1920x1080.png"])
            elif "轮换设置_1920x1080.png" in result and state == 0:
                if "自动轮换_1920x1080.png" in result:
                    self.op.点击(*result["自动轮换_1920x1080.png"])
                    self.op.sleep(1)
                self.op.点击(*result["轮换设置_1920x1080.png"])
                self.lunhuan()
                self.op.图片预加载(*imgs)
                state = 1
            elif "掉落宝箱_1920x1080.png" in result:
                self.op.点击(*result["掉落宝箱_1920x1080.png"])
            elif "奖励_1920x1080.png" in result:
                self.op.点击(*end)
            elif "失败_1920x1080.png" in result:
                from module.decorators import RaiseError
                raise RaiseError("k28任务异常退出：请检查式神御魂")
            elif "通关奖励_1920x1080.png" in result:
                self.op.点击(*result["通关奖励_1920x1080.png"])
            elif "大怪_1920x1080.png" in result:
                self.op.点击(*result["大怪_1920x1080.png"])
            elif "小怪_1920x1080.png" in result:
                self.op.点击(*result["小怪_1920x1080.png"])
            elif ("大怪_1920x1080.png" not in result or "小怪_1920x1080.png" not in result) and "退出_1920x1080.png" in result and state == 1:
                self.op.点击(int(self.op.height*7/12), int(self.op.width*8/10), int(self.op.width*1/15))
                self.op.sleep(3)
            else:
                self.op.sleep(5)
            
    def lunhuan(self):
        self.op.图片预加载("tasks/k28图片/全部_1920x1080.png", f"tasks/k28图片/{self.config['lunhuan']}_1920x1080.png", "tasks/k28图片/二星_1920x1080.png", "tasks/k28图片/候补式神_1920x1080.png")
        state = 0
        while True:
            self.op.check_stop()
            result = self.op.找图(priority_corner="tr")
            if state == 0 and "全部_1920x1080.png" in result:
                self.op.点击(*result["全部_1920x1080.png"])
                state += 1
                self.op.sleep(1)
            if f"{self.config['lunhuan']}_1920x1080.png" in result and state == 1:
                self.op.点击(*result[f"{self.config['lunhuan']}_1920x1080.png"])
                state += 1
                self.op.sleep(1)
            elif "二星_1920x1080.png" in result and (state == 2 or state == 3):
                self.op.点击(*result["二星_1920x1080.png"])
                state += 1
            elif "候补式神_1920x1080.png" in result and (state == 2 or state == 3):
                self.op.点击(*result["候补式神_1920x1080.png"])
                state += 1
            if state == 4:
                break

        self.op.图片预加载("tasks/k28图片/滑块_1920x1080.png", "tasks/k28图片/二星_1920x1080.png", "tasks/k28图片/确定设置_1920x1080.png")
        while True:
            self.op.check_stop()
            result = self.op.找图(y1=0.55)
            if "二星_1920x1080.png" in result and "确定设置_1920x1080.png" in result:
                self.op.长按(result["二星_1920x1080.png"][0], result["二星_1920x1080.png"][1], 3)
                self.op.sleep(1)
                self.op.点击(*result["确定设置_1920x1080.png"])
                break
            elif "二星_1920x1080.png" not in result and "滑块_1920x1080.png" in result:
                x , y, r, *els = result["滑块_1920x1080.png"]
                self.op.滑动(x, y, x+r, y, 5)      
        self.op.sleep(1)
