from module.adb import ADB


class Task_douji:
    def __init__(self, device:ADB, config:dict):
        self.op = device
        self.config = config

    def run(self):
        state = 0
        end = (int(self.op.width*3/5), int(self.op.height*9/10), int(self.op.height*1/10))
        self.op.图片预加载('tasks/斗技图片/斗技页_1920x1080.png', 'tasks/斗技图片/胜利_1920x1080.png', 'tasks/斗技图片/失败_1920x1080.png',
                       'tasks/斗技图片/胜场奖励_1920x1080.png', 'tasks/斗技图片/头筹_1920x1080.png', 'tasks/斗技图片/段位晋升_1920x1080.png')
        while True:
            self.op.sleep(0.5)
            result = self.op.找图()
            if '头筹_1920x1080.png' in result or '失败_1920x1080.png' in result or '胜利_1920x1080.png' in result or '胜场奖励_1920x1080.png' in result:
                self.op.点击(*end)
            elif '段位晋升_1920x1080.png' in result:
                self.op.点击(*result['段位晋升_1920x1080.png'])

            elif '斗技页_1920x1080.png' in result:    # 战前准备阶段
                if self.config["count"] == "point":                   
                    result = self.op.找字(y1=0.6, x2=0.3, target_txt=r"[0-9]{2,}/[0-9]{2,}", use_regex=True)
                    if result is None:
                        continue
                    for key in result:
                        a, b = key.split('/')
                        if a == b:  # 脚本结束
                            state = 1
                        break
                    if state == 1:
                        self.op.log('斗技脚本结束')
                        break

                while not state:
                    self.op.sleep(3)
                    result = self.op.找字()
                    if result is None:
                        continue
                    if '点击屏幕继续' in result:
                        break
                    if '自动' in result:
                        if '全部' not in result:
                            break
                        elif '取消' in result:
                            continue
                        else:
                            self.op.点击(*result['自动']) # 点击“自动上阵”
                    elif '手动' in result:
                        self.op.点击(*result['手动'])
                    elif '自动上阵' in result:
                        self.op.点击(*result['自动上阵'])
                    elif '准备' in result:
                        self.op.点击(*result['准备'])
                    elif '战' in result:
                        self.op.点击(*result['战'])

            else:        # 战斗中        
                texts = self.op.找字(y1=0.5)
                if not texts:
                    continue
                elif "自动" in texts:
                    self.op.重置定时器()
                    self.op.sleep(10)
        