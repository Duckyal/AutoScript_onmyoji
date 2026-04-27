/**
 * 应用主入口
 * 初始化所有模块
 */

const App = {
  /**
   * 初始化应用
   */
  init() {
    // 初始化各模块
    TerminalManager.init();
    ProcessManager.init();
    TaskManager.init();
    DialogManager.init();
    
    // 添加初始化日志
    TerminalManager.addLog('系统就绪，等待任务...', 'success');
    
    // 绑定全局事件
    this.bindGlobalEvents();
  },
  
  /**
   * 绑定全局事件
   */
  bindGlobalEvents() {
    // ESC 键关闭所有对话框
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        DialogManager.hideAddProcessDialog();
        DialogManager.hideRenameDialog();
      }
    });
    
    // 防止表单提交刷新页面
    document.querySelectorAll('form').forEach(form => {
      form.addEventListener('submit', (e) => {
        e.preventDefault();
      });
    });
    
    // 启动按钮点击事件
    const startBtn = document.getElementById('startBtn');
    if (startBtn) {
      startBtn.addEventListener('click', () => {
        this.startTask();
      });
    }
  },
  
  /**
   * 获取当前配置（用于发送到 FastAPI）
   * @returns {Object} 配置对象
   */
  getCurrentConfig() {
    const currentProcess = AppState.getCurrentProcess();
    const taskName = AppState.getCurrentTask();
    const taskConfig = TaskManager.getCurrentConfig();
    
    return {
      process: currentProcess?.name,
      task: taskName,
      config: taskConfig
    };
  },
  
  /**
   * 启动任务（示例方法，需要连接实际的 FastAPI）
   */
  async startTask() {
    const config = this.getCurrentConfig();
    TerminalManager.addLog(`启动任务: ${TaskManager.taskNames[config.task]}`, 'info');
    let response;

    // 调用 FastAPI
    try {
      if (config.task==='custom') {
        // 自定义任务，上传py文件
        const formData = new FormData();
        // 附带文本参数（后端用 Form() 接收）
        formData.append('process', config.process);
        // 注意：这里假设你在选文件时，把 File 对象存到了 AppState 里
        const pyFile = TaskManager.currentPyFile; 
        if (pyFile) {
          formData.append('file', pyFile); // 'file' 必须和后端参数名一致
        } else {
          TerminalManager.addLog('未找到待执行的 Python 文件', 'error');
          return;
        }
        response = await fetch('/start', {
          method: 'POST',
          body: formData 
        });
      } else {
        response = await fetch('/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(config)
        });
      }
    } catch (error) {
      TerminalManager.addLog(`任务发送失败: ${error.message}`, 'error');
    }
  },
  
  /**
   * 停止任务（示例方法） ng：暂无前端对接
   */
  async stopTask() {
    TerminalManager.addLog('正在停止任务...', 'warning');
    
    // TODO: 实际实现时，调用 FastAPI
  }
};

// DOM 加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
  App.init();
});
