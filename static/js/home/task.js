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
