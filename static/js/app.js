/**
 * 应用主入口
 */
const App = {
  deviceName: '',
  baseMode: 'auto', // 由于 HTML 中没有模式选择器，这里默认给 auto

  init() {
    // 从 URL 获取设备名
    const params = new URLSearchParams(window.location.search);
    this.deviceName = params.get('device_name') || '';

    // 初始化模块
    if (typeof TerminalManager !== 'undefined') TerminalManager.init();
    if (typeof TaskManager !== 'undefined') TaskManager.init();

    this.bindEvents();
  },

  bindEvents() {
    const startBtn = document.getElementById('startBtn');
    if (startBtn) {
      startBtn.addEventListener('click', () => this.startTask());
    }
  },

  async startTask() {
    const { task, config } = TaskManager.getCurrentConfig();

    // 获取当前任务的中文显示名
    const activeItem = document.querySelector('.sidebar-task__item.active');
    const displayName = activeItem ? activeItem.dataset.name : task;
    TerminalManager.addLog(`准备启动任务: ${displayName}`, 'info');

    // 发送给后端的执行参数
    const payload = {
      task: task,
      base: {
        device: this.deviceName,
        mode: this.baseMode
      },
      config: config
    };

    console.log("准备发送的配置:", payload);

    try {
      let response;
      
      if (task === 'custom') {
        // 自定义任务上传文件
        if (!TaskManager.currentPyFile) {
          TerminalManager.addLog('请先选择一个 Python 脚本文件', 'error');
          return;
        }
        
        const formData = new FormData();
        formData.append('process', payload.process);
        formData.append('file', TaskManager.currentPyFile);
        
        // 注意：后端的 custom 接口可能不需要 base/config，但带上 process 是必须的
        response = await fetch('/start', {
          method: 'POST',
          body: formData
        });
      } else {
        // 普通任务发送 JSON
        response = await fetch('/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }

      if (response.ok) {
        const result = await response.json();
        TerminalManager.addLog('任务已成功提交至后端执行', 'success');
      } else {
        const errText = await response.text();
        TerminalManager.addLog(`后端返回错误: ${errText}`, 'error');
      }
    } catch (error) {
      TerminalManager.addLog(`任务发送失败: ${error.message}`, 'error');
    }
  }
};

// DOM 加载完成后初始化应用
document.addEventListener('DOMContentLoaded', () => {
  App.init();
});
