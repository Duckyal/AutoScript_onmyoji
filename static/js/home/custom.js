/**
 * 自定义任务步骤编辑器
 *
 * 每个步骤对象：
 * {
 *   id: string,                 // 本地唯一 id
 *   type: string,               // 动作类型（见 STEP_TYPES）
 *   params: {...},              // 动作参数
 *   // 仅循环/条件分支有子数组：
 *   children?: Step[]           // 循环体内的子步骤
 * }
 *
 * 后端解释器（tasks/custom.py）按 JSON 一步步执行
 */

const STEP_TYPES = [
  // --- 准备 ---
  { value: "preload_images", label: "1. 预加载图片", group: "准备",
    params: [
      { key: "paths", label: "选择图片（可多选，来自 tasks/tmp 目录）",
        type: "image_multi",
        placeholder: "tasks/tmp/开始_1920x1080.png" }
    ]},
  // --- 循环 ---
  { value: "loop_count", label: "2a. 循环（次数）", group: "循环", isContainer: true,
    params: [
      { key: "count", label: "循环次数（0 表示无限）", type: "number", default: 0, min: 0 }
    ]},
  { value: "loop_until_match", label: "2b. 循环（直到找到图/字才退出）", group: "循环", isContainer: true,
    params: [
      { key: "target_type", label: "匹配目标", type: "select",
        options: [["image", "命中图片名"], ["text", "识别文字包含"]],
        default: "image" },
      { key: "target", label: "目标值（图片文件名 或 文本关键字）", type: "text",
        placeholder: "例如：胜利_1920x1080.png 或 准备" }
    ]},
  // --- 识图/识字 ---
  { value: "find_image", label: "3a. 找图（把结果存到变量 $last_find）", group: "识别",
    params: [
      { key: "sim", label: "相似度 (0-1)", type: "number", default: 0.9, step: 0.01, min: 0, max: 1 },
      { key: "corner", label: "角优先度", type: "select", default: "tl",
        options: [["tl","左上"], ["tr","右上"], ["bl","左下"], ["br","右下"]] },
      { key: "region", label: "区域（可选，x1,y1,x2,y2 比例或绝对，留空=全屏）",
        type: "text", placeholder: "例如 0.5,0,-1,-1 或 -1,-1,-1,-1" }
    ]},
  { value: "find_text", label: "3b. 找字(OCR，结果存到 $last_find)", group: "识别",
    params: [
      { key: "target", label: "目标文本（支持正则，留空则返回全部文字）",
        type: "text", placeholder: "例如：准备 / 或用正则 \\d+/30" },
      { key: "use_regex", label: "使用正则匹配", type: "checkbox", default: false },
      { key: "region", label: "区域（可选，留空=全屏，y1=0.5 表示上半屏不搜）",
        type: "text", placeholder: "例如 -1,0.5,-1,-1" }
    ]},
  // --- 条件分支（用户可以在 if_match / if_not_match 里做动作）---
  { value: "if_match", label: "3c. 条件分支（判断上一步找图/找字是否命中）", group: "判断", isContainer: true,
    params: [
      { key: "kind", label: "判断", type: "select", default: "has",
        options: [
          ["has", "结果里包含指定目标（图片名 或 文本关键字）"],
          ["not_has", "结果里不包含指定目标"],
          ["empty", "结果为空（没找到任何图/字）"],
          ["not_empty", "结果不为空"]
        ]},
      { key: "target", label: "目标值（仅 has / not_has 需要）",
        type: "text", placeholder: "图片文件名 或 文本关键字" }
    ]},
  // --- 执行操作 ---
  { value: "click_found", label: "4a. 点击上一步找到的结果（图片名 或 文本关键字）", group: "操作",
    params: [
      { key: "target", label: "指定命中的目标（图片名/文本关键字，留空则点第一个）",
        type: "text", placeholder: "留空=点击 $last_find 的第一个结果" },
      { key: "miss_skip", label: "没命中时是否跳过（不勾选则继续下一步）",
        type: "checkbox", default: true }
    ]},
  { value: "click", label: "4b. 点击坐标（x,y 支持比例 0~1 或绝对值）", group: "操作",
    params: [
      { key: "x", label: "x 坐标", type: "text", default: "0.5", placeholder: "0.5 或 960" },
      { key: "y", label: "y 坐标", type: "text", default: "0.5", placeholder: "0.5 或 540" }
    ]},
  { value: "long_press", label: "4c. 长按坐标（毫秒）", group: "操作",
    params: [
      { key: "x", label: "x 坐标", type: "text", default: "0.5" },
      { key: "y", label: "y 坐标", type: "text", default: "0.5" },
      { key: "duration", label: "长按时间(毫秒)", type: "number", default: 1000, min: 200 }
    ]},
  { value: "swipe", label: "4d. 滑动（x1,y1→x2,y2，毫秒）", group: "操作",
    params: [
      { key: "x1", label: "起点 x", type: "text", default: "0.5" },
      { key: "y1", label: "起点 y", type: "text", default: "0.8" },
      { key: "x2", label: "终点 x", type: "text", default: "0.5" },
      { key: "y2", label: "终点 y", type: "text", default: "0.2" },
      { key: "duration", label: "滑动时间(毫秒)", type: "number", default: 500, min: 100 }
    ]},
  { value: "sleep", label: "5. 休眠（秒）", group: "操作",
    params: [
      { key: "seconds", label: "秒数（支持小数，≥10 秒时不计入超时）",
        type: "number", default: 1, step: 0.1, min: 0.1 }
    ]},
  { value: "reset_timer", label: "6. 重置超时计时器", group: "操作", params: [] },
  { value: "log", label: "7. 输出一条日志", group: "操作",
    params: [
      { key: "msg", label: "日志内容", type: "text", default: "步骤完成" }
    ]},
  // --- 控制流 ---
  { value: "break", label: "8. 跳出当前一层循环", group: "控制流", params: [] },
  { value: "return", label: "9. 立即结束任务", group: "控制流", params: [] }
];

