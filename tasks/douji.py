from module.adb import ADB
import re


class Task_douji:
    def __init__(self, device:ADB, config:dict):
        self.op = device
        self.config = config

    def run(self):
        pattern = re.compile(r"[0-9]{2,}/[0-9]{2,}")
        start = None
        end = (int(self.op.height*3/5), int(self.op.width*1/5), int(self.op.width*1/10))
        self.op.图片预加载('tasks/斗技图片/头筹.png', 'tasks/斗技图片/胜利.png', 'tasks/斗技图片/失败.png', 'tasks/斗技图片/胜场奖励.png', 'tasks/斗技图片/自动上阵.png')
        while True:

            self.op.sleep(0.5)
            result = self.op.找图(0.9)
            if start is None and ('战1.png' in result or '战2.png' in result):
                start = result.get('战1.png') or result.get('战2.png')
            if '头筹.png' in result or '结束1.png' in result or '结束2.png' in result or '胜场奖励.png' in result:
                self.op.点击(*end)
            elif '斗技.png' in result or '活动.png' in result:
                while True:
                    self.op.check_stop()
                    result = self.op.找字(int(self.op.height/2), int(self.op.width/2), self.op.height, self.op.width)
                    state = 0
                    if result is None:
                        self.op.sleep(1)
                        continue
                    for i in result:
                        re_result = pattern.search(i)
                        if re_result != None:
                            ls = re_result.group().split('/')
                            if ls[0] == ls[1]:
                                print(ls)
                                state = 1
                                break
                    if state == 1:
                        print('本周荣誉值已满，停止运行')
                        return
                    if '观战' in result:
                        self.op.点击(*start) # type: ignore
                        break
            elif '自动上阵.png' in result:
                self.op.点击(*result['自动上阵.png'])
            else:                
                result = self.op.找字(0, int(self.op.width/2), self.op.height, self.op.width)
                if result and '自动' in result:
                    self.op.sleep(5)
                elif result and '手动' in result:
                    self.op.点击(result['手动'][0], result['手动'][1]+int(self. op.width/2), result['手动'][2])
                else:
                    self.op.sleep(2)