/**
 * 终端管理模块
 * 处理日志输出和显示
 */
const TerminalManager = {
  elements: {
    terminalBody: null,
    clearTerminalBtn: null,
    autoScrollBtn: null,
    deviceFilter: null
  },
  maxLines: 500,
  websocket: null,
  isConnecting: false,
  hasLoggedDisconnect: false,
  autoScrollEnabled: true,
  // 日志存储，用于筛选后重建
  logs: [],
  // 已发现的设备列表
  devices: new Set(),
  // 当前筛选的设备
  currentFilter: 'all',

  init() {
    this.elements.terminalBody = document.getElementById('terminalBody');
    this.elements.clearTerminalBtn = document.getElementById('clearTerminalBtn');
    this.elements.autoScrollBtn = document.getElementById('autoScrollBtn');
    this.elements.deviceFilter = document.getElementById('deviceFilter');
    
    if (!this.elements.terminalBody) return;
    
    if (this.elements.clearTerminalBtn) {
      this.elements.clearTerminalBtn.addEventListener('click', () => this.clear());
    }
    
    if (this.elements.autoScrollBtn) {
      this.elements.autoScrollBtn.addEventListener('click', () => this.toggleAutoScroll());
      this.updateAutoScrollButton();
    }

    if (this.elements.deviceFilter) {
      this.elements.deviceFilter.addEventListener('change', (e) => {
        this.currentFilter = e.target.value;
        this.renderLogs();
      });
    }
    
    // 监听手动滚动，当用户手动滚动时自动关闭自动滚动
    this.elements.terminalBody.addEventListener('scroll', () => {
      if (this.autoScrollEnabled) {
        const isAtBottom = this.elements.terminalBody.scrollHeight - this.elements.terminalBody.scrollTop <= this.elements.terminalBody.clientHeight + 10;
        if (!isAtBottom) {
          this.autoScrollEnabled = false;
          this.updateAutoScrollButton();
        }
      }
    });
    
    this.connectWebSocket();
  },

  // 添加日志（保存到内存并显示）
  addLog(message, type = 'info', source = null) {
    if (!this.elements.terminalBody) return;
    
    // 保存到日志存储
    this.logs.push({ message, type, source });
    if (this.logs.length > this.maxLines) {
      this.logs.shift();
    }
    
    // 更新设备列表
    if (source && !this.devices.has(source)) {
      this.devices.add(source);
      this.updateDeviceFilter();
    }
    
    // 根据筛选条件决定是否显示
    if (!this.shouldShow(source)) return;
    
    this.appendLogElement(message, type, source);
    this.trimDOMLines();
    this.scrollToBottom();
  },

  // 判断是否应该显示此日志
  shouldShow(source) {
    if (this.currentFilter === 'all') return true;
    return source === this.currentFilter;
  },

  // 更新设备筛选下拉框
  updateDeviceFilter() {
    if (!this.elements.deviceFilter) return;
    const currentValue = this.currentFilter;
    this.elements.deviceFilter.innerHTML = '<option value="all">全部设备</option>';
    this.devices.forEach(device => {
      const option = document.createElement('option');
      option.value = device;
      option.textContent = device;
      this.elements.deviceFilter.appendChild(option);
    });
    this.elements.deviceFilter.value = currentValue;
  },

  // 渲染所有日志（用于筛选切换时重建）
  renderLogs() {
    if (!this.elements.terminalBody) return;
    this.elements.terminalBody.innerHTML = '';
    this.logs.forEach(log => {
      if (this.shouldShow(log.source)) {
        this.appendLogElement(log.message, log.type, log.source);
      }
    });
  },

  // 追加单个日志元素到终端
  appendLogElement(message, type, source) {
    const ts = this.getTimestamp();
    const line = document.createElement('div');
    line.className = `terminal__line terminal__line--${type}`;

    let htmlContent = '';
    
    // 如果有日志来源，就显示在最前面
    if (source) {
        htmlContent += `<span class="terminal__device">[${source}]</span> `;
    }
    
    htmlContent += `<span class="terminal__timestamp">[${ts}]</span>${this.escapeHTML(message)}`;
    
    line.innerHTML = htmlContent;
    this.elements.terminalBody.appendChild(line);
  },

  clear() {
    if (this.elements.terminalBody) {
      this.elements.terminalBody.innerHTML = '';
    }
    this.logs = [];
    this.devices.clear();
    this.updateDeviceFilter();
    // 通知后端清空历史日志
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      this.websocket.send(JSON.stringify({ type: 'clear_history' }));
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
    if (this.elements.terminalBody && this.autoScrollEnabled) {
      this.elements.terminalBody.scrollTop = this.elements.terminalBody.scrollHeight;
    }
  },

  toggleAutoScroll() {
    this.autoScrollEnabled = !this.autoScrollEnabled;
    this.updateAutoScrollButton();
    if (this.autoScrollEnabled) {
      this.scrollToBottom();
      this.addLog('已启用自动滚动', 'info');
    } else {
      this.addLog('已禁用自动滚动', 'info');
    }
  },

  updateAutoScrollButton() {
    if (!this.elements.autoScrollBtn) return;
    if (this.autoScrollEnabled) {
      this.elements.autoScrollBtn.classList.add('terminal__auto-scroll-btn--active');
      this.elements.autoScrollBtn.setAttribute('title', '自动滚动已开启，点击关闭');
    } else {
      this.elements.autoScrollBtn.classList.remove('terminal__auto-scroll-btn--active');
      this.elements.autoScrollBtn.setAttribute('title', '自动滚动已关闭，点击开启');
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
          // 处理历史日志
          if (data.type === 'history') {
            this.addLog('===== 历史日志 =====', 'info');
            data.logs.forEach(log => {
              this.addLog(log.message, log.level || 'info', log.source);
            });
            this.addLog('===== 历史日志结束 =====', 'info');
          } else {
            // 把后端传来的 source 字段透传给 addLog
            this.addLog(data.message, data.level || 'info', data.source);
          }
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
