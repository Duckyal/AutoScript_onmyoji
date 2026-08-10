# =============================================================================================
#                                          超时装饰器
# =============================================================================================
import time


# 全局超时时间字典：{ device_id: start_time }
_time_starts = {}

def reset_timer(device_id: str):
    """重置指定设备的定时器"""
    global _time_starts
    _time_starts[device_id] = time.time()

def extra_time(device_id: str, seconds: float):
    """为指定设备额外增加超时时间"""
    global _time_starts
    if device_id not in _time_starts:
        reset_timer(device_id)
    else:
        _time_starts[device_id] += seconds

def check_timeout(device_id: str, seconds: float = 180.0):
    """检查指定设备是否超时:默认3分钟（180秒）"""
    global _time_starts
    if device_id not in _time_starts:
        reset_timer(device_id)
    elif time.time() - _time_starts[device_id] > seconds:
        raise TimeoutError(f"超时：{seconds}秒内未操控设备")

def cleanup_timeout(device_id: str):
    """清理指定设备的超时记录"""
    global _time_starts
    _time_starts.pop(device_id, None)

# =============================================================================================
#                                        停止信号装饰器
# =============================================================================================
import threading


class TaskStoppedException(Exception):
    """任务停止信号异常"""
    pass

# 全局停止信号字典：{ device_id: threading.Event }
_stop_signals = {}

def register_stop_signal(device_id: str):
    """注册停止信号"""
    _stop_signals[device_id] = threading.Event()

def trigger_stop_signal(device_id: str):
    """触发停止信号"""
    if device_id in _stop_signals:
        _stop_signals[device_id].set()
        return True
    return False

def cleanup_stop_signal(device_id: str):
    """清理停止信号"""
    _stop_signals.pop(device_id, None)
    
def check_stop(obj):
    """
    检查是否需要停止
    在任何耗时长的地方（循环里、sleep前）都可以调用这个
    
    用法：
        def run(self):
            for i in range(100):
                check_stop(self)  # 关键点检查
                do_something()
    """
    device_id = getattr(obj, 'device_id')
    if device_id in _stop_signals:
        if _stop_signals[device_id].is_set():
            raise TaskStoppedException("任务被终止")

# 可中断的 sleep
def interruptible_sleep(seconds: float, obj):
    """
    可中断的 sleep，每0.1秒检查一次停止信号
    
    用法：
        interruptible_sleep(5, self)  # 替代 time.sleep(5)
    """
    if seconds >= 30:
        device_id = getattr(obj, 'device_id')
        extra_time(device_id, seconds)
    end_time = time.time() + seconds
    
    while time.time() < end_time:
        if obj:
            check_stop(obj)
        time.sleep(0.1)  # 每次只睡0.1秒，检查更及时

# =============================================================================================
#                                        轨迹装饰器
# =============================================================================================

'''
author: cbb
这个库基于贝塞尔曲线实现模拟人手动滑动的轨迹
可以用于selenium轨迹的模拟，或者生成轨迹数组用于js加密通过网站服务器后端分控检测
QQ群 134064772
里面的人说话好听，个个都是人才
'''
import numpy as np
import math
import random


