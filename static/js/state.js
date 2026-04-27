/**
 * 状态管理模块
 * 管理应用的全局状态
 */

const AppState = {
  // 进程列表
  processes: [
    { id: 1, name: '进程1' }
  ],
  
  // 当前选中的进程ID
  selectedProcessId: 1,
  
  // 当前选中的任务（按进程ID存储）
  selectedTasks: {
    1: 'yuhun'
  },
  
  // 进程计数器（用于生成默认名称）
  processCounter: 1,
  
  // 正在重命名的进程ID
  renamingProcessId: null,
  
  // 任务配置数据（按进程ID存储）
  taskConfigs: {
    1: {
      yuhun: { layer: '10', count: '100', team: 'captain', shikigami: '' },
      douji: { count: '30', rank: 'current', refresh: 'yes' },
      tupo: { type: 'personal', count: '30', target: 'random', refresh: 'yes' },
      custom: { fileName: '' }
    }
  },
  
  // 日志数据（按进程ID存储）
  processLogs: {
    1: []
  },
  
  /**
   * 获取当前选中的进程
   * @returns {Object|undefined} 当前选中的进程对象
   */
  getCurrentProcess() {
    return this.processes.find(p => p.id === this.selectedProcessId);
  },
  
  /**
   * 获取当前进程的选中任务
   * @returns {string} 任务类型
   */
  getCurrentTask() {
    return this.selectedTasks[this.selectedProcessId] || 'yuhun';
  },
  
  /**
   * 获取当前进程的任务配置
   * @returns {Object} 任务配置
   */
  getCurrentTaskConfigs() {
    return this.taskConfigs[this.selectedProcessId] || this.getDefaultTaskConfigs();
  },
  
  /**
   * 获取当前进程的日志
   * @returns {Array} 日志数组
   */
  getCurrentLogs() {
    return this.processLogs[this.selectedProcessId] || [];
  },
  
  /**
   * 获取默认任务配置
   * @returns {Object} 默认配置
   */
  getDefaultTaskConfigs() {
    return {
      yuhun: { layer: '10', count: '100', team: 'captain', shikigami: '' },
      douji: { count: '30', rank: 'current', refresh: 'yes' },
      tupo: { type: 'personal', count: '30', target: 'random', refresh: 'yes' },
      custom: { fileName: '' }
    };
  },
  
  /**
   * 获取下一个进程的默认名称
   * @returns {string} 默认进程名称
   */
  getNextProcessName() {
    return `进程${this.processCounter + 1}`;
  },
  
  /**
   * 添加新进程
   * @param {string} name 进程名称
   * @returns {Object} 新创建的进程对象
   */
  addProcess(name) {
    this.processCounter++;
    const newProcess = {
      id: Date.now(), // 使用时间戳作为唯一ID
      name: name || this.getNextProcessName()
    };
    this.processes.push(newProcess);
    
    // 初始化新进程的状态
    this.selectedTasks[newProcess.id] = 'yuhun';
    this.taskConfigs[newProcess.id] = this.getDefaultTaskConfigs();
    this.processLogs[newProcess.id] = [];
    
    return newProcess;
  },
  
  /**
   * 删除进程
   * @param {number} id 进程ID
   * @returns {boolean} 是否删除成功
   */
  deleteProcess(id) {
    // 至少保留一个进程
    if (this.processes.length <= 1) {
      return false;
    }
    
    const index = this.processes.findIndex(p => p.id === id);
    if (index === -1) {
      return false;
    }
    
    this.processes.splice(index, 1);
    
    // 清理该进程的数据
    delete this.selectedTasks[id];
    delete this.taskConfigs[id];
    delete this.processLogs[id];
    
    // 如果删除的是当前选中的进程，选择第一个进程
    if (this.selectedProcessId === id) {
      this.selectedProcessId = this.processes[0].id;
    }
    
    return true;
  },
  
  /**
   * 重命名进程
   * @param {number} id 进程ID
   * @param {string} newName 新名称
   * @returns {boolean} 是否重命名成功
   */
  renameProcess(id, newName) {
    const process = this.processes.find(p => p.id === id);
    if (process && newName.trim()) {
      process.name = newName.trim();
      return true;
    }
    return false;
  },
  
  /**
   * 选择进程
   * @param {number} id 进程ID
   */
  selectProcess(id) {
    const process = this.processes.find(p => p.id === id);
    if (process) {
      this.selectedProcessId = id;
    }
  },
  
  /**
   * 选择任务（针对当前进程）
   * @param {string} task 任务类型
   */
  selectTask(task) {
    this.selectedTasks[this.selectedProcessId] = task;
  },
  
  /**
   * 保存当前进程的任务配置
   * @param {string} taskType 任务类型
   * @param {Object} config 配置数据
   */
  saveTaskConfig(taskType, config) {
    if (!this.taskConfigs[this.selectedProcessId]) {
      this.taskConfigs[this.selectedProcessId] = this.getDefaultTaskConfigs();
    }
    this.taskConfigs[this.selectedProcessId][taskType] = config;
  },
  
  /**
   * 添加日志到当前进程
   * @param {Object} logEntry 日志条目
   */
  addLog(logEntry) {
    if (!this.processLogs[this.selectedProcessId]) {
      this.processLogs[this.selectedProcessId] = [];
    }
    this.processLogs[this.selectedProcessId].push(logEntry);
    
    // 限制最大日志数
    const maxLogs = 500;
    if (this.processLogs[this.selectedProcessId].length > maxLogs) {
      this.processLogs[this.selectedProcessId].shift();
    }
  },
  
  /**
   * 清空当前进程的日志
   */
  clearCurrentLogs() {
    this.processLogs[this.selectedProcessId] = [];
  }
};
