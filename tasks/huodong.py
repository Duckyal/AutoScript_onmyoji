from module.adb import ADB

class Task_huodong:
    def __init__(self, device:ADB, config:dict):
        self.op = device
        self.config = config

    def run(self):
        if self.config.get("type") == "normal":
            self.sp()
        elif self.config.get("type") == "type1":
            self.type1()
        else:
            self.op.log(f"暂未支持该选项", level="error")

    def sp(self):
        n = int(self.config.get("count", 0))
        num = 0
        step = 'start'
        point = None
        self.op.图片预加载('tasks/活动图片/start_1920x1080.png', 'tasks/活动图片/over_1920x1080.png')
        while True:
            self.op.sleep(0.5)
            result = self.op.找图(0.9)
            if 'start_1920x1080.png' in result:
                if point is None:
                    point = result['start_1920x1080.png']
                self.op.点击(*point)
                step = 'start'
            elif 'over_1920x1080.png' in result:           
                if point is None:
                    self.op.点击(*result['over_1920x1080.png'])
                else:
                    self.op.点击(point[0], point[1]-100, point[2])
                if step != 'over':
                    num += 1
                    self.op.log(f'已完成{num}次')
                    step = 'over'
                self.op.sleep(1)
            else:
                if step == 'start':
                    self.op.sleep(8)
                    step = 'wait'
            self.op.sleep(1)
            if num == n and n != 0:
                self.op.log(f'任务结束')
                break

    def type1(self):
        n = int(self.config.get("count", 0))
        num = 0
        step = 'start'
        self.op.图片预加载("tasks/活动图片/继续挑战_1920x1080.png", "tasks/活动图片/开始挑战_1920x1080.png", "tasks/活动图片/胜利_1920x1080.png", 
                      "tasks/活动图片/失败_1920x1080.png", "tasks/活动图片/搜寻_1920x1080.png")
        while True:
            self.op.sleep(0.5)
            result = self.op.找图()
            if not result:
                texts = self.op.找字(y1=0.5)
                if not texts:
                    continue
                elif "准备" in texts:
                    self.op.点击(*texts["准备"])  # type: ignore
                elif "手动" in texts:
                    self.op.点击(*texts["手动"])  # type: ignore
                elif "自动" in texts:
                    self.op.重置定时器()
                    self.op.sleep(10)
            elif "搜寻_1920x1080.png" in result:
                if step == 'stop':
                    if num < n and n != 0:
                        num += 1
                        step = 'start'
                    elif num >= n:
                        self.op.log(f'任务结束')
                        break
                self.op.点击(*result["搜寻_1920x1080.png"])
                self.op.sleep(2)
            elif "继续挑战_1920x1080.png" in result:
                self.op.点击(*result["继续挑战_1920x1080.png"])
                self.op.sleep(2)
            elif "开始挑战_1920x1080.png" in result:
                self.op.点击(*result["开始挑战_1920x1080.png"])
                if step != "start":
                    step = 'start'
                self.op.sleep(2)
            elif "胜利_1920x1080.png" in result:
                self.op.点击(*result["胜利_1920x1080.png"])
                if step != 'start':
                    num += 1
                    self.op.log(f'已完成{num}次')
                    step = 'stop'
                self.op.sleep(1)
            elif "失败_1920x1080.png" in result:
                self.op.点击(*result["失败_1920x1080.png"])
                self.op.sleep(1)
