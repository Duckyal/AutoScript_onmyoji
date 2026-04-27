/**
 * 终端管理模块
 * 处理日志输出和显示
 */

const TerminalManager = {
  // DOM 元素引用
  elements: {
    terminalBody: null,
    clearTerminalBtn: null
  },
  
  // 最大日志行数
  maxLines: 500,
  
  // WebSocket 连接（用于接收 FastAPI 日志）
  websocket: null,
  
  /**
   * 初始化模块
   */
  init() {
    this.elements.terminalBody = document.getElementById('terminalBody');
    this.elements.clearTerminalBtn = document.getElementById('clearTerminalBtn');
    
    this.bindEvents();
    this.loadProcessLogs();
    
    // 如果需要，连接 WebSocket
    this.connectWebSocket();
  },
  
  /**
   * 绑定事件
   */
  bindEvents() {
    this.elements.clearTerminalBtn.addEventListener('click', () => {
      this.clear();
    });
  },
  
  /**
   * 加载当前进程的日志
   */
  loadProcessLogs() {
    // 清空当前显示
    this.elements.terminalBody.innerHTML = '';
    
    // 加载当前进程的日志
    const logs = AppState.getCurrentLogs();
    logs.forEach(log => {
      this.renderLogLine(log.message, log.type, log.timestamp);
    });
    
    // 滚动到底部
    this.scrollToBottom();
  },
  
  /**
   * 渲染日志行（不保存到状态）
   * @param {string} message 日志消息
   * @param {string} type 日志类型
   * @param {string} timestamp 时间戳
   */
  renderLogLine(message, type = 'info', timestamp = null) {
    const ts = timestamp || this.getTimestamp();
    const line = document.createElement('div');
    line.className = `terminal__line terminal__line--${type}`;
    line.innerHTML = `<span class="terminal__timestamp">[${ts}]</span>${this.escapeHTML(message)}`;
    
    this.elements.terminalBody.appendChild(line);
    
    // 限制最大行数（仅限DOM）
    this.trimDOMLines();
  },
  
  /**
   * 添加日志
   * @param {string} message 日志消息
   * @param {string} type 日志类型 (info|success|warning|error)
   */
  addLog(message, type = 'info') {
    const timestamp = this.getTimestamp();
    
    // 保存到状态
    AppState.addLog({
      message: message,
      type: type,
      timestamp: timestamp
    });
    
    // 渲染到DOM
    this.renderLogLine(message, type, timestamp);
    
    // 滚动到底部
    this.scrollToBottom();
  },
  
  /**
   * 添加原始日志（来自 FastAPI）
   * @param {string} rawMessage 原始日志消息
   */
  addRawLog(rawMessage) {
    const timestamp = this.getTimestamp();
    
    // 保存到状态
    AppState.addLog({
      message: rawMessage,
      type: 'raw',
      timestamp: timestamp
    });
    
    const line = document.createElement('div');
    line.className = 'terminal__line';
    line.textContent = rawMessage;
    
    this.elements.terminalBody.appendChild(line);
    this.trimDOMLines();
    this.scrollToBottom();
  },
  
  /**
   * 清空日志
   */
  clear() {
    // 清空状态中的日志
    AppState.clearCurrentLogs();
    
    // 清空DOM
    this.elements.terminalBody.innerHTML = '';
    this.addLog('日志已清空', 'info');
  },
  
  /**
   * 获取当前时间戳
   * @returns {string} 格式化的时间戳
   */
  getTimestamp() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  },
  
  /**
   * 限制DOM中的日志行数
   */
  trimDOMLines() {
    const lines = this.elements.terminalBody.children;
    while (lines.length > this.maxLines) {
      lines[0].remove();
    }
  },
  
  /**
   * 滚动到底部
   */
  scrollToBottom() {
    this.elements.terminalBody.scrollTop = this.elements.terminalBody.scrollHeight;
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
  },
  
  /**
   * 连接 WebSocket 接收 FastAPI 日志
   * @param {string} url WebSocket URL
   */
  connectWebSocket(url = 'ws://localhost:8000/logs') {
    // 防止页面还没加载完就疯狂重连
    if (this.isConnecting) return; 
    this.isConnecting = true;

    try {
      this.websocket = new WebSocket(url);
      
      this.websocket.onopen = () => {
        this.addLog('已连接到日志服务器', 'success');
      };
      
      this.websocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // 根据 source 区分来源，用不同前缀显示
          if (data.source === 'script') {
            this.addLog(`[脚本] ${data.message}`, 'info');
          } else {
            this.addLog(data.message, data.level || 'info');
          }
        } catch (e) {
          // 如果不是 JSON，直接输出原始消息
          this.addRawLog(event.data);
        }
      };
      
      this.websocket.onclose = () => {
        this.addLog('与日志服务器的连接已断开', 'warning');
        // 5秒后尝试重连
        setTimeout(() => this.connectWebSocket(url), 5000);
      };
      
      this.websocket.onerror = (error) => {
        this.addLog('WebSocket 连接错误', 'error');
      };
    } catch (error) {
      this.addLog(`无法连接到日志服务器: ${error.message}`, 'error');
    }
  },
  
  /**
   * 断开 WebSocket 连接
   */
  disconnectWebSocket() {
    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }
  }
};