const CustomStepsEditor = {
  /** @type {any[]} */
  steps: [],

  init() {
    this.$list = document.getElementById('customStepsList');
    this.$addBtn = document.getElementById('customStepAdd');
    this.$jsonInput = document.getElementById('custom_steps_json');
    this.$codeBtn = document.getElementById('customViewCode');
    if (!this.$list || !this.$addBtn || !this.$jsonInput) return;

    this.tmpImages = []; // 缓存 tasks/tmp 下的图片列表
    this._loadTmpImages();

    // 尝试从 localStorage 恢复上次编辑的步骤
    const saved = this._loadFromStorage();
    if (saved && Array.isArray(saved) && saved.length) {
      this.steps = saved;
    } else if (!this.steps.length) {
      // 示例：给一个最基础的骨架（4 步占位）方便用户直接改
      this.steps = [
        this._makeStep('preload_images'),
        this._makeStep('loop_count'),
        this._makeStep('find_image'),
        this._makeStep('sleep'),
      ];
      // 把 find_image 和 sleep 放进循环里
      const loop = this.steps[1];
      loop.children = [this.steps[2], this.steps[3]];
      this.steps.splice(2, 2);
    }

    this.$addBtn.addEventListener('click', () => {
      this.steps.push(this._makeStep('find_image'));
      this.render();
    });

    // 查看源码按钮
    if (this.$codeBtn) {
      this.$codeBtn.addEventListener('click', () => this._viewCode());
    }

    this.render();
    this._syncJson();
  },

  _STORAGE_KEY: 'custom_task_steps',

  _loadFromStorage() {
    try {
      const raw = localStorage.getItem(this._STORAGE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  },

  _saveToStorage() {
    try {
      localStorage.setItem(this._STORAGE_KEY, JSON.stringify(this.steps));
    } catch (e) {
      // localStorage 满或禁用，静默忽略
    }
  },

  async _loadTmpImages() {
    try {
      const r = await fetch('/api/list_tmp_images');
      const data = await r.json();
      this.tmpImages = data.images || [];
      // 如果当前已经渲染过，刷新一下含下拉的步骤
      this.render();
    } catch (e) {
      this.tmpImages = [];
    }
  },

  async _viewCode() {
    // 先同步 JSON
    this._syncJson();
    const steps = this.steps;
    if (!steps.length) {
      alert('步骤为空，无法生成代码');
      return;
    }
    try {
      const r = await fetch('/api/custom_generate_code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ steps })
      });
      const data = await r.json();
      if (data.success) {
        this._showCodeModal(data.code || '');
      } else {
        alert(data.message || '生成代码失败');
      }
    } catch (e) {
      alert('请求失败: ' + e.message);
    }
  },

  _showCodeModal(code) {
    // 复用已有的 email-modal 容器？不，单独一个弹窗更清晰
    let $modal = document.getElementById('customCodeModal');
    if (!$modal) {
      $modal = document.createElement('div');
      $modal.id = 'customCodeModal';
      Object.assign($modal.style, {
        position: 'fixed', inset: '0', zIndex: '99999',
        display: 'flex', alignItems: 'center', justifyContent: 'center'
      });
      $modal.innerHTML = `
        <div class="email-modal__mask" data-close></div>
        <div class="email-modal__box" style="width:680px;">
          <div class="email-modal__header">
            <h3 class="email-modal__title">生成的 Python 代码</h3>
            <button class="email-modal__close" data-close title="关闭">✕</button>
          </div>
          <div class="email-modal__body" style="padding:0;">
            <pre id="customCodePre" style="margin:0; padding:16px 20px; font-family:ui-monospace,Menlo,Consolas,monospace; font-size:13px; line-height:1.6; color:#1e293b; background-color:#f8fafc; overflow-x:auto; max-height:60vh; white-space:pre-wrap; word-break:break-all;"></pre>
          </div>
          <div class="email-modal__footer">
            <button class="btn btn--ghost" id="customCopyCode">复制代码</button>
            <div style="flex:1;"></div>
            <button class="btn btn--ghost" data-close>关闭</button>
          </div>
        </div>
      `;
      document.body.appendChild($modal);
      $modal.querySelectorAll('[data-close]').forEach(el => {
        el.addEventListener('click', () => { $modal.style.display = 'none'; });
      });
      const $copy = $modal.querySelector('#customCopyCode');
      $copy.addEventListener('click', () => {
        const code = $modal.querySelector('#customCodePre').textContent;
        navigator.clipboard.writeText(code).then(() => {
          $copy.textContent = '已复制';
          setTimeout(() => { $copy.textContent = '复制代码'; }, 1500);
        }).catch(() => {
          alert('复制失败，请手动选择文本复制');
        });
      });
    }
    $modal.querySelector('#customCodePre').textContent =
      'class Task_custom:\n' +
      '    def __init__(self, device, config):\n' +
      '        self.op = device\n' +
      '        self.config = config\n\n' +
      '    def run(self):\n' +
      (code ? code : '        pass');
    $modal.style.display = 'flex';
    // 确保缩进可见
  },

  // --- 步骤数据操作 ---
  _makeStep(type) {
    const tmpl = STEP_TYPES.find(t => t.value === type);
    const params = {};
    (tmpl?.params || []).forEach(p => {
      if (p.default !== undefined) params[p.key] = p.default;
      else if (p.type === 'checkbox') params[p.key] = false;
      else if (p.type === 'number') params[p.key] = 0;
      else params[p.key] = '';
    });
    const step = {
      id: 's_' + Math.random().toString(36).slice(2, 9),
      type,
      params
    };
    if (tmpl?.isContainer) step.children = [];
    if (type === 'if_match') step.else_children = [];
    return step;
  },

  /** 在给定数组里找到并删除 step.id，返回 true */
  _remove(stepId, list = this.steps) {
    for (let i = 0; i < list.length; i++) {
      if (list[i].id === stepId) { list.splice(i, 1); return true; }
      if (list[i].children && this._remove(stepId, list[i].children)) return true;
      if (list[i].else_children && this._remove(stepId, list[i].else_children)) return true;
    }
    return false;
  },

  _findParentList(stepId, list = this.steps, parent = null) {
    for (let i = 0; i < list.length; i++) {
      if (list[i].id === stepId) return { list, index: i };
      if (list[i].children) {
        const r = this._findParentList(stepId, list[i].children, list[i]);
        if (r) return r;
      }
      if (list[i].else_children) {
        const r = this._findParentList(stepId, list[i].else_children, list[i]);
        if (r) return r;
      }
    }
    return null;
  },

  _move(stepId, dir = -1) {
    const p = this._findParentList(stepId);
    if (!p) return;
    const newIdx = p.index + dir;
    if (newIdx < 0 || newIdx >= p.list.length) return;
    const [item] = p.list.splice(p.index, 1);
    p.list.splice(newIdx, 0, item);
    this.render();
  },

  _addChild(containerId, type = 'find_image') {
    const walk = (list) => {
      for (const s of list) {
        if (s.id === containerId) {
          if (!s.children) s.children = [];
          s.children.push(this._makeStep(type));
          return true;
        }
        if (s.children && walk(s.children)) return true;
        if (s.else_children && walk(s.else_children)) return true;
      }
      return false;
    };
    walk(this.steps);
    this.render();
  },

  _addElseChild(containerId, type = 'find_image') {
    const walk = (list) => {
      for (const s of list) {
        if (s.id === containerId && s.type === 'if_match') {
          if (!s.else_children) s.else_children = [];
          s.else_children.push(this._makeStep(type));
          return true;
        }
        if (s.children && walk(s.children)) return true;
        if (s.else_children && walk(s.else_children)) return true;
      }
      return false;
    };
    walk(this.steps);
    this.render();
  },

  _duplicate(stepId) {
    const p = this._findParentList(stepId);
    if (!p) return;
    const cloned = JSON.parse(JSON.stringify(p.list[p.index]));
    // 重新生成 id，避免冲突
    const reId = (node) => {
      node.id = 's_' + Math.random().toString(36).slice(2, 9);
      (node.children || []).forEach(reId);
      (node.else_children || []).forEach(reId);
    };
    reId(cloned);
    p.list.splice(p.index + 1, 0, cloned);
    this.render();
  },

  // --- 渲染 ---
  render() {
    this.$list.innerHTML = '';
    if (this.steps.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'custom-steps__empty';
      empty.textContent = '还没有步骤，点击右上角「+ 新增步骤」';
      this.$list.appendChild(empty);
      return;
    }
    this.steps.forEach((s, i) => {
      this.$list.appendChild(this._renderStep(s, i, this.steps, 0));
    });
    this._syncJson();
  },

  _renderStep(step, index, parentList, depth) {
    const tmpl = STEP_TYPES.find(t => t.value === step.type);
    const wrap = document.createElement('div');
    wrap.className = 'custom-step ' + (tmpl?.isContainer ? 'custom-step--container' : '');
    wrap.dataset.id = step.id;
    wrap.style.paddingLeft = (depth * 24) + 'px';
    if (depth > 0) {
      wrap.style.borderLeft = '3px solid #c7d2fe';
    }

    // --- header ---
    const head = document.createElement('div');
    head.className = 'custom-step__header';

    const left = document.createElement('div');
    left.className = 'custom-step__head-left';

    const typeSel = document.createElement('select');
    typeSel.className = 'custom-step__type';
    // 按 group 分 <optgroup>
    const groups = {};
    STEP_TYPES.forEach(t => {
      const g = t.group || '其他';
      if (!groups[g]) groups[g] = [];
      groups[g].push(t);
    });
    Object.keys(groups).forEach(g => {
      const optg = document.createElement('optgroup');
      optg.label = g;
      groups[g].forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.value;
        opt.textContent = t.label;
        if (t.value === step.type) opt.selected = true;
        optg.appendChild(opt);
      });
      typeSel.appendChild(optg);
    });
    typeSel.addEventListener('change', (e) => {
      // 切换类型：保留 id，重置为新类型的默认参数；保留原 children 仅当新类型也是容器
      const newStep = this._makeStep(e.target.value);
      const oldChildren = step.children;
      step.type = newStep.type;
      step.params = newStep.params;
      if (newStep.children !== undefined) step.children = oldChildren && oldChildren.length ? oldChildren : [];
      else delete step.children;
      this.render();
    });

    const idxLabel = document.createElement('span');
    idxLabel.className = 'custom-step__idx';
    idxLabel.textContent = `#${index + 1}`;

    left.appendChild(idxLabel);
    left.appendChild(typeSel);
    head.appendChild(left);

    // 操作按钮
    const act = document.createElement('div');
    act.className = 'custom-step__actions';
    act.innerHTML = `
      <button type="button" data-act="up" title="上移">↑</button>
      <button type="button" data-act="down" title="下移">↓</button>
      <button type="button" data-act="dup" title="复制步骤">⎘</button>
      <button type="button" data-act="del" title="删除">✕</button>
    `;
    act.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => {
        const a = btn.dataset.act;
        if (a === 'del') { if (confirm('删除此步骤？')) { this._remove(step.id); this.render(); } }
        else if (a === 'up') this._move(step.id, -1);
        else if (a === 'down') this._move(step.id, 1);
        else if (a === 'dup') this._duplicate(step.id);
      });
    });
    head.appendChild(act);
    wrap.appendChild(head);

    // --- params 区 ---
    const body = document.createElement('div');
    body.className = 'custom-step__body';
    (tmpl?.params || []).forEach(p => body.appendChild(this._renderParam(step, p)));
    wrap.appendChild(body);

    // --- 容器：循环只有 children，条件分支同时提供 IF/ELSE ---
    if (tmpl?.isContainer) {
      const renderBranch = (title, key, addHandler) => {
        const branchWrap = document.createElement('div');
        branchWrap.className = 'custom-step__children';
        if (!step[key]) step[key] = [];

        const branchTitle = document.createElement('div');
        branchTitle.textContent = title;
        branchTitle.style.cssText = 'font-weight:600;margin:8px 0 4px;color:#475569;';
        branchWrap.appendChild(branchTitle);

        if (step[key].length) {
          step[key].forEach((child, ci) => {
            branchWrap.appendChild(this._renderStep(child, ci, step[key], depth + 1));
          });
        } else {
          const empty = document.createElement('div');
          empty.className = 'custom-steps__empty custom-steps__empty--small';
          empty.textContent = '还没有子步骤';
          branchWrap.appendChild(empty);
        }

        const addBar = document.createElement('div');
        addBar.className = 'custom-step__child-add';
        const addSelect = document.createElement('select');
        addSelect.innerHTML = STEP_TYPES.map(t => `<option value="${t.value}">${t.label}</option>`).join('');
        const addBtn = document.createElement('button');
        addBtn.type = 'button';
        addBtn.className = 'btn btn--ghost btn--sm';
        addBtn.textContent = '+ 加子步骤';
        addBtn.addEventListener('click', () => addHandler(step.id, addSelect.value));
        addBar.appendChild(addSelect);
        addBar.appendChild(addBtn);
        branchWrap.appendChild(addBar);
        return branchWrap;
      };

      wrap.appendChild(renderBranch('IF 命中时执行', 'children', (id, type) => this._addChild(id, type)));
      if (step.type === 'if_match') {
        wrap.appendChild(renderBranch('ELSE 未命中时执行', 'else_children', (id, type) => this._addElseChild(id, type)));
      }
    }

    return wrap;
  },

  _renderParam(step, p) {
    const row = document.createElement('div');
    row.className = 'custom-param';
    const lab = document.createElement('label');
    lab.className = 'custom-param__label';
    lab.textContent = p.label;
    row.appendChild(lab);

    let input;
    if (p.type === 'image_multi') {
      // 图片多选下拉（数据来自 /api/list_tmp_images）
      input = document.createElement('div');
      input.className = 'custom-param__image-multi';

      const $sel = document.createElement('select');
      $sel.className = 'custom-param__select';
      $sel.multiple = true;
      $sel.size = 4;

      const fill = () => {
        const current = (step.params[p.key] || '').split(/[\n,;，；]+/).map(s => s.trim().replace(/^["']|["']$/g, '')).filter(Boolean);
        $sel.innerHTML = '';
        if (!this.tmpImages || !this.tmpImages.length) {
          $sel.innerHTML = '<option disabled>暂无图片，请先在开发页截图保存到 tasks/tmp</option>';
        } else {
          this.tmpImages.forEach(img => {
            const o = document.createElement('option');
            o.value = img;
            o.textContent = img;
            if (current.includes(img)) o.selected = true;
            $sel.appendChild(o);
          });
        }
      };
      fill();

      $sel.addEventListener('change', () => {
        step.params[p.key] = Array.from($sel.selectedOptions).map(o => o.value).join('\n');
        this._syncJson();
      });

      // 当前已选但可能不在 tmp 列表里的图片（手动添加路径兼容），展示在文本框
      const $ta = document.createElement('textarea');
      $ta.className = 'custom-param__textarea';
      $ta.rows = 2;
      $ta.placeholder = '或手动输入路径（每行一个或逗号分隔），如 tasks/tmp/胜利_1920x1080.png';
      $ta.value = step.params[p.key] || '';
      $ta.addEventListener('change', () => {
        step.params[p.key] = $ta.value;
        fill(); // 刷新选中态
        this._syncJson();
      });

      // 刷新按钮（重新拉取 tasks/tmp 列表）
      const $refresh = document.createElement('button');
      $refresh.type = 'button';
      $refresh.className = 'btn btn--ghost btn--sm';
      $refresh.textContent = '刷新';
      $refresh.style.marginTop = '4px';
      $refresh.addEventListener('click', async () => {
        $refresh.textContent = '加载中...';
        await this._loadTmpImages();
        fill();
        $refresh.textContent = '刷新';
      });

      input.appendChild($sel);
      input.appendChild($ta);
      input.appendChild($refresh);
    } else if (p.type === 'textarea') {
      input = document.createElement('textarea');
      input.rows = 3;
      input.className = 'custom-param__textarea';
      input.value = step.params[p.key] || '';
      if (p.placeholder) input.placeholder = p.placeholder;
      input.addEventListener('change', () => { step.params[p.key] = input.value; this._syncJson(); });
    } else if (p.type === 'select') {
      input = document.createElement('select');
      input.className = 'custom-param__select';
      (p.options || []).forEach(([v, t]) => {
        const o = document.createElement('option');
        o.value = v; o.textContent = t;
        if (step.params[p.key] + '' === v + '') o.selected = true;
        input.appendChild(o);
      });
      input.addEventListener('change', () => { step.params[p.key] = input.value; this._syncJson(); });
    } else if (p.type === 'checkbox') {
      input = document.createElement('label');
      input.className = 'custom-param__checkbox';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = !!step.params[p.key];
      cb.addEventListener('change', () => { step.params[p.key] = cb.checked; this._syncJson(); });
      input.appendChild(cb);
      const txt = document.createElement('span');
      txt.textContent = ' 启用';
      input.appendChild(txt);
    } else if (p.type === 'number') {
      input = document.createElement('input');
      input.type = 'number';
      input.className = 'custom-param__input';
      if (p.min !== undefined) input.min = p.min;
      if (p.max !== undefined) input.max = p.max;
      if (p.step !== undefined) input.step = p.step;
      input.value = step.params[p.key] !== '' ? step.params[p.key] : (p.default ?? '');
      input.addEventListener('input', () => {
        const v = input.value;
        step.params[p.key] = v === '' ? (p.default ?? '') : (input.step && parseFloat(input.step) % 1 ? parseFloat(v) : parseInt(v));
        this._syncJson();
      });
    } else {
      input = document.createElement('input');
      input.type = 'text';
      input.className = 'custom-param__input';
      input.value = step.params[p.key] || '';
      if (p.placeholder) input.placeholder = p.placeholder;
      input.addEventListener('input', () => { step.params[p.key] = input.value; this._syncJson(); });
    }
    row.appendChild(input);
    return row;
  },

  // --- 同步 JSON 到隐藏字段 ---
  _syncJson() {
    try {
      this.$jsonInput.value = JSON.stringify(this.steps);
    } catch (e) {
      this.$jsonInput.value = '[]';
    }
    this._saveToStorage();
  }
};

document.addEventListener('DOMContentLoaded', () => {
  try {
    CustomStepsEditor.init();
  } catch (e) {
    console.warn('CustomStepsEditor init failed', e);
  }
});
