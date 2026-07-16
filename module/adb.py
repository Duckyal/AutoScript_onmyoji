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
        
        if self.mode == "more":
            self.log(f'设备初始化完成: 宽:{self.width}, 高:{self.height}')

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
    def log(self, message: object, level: str = "info"):
        """
        专用的日志函数，会同时输出到本地终端 + 推送到前端 WebSocket
        - message: 日志内容
        - level: info / success / warning / error
        """
        # 调用 ws_manager
        if self.log_manager:
            self.log_manager.log(message, level, self.device_id)

    # ============================================================================================
    # ============================================================================================

    # API en-US
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
    
    def find_image(self, sim=0.95, x1:int|float=-1, y1:int|float=-1, x2:int|float=-1, y2:int|float=-1):
        '''
        sim: 图片相似度，默认为 0.95
        x1, y1, x2, y2: 截图区域坐标，默认为 -1 表示全屏
        '''
        return self.找图(sim, x1, y1, x2, y2)
    
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
        if self.mode == "more":
            self.log('启动应用:{0}'.format(package_name))
        
    def 关闭应用(self, package_name:str):
        if package_name == 'all':
            self.d.app_stop_all()
            if self.mode == "more":
                self.log('关闭全部用户应用')
        else:
            self.d.app_stop(package_name)
            if self.mode == "more":
                self.log('关闭应用:{0}'.format(package_name))
                
    def 息屏(self):
        self.d.screen_off()
        if self.mode == "more":
            self.log('已息屏')
    
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
        if self.mode == "more":
            self.log('已保存截图到:{0}'.format(save_path))
            
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
        if self.mode == "more":
            self.log('简单点击{0} {1}'.format(X, Y))
    
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

        if self.mode == "more":
            self.log(f'模拟点击({X}, {Y})')

    def 长按(self, x:int, y:int, duration:float=1.5, jitter:float=0.1):
        '''
        长按指定坐标，持续时间可选，默认1.5秒
        jitter: 随机时间前后偏移值，默认0.1
        '''
        self.d.touch.down(x, y)
        duration += np.random.uniform(-jitter, jitter)
        time.sleep(duration)
        self.d.touch.up(x, y)
        if self.mode == "more":
            self.log(f'模拟长按({x}, {y})')

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
        if self.mode == "more":
            self.log('模拟滑动{0} {1} -> {2} {3}'.format(start_x, start_y, end_x, end_y))
        
    def 输入(self, txt:str):
        self.d.clear_text() # 清除输入框所有内容
        self.d.send_keys(txt)
        self.d.send_action("send") # 根据输入框的需求，自动执行回车、搜索等指令,支持 go, search, send, next, done, previous
        if self.mode == "more":
            self.log('模拟输入{0}'.format(txt))
        
    def adb命令行(self, shell:str):
        '''
        执行命令行：在adb shell中执行
        示例：input tap 100 100
        '''
        shell = f"adb -s {self.device_id} shell {shell}"
        os.system(shell)
        if self.mode == "more":
            self.log('执行命令行:{0}'.format(shell))

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
            try:
                if isinstance(img, str):
                    if not os.path.exists(img):
                        self.log(f"警告：图片文件不存在 - {img}")
                        failed_count += 1
                        continue
                    img_name = os.path.basename(img)
                    gray_img = cv2.imread(img, cv2.IMREAD_GRAYSCALE)
                    if gray_img is None:
                        self.log(f"警告：图片读取失败 - {img}")
                        failed_count += 1
                        continue
                elif isinstance(img, bytes):
                    img_name = f"uploaded_image_{img_index}"
                    img_array = np.frombuffer(img, np.uint8)
                    color_img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                    if color_img is not None:
                        gray_img = cv2.cvtColor(color_img, cv2.COLOR_BGR2GRAY)
                    else:
                        self.log(f"警告：字节图片解码失败")
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
                        self.log(f"警告：上传图片解码失败 - {img_name}")
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
                    self.log(f"警告：不支持的图片类型 - {type(img)}")
                    failed_count += 1
                    continue
                
                self.cached_templates[img_name] = {
                    'img': gray_img,
                    'h': gray_img.shape[0],
                    'w': gray_img.shape[1]
                }
                img_index += 1
            except Exception as e:
                self.log(f"警告：加载图片失败 - {img if isinstance(img, str) else type(img)}: {e}")
                failed_count += 1
        
        self.log(f"成功预加载了 {len(self.cached_templates)} 张模板图片。")
        if self.current_scale is None or self.adapt_res_everytime:
            self._adapt_resolution()       

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
        
        # 此时 self.current_scale 必然已经被主线程锁定了
        scale = self.current_scale
        w_resized = int(temp_info['w'] * scale)
        h_resized = int(temp_info['h'] * scale)

        # 边界安全拦截
        h_main, w_main = main_gray.shape[:2]
        if w_resized > w_main or h_resized > h_main or w_resized < 10 or h_resized < 10:
            return None

        # 缩放模板（由于是已知缩放比，单次执行，速度极快）
        resized_sub = cv2.resize(temp_info['img'], (w_resized, h_resized), 
                                 interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC)
        
        result = cv2.matchTemplate(main_gray, resized_sub, cv2.TM_CCOEFF_NORMED)
        
        # 找出所有匹配度超过阈值的点
        locations = np.where(result >= sim)
        
        if len(locations[0]) == 0:
            return None
        
        # 根据角优先度选择最近的点
        h_main, w_main = main_gray.shape[:2]
        best_dist = float('inf')
        best_loc = None
        best_val = 0
        
        for y, x in zip(*locations):
            val = result[y, x]
            # 计算到目标角的距离
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
            # 算出绝对中心点坐标（加上偏移量）
            center_x = int(x + w_resized // 2) + offset_x
            center_y = int(y + h_resized // 2) + offset_y
            
            # 计算内切圆安全半径（即点击函数需要的 loc 范围）
            min_side = min(w_resized, h_resized)
            r = int((min_side // 2) * 0.8)
            r = max(r, 5) # 保底半径
            # 返回值格式： (图名, (匹配坐标x, 匹配坐标y, 推荐点击半径r, 模板宽度, 模板高度, 匹配度))
            return img_name, (center_x, center_y, r, w_resized, h_resized, float(best_val))
        return None
    

    def _adapt_resolution(self, sim=0.95, target_image=None):
        '''
        向外辐射式测算分辨率缩放比，每次运行仅在初始化时执行一次。
        :param sim: 匹配阈值，默认 0.95
        :param target_image: 指定图片，若为 None 则轮询库中所有图。
        '''
        if not self.cached_templates:
            raise RaiseError("缓存的模板库为空，请先调用'图片预加载'方法加载！")

        # 确定测试队列
        test_queue = []
        if target_image is not None:
            base_name = os.path.basename(target_image)
            if base_name in self.cached_templates:
                test_queue.append(base_name)
            else:
                self.log(f"指定图不在缓存中，切换为全库自动轮询。")
        
        if not test_queue:
            test_queue = list(self.cached_templates.keys())

        # 获取当前大图并灰度化
        main_img = self.获取截图()
        main_gray = cv2.cvtColor(main_img, cv2.COLOR_BGR2GRAY) # type: ignore
        h_main, w_main = main_gray.shape[:2]

        # 生成精准的缩放比例队列（从 0.5 到 1.8，步长 0.02）
        raw_scales = np.arange(0.5, 1.81, 0.02)
        
        # 极其粗暴且有效的排序：按距离 1.0 的远近升序排序！
        # 排序后的顺序为：[1.0, 0.98, 1.02, 0.96, 1.04, ... , 0.5, 1.8]
        scales = sorted(raw_scales, key=lambda x: abs(x - 1.0))

        global_best_val = -1
        global_best_scale = 1.0
        success_img_name = None

        # 轮询
        for img_name in test_queue:
            temp = self.cached_templates[img_name]
            w_sub, h_sub = temp['w'], temp['h']
            
            local_best_val = -1
            local_best_scale = 1.0
            
            for scale in scales:
                check_stop(self)  # 检查是否需要中断
                # 计算缩放后的目标尺寸
                w_resized = int(w_sub * scale)
                h_resized = int(h_sub * scale)
                
                # 过滤不合法的尺寸：不能超过大图，且不能缩得太小变成马赛克
                if w_resized > w_main or h_resized > h_main or w_resized < 15 or h_resized < 15:
                    continue
                    
                # 缩放模板图
                resized_sub = cv2.resize(temp['img'], (w_resized, h_resized), 
                                         interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC)
                
                # 模板匹配
                result = cv2.matchTemplate(main_gray, resized_sub, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(result)
                
                # 记录当前图片的最优解
                if max_val > local_best_val:
                    local_best_val = max_val
                    local_best_scale = scale
                    
                    # 只要 >= 0.98 认为就是原图或极度精准匹配，立刻断开当前图的后续测试
                    if local_best_val >= 0.98: 
                        break
            
            # 汇总到全局最优解
            if local_best_val > global_best_val:
                global_best_val = local_best_val
                global_best_scale = local_best_scale
                success_img_name = img_name
            
            # 只要当前图测出的最高分已经达到了用户要求的阈值（sim），说明分辨率已经锁定，直接结束全盘轮询！
            if global_best_val >= sim:
                break

        if global_best_val >= sim:
            self.current_scale = global_best_scale
            self.log(f"已锁定当前手机缩放比为: {global_best_scale:.4f}，成功匹配图: {success_img_name} (相似度: {global_best_val:.2f})")
            return True
        else:
            raise RaiseError(f"轮询了整个测试图库，在当前屏幕上均未找到匹配项。当前全库最高匹配度仅为: {global_best_val:.2f} (来自图: {success_img_name})")

    def 找图(self, sim=0.95, x1: int|float=-1, y1: int|float=-1, x2: int|float=-1, y2: int|float=-1, priority_corner='top-left') -> dict[str, tuple]:
        '''
        :param sim: 匹配阈值，默认 0.95 
        :param x1, y1, x2, y2: 截图区域坐标，默认为 -1 表示全屏
        :param priority_corner: 角优先度，可选 'tl', 'tr', 'bl', 'br'，默认左上角tl
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

        if self.mode == "more" and output:
            self.log(str(output))

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
            self.log("未识别到任何文本！")
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
                if self.mode == "more" and result_dict:
                    self.log(str(result_dict))
                return result_dict
            else:
                # 启用正则匹配
                if use_regex:
                    matched_results = []
                    pattern = re.compile(target_txt)
                    for word in result_dict.keys():
                        if pattern.search(word):
                            matched_results.append(word)
                    if self.mode == "more" and matched_results:
                        self.log(str(matched_results))
                    return matched_results
                else:
                    if self.mode == "more" and result_dict:
                        self.log(str(result_dict.get(target_txt, None)))
                    return result_dict.get(target_txt, None)
                
        except Exception as e:
            self.log(f"文本识别逻辑处理出错: {e}")
            return None