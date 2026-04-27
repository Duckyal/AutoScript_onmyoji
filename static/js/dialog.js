/**
 * 对话框管理模块
 * 处理弹出对话框的显示和交互
 */

const DialogManager = {
  // DOM 元素引用
  elements: {
    // 添加进程对话框
    addProcessDialog: null,
    newProcessName: null,
    closeAddDialogBtn: null,
    cancelAddBtn: null,
    confirmAddBtn: null,
    
    // 重命名进程对话框
    renameProcessDialog: null,
    renameProcessName: null,
    closeRenameDialogBtn: null,
    cancelRenameBtn: null,
    confirmRenameBtn: null
  },
  
  // 当前正在重命名的进程ID
  currentRenamingId: null,
  
  /**
   * 初始化模块
   */
  init() {
    // 添加进程对话框元素
    this.elements.addProcessDialog = document.getElementById('addProcessDialog');
    this.elements.newProcessName = document.getElementById('newProcessName');
    this.elements.closeAddDialogBtn = document.getElementById('closeAddDialogBtn');
    this.elements.cancelAddBtn = document.getElementById('cancelAddBtn');
    this.elements.confirmAddBtn = document.getElementById('confirmAddBtn');
    
    // 重命名进程对话框元素
    this.elements.renameProcessDialog = document.getElementById('renameProcessDialog');
    this.elements.renameProcessName = document.getElementById('renameProcessName');
    this.elements.closeRenameDialogBtn = document.getElementById('closeRenameDialogBtn');
    this.elements.cancelRenameBtn = document.getElementById('cancelRenameBtn');
    this.elements.confirmRenameBtn = document.getElementById('confirmRenameBtn');
    
    this.bindEvents();
  },
  
  /**
   * 绑定事件
   */
  bindEvents() {
    // 添加进程对话框事件
    this.elements.closeAddDialogBtn.addEventListener('click', () => {
      this.hideAddProcessDialog();
    });
    
    this.elements.cancelAddBtn.addEventListener('click', () => {
      this.hideAddProcessDialog();
    });
    
    this.elements.confirmAddBtn.addEventListener('click', () => {
      this.confirmAddProcess();
    });
    
    this.elements.newProcessName.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        this.confirmAddProcess();
      } else if (e.key === 'Escape') {
        this.hideAddProcessDialog();
      }
    });
    
    // 重命名进程对话框事件
    this.elements.closeRenameDialogBtn.addEventListener('click', () => {
      this.hideRenameDialog();
    });
    
    this.elements.cancelRenameBtn.addEventListener('click', () => {
      this.hideRenameDialog();
    });
    
    this.elements.confirmRenameBtn.addEventListener('click', () => {
      this.confirmRename();
    });
    
    this.elements.renameProcessName.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        this.confirmRename();
      } else if (e.key === 'Escape') {
        this.hideRenameDialog();
      }
    });
    
    // 点击遮罩层关闭对话框
    this.elements.addProcessDialog.addEventListener('click', (e) => {
      if (e.target === this.elements.addProcessDialog) {
        this.hideAddProcessDialog();
      }
    });
    
    this.elements.renameProcessDialog.addEventListener('click', (e) => {
      if (e.target === this.elements.renameProcessDialog) {
        this.hideRenameDialog();
      }
    });
  },
  
  /**
   * 显示添加进程对话框
   */
  showAddProcessDialog() {
    // 设置默认名称
    this.elements.newProcessName.value = AppState.getNextProcessName();
    
    // 显示对话框
    this.elements.addProcessDialog.style.display = '';
    
    // 聚焦并选中输入框内容
    setTimeout(() => {
      this.elements.newProcessName.focus();
      this.elements.newProcessName.select();
    }, 100);
  },
  
  /**
   * 隐藏添加进程对话框
   */
  hideAddProcessDialog() {
    this.elements.addProcessDialog.style.display = 'none';
    this.elements.newProcessName.value = '';
  },
  
  /**
   * 确认添加进程
   */
  confirmAddProcess() {
    const name = this.elements.newProcessName.value.trim();
    if (name) {
      ProcessManager.addProcess(name);
      this.hideAddProcessDialog();
    }
  },
  
  /**
   * 显示重命名对话框
   * @param {number} id 进程ID
   * @param {string} currentName 当前名称
   */
  showRenameDialog(id, currentName) {
    this.currentRenamingId = id;
    this.elements.renameProcessName.value = currentName;
    
    // 显示对话框
    this.elements.renameProcessDialog.style.display = '';
    
    // 聚焦并选中输入框内容
    setTimeout(() => {
      this.elements.renameProcessName.focus();
      this.elements.renameProcessName.select();
    }, 100);
  },
  
  /**
   * 隐藏重命名对话框
   */
  hideRenameDialog() {
    this.elements.renameProcessDialog.style.display = 'none';
    this.elements.renameProcessName.value = '';
    this.currentRenamingId = null;
  },
  
  /**
   * 确认重命名
   */
  confirmRename() {
    const newName = this.elements.renameProcessName.value.trim();
    if (newName && this.currentRenamingId !== null) {
      ProcessManager.renameProcess(this.currentRenamingId, newName);
      this.hideRenameDialog();
    }
  }
};
