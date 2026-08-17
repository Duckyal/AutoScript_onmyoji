/**
 * 任务管理模块 (自动化版本)
 * 自动收集表单，无需为新任务写死 JS
 */
const TaskManager = {
  currentTask: '',

  init() {
    // 自动获取初始任务名 (从 HTML 的 active 类获取)
    const activeItem = document.querySelector('.sidebar-task__item.active');
    if (activeItem) {
      this.currentTask = activeItem.dataset.task;
    }
    this.bindEvents();
    this.initDependencies();
    if (typeof EmailNotifier !== 'undefined') EmailNotifier.init();
  },

  initDependencies() {
    // 遍历所有带 data-from 的元素
    document.querySelectorAll('[data-from]').forEach(el => {
      const sourceName = el.dataset.from;
      const panel = el.closest('.task-panel');
      const source = panel ? panel.querySelector(`[name="${sourceName}"]`) : null;
      
      if (source) {
        source.addEventListener('change', () => this.updateDependent(el, source));
        this.updateDependent(el, source); // 初始化执行一次
      }
    });
  },

  updateDependent(el, source) {
    try {
      const options = JSON.parse(el.dataset.when);
      const selected = source.value;
      const allowed = options[selected] || [];
      
      el.querySelectorAll('option').forEach(opt => {
        opt.style.display = allowed.includes(opt.value) ? '' : 'none';
      });
      
      // 确保选中有效选项
      if (!allowed.includes(el.value)) {
        el.value = allowed[0] || '';
      }
    } catch (e) {
      console.error('依赖配置解析错误:', e);
    }
  },

  bindEvents() {
    // 绑定执行按钮活动
    const taskList = document.getElementById('taskList');
    if (taskList) {
      taskList.addEventListener('click', (e) => {
        const item = e.target.closest('.sidebar-task__item');
        if (item) {
          this.switchTask(item.dataset.task, item.dataset.name);
        }
      });
    }
  },

  switchTask(taskName, displayName) {
    this.currentTask = taskName;
    
    // 更新侧边栏激活状态
    document.querySelectorAll('.sidebar-task__item').forEach(item => {
      item.classList.toggle('active', item.dataset.task === taskName);
    });

    // 切换面板显示
    document.querySelectorAll('.task-panel').forEach(panel => {
      panel.style.display = 'none';
    });
    
    const activePanel = document.getElementById(`panel-${taskName}`);
    if (activePanel) {
      activePanel.style.display = 'block';
    }

    // 更新顶部标题
    if (displayName) {
      const taskNameEl = document.getElementById('taskName');
      if (taskNameEl) {
        taskNameEl.textContent = displayName;
      }
    }
  },

  /**
   * 自动收集当前任务配置
   * 找到当前显示的 panel，把里面带 name 的元素全抓出来打包成json给执行方法调用
   */
  getCurrentConfig() {
    // 自定义任务：强制把步骤编辑器数据同步到隐藏 input，确保执行时是最新内容
    if (typeof CustomStepsEditor !== 'undefined' && CustomStepsEditor._syncJson) {
      try { CustomStepsEditor._syncJson(); } catch (e) {}
    }

    const config = {};
    // 找到当前可见的那个面板
    const activePanel = document.querySelector('.task-panel[style*="display: block"], .task-panel:not([style*="display: none"])');
    
    if (activePanel) {
      // 抓取所有输入框、下拉框等
      activePanel.querySelectorAll('input, select, textarea').forEach(el => {
        if (el.name) {
          config[el.name] = el.value;
        }
      });
    }
    
    return {
      task: this.currentTask,
      config: config
    };
  }
};

/**
 * 任务结束邮件提醒模块
 * - 从 /api/email_config 拉取当前配置回填到开关
 * - 点击开关时：
 *     - 打开 / 关闭提醒（开：若没配置则弹配置窗；关：直接保存 enabled=false）
 *     - 配置弹窗里可以保存 + 发送测试
 */
