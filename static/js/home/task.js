/**
 * 任务管理模块 (自动化版本)
 * 自动收集表单，无需为新任务写死 JS
 */
const TaskManager = {
  currentTask: 'yuhun',
  currentPyFile: null,

  init() {
    // 自动获取初始任务名 (从 HTML 的 active 类获取)
    const activeItem = document.querySelector('.sidebar-task__item.active');
    if (activeItem) {
      this.currentTask = activeItem.dataset.task;
    }
    this.bindEvents();
  },

  bindEvents() {
    const taskList = document.getElementById('taskList');
    if (taskList) {
      taskList.addEventListener('click', (e) => {
        const item = e.target.closest('.sidebar-task__item');
        if (item) {
          this.switchTask(item.dataset.task, item.dataset.name);
        }
      });
    }

    // 处理自定义脚本文件选择
    const selectFileBtn = document.getElementById('selectFileBtn');
    if (selectFileBtn) {
      const fileInput = document.createElement('input');
      fileInput.type = 'file';
      fileInput.accept = '.py';
      fileInput.style.display = 'none';
      document.body.appendChild(fileInput);

      selectFileBtn.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
          this.currentPyFile = e.target.files[0];
          const fileNameEl = document.getElementById('fileName');
          if (fileNameEl) {
            fileNameEl.textContent = `已选择: ${this.currentPyFile.name}`;
          }
        }
      });
    }
  },

  switchTask(taskName, displayName) {
    this.currentTask = taskName;
    
    document.querySelectorAll('.sidebar-task__item').forEach(item => {
      item.classList.toggle('active', item.dataset.task === taskName);
    });

    document.querySelectorAll('.task-panel').forEach(panel => {
      panel.style.display = 'none';
    });
    
    const activePanel = document.getElementById(`panel-${taskName}`);
    if (activePanel) {
      activePanel.style.display = 'block';
    }

    if (displayName) {
      const titleProcessEl = document.getElementById('titleProcess');
      const separatorEl = document.getElementById('titleSeparator');
      if (titleProcessEl && separatorEl) {
        titleProcessEl.textContent = displayName;
        separatorEl.style.display = 'inline';
      }
    }
  },

  /**
   * 自动收集当前任务配置
   * 找到当前显示的 panel，把里面带 name 的元素全抓出来
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
