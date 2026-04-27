/**
 * 任务管理模块
 * 处理任务选择和内容切换
 */

const TaskManager = {
  // DOM 元素引用
  elements: {
    taskList: null,
    contentMain: null,
    panels: {},
    selectFileBtn: null,
    fileName: null
  },
  
  // 任务类型映射
  taskTypes: ['yuhun', 'douji', 'tupo', 'custom'],
  
  // 任务名称映射
  taskNames: {
    yuhun: '御魂',
    douji: '斗技',
    tupo: '突破',
    custom: '自定义'
  },
  
  // 表单字段映射
  formFields: {
    yuhun: ['yuhun-layer', 'yuhun-count', 'yuhun-team', 'yuhun-shikigami'],
    douji: ['douji-count', 'douji-rank', 'douji-refresh'],
    tupo: ['tupo-type', 'tupo-count', 'tupo-target', 'tupo-refresh'],
    custom: []
  },

  // 初始化存储py文件的对象
  currentPyFile: null, 


  /**
   * 初始化模块
   */
  init() {
    this.elements.taskList = document.getElementById('taskList');
    this.elements.contentMain = document.getElementById('contentMain');
    this.elements.selectFileBtn = document.getElementById('selectFileBtn');
    this.elements.fileName = document.getElementById('fileName');
    
    // 获取所有面板
    this.taskTypes.forEach(type => {
      this.elements.panels[type] = document.getElementById(`panel-${type}`);
    });
    
    this.bindEvents();
    this.loadProcessData();
  },
  
  /**
   * 绑定事件
   */
  bindEvents() {
    console.log('[v0] TaskManager.bindEvents - taskList:', this.elements.taskList);
    
    // 任务列表点击事件
    if (this.elements.taskList) {
      this.elements.taskList.addEventListener('click', (e) => {
        console.log('[v0] Task list clicked, target:', e.target);
        const item = e.target.closest('.sidebar-task__item');
        if (item) {
          const task = item.dataset.task;
          console.log('[v0] Task item clicked:', task);
          this.selectTask(task);
        }
      });
    }
    
    // 选择文件夹按钮
    this.elements.selectFileBtn.addEventListener('click', () => {
      this.handleSelectFile();
    });
    
    // 监听表单变化，实时保存
    this.taskTypes.forEach(type => {
      this.formFields[type].forEach(fieldId => {
        const field = document.getElementById(fieldId);
        if (field) {
          field.addEventListener('change', () => {
            this.saveCurrentConfig();
          });
          field.addEventListener('input', () => {
            this.saveCurrentConfig();
          });
        }
      });
    });
  },
  
  /**
   * 加载当前进程的数据
   */
  loadProcessData() {
    // 获取当前进程的选中任务
    const currentTask = AppState.getCurrentTask();
    
    // 渲染任务列表
    this.renderTaskList();
    
    // 显示对应面板
    this.showPanel(currentTask);
    
    // 加载表单数据
    this.loadFormData();
  },
  
  /**
   * 渲染任务列表
   */
  renderTaskList() {
    const currentTask = AppState.getCurrentTask();
    const items = this.elements.taskList.querySelectorAll('.sidebar-task__item');
    items.forEach(item => {
      const task = item.dataset.task;
      if (task === currentTask) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });
  },
  
  /**
   * 加载表单数据
   */
  loadFormData() {
    const configs = AppState.getCurrentTaskConfigs();

    // 获取任务名
    const taskType = AppState.getCurrentTask(); // 得到 'yuhun', 'douji' 等
    const taskName = this.taskNames[taskType];  // 得到 '御魂', '斗技' 等
    // 渲染到界面上
    if (taskName && this.elements.taskNameDisplay) {
      this.elements.taskNameDisplay.textContent = taskName;
    }

    // 御魂配置
    if (configs.yuhun) {
      this.setFieldValue('yuhun-layer', configs.yuhun.layer);
      this.setFieldValue('yuhun-count', configs.yuhun.count);
      this.setFieldValue('yuhun-team', configs.yuhun.team);
      this.setFieldValue('yuhun-shikigami', configs.yuhun.shikigami);
    }
    
    // 斗技配置
    if (configs.douji) {
      this.setFieldValue('douji-count', configs.douji.count);
      this.setFieldValue('douji-rank', configs.douji.rank);
      this.setFieldValue('douji-refresh', configs.douji.refresh);
    }
    
    // 突破配置
    if (configs.tupo) {
      this.setFieldValue('tupo-type', configs.tupo.type);
      this.setFieldValue('tupo-count', configs.tupo.count);
      this.setFieldValue('tupo-target', configs.tupo.target);
      this.setFieldValue('tupo-refresh', configs.tupo.refresh);
    }
    
    // 自定义配置
    if (configs.custom && this.elements.fileName) {
      this.elements.fileName.textContent = configs.custom.fileName || '';
    }
  },
  
  /**
   * 设置字段值
   * @param {string} fieldId 字段ID
   * @param {string} value 值
   */
  setFieldValue(fieldId, value) {
    const field = document.getElementById(fieldId);
    if (field && value !== undefined) {
      field.value = value;
    }
  },
  
  /**
   * 保存当前进程的配置
   */
  saveCurrentConfig() {
    // 保存御魂配置
    AppState.saveTaskConfig('yuhun', {
      layer: document.getElementById('yuhun-layer')?.value || '10',
      count: document.getElementById('yuhun-count')?.value || '100',
      team: document.getElementById('yuhun-team')?.value || 'captain',
      shikigami: document.getElementById('yuhun-shikigami')?.value || ''
    });
    
    // 保存斗技配置
    AppState.saveTaskConfig('douji', {
      count: document.getElementById('douji-count')?.value || '30',
      rank: document.getElementById('douji-rank')?.value || 'current',
      refresh: document.getElementById('douji-refresh')?.value || 'yes'
    });
    
    // 保存突破配置
    AppState.saveTaskConfig('tupo', {
      type: document.getElementById('tupo-type')?.value || 'personal',
      count: document.getElementById('tupo-count')?.value || '30',
      target: document.getElementById('tupo-target')?.value || 'random',
      refresh: document.getElementById('tupo-refresh')?.value || 'yes'
    });
    
    // 保存自定义配置
    AppState.saveTaskConfig('custom', {
      fileName: this.elements.fileName?.textContent || ''
    });
  },
  
  /**
   * 选择任务
   * @param {string} task 任务类型
   */
  selectTask(task) {
    if (!this.taskTypes.includes(task)) return;
    
    AppState.selectTask(task);
    this.renderTaskList();
    this.showPanel(task);
    TerminalManager.addLog(`切换任务: ${this.taskNames[task]}`, 'info');
  },
  
  /**
   * 显示指定面板
   * @param {string} task 任务类型
   */
  showPanel(task) {
    this.taskTypes.forEach(type => {
      const panel = this.elements.panels[type];
      if (panel) {
        panel.style.display = type === task ? '' : 'none';
      }
    });
  },
  
  /**
   * 处理选择 Python 文件
   */
  handleSelectFile() {
    // 检查浏览器是否支持现代文件选择 API (虽然选单文件两者差异不大，但保留结构方便扩展)
    if ('showOpenFilePicker' in window) {
      this.selectFileModern();
    } else {
      // 回退方案：传统的文件选择
      this.selectFileFallback();
    }
  },
  
  /**
   * 现代浏览器的文件选择
   */
  async selectFileModern() {
    try {
      // 限制只能选择 .py 文件
      const [fileHandle] = await window.showOpenFilePicker({
        types: [{
          description: 'Python Scripts',
          accept: { 'text/x-python': ['.py'] }
        }]
      });
      
      const fileName = fileHandle.name;
      
      // 二次校验后缀
      if (!fileName.endsWith('.py')) {
        TerminalManager.addLog('请选择 .py 格式的 Python 文件', 'warning');
        return;
      }

      // 获取真实的 File 对象并存到全局状态
      const file = await fileHandle.getFile();
      this.currentPyFile = file; 
      
      this.elements.fileName.textContent = fileName; // 注意这里的 DOM 元素名要对应
      this.saveCurrentConfig();
      TerminalManager.addLog(`已选择脚本: ${fileName}`, 'success');
      
    } catch (err) {
      // 用户取消选择时不报错
      if (err.name !== 'AbortError') {
        TerminalManager.addLog(`选择文件失败: ${err.message}`, 'error');
      }
    }
  },
  
  /**
   * 传统浏览器的文件选择（回退方案）
   */
  selectFileFallback() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.py'; // 限制文件选择器只能看到 .py 文件
    input.style.display = 'none';
    
    input.addEventListener('change', (e) => {
      if (e.target.files.length > 0) {
        const file = e.target.files[0];
        
        // 校验后缀
        if (!file.name.endsWith('.py')) {
          TerminalManager.addLog('请选择 .py 格式的 Python 文件', 'warning');
        } else {
          // 传统方式直接就是 File 对象，直接存
          this.currentPyFile = file; 
          this.elements.fileName.textContent = file.name; // 注意这里的 DOM 元素名要对应
          this.saveCurrentConfig();
          TerminalManager.addLog(`已选择脚本: ${file.name}`, 'success');
        }
      }
      
      // 清理 input 元素
      document.body.removeChild(input);
    });
    
    document.body.appendChild(input);
    input.click();
  },
  
  /**
   * 获取当前任务配置
   * @returns {Object} 任务配置对象
   */
  getCurrentConfig() {
    const task = AppState.getCurrentTask();
    const configs = AppState.getCurrentTaskConfigs();
    return configs[task] || {};
  }
};
