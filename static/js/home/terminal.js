/**
 * 终端管理模块
 * 处理日志输出和显示
 */
const TerminalManager = {
  elements: {
    terminalBody: null,
    clearTerminalBtn: null
  },
  maxLines: 500,
  websocket: null,
  isConnecting: false,
  hasLoggedDisconnect: false,

  init() {
    this.elements.terminalBody = document.getElementById('terminalBody');
    this.elements.clearTerminalBtn = document.getElementById('clearTerminalBtn');
    
    if (!this.elements.terminalBody) return;
    
    if (this.elements.clearTerminalBtn) {
      this.elements.clearTerminalBtn.addEventListener('click', () => this.clear());
    }
    
    this.connectWebSocket();
  },

  // 增加 device 参数
  addLog(message, type = 'info', source = null) {
    if (!this.elements.terminalBody) return;
    
    const ts = this.getTimestamp();
    const line = document.createElement('div');
    line.className = `terminal__line terminal__line--${type}`;

    let htmlContent = '';
    
    // 如果有日志来源，就显示在最前面
    if (source) {
        // 加了 terminal__device 类，方便你在 CSS 里给不同设备上色
        htmlContent += `<span class="terminal__device">[${source}]</span> `;
    }
    
    htmlContent += `<span class="terminal__timestamp">[${ts}]</span>${this.escapeHTML(message)}`;
    
    line.innerHTML = htmlContent;
    
    this.elements.terminalBody.appendChild(line);
    this.trimDOMLines();
    this.scrollToBottom();
  },

  clear() {
    if (this.elements.terminalBody) {
      this.elements.terminalBody.innerHTML = '';
    }
    this.addLog('日志已清空', 'info');
  },

  getTimestamp() {
    const now = new Date();
    const p = (n) => String(n).padStart(2, '0');
    return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())} ${p(now.getHours())}:${p(now.getMinutes())}:${p(now.getSeconds())}`;
  },

  trimDOMLines() {
    if (!this.elements.terminalBody) return;
    while (this.elements.terminalBody.children.length > this.maxLines) {
      this.elements.terminalBody.removeChild(this.elements.terminalBody.children[0]);
    }
  },

  scrollToBottom() {
    if (this.elements.terminalBody) {
      this.elements.terminalBody.scrollTop = this.elements.terminalBody.scrollHeight;
    }
  },

  escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  },

  connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/logs`;
    
    if (this.isConnecting) return;
    this.isConnecting = true;

    try {
      this.websocket = new WebSocket(url);
      
      this.websocket.onopen = () => {
        this.isConnecting = false;
        this.hasLoggedDisconnect = false;   // 连接成功，重置标志位
        this.addLog('已连接到日志服务器', 'success');
      };
      
      this.websocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          // 把后端传来的 source 字段透传给 addLog
          this.addLog(data.message, data.level || 'info', data.source);
        } catch (e) {
          this.addLog(event.data, 'raw');
        }
      };
      
      this.websocket.onclose = () => {
        this.isConnecting = false;
        // 避免日志刷屏
        if (!this.hasLoggedDisconnect) {
          this.addLog('与日志服务器的连接已断开', 'warning');
          this.hasLoggedDisconnect = true;
        }
        setTimeout(() => this.connectWebSocket(), 5000);
      };
      
      this.websocket.onerror = () => {
        // 避免日志刷屏
        if (!this.hasLoggedDisconnect) {
          this.addLog('WebSocket 连接错误', 'error');
        }
      };
    } catch (error) {
      this.isConnecting = false;
      this.addLog(`无法连接到日志服务器: ${error.message}`, 'error');
    }
  }
};
