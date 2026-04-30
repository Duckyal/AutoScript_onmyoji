import uiautomator2 as u2
from rapidocr import RapidOCR
from module.decorators import *
from module.log import log

import cv2
import numpy as np

import os
import time 
from concurrent.futures import ThreadPoolExecutor


class ADB:
    adb_path = os.path.dirname(__file__)   #取文件所在文件夹绝对路径
    # 截图默认分辨率，后续会自动更新为设备分辨率
    width, height = 1280, 720
    
    def __init__(self, adb_tcp:str=None, mode:int=1):
        '''
        adb_tcp：无线调试端口或ip+端口
        mode: 1.开启日志  0. 关闭日志
        '''
        self.mode = mode   
        self.bz = bezierTrajectory()  
        try:
            if adb_tcp == None:
                self.d = u2.connect()
            else:
                if len(adb_tcp.split(':')) == 1:
                    self.d = u2.connect('127.0.0.1:'+adb_tcp.split(':')[-1])
                else:
                    self.d = u2.connect(adb_tcp)
            self._size()
            self.engine = RapidOCR()
        except AttributeError:
            log('设备初始化失败, 请检查设备是否连接', "error", "script")
            exit()
            
    def _size(self):
        size = self.d.window_size()
        self.width = size[0] if size[0]<size[1] else size[1]
        self.height = size[1] if size[0]<size[1] else size[0]
        if self.mode == 1:
            log(f'设备初始化完成:宽:{self.width},高:{self.height}', source="script")

    # ============================================================================================
    # ============================================================================================

    # API en-US
    def launch_app(self, package_name:str):
        self.启动应用(package_name)

    def close_app(self, package_name:str):
        self.关闭应用(package_name)

    def screen_off(self):
        self.息屏()

    def save_screenshot(self, save_path:str=adb_path, *point:tuple):
        self.截图保存(save_path, *point)

    def get_screenshot(self, x1:int=None, y1:int=None, x2:int=None, y2:int=None):
        return self.获取截图对象(x1, y1, x2, y2)
    
    def simple_click(self, x:int, y:int, r, *els):
        self.简单点击(x, y, r, *els)

    def click(self, x:int, y:int, loc:int='均值(一般取正态分布的生成半径)', *els):
        self.点击(x, y, loc, *els)

    def swipe(self, start_x:int, start_y:int, end_x:int, end_y:int, count:int=30, delay:float=0.01):
        self.滑动(start_x, start_y, end_x, end_y, count, delay)

    def input_text(self, txt:str):
        self.输入(txt)

    def adb_shell(self, shell:str):
        self.命令行(shell)

    def resize_image(self, img_path:str, resolution:tuple=(1280,720), save_path=None):
        return self.缩扩图(img_path, resolution, save_path)
    
    def color_match(self, match_img:str, pos:tuple=None, color_threshold:int=30):
        return self.比色(match_img, pos, color_threshold)
    
    def find_image(self, images:str | list, sim=0.95, x1:int=None, y1:int=None, x2:int=None, y2:int=None):
        return self.找图(images, sim, x1, y1, x2, y2)
    
    def find_text(self, x1:int=None, y1:int=None, x2:int=None, y2:int=None, target_txt:str=None):
        return self.找字(x1, y1, x2, y2, target_txt)
    

    # ============================================================================================
    # ============================================================================================

    # API zh-CN
    def 启动应用(self, package_name:str):
        self.d.app_start(package_name)
        if self.mode == 1:
            log('启动应用:{0}'.format(package_name), source="script")
        
    def 关闭应用(self, package_name:str):
        if package_name == 'all':
            self.d.app_stop_all()
            if self.mode == 1:
                log('关闭全部用户应用', source="script")
        else:
            self.d.app_stop(package_name)
            if self.mode == 1:
                log('关闭应用:{0}'.format(package_name), source="script")
                
    def 息屏(self):
        self.d.screen_off()
        if self.mode == 1:
            log('已息屏', source="script")
    
    def 截图保存(self, save_path:str=adb_path, *point:tuple):
        if len(point) == 0:
            cv2.imwrite(save_path, self.d.screenshot(format='opencv'))
        else:
            cv2.imwrite(save_path, self.d.screenshot(format='opencv')[point[1]:point[3], point[0]:point[2]])
        if self.mode == 1:
            log('已保存截图到:{0}'.format(save_path), source="script")
            
    def 获取截图对象(self, x1:int=None, y1:int=None, x2:int=None, y2:int=None):
        img = self.d.screenshot(format='opencv')
        # cv2.imshow('img', img)    # 显示图片
        if x1!=None and y1!=None and x2!=None and y2!=None:
            x1 = int(self.height*x1) if isinstance(x1, float) else x1
            y1 = int(self.width*y1) if isinstance(y1, float) else y1
            x2 = int(self.height*x2) if isinstance(x2, float) else x2
            y2 = int(self.width*y2) if isinstance(y2, float) else y2
            return img[y1:y2, x1:x2]
        else:
            return img
        if self.mode == 1:
            log('已保存截图到:{0}'.format(save_path), source="script")
                     
    def 简单点击(self, x:int, y:int, r, *els):
        '''
        x,y:点击中心坐标
        r:偏移值(一般取图片平均半径)，
        els:处理其他无效参数
        '''
        X, Y = x+r, y+r
        self.d.click(X, Y)
        if self.mode == 1:
            log('快速点击{0} {1}'.format(X, Y), source="script")
              
    def 点击(self, x:int, y:int, loc:int, *els):
        '''
        x,y:点击中心坐标
        loc:点击位置的随机范围，建议取正态分布生成半径(即loc**0.5)，
        els:处理其他无效参数
        '''
        # x,y应为左上角坐标
        mouse = np.random.normal(loc, int(loc**0.5), 2)
        X, Y = int(mouse[0]+x), int(mouse[1]+y)
        # self.d.click(X, Y)
        self.d.touch.down(X, Y)
        time.sleep(np.random.uniform(0, 0.4))
        self.d.touch.up(X, Y)
        if self.mode == 1:
            log('模拟点击{0} {1}'.format(X, Y), source="script")
    
    def 滑动(self, start_x:int, start_y:int, end_x:int, end_y:int, count:int=30, delay:float=0.01):
        '''
        start_x, start_y 为起始坐标,
        end_x, end_y 为终点坐标,
        count 决定了轨迹的细腻程度（点越多越慢越丝滑）
        delay 决定了每次移动的间隔时间（单位：秒，值越大越慢）
        '''
        points = self.bz.get_bezier_points((start_x, start_y), (end_x, end_y), count)
        # 首先：手指按下
        self.d.touch.down(start_x, start_y)
        # 其次：遍历轨迹点进行移动
        for x, y in points:
            # 适当微调间隔时间增加拟人感
            self.d.touch.move(x, y)
            time.sleep(0.01) 
        # 最后：手指抬起
        self.d.touch.up(end_x, end_y)
        if self.mode == 1:
            log('模拟滑动{0} {1} -> {2} {3}'.format(start_x, start_y, end_x, end_y), source="script")
        
    def 输入(self, txt:str):
        self.d.clear_text() # 清除输入框所有内容
        self.d.send_keys(txt)
        self.d.send_action("send") # 根据输入框的需求，自动执行回车、搜索等指令,支持 go, search, send, next, done, previous
        if self.mode == 1:
            log('模拟输入{0}'.format(txt), source="script")
        
    def adb命令行(self, shell:str):
        os.system(shell)
        if self.mode == 1:
            log('执行命令行:{0}'.format(shell), source="script")

    def 缩扩图(self, img_path:str, resolution:tuple=(1280,720), save_path=None):
        '''
        img_path:目标图片路径
        resolution:导入图片的分辨率 例:(1280, 720）
        save_path:是否保存结果图(保存路径)
        '''
        # 获取原始图片的名字、高度和宽度
        img_name = os.path.basename(img_path)
        image = cv2.imread(img_path)
        height, width = image.shape[:2]
        # 计算新的宽度和高度
        old_width, old_height = resolution
        ratio = self.height/old_width if abs(self.height-old_width)<abs(self.width-old_height) else self.width/old_height
        if ratio == 1.0:
            return (img_name, image)
        else:
            new_width = int(width * ratio)
            new_height = int(height * ratio)
            # 扩大图片
            resized_image = cv2.resize(image, (new_width, new_height))
            # 返回结果
            if save_path != None:
                cv2.imwrite(save_path, resized_image)
            else:
                return(img_name, resized_image)
    
    @Loop()
    def 比色(self, match_img:str, pos:tuple=None, color_threshold:int=30):
        sub_image = cv2.imread(match_img)
        sub_image_size = sub_image.shape[:2]
        if pos == None:
            # 寻找match_img位置
            _result = self._match_image(cv2.cvtColor(self.获取截图对象(), cv2.COLOR_BGR2GRAY), sub_image, 0.9, os.path.basename(match_img), sub_image_size)[1]
            x1, y1, w, h = _result[0], _result[1], _result[3], _result[4]
            x2, y2 = x1+w, y1+h
        elif isinstance(pos, tuple):
            x1, y1, w, h = pos
            x2, y2 = x1+w, y1+h
        else:
            raise ValueError('match_img并非路径或元组')
        # 提取矩形区域
        rect_area = w * h
        roi = self.获取截图对象(x1,y1,x2,y2)
        
        # 简单地取平均颜色作为主要颜色
        main_color_roi = np.mean(roi, axis=(0, 1)).astype(int)
        main_color_sub = np.mean(sub_image, axis=(0, 1)).astype(int)
        # 计算颜色差值
        diff = np.sum(np.abs(main_color_roi - main_color_sub))
        if self.mode == 1:
            log('{0}匹配结果:{1}'.format(os.path.basename(match_img), diff), source="script")
        return diff < color_threshold
    
    @Loop()
    def 找图(self, images:str | list, sim=0.95, x1:int=None, y1:int=None, x2:int=None, y2:int=None):
        '''
        images:匹配图路径或对象列表
        sim:匹配度阈值，默认0.95，范围0-1，值越大越严格
        x1, y1, x2, y2:截图区域坐标，默认为全屏
        '''
        main_img = self.获取截图对象(x1, y1, x2, y2)
        main_gray = cv2.cvtColor(main_img, cv2.COLOR_BGR2GRAY)
        output = {}
        sub_images_info = []

        if isinstance(images, str):
            images = [images]
        for image in images:
            try:
                img_name = os.path.basename(image)
                if os.path.exists(image):
                    sub_image = cv2.imread(image)
                    sub_image_size = sub_image.shape[:2]
                    sub_images_info.append((sub_image, sim, img_name, sub_image_size))
                else:
                    continue
            except TypeError:
                img_name = image[0]
                sub_image = image[1]
                sub_image_size = sub_image.shape[:2]
                sub_images_info.append((sub_image, sim, img_name, sub_image_size))
            
    
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(lambda info: self._match_image(main_gray, *info), sub_images_info))

        for result in results:
            if result:
                img_name, value = result
                output[img_name] = value
    
        if self.mode == 1:
            log(output, source="script")

        if len(output) == 0:
            return None
        else:    
            return output
        
    def _match_image(self, main_gray, sub_image, sim: float, img_name: str, sub_image_size: tuple):
        sub_gray = cv2.cvtColor(sub_image, cv2.COLOR_BGR2GRAY)
        result = cv2.matchTemplate(main_gray, sub_gray, cv2.TM_CCOEFF_NORMED)
        # 1. 获取全局最大匹配度及其位置
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        # 2. 判断最大值是否达到阈值 (可以稍微放宽一点，比如 sim - 0.02，或者直接用 sim)
        if max_val >= sim:
            x, y = max_loc  # max_loc 直接就是 (x, y)，不需要像 np.where 那样倒序
            w, h = sub_image_size[1], sub_image_size[0]
            # r 的计算：如果是正方形/近似正方形，取一半没问题
            # 如果是长条形，建议取 min(w, h) / 2 或者 sqrt(w^2+h^2)/2
            r = int(min(w, h) / 2)  
            # 可以把 max_val 也返回去，方便外面知道这张图到底匹配了百分之几
            return img_name, (int(x), int(y), r, w, h, max_val)
        return None


    @Loop()
    def 找字(self, x1:int=None, y1:int=None, x2:int=None, y2:int=None, target_txt:str=None):
        '''
        x1, y1, x2, y2:截图区域坐标，默认为全屏
        target_txt:目标文本（如果不提供则返回所有文本框信息）
        '''
        img_path = self.获取截图对象(x1, y1, x2, y2)
        result_list = self.engine(img_path, use_det=True, use_cls=True, use_rec=True)
        try:
            result_dict = {}
            for i in result_list:
                if x1==None or y1==None:
                    word, x1, y1, x2, y2 = i[1], int(i[0][0][0]), int(i[0][0][1]), int(i[0][2][0]), int(i[0][2][1])
                else:
                    word, x1, y1, x2, y2 = i[1], int(i[0][0][0])+x1, int(i[0][0][1])+y1, int(i[0][2][0])+x1, int(i[0][2][1])+y1
                w, h = (x2-x1)//2, (y2-y1)//2
                r = w if w <= h else h
                result_dict[word] = (x1, y1, r)

            if self.mode == 1:
                log(result_dict, source="script")

            if target_txt == None:
                if result_dict == {}:
                    return None
                return result_dict
            else:
                return result_dict.get(target_txt)
            
        except TypeError:
            return None