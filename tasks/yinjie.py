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
        self.加成顺序_源赖光 = ['追斩', '增进', '血啸', '透甲', '附魂', 
                              '万刃', '乘胜', '锐利', '绝命', '刃降', 
                              '暴击加成', '伤害加成', '速度提升']
        self.加成顺序_藤原道长 = ['同调',                                   # 咏叹+琴月
                               '泛音', '凝啸', '韵驰', '叩弦', '霆斥',      # 破阵+神鸟
                               '弥天', '叠辉', '敛神',                     # 咏叹+琴月
                               '伤害加成', '速度提升', '暴击加成']

    def run(self):    # 运行脚本
        mode = self.config.get('type')
        if mode == 'yuan':
            pass
        elif mode == 'tengyuan':
            self.op.log("运行脚本-藤原道长")
            加成顺序 = self.加成顺序_藤原道长
            self.op.图片预加载('tasks/英杰图片/挑战2_1920x1080.png', 'tasks/英杰图片/选加成2_1920x1080.png', 'tasks/英杰图片/战斗中2_1920x1080.png',
                           'tasks/英杰图片/胜利2_1920x1080.png', 'tasks/英杰图片/失败2_1920x1080.png', 'tasks/英杰图片/结束_1920x1080.png')
            num = self.config.get('refresh', 3)
            while True:
                self.op.check_stop()
                result = self.op.找图()
                if '结束_1920x1080.png' in result:
                    self.op.log("藤原道长脚本结束")
                    break
                if '挑战2_1920x1080.png' in result:
                    self.op.点击(*result['挑战2_1920x1080.png'])
                elif '战斗中2_1920x1080.png' in result:
                    self.op.sleep(5)
                elif '胜利2_1920x1080.png' in result:
                    self.op.点击(*self.结束点击)
                elif '失败2_1920x1080.png' in result:
                    self.op.点击(*self.结束点击)
                    num += 1
                    if num >= num:
                        self.op.log(f"失败重新挑战{num}次，退出脚本", "error")
                        break
                elif '选加成2_1920x1080.png' in result:
                    tmp_pos = result['选加成2_1920x1080.png'] # type: ignore
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
    