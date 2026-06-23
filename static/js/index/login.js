const deviceInput = document.getElementById('deviceInput');
const datalist = document.getElementById('adbDevices');
const refreshBtn = document.getElementById('refreshBtn');
const statusText = document.getElementById('statusText');
const loginBtn = document.getElementById('loginBtn');
const devBtn = document.getElementById('devBtn');

// 获取设备的函数
async function fetchDevices() {
  refreshBtn.disabled = true;
  refreshBtn.textContent = '正在搜索设备...';
  statusText.textContent = '';
  
  try {
    // 请求后端的 /api/get_devices 接口
    const response = await fetch('/api/get_devices');
    if (!response.ok) throw new Error('网络响应错误');
    
    const data = await response.json();
    
    // 清空旧的选项
    datalist.innerHTML = '';
    
    if (data.devices && data.devices.length > 0) {
      // 有设备，填充下拉框
      data.devices.forEach(device => {
        const option = document.createElement('option');
        option.value = device;
        datalist.appendChild(option);
      });
      statusText.style.color = '#a6e3a1'; // 绿色提示
      statusText.textContent = `成功检测到 ${data.devices.length} 个设备`;
    } else {
      // 无设备
      statusText.style.color = '#f38ba8';
      statusText.textContent = '未检测到已连接的设备';
    }
  } catch (error) {
    console.error('获取设备失败:', error);
    statusText.style.color = '#f38ba8';
    statusText.textContent = '获取设备失败，请检查后端是否运行';
  } finally {
    refreshBtn.disabled = false;
    refreshBtn.textContent = '刷新设备列表';
  }
}

// 页面加载完成时，自动获取一次设备
window.addEventListener('DOMContentLoaded', fetchDevices);

// 绑定刷新按钮
refreshBtn.addEventListener('click', fetchDevices);

// 绑定设备页按钮
loginBtn.addEventListener('click', async function() {
  let deviceName = deviceInput.value.trim();
  // 如果输入框为空
  if (!deviceName) {
    const availableDevices = datalist.options;
    
    if (availableDevices.length === 1) {
    // 列表只有 1 个设备，自动使用它
        deviceName = availableDevices[0].value;
    } else if (availableDevices.length === 0) {
        // 没有设备
        statusText.style.color = '#f38ba8';
        statusText.textContent = '未检测到设备，请先连接设备或手动输入';
        return;
    } else {
        // 有多个设备，必须手动选择
        statusText.style.color = '#f38ba8';
        statusText.textContent = '检测到多个设备，请在下拉列表中选择一个';
        return;
    }
  }

  // 跳转到设备管理页（/home）
  setTimeout(() => {
    window.location.href = '/home?device=' + encodeURIComponent(deviceName);
  }, 100);
});

// 绑定开发页按钮
devBtn.addEventListener('click', async function() {
  let deviceName = deviceInput.value.trim();
  // 如果输入框为空
  if (!deviceName) {
    const availableDevices = datalist.options;
    
    if (availableDevices.length === 1) {
    // 列表只有 1 个设备，自动使用它
        deviceName = availableDevices[0].value;
    } else if (availableDevices.length === 0) {
        // 没有设备
        statusText.style.color = '#f38ba8';
        statusText.textContent = '未检测到设备，请先连接设备或手动输入';
        return;
    } else {
        // 有多个设备，必须手动选择
        statusText.style.color = '#f38ba8';
        statusText.textContent = '检测到多个设备，请在下拉列表中选择一个';
        return;
    }
  }

  // 跳转到设备开发页（/dev）
  setTimeout(() => {
    window.location.href = '/dev?device=' + encodeURIComponent(deviceName);
  }, 100);
});