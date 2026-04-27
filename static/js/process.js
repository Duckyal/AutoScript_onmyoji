/**
 * 进程管理模块
 * 处理进程列表的渲染和交互
 */

const ProcessManager = {
  // DOM 元素引用
  elements: {
    processList: null,
    titleProcess: null,
    titleSeparator: null,
    addProcessBtn: null
  },
  
  /**
   * 初始化模块
   */
  init() {
    this.elements.processList = document.getElementById('processList');
    this.elements.titleProcess = document.getElementById('titleProcess');
    this.elements.titleSeparator = document.getElementById('titleSeparator');
    this.elements.addProcessBtn = document.getElementById('addProcessBtn');
    
    this.bindEvents();
    this.render();
    this.updateHeader();
  },
  
  /**
   * 绑定事件
   */
  bindEvents() {
    // 添加进程按钮
    if (this.elements.addProcessBtn) {
      this.elements.addProcessBtn.addEventListener('click', () => {
        console.log('[v0] Add process button clicked');
        DialogManager.showAddProcessDialog();
      });
    }
    
    // 进程列表点击事件（事件委托）
    if (this.elements.processList) {
      this.elements.processList.addEventListener('click', (e) => {
        console.log('[v0] Process list clicked, target:', e.target);
        const item = e.target.closest('.sidebar-process__item');
        if (!item) return;
        
        const processId = parseInt(item.dataset.id);
        console.log('[v0] Process item clicked, id:', processId);
        
        // 检查是否点击了操作按钮
        const actionBtn = e.target.closest('.sidebar-process__action-btn');
        if (actionBtn) {
          if (actionBtn.classList.contains('sidebar-process__action-btn--rename')) {
            this.handleRename(processId);
          } else if (actionBtn.classList.contains('sidebar-process__action-btn--delete')) {
            this.handleDelete(processId);
          }
          return;
        }
        
        // 选择进程
        this.selectProcess(processId);
      });
    }
  },
  
  /**
   * 渲染进程列表
   */
  render() {
    const html = AppState.processes.map(process => this.createProcessItemHTML(process)).join('');
    this.elements.processList.innerHTML = html;
  },
  
  /**
   * 创建进程列表项 HTML
   * @param {Object} process 进程对象
   * @returns {string} HTML 字符串
   */
  createProcessItemHTML(process) {
    const isActive = process.id === AppState.selectedProcessId;
    return `
      <li class="sidebar-process__item ${isActive ? 'active' : ''}" data-id="${process.id}">
        <span class="sidebar-process__item-name">${this.escapeHTML(process.name)}</span>
        <div class="sidebar-process__item-actions">
          <button class="sidebar-process__action-btn sidebar-process__action-btn--rename" title="重命名">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>
          </button>
          <button class="sidebar-process__action-btn sidebar-process__action-btn--delete" title="删除">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </div>
      </li>
    `;
  },
  
  /**
   * 选择进程
   * @param {number} id 进程ID
   */
  selectProcess(id) {
    // 先保存当前进程的表单数据
    TaskManager.saveCurrentConfig();
    
    // 切换进程
    AppState.selectProcess(id);
    this.render();
    this.updateHeader();
    
    // 加载新进程的任务和表单
    TaskManager.loadProcessData();
    
    // 加载新进程的日志
    TerminalManager.loadProcessLogs();
    
    TerminalManager.addLog(`已切换到: ${AppState.getCurrentProcess().name}`, 'info');
  },
  
  /**
   * 添加新进程
   * @param {string} name 进程名称
   */
  addProcess(name) {
    // 先保存当前进程的表单数据
    TaskManager.saveCurrentConfig();
    
    const newProcess = AppState.addProcess(name);
    this.selectProcess(newProcess.id);
    TerminalManager.addLog(`创建新进程: ${newProcess.name}`, 'success');
  },
  
  /**
   * 处理重命名
   * @param {number} id 进程ID
   */
  handleRename(id) {
    const process = AppState.processes.find(p => p.id === id);
    if (process) {
      DialogManager.showRenameDialog(id, process.name);
    }
  },
  
  /**
   * 重命名进程
   * @param {number} id 进程ID
   * @param {string} newName 新名称
   */
  renameProcess(id, newName) {
    const oldProcess = AppState.processes.find(p => p.id === id);
    const oldName = oldProcess ? oldProcess.name : '';
    
    if (AppState.renameProcess(id, newName)) {
      this.render();
      this.updateHeader();
      TerminalManager.addLog(`进程重命名: ${oldName} -> ${newName}`, 'info');
    }
  },
  
  /**
   * 处理删除
   * @param {number} id 进程ID
   */
  handleDelete(id) {
    const process = AppState.processes.find(p => p.id === id);
    if (!process) return;
    
    if (AppState.processes.length <= 1) {
      TerminalManager.addLog('无法删除: 至少需要保留一个进程', 'warning');
      return;
    }
    
    if (confirm(`确定要删除进程 "${process.name}" 吗？`)) {
      const deletedName = process.name;
      const wasSelected = id === AppState.selectedProcessId;
      
      if (AppState.deleteProcess(id)) {
        this.render();
        this.updateHeader();
        
        // 如果删除的是当前选中的进程，需要加载新的当前进程数据
        if (wasSelected) {
          TaskManager.loadProcessData();
          TerminalManager.loadProcessLogs();
        }
        
        TerminalManager.addLog(`已删除进程: ${deletedName}`, 'warning');
      }
    }
  },
  
  /**
   * 更新标题栏
   */
  updateHeader() {
    const currentProcess = AppState.getCurrentProcess();
    if (currentProcess) {
      this.elements.titleProcess.textContent = currentProcess.name;
      this.elements.titleSeparator.style.display = '';
    }
  },
  
  /**
   * HTML 转义
   * @param {string} str 原始字符串
   * @returns {string} 转义后的字符串
   */
  escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }
};
