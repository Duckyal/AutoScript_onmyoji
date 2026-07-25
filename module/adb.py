import uiautomator2 as u2
from rapidocr import RapidOCR
from module.decorators import *
from module.logmanager import ws_manager

import cv2
import numpy as np
import os
import time 
import re

from concurrent.futures import ThreadPoolExecutor


class ADB():
    adb_path = os.path.dirname(__file__)   # 取文件所在文件夹绝对路径
    
    # 用字典代替单一的 _instance，key 是传入的参数，value 是对应的实例
    _instances = {}

    def __new__(cls, device_id: str, mode: str = "less", max_workers=4, adapt_res_everytime: bool = False, source: str = "server"):
        # 把传入的参数变成一个可哈希的 key（比如元组）
        cache_key = (device_id, mode, max_workers, adapt_res_everytime, source)
        
        # 如果这个参数组合没被实例化过，就新建一个
        if cache_key not in cls._instances:
            cls._instances[cache_key] = super().__new__(cls)
        # 返回这个参数对应的唯一实例
        return cls._instances[cache_key]

    def __init__(self, device_id: str, mode: str = "less", max_workers=4, adapt_res_everytime: bool = False, source: str = "server"):
        """
        初始化ADB实例，连接指定设备。
        :param device_id: 设备ID，或"None"表示连接所有设备。
        :param mode: 模式，"less"或"more"。
        :param max_workers: 最大线程数。
        :param adapt_res_everytime: 是否每次找图都适配分辨率。
        :param source: 日志来源，"server"或"client"。
        :return: ADB实例。
        """
        # 由于 Python 机制，每次 return 缓存实例时，都会强制调用 __init__
        # 所以必须加一个标记，防止同一个实例被重复初始化
        if getattr(self, "_is_initialized", False):
            return
        
        self.device_id = device_id
        self.mode = mode
        self.log_manager = ws_manager
        self.bz = bezierTrajectory()

        self.max_workers = max_workers  
        self.adapt_res_everytime = adapt_res_everytime
        self.current_scale = None       # 全局缓存的手机分辨率缩放比
        self.cached_templates = {}      # 缓存所有模板图的灰度矩阵和原始尺寸
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers) # 复用线程池，避免高频创建销毁
        
        # ORB 检测器缓存，避免重复初始化
        self._orb_detector = None
        self._orb_bf_matcher = None
        
        # 模板金字塔缓存，预先计算多个缩放级别的模板
        self._pyramid_cache = {}
        
        try:
            if device_id == "None":
                self.d = u2.connect()
            elif ':' not in device_id and device_id.isdigit():
                self.d = u2.connect(f'127.0.0.1:{device_id}')
            else:
                self.d = u2.connect(device_id)
                
            self.engine = RapidOCR()
            # 标记当前这个实例已经初始化完毕
            self._is_initialized = True
        except Exception as e:
            self.log(f'设备初始化失败, 请检查设备是否连接。原始错误: {e}', "error")
            # 从缓存字典里删掉这个失败的实例
            # 修复缓存键不一致问题，确保设备初始化失败时能正确清理缓存
            cache_key = (device_id or "None", mode, max_workers, adapt_res_everytime, source)
            ADB._instances.pop(cache_key, None)
            raise Exception(f"设备 {device_id} 初始化失败") 

        # 获取并更新设备分辨率(竖屏状态)
        w, h = self.d.window_size()
        self.width = min(w, h)
        self.height = max(w, h)
        
        self.log(f'设备初始化完成: 宽:{self.width}, 高:{self.height}', 'debug')

    # 封装module/decorators.py里中断函数的方法
    def sleep(self, seconds: float):
        """
        可中断的睡眠函数，支持在睡眠过程中被外部中断。
        :param seconds: 需要睡眠的秒数
        """
        interruptible_sleep(seconds, self)

    def check_stop(self):
        """
        检查是否需要中断当前任务，如果需要则抛出异常。
        """
        check_stop(self)

    # 封装module/logmanager.py里日志函数的方法
    def log(self, message: object, level: str = "info", source: str = ''):
        """
        专用的日志函数，会同时输出到本地终端 + 推送到前端 WebSocket
        - message: 日志内容
        - level: info / debug / warning / error
        - source: 日志来源，默认设备ID
        """
        # 调用 ws_manager
        if self.log_manager:
            self.log_manager.log(message, level, self.device_id if source == '' else self.device_id+"_"+ source)

    # ============================================================================================
    # ============================================================================================

    def _get_orb_detector(self):
        """获取缓存的 ORB 检测器实例"""
        if self._orb_detector is None:
            self._orb_detector = cv2.ORB_create(
                nfeatures=800, 
                scaleFactor=1.2, 
                nlevels=8, 
                edgeThreshold=15
            )
        return self._orb_detector
    
    def _get_bf_matcher(self):
        """获取缓存的 BFMatcher 实例"""
        if self._orb_bf_matcher is None:
            self._orb_bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        return self._orb_bf_matcher
    
    def _build_pyramid(self, img_name, temp_info, scale_range=(0.5, 1.5), steps=11):
        """
        构建模板金字塔，预先计算多个缩放级别的模板
        :param scale_range: 缩放范围 (min_scale, max_scale)
        :param steps: 缩放级别数量
        """
        if img_name in self._pyramid_cache:
            return
        
        template = temp_info['img']
        h, w = template.shape[:2]
        
        scales = np.linspace(scale_range[0], scale_range[1], steps)
        pyramid = {}
        
        for scale in scales:
            sw = int(w * scale)
            sh = int(h * scale)
            if sw >= 10 and sh >= 10:
                resized = cv2.resize(template, (sw, sh), 
                                    interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC)
                pyramid[scale] = {
                    'img': resized,
                    'w': sw,
                    'h': sh
                }
        
        self._pyramid_cache[img_name] = pyramid
    
    def _get_pyramid_template(self, img_name, scale_x, scale_y):
        """
        从金字塔中获取最接近目标缩放的模板
        """
        if img_name not in self._pyramid_cache:
            return None
        
        pyramid = self._pyramid_cache[img_name]
        avg_scale = (scale_x + scale_y) / 2
        
        # 找最接近的缩放级别
        best_scale = None
        min_diff = float('inf')
        for scale in pyramid.keys():
            diff = abs(scale - avg_scale)
            if diff < min_diff:
                min_diff = diff
                best_scale = scale
        
        if best_scale is not None:
            return pyramid[best_scale]
        
        return None
    def launch_app(self, package_name:str):
        '''
        package_name: 应用包名
        '''
        self.启动应用(package_name)

    def close_app(self, package_name:str):
        '''
        package_name: 应用包名
        '''
        self.关闭应用(package_name)

    def screen_off(self):
        '''
        息屏
        '''
        self.息屏()

    def save_screenshot(self, save_path:str=adb_path, x1:int|float=-1, y1:int|float=-1, x2:int|float=-1, y2:int|float=-1):
        '''
        save_path: 保存截图的路径，默认为 adb_path
        x1, y1, x2, y2: 截图区域坐标，默认为 -1 表示全屏
        '''
        self.截图保存(save_path, x1, y1, x2, y2)

    def get_screenshot(self, x1:int|float=-1, y1:int|float=-1, x2:int|float=-1, y2:int|float=-1):
        '''
        x1, y1, x2, y2: 截图区域坐标，默认为 -1 表示全屏
        '''
        return self.获取截图(x1, y1, x2, y2)
    
    def simple_click(self, x:int, y:int, r, *els):
        '''
        x, y: 点击坐标
        r: 点击位置，默认为 0
        *els: 其他元素坐标，用于点击多个元素
        '''
        self.简单点击(x, y, r, *els)

    def click(self, x:int, y:int, loc:int, *els):
        '''
        x, y: 点击坐标
        loc: 点击位置，默认为 0
        *els: 其他元素坐标，用于点击多个元素
        '''
        self.点击(x, y, loc, *els)

    def swipe(self, start_x:int, start_y:int, end_x:int, end_y:int, count:int=30, delay:float=0.01):
        '''
        start_x, start_y: 起始点坐标
        end_x, end_y: 结束点坐标
        count: 滑动次数，默认为 30
        delay: 每次滑动间隔，默认为 0.01
        '''
        self.滑动(start_x, start_y, end_x, end_y, count, delay)

    def input_text(self, txt:str):
        '''
        txt: 要输入的文本
        '''
        self.输入(txt)

    def adb_shell(self, shell:str):
        '''
        shell: 要执行的命令
        '''
        self.adb命令行(shell)
    
    def image_preloading(self, *image_paths):
        '''
        image_paths: 图片路径列表
        '''
        self.图片预加载(*image_paths)
    
    def find_image(self, sim=0.90, x1:int|float=-1, y1:int|float=-1, x2:int|float=-1, y2:int|float=-1):
        '''
        sim: 图片相似度，默认为 0.90
        x1, y1, x2, y2: 截图区域坐标，默认为 -1 表示全屏
        '''
        return self.找图(sim=sim, x1=x1, y1=y1, x2=x2, y2=y2)
    
    def find_text(self, x1:int|float=-1, y1:int|float=-1, x2:int|float=-1, y2:int|float=-1, Specified_image=None, target_txt:str='', use_regex: bool = False):
        '''
        x1, y1, x2, y2: 截图区域坐标，默认为 -1 表示全屏
        Specified_image: 指定图片（如果不提供则使用当前截图）
        target_txt: 目标文本（如果不提供则返回所有文本框信息），支持正则表达式，返回值为匹配到的文本对应坐标或None
        use_regex: 是否启用正则匹配，默认为 False,;为True则返回值将为匹配到的文本列表，为False则返回匹配到的文本及其坐标
        '''
        return self.找字(x1, y1, x2, y2, Specified_image, target_txt, use_regex)
    

    # ============================================================================================
    # ============================================================================================

    # API zh-CN
    def 启动应用(self, package_name:str):
        self.d.app_start(package_name)
        self.log('启动应用:{0}'.format(package_name), 'debug')
        
    def 关闭应用(self, package_name:str):
        if package_name == 'all':
            self.d.app_stop_all()
            self.log('关闭全部用户应用', 'debug')
        else:
            self.d.app_stop(package_name)
            self.log('关闭应用:{0}'.format(package_name), 'debug')
                
    def 息屏(self):
        self.d.screen_off()
        self.log('已息屏', 'debug')
    
    def 截图保存(self, save_path:str=adb_path, x1:int|float=-1, y1:int|float=-1, x2:int|float=-1, y2:int|float=-1):
        if x1 != -1:
            x1 = int(self.height*x1) if isinstance(x1, float) else x1
        else:
            x1 = 0
        if y1 != -1:
            y1 = int(self.width*y1) if isinstance(y1, float) else y1
        else:
            y1 = 0

        if x2 != -1:
            x2 = int(self.height*x2) if isinstance(x2, float) else x2
        else:
            x2 = self.height
        if y2 != -1:
            y2 = int(self.width*y2) if isinstance(y2, float) else y2
        else:
            y2 = self.width
            
        cv2.imwrite(save_path, self.d.screenshot(format='opencv')[y1:y2, x1:x2, :]) # type: ignore
        self.log('已保存截图到:{0}'.format(save_path), 'debug')
            
    def 获取截图(self, x1:int|float=-1, y1:int|float=-1, x2:int|float=-1, y2:int|float=-1):
        img = self.d.screenshot(format='opencv')
        if x1 != -1:
            x1 = int(self.height*x1) if isinstance(x1, float) else x1
        else:
            x1 = 0
        if y1 != -1:
            y1 = int(self.width*y1) if isinstance(y1, float) else y1
        else:
            y1 = 0

        if x2 != -1:
            x2 = int(self.height*x2) if isinstance(x2, float) else x2
        else:
            x2 = self.height
        if y2 != -1:
            y2 = int(self.width*y2) if isinstance(y2, float) else y2
        else:
            y2 = self.width

        return img[y1:y2, x1:x2, :] # type: ignore
        
                     
    def 简单点击(self, x:int, y:int, *els):
        '''
        x,y:点击中心坐标
        els:处理其他无效参数
        '''
        X, Y = x, y
        self.d.click(X, Y)
        self.log('简单点击{0} {1}'.format(X, Y), 'debug')
    
    def 点击(self, center_x: int, center_y: int, loc: int, *els):
        '''
        center_x, center_y: 点击的目标中心坐标
        loc: 允许的随机半径范围（安全边界）
        els: 用于接收处理多余参数（如 w, h, sim 等，此处不使用但保证解包不报错）
        '''
        # 均值设为 0：因为我们要的是围绕传入的 center 坐标向四周做正态分布扩散
        # 标准差设为 loc / 3.0：确保 99.7% 的点击点严格落在安全半径内
        sigma = max(1.0, loc / 3.0)
        
        offset_x = np.random.normal(0, sigma)
        offset_y = np.random.normal(0, sigma)
        
        # 安全截断：物理防御，斩断正态分布极端大值引发的出界可能
        offset_x = np.clip(offset_x, -loc, loc)
        offset_y = np.clip(offset_y, -loc, loc)

        # 在中心点基础上施加随机偏移
        X = int(center_x + offset_x)
        Y = int(center_y + offset_y)

        # 执行物理触控
        self.d.touch.down(X, Y)
        # 短暂延迟模拟人类点击习惯，增加随机性
        time.sleep(np.random.uniform(0.05, 0.15))
        self.d.touch.up(X, Y)

        self.log(f'模拟点击({X}, {Y})', 'debug')

    def 长按(self, x:int, y:int, duration:float=1.5, jitter:float=0.1):
        '''
        长按指定坐标，持续时间可选，默认1.5秒
        jitter: 随机时间前后偏移值，默认0.1
        '''
        self.d.touch.down(x, y)
        duration += np.random.uniform(-jitter, jitter)
        time.sleep(duration)
        self.d.touch.up(x, y)
        self.log(f'模拟长按({x}, {y})', 'debug')

    def 滑动(self, start_x:int, start_y:int, end_x:int, end_y:int, count:int=30, delay:float=0.01):
        '''
        start_x, start_y 为起始坐标,
        end_x, end_y 为终点坐标,
        count 决定了轨迹的细腻程度（点越多越慢越丝滑）
        delay 决定了每次移动的间隔时间（单位：秒，值越大越慢）
        '''
        points = self.bz.trackArray((start_x, start_y), (end_x, end_y), count)['trackArray']
        # 首先：手指按下
        self.d.touch.down(start_x, start_y)
        # 其次：遍历轨迹点进行移动
        for x, y in points:
            self.d.touch.move(x, y)
            time.sleep(delay) 
        # 最后：手指抬起
        self.d.touch.up(end_x, end_y)
        self.log('模拟滑动{0} {1} -> {2} {3}'.format(start_x, start_y, end_x, end_y), 'debug')
        
    def 输入(self, txt:str):
        self.d.clear_text() # 清除输入框所有内容
        self.d.send_keys(txt)
        self.d.send_action("send") # 根据输入框的需求，自动执行回车、搜索等指令,支持 go, search, send, next, done, previous
        self.log('模拟输入{0}'.format(txt), 'debug')
        
    def adb命令行(self, shell:str):
        '''
        执行命令行：在adb shell中执行
        示例：input tap 100 100
        '''
        shell = f"adb -s {self.device_id} shell {shell}"
        os.system(shell)
        self.log('执行命令行:{0}'.format(shell), 'debug')

    def _parse_screen_from_filename(self, filename):
        """
        从文件名提取屏幕参数（格式：xxx_WxH.png）
        :param filename: 文件名
        :return: (screen_width, screen_height)，如果无法解析则返回 (None, None)
        """
        import re
        # 匹配格式：xxx_1920x1080.png 或 xxx_1080x1920.jpg
        pattern = r'_(\d+)x(\d+)\.'
        match = re.search(pattern, filename)
        if match:
            w = int(match.group(1))
            h = int(match.group(2))
            return w, h
        return None, None
    
    def 图片预加载(self, *images):
        '''
        在进入 while 循环前，一次性把所有图片读入内存并转为灰度图。
        避免在 while 循环中频繁进行磁盘 I/O 和色彩空间转换。
        
        调用方式：
            self.op.图片预加载(图片1, 图片2, 图片3, ...)

        支持类型：
            1. 图片路径字符串
            2. cv2 数组
            3. PIL 图片对象
        '''
        self.cached_templates.clear()
        failed_count = 0
        img_index = 0
        for img in images:
            check_stop(self)
            gray_img = None
            screen_width = None
            screen_height = None
            try:
                if isinstance(img, str):
                    if not os.path.exists(img) and self.mode == "more":
                        self.log(f"警告：图片文件不存在 - {img}", 'warning')
                        failed_count += 1
                        continue
                    img_name = os.path.basename(img)
                    # 从文件名提取屏幕参数（格式：xxx_WxH.png）
                    screen_width, screen_height = self._parse_screen_from_filename(img_name)
                    # 用 np.fromfile + cv2.imdecode 替代 cv2.imread
                    # 解决 Windows 下 cv2.imread 不支持中文路径的问题
                    img_data = np.fromfile(img, dtype=np.uint8)
                    gray_img = cv2.imdecode(img_data, cv2.IMREAD_GRAYSCALE)
                    if gray_img is None:
                        self.log(f"警告：图片读取失败 - {img}", 'warning')
                        failed_count += 1
                        continue
                elif isinstance(img, bytes):
                    img_name = f"uploaded_image_{img_index}"
                    img_array = np.frombuffer(img, np.uint8)
                    color_img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    if color_img is not None:
                        gray_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2GRAY)
                    else:
                        if self.mode == "more":
                            self.log(f"警告：字节图片解码失败 - {img_name}", 'warning')
                        failed_count += 1
                        continue
                elif isinstance(img, np.ndarray):
                    img_name = f"cv2_array_{img_index}"
                    if len(img.shape) == 2:
                        gray_img = img
                    else:
                        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                elif hasattr(img, 'read'):
                    img_name = img.filename or "uploaded_image"
                    img_bytes = img.read()
                    img_array = np.frombuffer(img_bytes, np.uint8)
                    color_img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    if color_img is not None:
                        gray_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2GRAY)
                    else:
                        if self.mode == "more":
                            self.log(f"警告：上传图片解码失败 - {img_name}", 'warning')
                        failed_count += 1
                        continue
                elif hasattr(img, 'tobytes'):
                    img_name = f"pil_image_{img_index}"
                    img_array = np.array(img)
                    if len(img_array.shape) == 2:
                        gray_img = img_array
                    elif img_array.shape[2] == 4:
                        gray_img = cv2.cvtColor(img_array, cv2.COLOR_RGBA2GRAY)
                    else:
                        gray_img = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
                else:
                    if self.mode == "more":
                        self.log(f"警告：不支持的图片类型 - {type(img)}", 'warning')
                    failed_count += 1
                    continue
                
                self.cached_templates[img_name] = {
                    'img': gray_img,
                    'h': gray_img.shape[0],
                    'w': gray_img.shape[1],
                    'screen_width': screen_width,
                    'screen_height': screen_height
                }
                # 构建模板金字塔（仅对大于等于50x50的图构建）
                if gray_img.shape[0] >= 50 and gray_img.shape[1] >= 50:
                    self._build_pyramid(img_name, {
                        'img': gray_img,
                        'h': gray_img.shape[0],
                        'w': gray_img.shape[1],
                        'screen_width': screen_width,
                        'screen_height': screen_height
                    })
                img_index += 1
            except Exception as e:
                self.log(f"警告：加载图片失败 - {img if isinstance(img, str) else type(img)}: {e}", 'warning')
                failed_count += 1
        
        self.log(f"成功预加载了 {len(self.cached_templates)} 张模板图片。", 'debug')
        # 强制重新计算分辨率适配，确保缩放比例与当前屏幕匹配
        self._adapt_resolution()       

    def _match_by_orb(self, main_gray, img_name, temp_info, sim, offset_x=0, offset_y=0):
        '''
        使用 ORB 特征匹配（对尺寸变化更鲁棒）
        适用于缩放后尺寸过小的模板图
        '''
        template = temp_info['img']
        
        # 使用缓存的 ORB 检测器
        orb = self._get_orb_detector()
        
        # 检测关键点和描述符
        kp1, des1 = orb.detectAndCompute(template, None)
        kp2, des2 = orb.detectAndCompute(main_gray, None)
        
        if des1 is None or des2 is None or len(kp1) < 3 or len(kp2) < 10:
            if self.mode == "more":
                self.log(f"找图失败(ORB): {img_name} (关键点不足)", 'warning')
            return None
        
        # 使用缓存的 BFMatcher
        bf = self._get_bf_matcher()
        matches = bf.match(des1, des2)
        
        if len(matches) < 3:
            if self.mode == "more":
                self.log(f"找图失败(ORB): {img_name} (匹配点不足)", 'warning')
            return None
        
        # 按匹配距离排序
        matches = sorted(matches, key=lambda x: x.distance)
        
        # 计算匹配率（好匹配占比）
        # 距离阈值设为 40，允许更多匹配点
        good_matches = [m for m in matches if m.distance < 40]
        
        if len(good_matches) < 3:
            if self.mode == "more":
                self.log(f"找图失败(ORB): {img_name} (好匹配点不足)", 'warning')
            return None
        
        match_ratio = len(good_matches) / len(kp1)
        
        # 匹配率阈值：至少需要 sim*0.4 的匹配率
        if match_ratio < (sim * 0.4):
            if self.mode == "more":
                self.log(f"找图失败(ORB): {img_name} (匹配率:{match_ratio:.4f})", 'warning')
            return None
        
        # 获取匹配点坐标
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        
        # 使用 RANSAC 计算单应性矩阵
        try:
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        except:
            if self.mode == "more":
                self.log(f"找图失败(ORB): {img_name} (单应性矩阵计算失败)", 'warning')
            return None
        
        if M is None:
            if self.mode == "more":
                self.log(f"找图失败(ORB): {img_name} (单应性矩阵为空)", 'warning')
            return None
        
        # 获取模板四个角在大图中的位置
        h, w = template.shape[:2]
        pts = np.float32([[0, 0], [0, h - 1], [w - 1, h - 1], [w - 1, 0]]).reshape(-1, 1, 2)
        dst = cv2.perspectiveTransform(pts, M)
        
        # 计算中心点
        dst = dst.reshape(4, 2)
        center_x = int(np.mean(dst[:, 0])) + offset_x
        center_y = int(np.mean(dst[:, 1])) + offset_y
        
        # 计算宽高
        w_resized = int(np.linalg.norm(dst[0] - dst[3]))
        h_resized = int(np.linalg.norm(dst[0] - dst[1]))
        
        # 计算匹配半径
        min_side = min(w_resized, h_resized)
        r = int((min_side // 2) * 0.8)
        r = max(r, 5)
        
        if self.mode == "more":
            self.log(f"找图成功(ORB): {img_name} (匹配率:{match_ratio:.4f})", 'debug')
        
        return img_name, (center_x, center_y, r, w_resized, h_resized, float(match_ratio))
    
    def _match_single_task(self, main_gray, img_name, sim, offset_x=0, offset_y=0, priority_corner='tl'):
        '''
        多线程内部执行的单张图匹配任务
        :param offset_x, offset_y: 局部截图相对于全屏的偏移量
        :param priority_corner: 角优先度，可选 'tl', 'tr', 'bl', 'br'，默认左上角tl
        '''
        temp_info = self.cached_templates.get(img_name)
        if not temp_info:
            return None
        if self.current_scale is None:
            raise RaiseError("未锁定分辨率，请先调用'适配分辨率(adapt_res_everytime)'方法进行测算！")
        
        h_main, w_main = main_gray.shape[:2]

        # 移除小图特殊处理，让所有尺寸的图片都参与正常的模板匹配流程
        # 小图（如 164x37 的二星图标）也能通过模板匹配找到，不需要特殊处理
        # if temp_info['w'] < 50 or temp_info['h'] < 50:
        #     ...

        base_scale_x = getattr(self, 'current_scale_x', self.current_scale)
        base_scale_y = getattr(self, 'current_scale_y', self.current_scale)
        
        # 计算平均缩放因子
        avg_scale = (base_scale_x + base_scale_y) / 2

        # ========== 优化策略：先尝试原始尺寸直接匹配 ==========
        # 直接用原始模板尺寸在大图中搜索，避免缩放带来的撕裂和精度损失
        # 这是解决"大图放大小图匹配度低"问题的关键改进
        # 原理：模板是基准分辨率(1920x1080)的，当截图分辨率 > 基准分辨率时（scale_factor >= 1），
        # 截图中目标的实际尺寸 = 模板尺寸 * scale_factor，
        # 直接用原始模板匹配相当于在大图中搜索模板大小的区域，匹配到的位置是模板左上角在截图中的坐标
        # 但实际目标尺寸是模板尺寸 * scale_factor，所以需要用实际尺寸计算中心坐标
        # 注意：只有当 scale_factor >= 1 时才适用（截图分辨率 >= 基准分辨率），
        # 当 scale_factor < 1 时，模板尺寸 > 截图中目标尺寸，直接匹配会出错
        direct_max_val = 0.0
        direct_result = None
        
        # 只有当 scale_factor >= 1 时才尝试原始尺寸直接匹配
        if avg_scale >= 1.0 and temp_info['w'] <= w_main and temp_info['h'] <= h_main:
            direct_result = cv2.matchTemplate(main_gray, temp_info['img'], cv2.TM_CCOEFF_NORMED)
            _, direct_max_val, _, _ = cv2.minMaxLoc(direct_result)
        
        # 如果原始尺寸匹配度已经很高，直接返回（避免缩放带来的精度损失）
        # 关键修正：匹配坐标是模板左上角在截图中的位置，
        # 但实际目标尺寸是模板尺寸 * 缩放因子，所以需要用实际尺寸计算中心坐标
        if direct_result is not None and direct_max_val >= sim:
            if self.mode == "more":
                self.log(f"找图成功(原始尺寸): {img_name} (匹配度:{direct_max_val:.4f})", 'debug')
            
            # 使用实际匹配度作为阈值，确保选择匹配度最高的位置
            locations = np.where(direct_result >= direct_max_val)
            best_dist = float('inf')
            best_loc = None
            best_val = 0
            
            for y, x in zip(*locations):
                val = direct_result[y, x]
                if priority_corner == 'tl':
                    dist = x + y
                elif priority_corner == 'tr':
                    dist = (w_main - x) + y
                elif priority_corner == 'bl':
                    dist = x + (h_main - y)
                elif priority_corner == 'br':
                    dist = (w_main - x) + (h_main - y)
                else:
                    dist = x + y
                
                if dist < best_dist or (dist == best_dist and val > best_val):
                    best_dist = dist
                    best_loc = (x, y)
                    best_val = val
            
            if best_loc:
                match_x, match_y = best_loc
                # 计算实际目标尺寸（模板尺寸 * 缩放因子）
                actual_w = int(temp_info['w'] * base_scale_x)
                actual_h = int(temp_info['h'] * base_scale_y)
                
                # 中心坐标 = 匹配位置 + 实际尺寸的一半 + 偏移量
                center_x = int(match_x + actual_w // 2) + offset_x
                center_y = int(match_y + actual_h // 2) + offset_y
                
                # 计算匹配半径
                min_side = min(actual_w, actual_h)
                r = int((min_side // 2) * 0.8)
                r = max(r, 5)
                
                return img_name, (center_x, center_y, r, actual_w, actual_h, float(best_val))
        
        # ========== 智能双向匹配策略（作为 fallback，与原始尺寸匹配比较） ==========
        # - 当缩放因子 > 1（需要放大模板）：缩小截图，保持模板细节完整
        # - 当缩放因子 <= 1（需要缩小模板）：缩小模板，保持截图细节完整
        
        # 初始化最佳匹配结果
        best_match = None
        best_match_val = max(direct_max_val, 0.0)
        
        if avg_scale > 1.0:
            # 方案A：缩小截图，保持模板原始分辨率
            # 计算需要将截图缩小到的尺寸
            scale_down_x = 1.0 / base_scale_x
            scale_down_y = 1.0 / base_scale_y
            
            target_w = int(w_main * scale_down_x)
            target_h = int(h_main * scale_down_y)
            
            if target_w >= temp_info['w'] and target_h >= temp_info['h']:
                # 使用 INTER_AREA 缩小截图，效果最好
                resized_main = cv2.resize(main_gray, (target_w, target_h), interpolation=cv2.INTER_AREA)
                
                # 直接使用原始模板匹配
                result = cv2.matchTemplate(resized_main, temp_info['img'], cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                
                if max_val > best_match_val:
                    best_match_val = max_val
                    best_match = ('scale_down', result, temp_info['w'], temp_info['h'], 
                                  target_w, target_h, scale_down_x, scale_down_y)
            
            # fallback 搜索：搜索缩小比例
            if best_match_val < 0.85:
                search_range = np.arange(-0.15, 0.151, 0.05)
                
                for dx in search_range:
                    check_stop(self)
                    sdx = scale_down_x + dx
                    if sdx <= 0.1 or sdx >= 0.8:
                        continue
                    
                    sdw = int(w_main * sdx)
                    sdh = int(h_main * sdx)
                    if sdw < temp_info['w'] or sdh < temp_info['h']:
                        continue
                    
                    resized_m = cv2.resize(main_gray, (sdw, sdh), interpolation=cv2.INTER_AREA)
                    fallback_result = cv2.matchTemplate(resized_m, temp_info['img'], cv2.TM_CCOEFF_NORMED)
                    _, f_max_val, _, _ = cv2.minMaxLoc(fallback_result)
                    
                    if f_max_val > best_match_val:
                        best_match_val = f_max_val
                        best_match = ('scale_down', fallback_result, temp_info['w'], temp_info['h'], 
                                      sdw, sdh, sdx, sdx)
        else:
            # 方案B：放大截图到基准分辨率，保持模板原始细节（修复细节丢失问题）
            # 计算需要将截图放大到的尺寸（基准分辨率）
            scale_up_x = 1.0 / base_scale_x
            scale_up_y = 1.0 / base_scale_y
            
            target_w = int(w_main * scale_up_x)
            target_h = int(h_main * scale_up_y)
            
            if target_w >= temp_info['w'] and target_h >= temp_info['h']:
                # 使用 INTER_CUBIC 放大截图，保持细节
                resized_main = cv2.resize(main_gray, (target_w, target_h), interpolation=cv2.INTER_CUBIC)
                
                # 直接使用原始模板匹配
                result = cv2.matchTemplate(resized_main, temp_info['img'], cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                
                if max_val > best_match_val:
                    best_match_val = max_val
                    best_match = ('scale_up', result, temp_info['w'], temp_info['h'], 
                                  target_w, target_h, scale_up_x, scale_up_y)
            
            # fallback 搜索：搜索放大比例的微调
            if best_match_val < 0.85:
                search_range = np.arange(-0.15, 0.151, 0.05)

                for dx in search_range:
                    check_stop(self)
                    sdx = scale_up_x + dx
                    if sdx <= 0.5 or sdx >= 2.0:
                        continue
                    
                    sdw = int(w_main * sdx)
                    sdh = int(w_main * sdx * (h_main / w_main))  # 保持宽高比
                    if sdw < temp_info['w'] or sdh < temp_info['h']:
                        continue
                    
                    resized_m = cv2.resize(main_gray, (sdw, sdh), interpolation=cv2.INTER_CUBIC)
                    fallback_result = cv2.matchTemplate(resized_m, temp_info['img'], cv2.TM_CCOEFF_NORMED)
                    _, f_max_val, _, _ = cv2.minMaxLoc(fallback_result)
                    
                    if f_max_val > best_match_val:
                        best_match_val = f_max_val
                        best_match = ('scale_up', fallback_result, temp_info['w'], temp_info['h'], 
                                      sdw, sdh, sdx, sdx)
        
        # ========== 最终比较：选择最佳匹配结果 ==========
        # 优先选择原始尺寸匹配，其次选择缩放匹配
        # 如果两者都有结果，选择匹配度更高的
        if direct_result is not None and direct_max_val >= sim:
            if self.mode == "more":
                self.log(f"找图成功(原始尺寸): {img_name} (匹配度:{direct_max_val:.4f})", 'debug')
            return self._select_best_location(
                direct_result, temp_info['w'], temp_info['h'], sim,
                priority_corner, w_main, h_main, offset_x, offset_y, img_name
            )
        
        # 使用用户传入的匹配阈值，而不是硬编码
        if best_match is not None and best_match_val >= sim:
            match_type, result, w_resized, h_resized, w_main_res, h_main_res, scale_x, scale_y = best_match
            if self.mode == "more":
                if match_type == 'scale_down':
                    self.log(f"找图成功(缩放-缩小截图): {img_name} (匹配度:{best_match_val:.4f})")
                elif match_type == 'scale_up':
                    self.log(f"找图成功(缩放-放大截图): {img_name} (匹配度:{best_match_val:.4f})")
                else:
                    self.log(f"找图成功(缩放-缩小模板): {img_name} (匹配度:{best_match_val:.4f})")
            
            # 使用实际匹配度作为阈值，确保选择匹配度最高的位置，而不是角优先度最高的位置
            # 这样可以避免因为角优先度导致的坐标偏移问题
            if match_type == 'scale_down' or match_type == 'scale_up':
                return self._select_best_location_with_scale(
                    result, w_resized, h_resized, best_match_val,
                    priority_corner, w_main_res, h_main_res, offset_x, offset_y, img_name,
                    scale_x, scale_y
                )
            else:
                    return self._select_best_location(
                        result, w_resized, h_resized, best_match_val,
                        priority_corner, w_main_res, h_main_res, offset_x, offset_y, img_name
                    )
        
        if self.mode == "more":
            self.log(f"找图失败: {img_name} (原始尺寸匹配度:{direct_max_val:.4f}, 缩放匹配度:{best_match_val:.4f})", 'warning')
        return None
    
    def _select_best_location(self, result, w_resized, h_resized, threshold, 
                             priority_corner, w_main, h_main, offset_x, offset_y, img_name):
        """
        根据角优先度选择最佳匹配位置
        """
        locations = np.where(result >= threshold)
        
        best_dist = float('inf')
        best_loc = None
        best_val = 0
        
        for y, x in zip(*locations):
            val = result[y, x]
            if priority_corner == 'tl':
                dist = x + y
            elif priority_corner == 'tr':
                dist = (w_main - x) + y
            elif priority_corner == 'bl':
                dist = x + (h_main - y)
            elif priority_corner == 'br':
                dist = (w_main - x) + (h_main - y)
            else:
                dist = x + y
            
            if dist < best_dist or (dist == best_dist and val > best_val):
                best_dist = dist
                best_loc = (x, y)
                best_val = val
        
        if best_loc:
            x, y = best_loc
            center_x = int(x + w_resized // 2) + offset_x
            center_y = int(y + h_resized // 2) + offset_y
            
            min_side = min(w_resized, h_resized)
            r = int((min_side // 2) * 0.8)
            r = max(r, 5)
            return img_name, (center_x, center_y, r, w_resized, h_resized, float(best_val))
        
        return None
    
    def _select_best_location_with_scale(self, result, w_resized, h_resized, threshold,
                                         priority_corner, w_main, h_main, offset_x, offset_y, img_name,
                                         scale_down_x, scale_down_y):
        """
        根据角优先度选择最佳匹配位置（带缩放因子，用于缩小截图后匹配的坐标反向映射）
        :param scale_down_x, scale_down_y: 截图缩小的比例，用于反向映射回原始坐标
        """
        locations = np.where(result >= threshold)
        
        best_dist = float('inf')
        best_loc = None
        best_val = 0
        
        for y, x in zip(*locations):
            val = result[y, x]
            if priority_corner == 'tl':
                dist = x + y
            elif priority_corner == 'tr':
                dist = (w_main - x) + y
            elif priority_corner == 'bl':
                dist = x + (h_main - y)
            elif priority_corner == 'br':
                dist = (w_main - x) + (h_main - y)
            else:
                dist = x + y
            
            if dist < best_dist or (dist == best_dist and val > best_val):
                best_dist = dist
                best_loc = (x, y)
                best_val = val
        
        if best_loc:
            x, y = best_loc
            # 坐标反向映射回原始截图：除以缩小比例
            center_x = int((x + w_resized // 2) / scale_down_x) + offset_x
            center_y = int((y + h_resized // 2) / scale_down_y) + offset_y
            
            # 计算原始尺寸下的匹配半径
            orig_w = int(w_resized / scale_down_x)
            orig_h = int(h_resized / scale_down_y)
            min_side = min(orig_w, orig_h)
            r = int((min_side // 2) * 0.8)
            r = max(r, 5)
            return img_name, (center_x, center_y, r, orig_w, orig_h, float(best_val))
        
        return None
    

    def _adapt_resolution(self, sim=0.90, target_image=None):
        '''
        测算分辨率缩放比，支持分离的 scale_x 和 scale_y 以处理非均匀拉伸（如小窗模式）。
        :param sim: 匹配阈值，默认 0.90
        :param target_image: 指定图片，若为 None 则轮询库中所有图。
        '''
        if not self.cached_templates:
            raise RaiseError("缓存的模板库为空，请先调用'图片预加载'方法加载！")

        main_img = self.获取截图()
        main_gray = cv2.cvtColor(main_img, cv2.COLOR_BGR2GRAY)
        h_main, w_main = main_gray.shape[:2]

        screenshot_w, screenshot_h = w_main, h_main
        
        if self.mode == "more":
            self.log(f"截图分辨率: {screenshot_w}x{screenshot_h}", 'debug')

        template_base_w, template_base_h = 1920, 1080
        
        # 尝试从模板文件名中提取基准分辨率
        for img_name in list(self.cached_templates.keys()):
            temp = self.cached_templates.get(img_name)
            if temp and temp.get('screen_width') and temp.get('screen_height'):
                template_base_w = temp['screen_width']
                template_base_h = temp['screen_height']
                if self.mode == "more":
                    self.log(f"从模板文件名提取基准分辨率: {template_base_w}x{template_base_h}", 'debug')
                break

        scale_x = screenshot_w / template_base_w
        scale_y = screenshot_h / template_base_h
        
        self.current_scale_x = scale_x
        self.current_scale_y = scale_y
        self.current_scale = (scale_x + scale_y) / 2
        
        if self.mode == "more":
            self.log(f"默认缩放比: scale_x={scale_x:.4f}, scale_y={scale_y:.4f}, 统一比例={self.current_scale:.4f}", 'debug')

        test_images = [target_image] if target_image else list(self.cached_templates.keys())
        
        success_count = 0
        total_score = 0.0
        for img_name in test_images:
            temp = self.cached_templates.get(img_name)
            if not temp:
                continue
            
            # 降低最小尺寸限制，允许小图参与分辨率适配测试
            if temp['w'] < 20 or temp['h'] < 20:
                continue
            
            tw = int(temp['w'] * scale_x)
            th = int(temp['h'] * scale_y)
            if tw > w_main or th > h_main or tw < 10 or th < 10:
                continue
            
            resized = cv2.resize(temp['img'], (tw, th), 
                                interpolation=cv2.INTER_AREA if scale_x < 1.0 and scale_y < 1.0 else cv2.INTER_CUBIC)
            result = cv2.matchTemplate(main_gray, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            
            if max_val >= sim:
                success_count += 1
                total_score += max_val

        if success_count >= len(test_images) * 0.5:
            avg_score = total_score / success_count if success_count > 0 else 0
            if self.mode == "more":
                self.log(f"默认比例验证通过: {success_count}/{len(test_images)} 张匹配成功, 平均相似度={avg_score:.4f}", 'debug')
            return True

        if self.mode == "more":
            self.log(f"默认比例验证失败，进行优化搜索...", 'debug')
        
        # 使用一维搜索代替二维搜索，提升速度
        search_range = np.arange(-0.05, 0.051, 0.03)  # 步长从 0.02 增加到 0.03
        best_scale_x = scale_x
        best_scale_y = scale_y
        best_success = success_count
        best_score = total_score

        # 先搜索 x 方向（保持宽高比一致）
        for dx in search_range:
            check_stop(self)
            sx = scale_x + dx
            if sx <= 0.2 or sx >= 1.5:
                continue
            
            current_success = 0
            current_score = 0.0
            
            for img_name in test_images:
                temp = self.cached_templates.get(img_name)
                if not temp:
                    continue
                
                # 降低最小尺寸限制，允许小图参与分辨率适配测试
                if temp['w'] < 20 or temp['h'] < 20:
                    continue
                
                tw = int(temp['w'] * sx)
                th = int(temp['h'] * sx)  # 保持宽高比一致
                if tw > w_main or th > h_main or tw < 10 or th < 10:
                    continue
                
                # 尝试从金字塔获取
                py_temp = self._get_pyramid_template(img_name, sx, sx)
                if py_temp is not None:
                    resized = py_temp['img']
                else:
                    resized = cv2.resize(temp['img'], (tw, th), 
                                        interpolation=cv2.INTER_AREA if sx < 1.0 else cv2.INTER_CUBIC)
                result = cv2.matchTemplate(main_gray, resized, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                
                if max_val >= sim:
                    current_success += 1
                    current_score += max_val
            
            if current_success > best_success or \
               (current_success == best_success and current_score > best_score):
                best_success = current_success
                best_score = current_score
                best_scale_x = sx
                best_scale_y = sx

        # 如果 x 方向没找到更好的，再搜索 y 方向
        if best_success == success_count:
            for dy in search_range:
                check_stop(self)
                sy = scale_y + dy
                if sy <= 0.2 or sy >= 1.5:
                    continue
                
                current_success = 0
                current_score = 0.0
                
                for img_name in test_images:
                    temp = self.cached_templates.get(img_name)
                    if not temp:
                        continue
                    
                    # 降低最小尺寸限制，允许小图参与分辨率适配测试
                    if temp['w'] < 20 or temp['h'] < 20:
                        continue
                    
                    tw = int(temp['w'] * scale_x)
                    th = int(temp['h'] * sy)
                    if tw > w_main or th > h_main or tw < 10 or th < 10:
                        continue
                    
                    resized = cv2.resize(temp['img'], (tw, th), 
                                        interpolation=cv2.INTER_AREA if sy < 1.0 else cv2.INTER_CUBIC)
                    result = cv2.matchTemplate(main_gray, resized, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(result)
                    
                    if max_val >= sim:
                        current_success += 1
                        current_score += max_val
                
                if current_success > best_success or \
                   (current_success == best_success and current_score > best_score):
                    best_success = current_success
                    best_score = current_score
                    best_scale_y = sy

        self.current_scale_x = best_scale_x
        self.current_scale_y = best_scale_y
        self.current_scale = (best_scale_x + best_scale_y) / 2
        
        avg_score = best_score / best_success if best_success > 0 else 0
        if self.mode == "more":
            self.log(f"优化完成: scale_x={best_scale_x:.4f}, scale_y={best_scale_y:.4f}, 统一比例={self.current_scale:.4f}, "
                     f"{best_success}/{len(test_images)} 张匹配成功, 平均相似度={avg_score:.4f}", 'debug')
        
        return True

    def 找图(self, sim=0.90, priority_corner='tl', x1: int|float=-1, y1: int|float=-1, x2: int|float=-1, y2: int|float=-1) -> dict[str, tuple]:
        '''
        :param sim: 匹配阈值，默认 0.90
        :param priority_corner: 角优先度，可选 'tl', 'tr', 'bl', 'br'，默认左上角tl
        :param x1, y1, x2, y2: 截图区域坐标，默认为 -1 表示全屏
        返回值字典： {图名: (匹配坐标x, 匹配坐标y, 推荐点击半径r, 模板宽度, 模板高度, 匹配度)}
        '''
        if not self.cached_templates:
            raise RaiseError("没有可用的模板图片，请先调用'图片预加载'方法加载图片！")
            
        # 计算偏移量（局部截图相对于全屏的坐标偏移）
        offset_x = int(self.height * x1) if isinstance(x1, float) and x1 != -1 else (int(x1) if x1 != -1 else 0)
        offset_y = int(self.width * y1) if isinstance(y1, float) and y1 != -1 else (int(y1) if y1 != -1 else 0)
            
        # 已有分辨率，多线程并发极速找所有图
        output = {}
        img_names = list(self.cached_templates.keys())
        
        main_img = self.获取截图(x1, y1, x2, y2)
        main_gray = cv2.cvtColor(main_img, cv2.COLOR_BGR2GRAY) # type: ignore

        # 复用 init 里的线程池，避免 while 循环高频创建线程导致内存泄漏和 CPU 暴涨
        results = list(self.executor.map(lambda name: self._match_single_task(main_gray, name, sim, offset_x, offset_y, priority_corner), img_names))

        for result in results:
            if result:
                img_name, value = result
                output[img_name] = value
        if output:
            self.log(str(output), 'debug', source='找图')
        else:
            print(f"[DEBUG] [{self.device_id}_找图] 未匹配到任何图片")
        return output
    
    def 找字(self, x1: int|float = -1, y1: int|float = -1, x2: int|float = -1, y2: int|float = -1, Specified_image=None, target_txt: str = '', use_regex: bool = False):
        '''
        x1, y1, x2, y2: 截图区域坐标，默认为 -1 表示全屏
        Specified_image: 指定图片（如果不提供则使用当前截图）
        target_txt: 目标文本（如果不提供则返回所有文本框信息），支持正则表达式，返回值为匹配到的文本对应坐标或None
        use_regex: 是否启用正则匹配，默认为 False,;为True则返回值将为匹配到的文本列表，为False则返回匹配到的文本及其坐标
        '''
        
        if Specified_image:
            if isinstance(Specified_image, bytes):
                img_array = np.frombuffer(Specified_image, np.uint8)
                crop_img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            elif isinstance(Specified_image, np.ndarray):
                crop_img = Specified_image
            elif hasattr(Specified_image, 'tobytes'):
                crop_img = cv2.cvtColor(np.array(Specified_image), cv2.COLOR_RGB2BGR)
            else:
                crop_img = Specified_image
        else:
            crop_img = self.获取截图(x1, y1, x2, y2)
        result = self.engine(crop_img, use_det=True, use_cls=True, use_rec=True) # type: ignore
        
        # 兜底：如果 RapidOCR 完全没有识别到任何东西
        if not result or not hasattr(result, 'txts') or not result.txts: # type: ignore
            self.log("未识别到任何文本！", 'debug', source='找字')
            return None

        # 如果是全屏模式（-1 或 None），偏移量就是 0；如果是裁剪区域，偏移量就是左上角起点
        offset_x = int(self.height * x1) if (isinstance(x1, float) and x1 != -1) else (int(x1) if x1 != -1 else 0)
        offset_y = int(self.width * y1) if (isinstance(y1, float) and y1 != -1) else (int(y1) if y1 != -1 else 0)

        result_dict = {}
        try:
            for i in range(len(result.txts)): # type: ignore
                word = result.txts[i] # type: ignore
                box = result.boxes[i] # type: ignore
                
                # box[0] 为左上角 [x, y]，box[2] 为右下角 [x, y]
                abs_x1 = int(box[0][0]) + offset_x
                abs_y1 = int(box[0][1]) + offset_y
                abs_x2 = int(box[2][0]) + offset_x
                abs_y2 = int(box[2][1]) + offset_y
                
                # 计算你原本逻辑中的宽高半径（沿用你原本的逻辑输出）
                w, h = (abs_x2 - abs_x1) // 2, (abs_y2 - abs_y1) // 2
                r = w if w <= h else h
                
                # 写入返回字典
                result_dict[word] = (abs_x1, abs_y1, r)

            if target_txt == '':
                if result_dict:
                    self.log(str(result_dict), 'debug', source='找字')
                return result_dict
            else:
                # 启用正则匹配
                if use_regex:
                    matched_results = []
                    pattern = re.compile(target_txt)
                    for word in result_dict.keys():
                        if pattern.search(word):
                            matched_results.append(word)
                    if matched_results:
                        self.log(str(matched_results), 'debug', source='找字')
                    return matched_results
                else:
                    if result_dict:
                        self.log(str(result_dict.get(target_txt, None)), 'debug', source='找字')
                    return result_dict.get(target_txt, None)
                
        except Exception as e:
            self.log(f"文本识别逻辑处理出错: {e}", 'error', source='找字')
            return None