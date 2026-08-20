"""
自定义任务解释器
========================
根据前端「自定义任务」面板生成的 steps JSON 数组，按顺序执行每一步。
支持的步骤类型（与 static/js/home/custom.js 中 STEP_TYPES 一一对应）：

  准备类:
    - preload_images          预加载模板图片
  循环类 (容器，含 children):
    - loop_count              按次数循环（count=0 无限）
    - loop_until_match        循环直到命中图片名或文字关键字
  识别类:
    - find_image              找图，结果存 $last_find
    - find_text               找字(OCR)，结果存 $last_find
  判断类 (容器，含 children + else_children):
    - if_match                条件分支（命中走 children，否则走 else_children）
                              match_type: image_has/image_not_has/text_has/text_not_has/empty/not_empty
                              target 留空时，IF/ELSE 分支内的 click_found 会自动继承本步 target
                              （仅当该分支语义为"target 出现"时才继承，避免 not_has 误继承）
                              elif 语义：在 else_children 里再嵌套一个 if_match 即可
  操作类:
    - click_found             点击上一步 $last_find 中的命中项
                              （target 留空时自动继承最近一层"target 出现"的条件分支 target）
                              loc 可选：覆盖找图返回的推荐半径 r（>0 生效）
    - click                   点击坐标（loc=随机偏移半径，0=精确点击中心）
    - long_press              长按坐标
    - swipe                   滑动
    - sleep                   休眠
    - reset_timer             重置超时计时器
    - log                     输出日志
  控制流类:
    - break                   跳出当前一层循环
    - return                  立即结束任务

每个步骤格式:
    {
      "id": "...",
      "type": "find_image",
      "params": { ... },
      "children": [ ... ],      // 仅容器类有此字段
      "else_children": [ ... ]  // 仅 if_match 有此字段（ELSE 分支，可空）
    }
"""
from __future__ import annotations

import json
from typing import Any, Optional


class _CustomBreak(Exception):
    """跳出一层循环的信号"""
    pass


class _CustomReturn(Exception):
    """立即结束任务的信号"""
    pass


