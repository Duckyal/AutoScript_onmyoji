from module.adb import ADB
import time
import re

# 初始化
op = ADB("92.168.240.112:5555")
pattern = re.compile(r"[0-9]{2,}/[0-9]{2,}")
start = None
end = (int(op.height*3/5), int(op.width*1/5), int(op.width*1/10))


def wait():     # 等待斗技页面
    global start
    while True:
        result = op.找图(op.获取截图对象(), 0.9, 'tasks/斗技图片/斗技.png', 'tasks/斗技图片/活动.png')
        if '斗技.png' in result:
            while True:
                result = op.找图(op.获取截图对象(), 0.9, 'tasks/斗技图片/斗技.png', 'tasks/斗技图片/战1.png', 'tasks/斗技图片/战2.png', 'tasks/斗技图片/战3.png', 'tasks/斗技图片/练.png')
                if '斗技.png' in result:
                    if '战1.png' in result:
                        start = result['战1.png']
                        print('准备运行脚本')
                        return True
                    elif '战2.png' in result:
                        start = result['战2.png']
                        print('准备运行脚本')
                        return True
                    elif '战3.png' in result:
                        start = result['战3.png']
                        print('准备运行脚本')
                        return True
                    elif '练.png' in result:
                        print('未在活动时间内')
                        return False
        elif '活动.png' in result:    # 斗技赛
            while True:
                result = op.找图(op.获取截图对象(), 0.9, 'tasks/斗技图片/活动.png', 'tasks/斗技图片/活动战1.png', 'tasks/斗技图片/活动战2.png', 'tasks/斗技图片/活动战3.png', 'tasks/斗技图片/活动练.png')
                if '活动.png' in result:
                    if '活动战1.png' in result:
                        start = result['活动战1.png']
                        print('准备运行脚本')
                        return True
                    elif '活动战2.png' in result:
                        start = result['活动战2.png']
                        print('准备运行脚本')
                        return True
                    elif '活动战3.png' in result:
                        start = result['活动战3.png']
                        print('准备运行脚本')
                        return True
                    elif '活动练.png' in result:
                        print('未在活动时间内')
                        return False
                
def main():
    while True:
        time.sleep(0.5)
        result = op.找图(op.获取截图对象(), 0.9, 'tasks/斗技图片/斗技.png', 'tasks/斗技图片/活动.png', 'tasks/斗技图片/头筹.png', 'tasks/斗技图片/结束1.png', 'tasks/斗技图片/结束2.png', 'tasks/斗技图片/胜场奖励.png', 'tasks/斗技图片/自动上阵.png')
        if '头筹.png' in result or '结束1.png' in result or '结束2.png' in result or '胜场奖励.png' in result:
            op.点击(*end)
        elif '斗技.png' in result or '活动.png' in result:
            while True:
                result = op.找字框(op.获取截图对象(int(op.height/2), int(op.width/2), op.height, op.width))
                state = 0
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
                    op.点击(*start)
                    break
        elif '自动上阵.png' in result:
            op.点击(*result['自动上阵.png'])
        else:                
            result = op.找字框(op.获取截图对象(0, int(op.width/2), op.height, op.width))
            if '自动' in result:
                time.sleep(5)
            elif '手动' in result:
                op.点击(result['手动'][0], result['手动'][1]+int(op.width/2), result['手动'][2])
            else:
                time.sleep(2)
                
    
if __name__ == '__main__':
    if wait() == True:
        main()
    op.息屏()