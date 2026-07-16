from module.adb import ADB


class Task_k28:
    def __init__(self, device:ADB, config:dict):
        self.op = device
        self.config = config

            
    def run(self):
        end = (int(self.op.height*3/5), int(self.op.width*9/10), int(self.op.width*1/10))
        self.op.图片预加载("tasks/k28图片/k28.png", "tasks/k28图片/退出.png", "tasks/k28图片/确认退出.png")
        while True:
            self.op.sleep(1)
            result = self.op.找图()
            if "k28.png" in result:
                break
            elif "确认退出.png" in result:
                self.op.点击(*result["确认退出.png"])
            elif "退出.png" in result:
                self.op.点击(*result["退出.png"])

        imgs = ('tasks/k28图片/k28.png', "tasks/k28图片/探索.png", "tasks/k28图片/自动轮换.png",
                "tasks/k28图片/轮换设置.png", "tasks/k28图片/小怪.png", "tasks/k28图片/大怪.png", 
                "tasks/k28图片/奖励.png", "tasks/k28图片/失败.png", "tasks/k28图片/通关奖励.png", 
                "tasks/k28图片/结界突破.png", "tasks/k28图片/掉落宝箱.png", "tasks/k28图片/退出.png")
        self.op.图片预加载(*imgs)
        state = 0
        while True:
            self.op.sleep(1)
            result = self.op.找图(priority_corner="br")
            if "k28.png" in result and "结界突破.png" in result:
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
                                self.op.点击(*result["结界突破.png"])
                                from tasks.tupo import Task_tupo
                                Task_tupo(self.op, self.config).refresh_kekkai()
                                self.op.图片预加载(*imgs)
                                state = 0
                            else:
                                self.op.点击(*result["k28.png"])
                        else:
                            self.op.点击(*result["k28.png"])
            elif "探索.png" in result:
                self.op.点击(*result["探索.png"])
            elif "轮换设置.png" in result and state == 0:
                if "自动轮换.png" in result:
                    self.op.点击(*result["自动轮换.png"])
                    self.op.sleep(1)
                self.op.点击(*result["轮换设置.png"])
                self.lunhuan()
                self.op.图片预加载(*imgs)
                state = 1
            elif "掉落宝箱.png" in result:
                self.op.点击(*result["掉落宝箱.png"])
            elif "奖励.png" in result:
                self.op.点击(*end)
            elif "失败.png" in result:
                from module.decorators import RaiseError
                raise RaiseError("k28任务异常退出：请检查式神御魂")
            elif "通关奖励.png" in result:
                self.op.点击(*result["通关奖励.png"])
            elif "大怪.png" in result:
                self.op.点击(*result["大怪.png"])
            elif "小怪.png" in result:
                self.op.点击(*result["小怪.png"])
            elif ("大怪.png" not in result or "小怪.png" not in result) and "退出.png"in result:
                   self.op.点击(int(self.op.height*7/10), int(self.op.width*8/10), int(self.op.width*1/10))
            else:
                self.op.sleep(5)
            
    def lunhuan(self):
        self.op.图片预加载("tasks/k28图片/全部.png", f"tasks/k28图片/{self.config['lunhuan']}.png", "tasks/k28图片/二星.png", "tasks/k28图片/候补式神.png")
        state = 0
        while True:
            self.op.sleep(1)
            result = self.op.找图(priority_corner="tr")
            if state == 0 and "全部.png" in result:
                self.op.点击(*result["全部.png"])
                state += 1
                self.op.sleep(1)
            if f"{self.config['lunhuan']}.png" in result and state == 1:
                self.op.点击(*result[f"{self.config['lunhuan']}.png"])
                state += 1
                self.op.sleep(1)
            elif "二星.png" in result and (state == 2 or state == 3):
                self.op.点击(*result["二星.png"])
                state += 1
            elif "候补式神.png" in result:
                self.op.点击(*result["候补式神.png"])
                state += 1
            if state == 4:
                break

        self.op.图片预加载("tasks/k28图片/滑块.png", "tasks/k28图片/二星.png", "tasks/k28图片/确定设置.png")
        while True:
            self.op.sleep(1)
            result = self.op.找图(y1=0.55)
            if "二星.png" in result and "确定设置.png" in result:
                self.op.长按(result["二星.png"][0], result["二星.png"][1], 3)
                self.op.sleep(1)
                self.op.点击(*result["确定设置.png"])
                break
            elif "二星.png" not in result and "滑块.png" in result:
                x , y, r, *els = result["滑块.png"]
                self.op.滑动(x, y, x+r, y, 5)      
        self.op.sleep(1)
