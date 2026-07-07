from module.adb import ADB


# 全局停止信号字典
stop_signals = {}

class Task_yinjie:
    def __init__(self, device:ADB, config:dict):
        self.op = device
        self.config = config
        config.get("mode", "less")

        # 初始化
        self.结束点击 = (int(self.op.height*4/5), int(self.op.width*2/5), int(self.op.height*1/10))
        self.加成顺序_源赖光 = ['追斩', '增进', '血啸', '透甲', '附魂', '万刃', '乘胜', '锐利', '绝命', '刃降', '暴击加成', '伤害加成', '速度提升']
        self.加成顺序_藤原道长 = ['敛神','同调', '涤尘', '弥天', '韵驰', '遏云', '音迹', '泛音', '凝啸', '逐空', '伤害加成', '速度提升', '暴击加成']

    def run(self):    # 运行脚本
        mode = self.config.get('type')
        if mode == 'yuan':
            self.op.log("运行脚本-源赖光")
            加成顺序 = self.加成顺序_源赖光
            self.op.图片预加载('tasks/兵藏图片/挑战.png', 'tasks/兵藏图片/选加成.png', 'tasks/兵藏图片/战斗中.png', 'tasks/兵藏图片/胜利.png', 'tasks/兵藏图片/失败.png', 'tasks/兵藏图片/结束.png', 'tasks/兵藏图片/确认重置.png')
            while True:
                self.op.check_stop()
                result = self.op.找图(0.95)
                print(result)
                if '结束.png' in result:
                    print('兵藏秘境.py', '挑战次数已用完')
                    break
                if '确认重置.png' in result:
                    self.op.点击(*result['确认重置.png'])
                elif '挑战.png' in result:
                    self.op.点击(*result['挑战.png'])
                elif '战斗中.png' in result:
                    self.op.sleep(5)
                elif '胜利.png' in result:
                    self.op.点击(*self.结束点击)
                elif '失败.png' in result:
                    self.op.点击(*self.结束点击)
                    self.op.sleep(2)
                    print('准备重置关卡')
                    while True:
                        self.op.sleep(1)
                        result = self.op.找字()
                        if '确认重置' in result: # type: ignore
                            self.op.点击(*result['确认重置']) # type: ignore
                            break
                        elif '关卡' in result:   # type: ignore
                            self.op.点击(*result['关卡'])       # type: ignore
                elif '选加成.png' in result:
                    result = self.op.找字()
                    sign = True
                    for i in 加成顺序: # type: ignore
                        for l in list(result.keys()): # type: ignore
                            if i in l:
                                print('选择加成:', i)
                                self.op.点击(*result[l]) # type: ignore
                                self.op.sleep(1)
                                sign = False
                                break
                        if sign == False:
                            break
                    while True:
                        self.op.sleep(1)
                        result = self.op.找字()
                        if '确定' in result: # type: ignore
                            self.op.点击(*result['确定']) # type: ignore
                            break
        elif mode == 'tengyuan':
            self.op.log("运行脚本-藤原道长")
            加成顺序 = self.加成顺序_藤原道长
            self.op.图片预加载('tasks/兵藏图片/挑战2.png', 'tasks/兵藏图片/选加成2.png', 'tasks/兵藏图片/战斗中2.png', 'tasks/兵藏图片/胜利2.png')
            while True:
                self.op.check_stop()
                self.op.sleep(1)
                result = self.op.找图()
                if '挑战2.png' in result:
                    self.op.点击(*result['挑战2.png'])
                elif '战斗中2.png' in result:
                    self.op.sleep(5)
                elif '胜利2.png' in result:
                    self.op.点击(*self.结束点击)
                elif '选加成2.png' in result:
                    tmp_pos = result['选加成2.png'] # type: ignore
                    print('选加成界面坐标:', tmp_pos)
                    result = self.op.找字()
                    sign = True
                    for i in 加成顺序: # type: ignore
                        for l in list(result.keys()): # type: ignore
                            if i in l:
                                print('选择加成:', i, '加成顺序:', *result[l]) # type: ignore
                                self.op.点击(*result[l]) # type: ignore
                                self.op.sleep(1)
                                self.op.点击(*tmp_pos) # type: ignore
                                sign = False
                                break
                        if sign == False:
                            break
    