const EmailNotifier = {
  currentAuthCode: "",     // 已保存的授权码是否存在（通过掩码 auth_code_set，真实值不传回前端）
  cachedHasAuthCode: false,

  init() {
    this.$toggle = document.getElementById('emailToggleBtn');
    this.$modal = document.getElementById('emailModal');
    if (!this.$toggle || !this.$modal) return;
    this.enabled = false; // 当前是否已开启

    this.bindToggle();
    this.bindModal();
    this.loadConfigAndSync();
  },

  bindToggle() {
    // 用户点击按钮：
    //   未开启 -> 弹配置窗（回填已保存的配置方便修改），保存成功后置为开启
    //   已开启 -> 直接保存 enabled=false
    this.$toggle.addEventListener('click', async (e) => {
      e.preventDefault();
      if (!this.enabled) {
        const cfg = await this.fetchConfig();
        this.openModal(cfg, /*enableOnSave=*/true);
      } else {
        const cfg = await this.fetchConfig();
        await this.saveConfigToBackend({ ...cfg, enabled: false, keepAuth: true });
        this.setEnabled(false);
        this.showToast("已关闭任务结束提醒");
      }
    });
  },

  setEnabled(on) {
    this.enabled = on;
    if (on) {
      this.$toggle.classList.add('is-email-on');
    } else {
      this.$toggle.classList.remove('is-email-on');
    }
  },

  bindModal() {
    // 关闭
    this.$modal.querySelectorAll('[data-close]').forEach(el => {
      el.addEventListener('click', () => this.closeModal());
    });

    // 发送测试
    const $test = document.getElementById('emTestBtn');
    if ($test) {
      $test.addEventListener('click', async () => {
        const formCfg = this.collectForm();
        if (!this.validate(formCfg, true)) return;
        $test.disabled = true;
        $test.textContent = "发送中...";
        try {
          const resp = await fetch('/api/email_test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config: formCfg })
          });
          const data = await resp.json();
          if (data.success) {
            this.showToast(data.message || "测试邮件已发送");
          } else {
            alert(data.message || "发送失败");
          }
        } catch (err) {
          alert("请求失败: " + err.message);
        } finally {
          $test.disabled = false;
          $test.textContent = "发送测试";
        }
      });
    }

    // 保存并启用
    const $save = document.getElementById('emSaveBtn');
    if ($save) {
      $save.addEventListener('click', async () => {
        const formCfg = this.collectForm();
        const needAuth = !this.cachedHasAuthCode || !!formCfg.auth_code;
        if (!this.validate(formCfg, needAuth)) return;

        // 如果本次没输入授权码但已缓存，后端会自动沿用
        const payload = { ...formCfg, enabled: true };
        const ok = await this.saveConfigToBackend(payload);
        if (ok) {
          this.setEnabled(true);
          this.closeModal();
          this.showToast("配置已保存，已开启提醒");
        }
      });
    }

    // ESC 关闭
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.$modal.style.display !== 'none') {
        this.closeModal();
      }
    });
  },

  validate(cfg, requireAuth) {
    if (!cfg.smtp_server) { alert("请填写 SMTP 服务器"); return false; }
    if (!cfg.smtp_port) { alert("请填写 SMTP 端口"); return false; }
    if (!cfg.sender_email) { alert("请填写发件人邮箱"); return false; }
    if (requireAuth && !cfg.auth_code) {
      alert("请填写邮箱授权码/密钥");
      return false;
    }
    if (!cfg.receiver_email) { alert("请填写收件人邮箱"); return false; }
    return true;
  },

  collectForm() {
    return {
      smtp_server: document.getElementById('emSmtpServer').value.trim(),
      smtp_port: parseInt(document.getElementById('emSmtpPort').value) || 465,
      use_ssl: document.getElementById('emUseSsl').value === 'true',
      sender_email: document.getElementById('emSender').value.trim(),
      auth_code: document.getElementById('emAuthCode').value, // 空则沿用之前
      receiver_email: document.getElementById('emReceiver').value.trim(),
    };
  },

  fillForm(cfg) {
    document.getElementById('emSmtpServer').value = cfg.smtp_server || 'smtp.qq.com';
    document.getElementById('emSmtpPort').value = cfg.smtp_port || 465;
    document.getElementById('emUseSsl').value = (cfg.use_ssl !== false) ? 'true' : 'false';
    document.getElementById('emSender').value = cfg.sender_email || '';
    const authLabel = document.getElementById('emAuthLabel');
    const authInput = document.getElementById('emAuthCode');
    this.cachedHasAuthCode = !!cfg.auth_code_set;
    if (cfg.auth_code_set) {
      authInput.placeholder = '已保存授权码；留空则沿用，重新输入则覆盖';
      authLabel.textContent = '邮箱授权码 / 密钥（已保存）';
    } else {
      authInput.placeholder = '输入授权码（不是登录密码）';
      authLabel.textContent = '邮箱授权码 / 密钥';
    }
    authInput.value = '';
    document.getElementById('emReceiver').value = cfg.receiver_email || '';
  },

  async fetchConfig() {
    try {
      const r = await fetch('/api/email_config');
      return await r.json();
    } catch (e) {
      return {
        enabled: false, smtp_server: 'smtp.qq.com', smtp_port: 465,
        use_ssl: true, sender_email: '', auth_code_set: false, receiver_email: ''
      };
    }
  },

  async loadConfigAndSync() {
    const cfg = await this.fetchConfig();
    this.setEnabled(!!cfg.enabled);
  },

  openModal(cfg, enableOnSave = false) {
    this.fillForm(cfg);
    this.$modal.style.display = 'flex';
    this._enableOnSave = enableOnSave;
    // 聚焦
    setTimeout(() => {
      const first = document.getElementById('emSmtpServer');
      if (first) first.focus();
    }, 50);
  },

  closeModal() {
    this.$modal.style.display = 'none';
  },

  async saveConfigToBackend(cfg) {
    try {
      const resp = await fetch('/api/email_config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(cfg)
      });
      const data = await resp.json();
      if (!data.success) {
        alert(data.message || "保存失败");
        return false;
      }
      return true;
    } catch (e) {
      alert("保存请求失败: " + e.message);
      return false;
    }
  },

  showToast(msg) {
    let $toast = document.getElementById('__emailToast');
    if (!$toast) {
      $toast = document.createElement('div');
      $toast.id = '__emailToast';
      Object.assign($toast.style, {
        position: 'fixed', bottom: '32px', left: '50%', transform: 'translateX(-50%)',
        background: 'rgba(15, 23, 42, 0.92)', color: '#f8fafc',
        padding: '10px 18px', borderRadius: '6px', fontSize: '14px', zIndex: 999999,
        boxShadow: '0 8px 24px rgba(0,0,0,0.3)', opacity: '0',
        transition: 'opacity .2s ease', pointerEvents: 'none'
      });
      document.body.appendChild($toast);
    }
    $toast.textContent = msg;
    $toast.style.opacity = '1';
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => {
      $toast.style.opacity = '0';
    }, 2000);
  }
};
