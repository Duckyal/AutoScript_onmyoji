from module.adb import ADB
import re

class Task_tupo:
    def __init__(self, device:ADB, config:dict):
        self.op = device
        self.config = config
        self.end = (int(self.op.width*3/5), int(self.op.height*9/10), int(self.op.height*1/10))

    def run(self):
        type = self.config.get("type")
        # 找模式
        self.op.图片预加载(f"tasks/突破图片/{type}_1920x1080.png", "tasks/突破图片/退出_1920x1080.png")
        while True:
            self.op.sleep(1)
            result = self.op.找图()
            if not result:
                continue
            if f"{type}_1920x1080.png" in result:
                self.op.点击(*result[f"{type}_1920x1080.png"])
            elif "退出_1920x1080.png" in result:
                break
        if type == "个人突破":
            self.refresh_kekkai()
        else:
            self.refresh_ryou()
            
    def refresh_kekkai(self):
        self.op.log(f"准备运行个人突破")
        refresh = self.config.get("refresh", "yes")
        self.op.图片预加载("tasks/突破图片/入口_1920x1080.png", "tasks/突破图片/进攻_1920x1080.png", "tasks/突破图片/刷新_1920x1080.png", 
                      "tasks/突破图片/确定刷新_1920x1080.png", "tasks/突破图片/奖励_1920x1080.png", "tasks/突破图片/失败_1920x1080.png",
                      "tasks/突破图片/未锁定_1920x1080.png", "tasks/突破图片/退出_1920x1080.png")
        while True:
            self.op.sleep(1)
            result = self.op.找图()
            if not result:
                self.op.sleep(3)
                continue
            if "未锁定_1920x1080.png" in result:
                self.op.点击(*result["未锁定_1920x1080.png"])
            elif "确定刷新_1920x1080.png" in result:
                self.op.点击(*result["确定刷新_1920x1080.png"])
            elif "进攻_1920x1080.png" in result:
                self.op.点击(*result["进攻_1920x1080.png"])
                self.op.sleep(int(self.config.get("sleep", 5)))
            elif "奖励_1920x1080.png" in result or "失败_1920x1080.png" in result:
                self.op.点击(*self.end)
            elif "入口_1920x1080.png" in result and "退出_1920x1080.png" in result:
                x, y, r = result["入口_1920x1080.png"][0], result["入口_1920x1080.png"][1], result["入口_1920x1080.png"][2]

                # 检测突破券数量
                result_txt = self.op.找字(x1=0.7, y2=0.1, target_txt="\d+/30", use_regex=True)
                if result_txt:
                    a = result_txt[0].split("/")[0]
                    if a == "0":
                        self.op.点击(*result["退出_1920x1080.png"])
                        self.op.sleep(3)
                        if "退出_1920x1080.png" not in self.op.找图():
                            break
                    else:        
                        self.op.点击(x-r, y+r, r)
                        self.op.sleep(1)
                    
            elif "刷新_1920x1080.png" in result:
                if refresh == "yes":
                    self.op.点击(*result["刷新_1920x1080.png"])
                else:
                    break
        self.op.log(f"个人突破完成")
                
    def refresh_ryou(self):
        self.op.log(f"开始运行寮突破")
        count = 0
        self.op.图片预加载("tasks/突破图片/入口_1920x1080.png", "tasks/突破图片/奖励_1920x1080.png", "tasks/突破图片/失败_1920x1080.png", 
                      "tasks/突破图片/进攻_1920x1080.png", "tasks/突破图片/未锁定_1920x1080.png", "tasks/突破图片/退出_1920x1080.png",
                      "tasks/突破图片/滑块_1920x1080.png")
        while True:
            self.op.sleep(0.5)
            state = 0
            result = self.op.找图()
            if not result:
                self.op.sleep(3)
                continue
            if "未锁定_1920x1080.png" in result:
                self.op.点击(*result["未锁定_1920x1080.png"])
            elif "进攻_1920x1080.png" in result:
                self.op.点击(*result["进攻_1920x1080.png"])
                self.op.sleep(int(self.config.get("sleep", 5)))
            elif "奖励_1920x1080.png" in result or "失败_1920x1080.png" in result:
                self.op.点击(*self.end)
            elif "入口_1920x1080.png" in result and "退出_1920x1080.png" in result:
                x, y, r = result["入口_1920x1080.png"][0], result["入口_1920x1080.png"][1], result["入口_1920x1080.png"][2]

                # 检测寮突挑战数量（晚上21点后不检测挑战次数）
                result_txt = self.op.找字(x1=0.1, y1=0.5, x2=0.3, y2=0.9)
                if result_txt:                       
                    for item in result_txt:
                        # 匹配百分比（如 0.83%、100%）
                        match1 = re.search(r"(\d+(\.\d+)?)%", item)
                        if match1:
                            percent = float(match1.group(1))
                            if percent >= 90:
                                state += 1
                                break
                        # 匹配"击败次数：x/6"
                        match2 = re.search(r"击败次数[：:]?\s*(\d+)/6", item)
                        if match2:
                            a = match2.group(1)
                            if a == "0":
                                if self.config.get("refresh") == "no":
                                    self.op.点击(*result["退出_1920x1080.png"])
                                    state += 1
                                else:
                                    self.op.log("等待寮突破次数增加")
                                    self.op.sleep(300)
                                break
                    if state == 0:            
                        self.op.点击(x-2*r, y+r, r)
                    else:
                        self.op.log("寮突破任务结束")
                        break

            elif "滑块_1920x1080.png" in result and "入口_1920x1080.png" not in result:
                count += 1
                x, y, r = result["滑块_1920x1080.png"][0], result["滑块_1920x1080.png"][1], result["滑块_1920x1080.png"][2]
                self.op.滑动(x, y, int(x-r/10), y+r, 5)
            if count >= 3:
                self.op.log("寮突破异常结束：无可突破对象")
                break