class Task_custom:
    def __init__(self, device, config: dict):
        self.op = device
        self.config = config
        self.verbose = config.get("mode") == "more"
        self.task_name = config.get("custom_task_name") or "自定义"
        steps_raw = config.get("steps")
        if isinstance(steps_raw, str) and steps_raw:
            try:
                steps_raw = json.loads(steps_raw)
            except Exception:
                steps_raw = []
        self.steps: list[dict] = steps_raw if isinstance(steps_raw, list) else []
        # 运行时上下文
        self.ctx: dict[str, Any] = {"last_find": None}

    # ------------------------------------------------------------------
    # 入口
    # ------------------------------------------------------------------
    def run(self):
        self.op.log(f"开始执行自定义任务【{self.task_name}】，共 {len(self.steps)} 个顶级步骤")
        if not self.steps:
            self.op.log("步骤列表为空，直接结束")
            return
        try:
            self._exec_list(self.steps, depth=0)
        except _CustomReturn:
            self.op.log("自定义任务被『结束任务』步骤终止")
            return
        self.op.log(f"自定义任务【{self.task_name}】执行完毕")

    # ------------------------------------------------------------------
    # 调度
    # ------------------------------------------------------------------
    def _exec_list(self, steps: list[dict], depth: int, cond_target: str = "") -> None:
        """cond_target：最近一层"target 出现"的条件分支传下来的 target，
        供 click_found 在 target 留空时继承。循环体不主动设值，透传给内部 if_match 自建。"""
        for idx, step in enumerate(steps):
            self.op.check_stop()
            if self.verbose:
                self.op.log(f"[步骤{idx+1}] type={step.get('type')} depth={depth}")
            self._exec_one(step, depth=depth, cond_target=cond_target)

    def _exec_one(self, step: dict, depth: int, cond_target: str = "") -> None:
        typ = (step.get("type") or "").strip()
        params = step.get("params") or {}
        children = step.get("children") or []

        if typ == "preload_images":
            paths = self._split_paths(params.get("paths") or "")
            if not paths:
                raise ValueError("预加载图片路径为空")
            n = self.op.图片预加载(*paths)
            self.op.log(f"成功预加载了 {n} 张模板图片")
            return

        if typ == "loop_count":
            count = int(params.get("count") or 0)
            times = 0
            while True:
                self.op.check_stop()
                if count > 0 and times >= count:
                    break
                times += 1
                if self.verbose:
                    self.op.log(f"[循环] 第 {times} 次" + (f"/{count}" if count > 0 else ""))
                try:
                    self._exec_list(children, depth + 1, cond_target=cond_target)
                except _CustomBreak:
                    if self.verbose:
                        self.op.log("[循环] 被 break 跳出")
                    break
            return

        if typ == "loop_until_match":
            target_type = params.get("target_type") or "image"
            target = (params.get("target") or "").strip()
            if not target:
                raise ValueError("loop_until_match 需要配置 target")
            iter_num = 0
            while True:
                self.op.check_stop()
                iter_num += 1
                try:
                    self._exec_list(children, depth + 1, cond_target=cond_target)
                except _CustomBreak:
                    if self.verbose:
                        self.op.log(f"[循环] 第 {iter_num} 次被 break 跳出")
                    break
                # 每次子步骤跑完后用 $last_find 判断是否该退出
                last = self.ctx.get("last_find")
                if self._match_last_find(last, target_type, target):
                    if self.verbose:
                        self.op.log(f"[循环] 命中目标『{target}』，退出循环")
                    break
            return

        if typ == "find_image":
            result = self._do_find_image(params)
            self.ctx["last_find"] = result
            if self.verbose:
                self.op.log(f"[找图] 命中 {len(result) if result else 0} 项: {list(result.keys()) if result else '空'}")
            return

        if typ == "find_text":
            result = self._do_find_text(params)
            self.ctx["last_find"] = result
            if self.verbose:
                self.op.log(f"[找字] 命中 {len(result) if result else 0} 项: {list(result.keys()) if result else '空'}")
            return

        if typ == "if_match":
            # 兼容旧数据：旧字段 kind → 新字段 match_type（has→image_has, not_has→image_not_has 等）
            match_type = (params.get("match_type") or params.get("kind") or "image_has").strip()
            target = (params.get("target") or "").strip()
            else_children = step.get("else_children") or []
            last = self.ctx.get("last_find")
            hit, positive = self._judge(last, match_type, target)
            branch = children if hit else else_children
            branch_name = "IF" if hit else "ELSE"
            if self.verbose:
                self.op.log(f"[条件] match_type={match_type} target='{target}' => {'命中' if hit else '不命中'} (走{branch_name})")
            # 仅当该分支语义为"target 出现"时，把 target 传给下层 click_found 继承
            # (positive==hit 表示当前分支表示 target 存在)；empty/not_empty 无 target 不传
            branch_means_present = bool(target) and (positive == hit) and match_type not in ("empty", "not_empty")
            next_cond = target if branch_means_present else cond_target
            # break/return 在分支内自然穿层到最近一层循环/任务，无需此处 try/except
            self._exec_list(branch, depth + 1, cond_target=next_cond)
            return

        if typ == "click_found":
            target = (params.get("target") or "").strip()
            # target 留空时自动继承最近一层"target 出现"的条件分支 target
            if not target:
                target = cond_target
            miss_skip = bool(params.get("miss_skip", True))
            last = self.ctx.get("last_find")
            picked = self._pick_location(last, target)
            if picked is None:
                if self.verbose:
                    self.op.log(f"[点击] 未命中{'目标 '+target if target else ''}，{'跳过' if miss_skip else '继续下一步但不点击'}")
                return
            x, y, r = picked
            # loc 覆盖：用户显式传 loc>0 时覆盖找图返回的推荐半径 r
            loc_override = self._to_num(params.get("loc"))
            click_loc = loc_override if (loc_override is not None and loc_override > 0) else r
            self.op.点击(x, y, click_loc)
            if self.verbose:
                self.op.log(f"[点击] ({x}, {y}) loc={click_loc} 目标='{target or '默认'}")
            return

        if typ == "click":
            x = self._to_num(params.get("x"))
            y = self._to_num(params.get("y"))
            if x is None or y is None:
                raise ValueError("点击坐标参数缺失")
            # loc=随机偏移半径；0/缺省=精确点击中心（adb.点击 内部 loc<=3 直接点中心）
            loc = self._to_num(params.get("loc"))
            loc = loc if (loc is not None and loc > 0) else 0
            self.op.点击(x, y, loc)
            if self.verbose:
                self.op.log(f"[点击] ({x}, {y}) loc={loc}")
            return

        if typ == "long_press":
            x = self._to_num(params.get("x"))
            y = self._to_num(params.get("y"))
            duration = int(params.get("duration") or 1000)
            if x is None or y is None:
                raise ValueError("长按坐标参数缺失")
            self.op.长按(x, y, duration / 1000.0)
            if self.verbose:
                self.op.log(f"[长按] ({x}, {y}) {duration}ms")
            return

        if typ == "swipe":
            x1 = self._to_num(params.get("x1"))
            y1 = self._to_num(params.get("y1"))
            x2 = self._to_num(params.get("x2"))
            y2 = self._to_num(params.get("y2"))
            duration = int(params.get("duration") or 500)
            if None in (x1, y1, x2, y2):
                raise ValueError("滑动坐标参数缺失")
            self.op.滑动(x1, y1, x2, y2, duration / 1000.0)
            if self.verbose:
                self.op.log(f"[滑动] ({x1},{y1}) -> ({x2},{y2}) {duration}ms")
            return

        if typ == "sleep":
            sec = float(params.get("seconds") or 0)
            if sec <= 0:
                return
            self.op.sleep(sec)
            if self.verbose:
                self.op.log(f"[休眠] {sec}s")
            return

        if typ == "reset_timer":
            self.op.重置定时器()
            if self.verbose:
                self.op.log("[重置超时]")
            return

        if typ == "log":
            msg = str(params.get("msg") or "")
            self.op.log(msg)
            return

        if typ == "break":
            if self.verbose:
                self.op.log("[break] 跳出当前一层循环")
            raise _CustomBreak()

        if typ == "return":
            if self.verbose:
                self.op.log("[return] 结束任务")
            raise _CustomReturn()

        # 未知类型
        self.op.log(f"[跳过] 未知步骤类型: {typ}")

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------
    @staticmethod
    def _split_paths(raw: str) -> list[str]:
        # 允许换行、逗号、分号分隔，自动去除空项与空白
        import re
        items = re.split(r"[\n,;，；]+", raw or "")
        return [s.strip().strip("\"'") for s in items if s.strip()]

    @staticmethod
    def _to_num(v) -> Optional[float]:
        """把 '0.5' / 960 / '960' 等格式统一成 float 或 int，透传给 op.点击 / 长按 / 滑动"""
        if v is None or v == "":
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        # 若是整数，尽量用 int（ADB 里允许比例或绝对像素）
        if f.is_integer():
            return int(f)
        return f

    @staticmethod
    def _parse_region(raw: str):
        raw = (raw or "").strip()
        if not raw or raw == "-1,-1,-1,-1":
            return (-1, -1, -1, -1)
        parts = [p.strip() for p in raw.split(",")]
        if len(parts) != 4:
            return (-1, -1, -1, -1)
        res = []
        for p in parts:
            n = Task_custom._to_num(p)
            res.append(n if n is not None else -1)
        return tuple(res)

    # ------------------------------------------------------------------
    def _do_find_image(self, params: dict) -> Optional[dict]:
        sim = float(params.get("sim") or 0.9)
        corner = params.get("corner") or "tl"
        x1, y1, x2, y2 = self._parse_region(params.get("region") or "")
        kwargs = {"sim": sim, "priority_corner": corner}
        if (x1, y1, x2, y2) != (-1, -1, -1, -1):
            kwargs.update({"x1": x1, "y1": y1, "x2": x2, "y2": y2})
        return self.op.找图(**kwargs)

    def _do_find_text(self, params: dict) -> Optional[dict]:
        target = (params.get("target") or "").strip()
        use_regex = bool(params.get("use_regex", False))
        x1, y1, x2, y2 = self._parse_region(params.get("region") or "")
        kwargs = {}
        if target:
            kwargs["target_txt"] = target
            kwargs["use_regex"] = use_regex
        if (x1, y1, x2, y2) != (-1, -1, -1, -1):
            kwargs.update({"x1": x1, "y1": y1, "x2": x2, "y2": y2})
        return self.op.找字(**kwargs)

    # ------------------------------------------------------------------
    # 判断/匹配辅助
    # ------------------------------------------------------------------
    @staticmethod
    def _last_find_keys(last) -> set:
        """把找图返回的 dict keys / 找字返回的 dict keys / 其他结构统一抽成字符串集合"""
        keys = set()
        if isinstance(last, dict):
            for k in last.keys():
                keys.add(str(k))
        return keys

    @staticmethod
    def _last_find_strset(last) -> set:
        """找图 key 为文件名(含 png)，找字 key 为文本。两者都返回字符串集合，方便匹配"""
        return Task_custom._last_find_keys(last)

    @staticmethod
    def _match_last_find(last, target_type: str, target: str) -> bool:
        """用于 loop_until_match 循环退出判断"""
        if not target:
            return False
        s = Task_custom._last_find_strset(last)
        if not s:
            return False
        if target_type == "text":
            return any(target in x for x in s)
        # 图片名：精确匹配文件名包含即可（允许用户只写"胜利"包含于"胜利_1920x1080.png"）
        return any(target in x for x in s)

    def _judge(self, last, kind: str, target: str) -> tuple[bool, bool]:
        """返回 (是否命中, 当前条件是否表示目标出现)。"""
        kind = {"has": "image_has", "not_has": "image_not_has"}.get(kind, kind)
        empty = not last
        if kind == "empty":
            return empty, False
        if kind == "not_empty":
            return not empty, False
        is_positive = kind in ("image_has", "text_has")
        if empty:
            return not is_positive, is_positive
        s = self._last_find_strset(last)
        has = any(target in x for x in s) if target else bool(s)
        return (has if is_positive else not has), is_positive

    @staticmethod
    def _pick_location(last, target: str):
        """从 last_find 里选一个 (x, y) 坐标点。
        last_find 的返回格式：对于找图是 {filename: (x, y, w, h, cx, cy, val)}，
        找字通常是 {text: (x, y, w, h)}；这里统一用前两个值作为 x,y。
        """
        if not isinstance(last, dict) or not last:
            return None
        picked_key = None
        if target:
            for k in last.keys():
                if target in str(k):
                    picked_key = k
                    break
        else:
            # 取第一个
            for k in last.keys():
                picked_key = k
                break
        if picked_key is None:
            return None
        val = last[picked_key]
        try:
            # 找图返回 (x, y, w, h, cx, cy, val)；找字返回 (x, y, w, h)；我们取前两项
            if isinstance(val, (list, tuple)) and len(val) >= 2:
                x, y = val[0], val[1]
                radius = val[2] if len(val) >= 6 else 0
                return (x, y, radius)
        except Exception:
            return None
        return None