class bezierTrajectory:

    def _bztsg(self, dataTrajectory):
        lengthOfdata = len(dataTrajectory)

        def staer(x):
            t = ((x - dataTrajectory[0][0]) / (dataTrajectory[-1][0] - dataTrajectory[0][0]))
            y = np.array([0, 0], dtype=np.float64)
            for s in range(len(dataTrajectory)):
                y += dataTrajectory[s] * ((math.factorial(lengthOfdata - 1) / (
                            math.factorial(s) * math.factorial(lengthOfdata - 1 - s))) * math.pow(t, s) * math.pow(
                    (1 - t), lengthOfdata - 1 - s))
            return y[1]

        return staer

    def _type(self, type, x, numberList):
        numberListre = []
        pin = (x[1] - x[0]) / numberList
        if type == 0:
            for i in range(numberList):
                numberListre.append(i * pin)
            if pin >= 0:
                numberListre = numberListre[::-1]
        elif type == 1:
            for i in range(numberList):
                numberListre.append(1 * ((i * pin) ** 2))
            numberListre = numberListre[::-1]
        elif type == 2:
            for i in range(numberList):
                numberListre.append(1 * ((i * pin - x[1]) ** 2))

        elif type == 3:
            dataTrajectory = [np.array([0,0]), np.array([(x[1]-x[0])*0.8, (x[1]-x[0])*0.6]), np.array([x[1]-x[0], 0])]
            fun = self._bztsg(dataTrajectory)
            numberListre = [0]
            for i in range(1,numberList):
                numberListre.append(fun(i * pin) + numberListre[-1])
            if pin >= 0:
                numberListre = numberListre[::-1]
        numberListre = np.abs(np.array(numberListre) - max(numberListre))
        biaoNumberList = ((numberListre - numberListre[numberListre.argmin()]) / (
                    numberListre[numberListre.argmax()] - numberListre[numberListre.argmin()])) * (x[1] - x[0]) + x[0]
        biaoNumberList[0] = x[0]
        biaoNumberList[-1] = x[1]
        return biaoNumberList

    def getFun(self, s):
        '''

        :param s: 传入P点
        :return: 返回公式
        '''
        dataTrajectory = []
        for i in s:
            dataTrajectory.append(np.array(i))
        return self._bztsg(dataTrajectory)

    def simulation(self, start, end, le=1, deviation=0, bias=0.5):
        '''

        :param start:开始点的坐标 如 start = [0, 0]
        :param end:结束点的坐标 如 end = [100, 100]
        :param le:几阶贝塞尔曲线，越大越复杂 如 le = 4
        :param deviation:轨迹上下波动的范围 如 deviation = 10
        :param bias:波动范围的分布位置 如 bias = 0.5
        :return:返回一个字典equation对应该曲线的方程，P对应贝塞尔曲线的影响点
        '''
        start = np.array(start)
        end = np.array(end)
        cbb = []
        if le != 1:
            e = (1 - bias) / (le - 1)
            cbb = [[bias + e * i, bias + e * (i + 1)] for i in range(le - 1)]

        dataTrajectoryList = [start]

        t = random.choice([-1, 1])
        w = 0
        for i in cbb:
            px1 = start[0] + (end[0] - start[0]) * (random.random() * (i[1] - i[0]) + (i[0]))
            p = np.array([px1, self._bztsg([start, end])(px1) + t * deviation])
            dataTrajectoryList.append(p)
            w += 1
            if w >= 2:
                w = 0
                t = -1 * t

        dataTrajectoryList.append(end)
        return {"equation": self._bztsg(dataTrajectoryList), "P": np.array(dataTrajectoryList)}

    def trackArray(self, start, end, numberList, le=1, deviation=0, bias=0.5, type=0, cbb=0, yhh=10):
        '''

        :param start:开始点的坐标 如 start = [0, 0]
        :param end:结束点的坐标 如 end = [100, 100]
        :param numberList:返回的数组的轨迹点的数量 numberList = 150
        :param le:几阶贝塞尔曲线，越大越复杂 如 le = 4
        :param deviation:轨迹上下波动的范围 如 deviation = 10
        :param bias:波动范围的分布位置 如 bias = 0.5
        :param type:0表示均速滑动，1表示先慢后快，2表示先快后慢，3表示先慢中间快后慢 如 type = 1
        :param cbb:在终点来回摆动的次数
        :param yhh:在终点来回摆动的范围
        :return:返回一个字典trackArray对应轨迹数组，P对应贝塞尔曲线的影响点
        '''
        s = []
        fun = self.simulation(start, end, le, deviation, bias)
        w = fun['P']
        fun = fun["equation"]
        if cbb != 0:
            numberListOfcbb = round(numberList*0.2/(cbb+1))
            numberList -= (numberListOfcbb*(cbb+1))

            xTrackArray = self._type(type, [start[0], end[0]], numberList)
            for i in xTrackArray:
                s.append([i, fun(i)])
            dq = yhh/cbb
            kg = 0
            ends = np.copy(end)
            for i in range(cbb):
                if kg == 0:
                    d = np.array([end[0] + (yhh-dq*i), ((end[1]-start[1])/(end[0]-start[0]))*(end[0]+(yhh-dq*i)) +(end[1]-((end[1]-start[1])/(end[0]-start[0]))*end[0])   ])
                    kg = 1
                else:
                    d = np.array([end[0] - (yhh - dq * i), ((end[1]-start[1])/(end[0]-start[0]))*(end[0]-(yhh-dq*i)) +(end[1]-((end[1]-start[1])/(end[0]-start[0]))*end[0])  ])
                    kg = 0
                print(d)
                y = self.trackArray(ends, d, numberListOfcbb, le=2, deviation=0, bias=0.5, type=0, cbb=0, yhh=10)
                s += list(y['trackArray'])
                ends = d
            y = self.trackArray(ends, end, numberListOfcbb, le=2, deviation=0, bias=0.5, type=0, cbb=0, yhh=10)
            s += list(y['trackArray'])

        else:
            xTrackArray = self._type(type, [start[0], end[0]], numberList)
            for i in xTrackArray:
                s.append([i, fun(i)])
        return {"trackArray": np.array(s), "P": w}
