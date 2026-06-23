import uiautomator2 as u2
from rapidocr import RapidOCR
from module.decorators import *
from module.log import WebSocketLogManager

import cv2
import numpy as np

import os
import time 
from concurrent.futures import ThreadPoolExecutor


class ADB:
    adb_path = os.path.dirname(__file__)   # 取文件所在文件夹绝对路径
    
    # 用字典代替单一的 _instance，key 是传入的参数，value 是对应的实例
    _instances = {}

    def __new__(cls, adb_tcp: str = "None", mode: str = "less", max_workers=4, source: str = "server"):
        # 把传入的参数变成一个可哈希的 key（比如元组）
        cache_key = (adb_tcp or "None", mode, max_workers, source)
        
        # 如果这个参数组合没被实例化过，就新建一个
        if cache_key not in cls._instances:
            cls._instances[cache_key] = super().__new__(cls)
        # 返回这个参数对应的唯一实例
        return cls._instances[cache_key]

    def __init__(self, adb_tcp: str = "None", mode: str = "less", max_workers=4, source: str = "server"):
        # 由于 Python 机制，每次 return 缓存实例时，都会强制调用 __init__
        # 所以必须加一个标记，防止同一个实例被重复初始化
        if getattr(self, "_is_initialized", False):
            return
            
        self.mode = mode
        self.log_manager = WebSocketLogManager(source)
        self.bz = bezierTrajectory()

        self.max_workers = max_workers  
        self.current_scale = None       # 全局缓存的手机分辨率缩放比
        self.cached_templates = {}      # 缓存所有模板图的灰度矩阵和原始尺寸
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers) # 复用线程池，避免高频创建销毁
        
        try:
            if adb_tcp == "None":
                self.d = u2.connect()
            elif ':' not in adb_tcp and adb_tcp.isdigit():
                self.d = u2.connect(f'127.0.0.1:{adb_tcp}')
            else:
                self.d = u2.connect(adb_tcp)
                
            self.engine = RapidOCR()
            # 标记当前这个实例已经初始化完毕
            self._is_initialized = True
        except Exception as e:
            self.log(f'设备初始化失败, 请检查设备是否连接。原始错误: {e}', "error")
            # 从缓存字典里删掉这个失败的实例
            cache_key = (adb_tcp or "None", mode, source)
            ADB._instances.pop(cache_key, None)
            raise Exception(f"设备 {adb_tcp} 初始化失败") 

        # 获取并更新设备分辨率(竖屏状态)
        w, h = self.d.window_size()
        self.width = min(w, h)
        self.height = max(w, h)
        
        if self.mode == "more":
            self.log(f'设备初始化完成: 宽:{self.width}, 高:{self.height}')

    def log(self, message: str, level: str = "info"):
        """
        专用的日志函数，会同时输出到本地终端 + 推送到前端 WebSocket
        - message: 日志内容
        - level: info / success / warning / error
        """
        self.log_manager.log(message, level)

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

    def get_screenshot(self, x1:int, y1:int, x2:int, y2:int):
        return self.获取截图(x1, y1, x2, y2)
    
    def simple_click(self, x:int, y:int, r, *els):
        self.简单点击(x, y, r, *els)

    def click(self, x:int, y:int, loc:int, *els):
        self.点击(x, y, loc, *els)

    def swipe(self, start_x:int, start_y:int, end_x:int, end_y:int, count:int=30, delay:float=0.01):
        self.滑动(start_x, start_y, end_x, end_y, count, delay)

    def input_text(self, txt:str):
        self.输入(txt)

    def adb_shell(self, shell:str):
        self.adb命令行(shell)
    
    def color_match(self, match_img:str, pos:tuple, color_threshold:int=30):
        return self.比色(match_img, pos, color_threshold)
    
    def image_preloading(self, image_paths: list):
        self.图片预加载(image_paths)
    
    def find_image(self, sim=0.95, x1:int=-1, y1:int=-1, x2:int=-1, y2:int=-1):
        return self.找图(sim, x1, y1, x2, y2)
    
    def find_text(self, x1:int, y1:int, x2:int, y2:int, target_txt:str=''):
        return self.找字(x1, y1, x2, y2, target_txt)
    

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
    
    def 截图保存(self, save_path:str=adb_path, *point:tuple):
        if len(point) == 0:
            cv2.imwrite(save_path, self.d.screenshot(format='opencv')) # type: ignore
        else:
            cv2.imwrite(save_path, self.d.screenshot(format='opencv')[point[1]:point[3], point[0]:point[2]]) # type: ignore
        if self.mode == "more":
            self.log('已保存截图到:{0}'.format(save_path))
            
    def 获取截图(self, x1:int=-1, y1:int=-1, x2:int=-1, y2:int=-1):
        img = self.d.screenshot(format='opencv')
        # cv2.imshow('img', img)    # 显示图片
        if x1!=-1 and y1!=-1 and x2!=-1 and y2!=-1:
            x1 = int(self.height*x1) if isinstance(x1, float) else x1
            y1 = int(self.width*y1) if isinstance(y1, float) else y1
            x2 = int(self.height*x2) if isinstance(x2, float) else x2
            y2 = int(self.width*y2) if isinstance(y2, float) else y2
            return img[y1:y2, x1:x2] # type: ignore
        else:
            return img
        
                     
    def 简单点击(self, x:int, y:int, r, *els):
        '''
        x,y:点击中心坐标
        r:偏移值(一般取图片平均半径)
        els:处理其他无效参数
        '''
        X, Y = x+r, y+r
        self.d.click(X, Y)
        if self.mode == "more":
            self.log('快速点击{0} {1}'.format(X, Y))
              
    """def 点击(self, x:int, y:int, loc:int, *els):
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
        if self.mode == "more":
            self.log('模拟点击{0} {1}'.format(X, Y))"""
    
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

    def 滑动(self, start_x:int, start_y:int, end_x:int, end_y:int, count:int=30, delay:float=0.01):
        '''
        start_x, start_y 为起始坐标,
        end_x, end_y 为终点坐标,
        count 决定了轨迹的细腻程度（点越多越慢越丝滑）
        delay 决定了每次移动的间隔时间（单位：秒，值越大越慢）
        '''
        points = self.bz.trackArray((start_x, start_y), (end_x, end_y), count)
        # 首先：手指按下
        self.d.touch.down(start_x, start_y)
        # 其次：遍历轨迹点进行移动
        for x, y in points:
            # 适当微调间隔时间增加拟人感
            self.d.touch.move(x, y)
            time.sleep(0.01) 
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
        os.system(shell)
        if self.mode == "more":
            self.log('执行命令行:{0}'.format(shell))
    
    #@Loop()
    def 比色(self, match_img:str, pos:tuple=(), color_threshold:int=30):
        sub_image = cv2.imread(match_img)
        sub_image_size = sub_image.shape[:2] # type: ignore
        if pos == ():
            # 寻找match_img位置
            _result = self._match_single_task(cv2.cvtColor(self.获取截图(), cv2.COLOR_BGR2GRAY), sub_image, 0.9, os.path.basename(match_img), sub_image_size)[1] # type: ignore
            x1, y1, w, h = _result[0], _result[1], _result[3], _result[4]
            x2, y2 = x1+w, y1+h
        elif isinstance(pos, tuple):
            x1, y1, w, h = pos
            x2, y2 = x1+w, y1+h
        else:
            raise ValueError('match_img并非路径或元组')
        # 提取矩形区域
        rect_area = w * h
        roi = self.获取截图(x1,y1,x2,y2)
        
        # 简单地取平均颜色作为主要颜色
        main_color_roi = np.mean(roi, axis=(0, 1)).astype(int) # type: ignore
        main_color_sub = np.mean(sub_image, axis=(0, 1)).astype(int) # type: ignore
        # 计算颜色差值
        diff = np.sum(np.abs(main_color_roi - main_color_sub))
        if self.mode == "more":
            self.log('{0}匹配结果:{1}'.format(os.path.basename(match_img), diff))
        return diff < color_threshold
    

    def 图片预加载(self, image_paths: list):
        '''
        在进入 while 循环前，一次性把所有图片读入内存并转为灰度图。
        避免在 while 循环中频繁进行磁盘 I/O 和色彩空间转换。
        '''
        self._clear_cache() # 预加载前先清理缓存，避免旧图干扰新图
        for path in image_paths:
            if not os.path.exists(path):
                continue
            img_name = os.path.basename(path)
            # 直接以灰度图读入内存
            gray_img = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
            if gray_img is not None:
                # 缓存 灰度图矩阵、高度、宽度
                self.cached_templates[img_name] = {
                    'img': gray_img,
                    'h': gray_img.shape[0],
                    'w': gray_img.shape[1]
                }
        self.log(f"成功预加载了 {len(self.cached_templates)} 张模板图片。")
        self._adapt_resolution() # 预加载后立即适配一次分辨率，锁定缩放比，提升后续找图效率

    def _clear_cache(self):
        self.cached_templates.clear()
        self.current_scale = None
        self.log("已初始化预加载缓存。")

    def _match_single_task(self, main_gray, img_name, sim):
        '''
        多线程内部执行的单张图匹配任务
        '''
        temp_info = self.cached_templates.get(img_name)
        if not temp_info:
            return None
        if self.current_scale is None:
            raise RaiseError("未锁定分辨率，请先调用'适配分辨率(adapt_resolution)'方法进行测算！")
        
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
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= sim:
            x, y = max_loc
            # 算出绝对中心点坐标
            center_x = int(x + w_resized // 2)
            center_y = int(y + h_resized // 2)
            
            # 计算内切圆安全半径（即点击函数需要的 loc 范围）
            min_side = min(w_resized, h_resized)
            r = int((min_side // 2) * 0.8)
            r = max(r, 5) # 保底半径
            # 返回值格式： (图名, (匹配坐标x, 匹配坐标y, 推荐点击半径r, 模板宽度, 模板高度, 匹配度))
            return img_name, (center_x, center_y, r, w_resized, h_resized, float(max_val))
        return None
    

    def _adapt_resolution(self, sim=0.85, target_image=None):
        '''
        向外辐射式测算分辨率缩放比，每次运行仅在初始化时执行一次。
        :param sim: 匹配阈值
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
        # 手机画面适配基本不可能超出这个范围
        raw_scales = np.arange(0.5, 1.81, 0.02)
        
        # 极其粗暴且有效的排序：按距离 1.0 的远近升序排序！
        # 排序后的顺序为：[1.0, 0.98, 1.02, 0.96, 1.04, ... , 0.5, 1.8]
        scales = sorted(raw_scales, key=lambda x: abs(x - 1.0))

        global_best_val = -1
        global_best_scale = 1.0
        success_img_name = None

        # 4. 开始轮询
        for img_name in test_queue:
            temp = self.cached_templates[img_name]
            w_sub, h_sub = temp['w'], temp['h']
            
            local_best_val = -1
            local_best_scale = 1.0
            
            for scale in scales:
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

        # 5. 最终结果判定
        if global_best_val >= sim:
            self.current_scale = global_best_scale
            self.log(f"[适配成功] 已锁定当前手机缩放比为: {global_best_scale:.4f}，成功匹配图: {success_img_name} (相似度: {global_best_val:.2f})")
            return True
        else:
            raise RaiseError(f"[适配失败] 轮询了整个测试图库，在当前屏幕上均未找到匹配项。当前全库最高匹配度仅为: {global_best_val:.2f} (来自图: {success_img_name})")

    def 找图(self, sim=0.85, x1=-1, y1=-1, x2=-1, y2=-1) -> dict[str, tuple]:
        '''
        返回值字典： {图名: (匹配坐标x, 匹配坐标y, 推荐点击半径r, 模板宽度, 模板高度, 匹配度)}
        '''
        if not self.cached_templates:
            raise RaiseError("没有可用的模板图片，请先调用'图片预加载'方法加载图片！")
        
        # 没有锁定分辨率，先进行一次性测算
        if self.current_scale is None:
            self.current_scale = self._adapt_resolution(sim)
            
        # 已有分辨率，多线程并发极速找所有图
        output = {}
        img_names = list(self.cached_templates.keys())
        
        main_img = self.获取截图(x1, y1, x2, y2)
        main_gray = cv2.cvtColor(main_img, cv2.COLOR_BGR2GRAY) # type: ignore

        # 复用 init 里的线程池，避免 while 循环高频创建线程导致内存泄漏和 CPU 暴涨
        results = list(self.executor.map(lambda name: self._match_single_task(main_gray, name, sim), img_names))

        for result in results:
            if result:
                img_name, value = result
                output[img_name] = value

        if self.mode == "more":
            self.log(output) # type: ignore

        return output
    
    def 找字(self, x1: int = -1, y1: int = -1, x2: int = -1, y2: int = -1, target_txt: str = ''):
        '''
        x1, y1, x2, y2: 截图区域坐标，默认为 -1 表示全屏
        target_txt: 目标文本（如果不提供则返回所有文本框信息）
        '''
        crop_img = self.获取截图(x1, y1, x2, y2)
        result = self.engine(crop_img, use_det=True, use_cls=True, use_rec=True) # type: ignore
        
        # 兜底：如果 RapidOCR 完全没有识别到任何东西
        if not result or not hasattr(result, 'txts') or not result.txts: # type: ignore
            self.log("未识别到任何文本！")
            return {}

        # 如果是全屏模式（-1 或 None），偏移量就是 0；如果是裁剪区域，偏移量就是左上角起点
        offset_x = x1 if (x1 is not None and x1 != -1) else 0
        offset_y = y1 if (y1 is not None and y1 != -1) else 0

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

            if self.mode == "more":
                self.log(str(result_dict))

            if target_txt == '':
                return result_dict
            else:
                return result_dict.get(target_txt)
                
        except Exception as e:
            self.log(f"文本识别逻辑处理出错: {e}")
            return {}