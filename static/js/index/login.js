const deviceInput = document.getElementById('deviceInput');
const datalist = document.getElementById('adbDevices');
const refreshBtn = document.getElementById('refreshBtn');
const statusText = document.getElementById('statusText');

// 当输入框被点击时，强制显示所有设备选项
deviceInput.addEventListener('click', function () {
  if (datalist.options.length === 0) return;
  
  // 保存当前值
  const val = deviceInput.value;
  // 清空值（强制浏览器显示所有选项）
  deviceInput.value = '';
  // 下一帧恢复值
  requestAnimationFrame(() => {
    deviceInput.value = val;
    // 选中所有文字，方便用户直接编辑
    deviceInput.select();
  });
});

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

// 解析用户选中的设备：输入框有值用输入值；为空时，单设备自动取用、无设备/多设备则提示
function resolveDevice() {
  let deviceName = deviceInput.value.trim();
  if (deviceName) return deviceName;

  const availableDevices = datalist.options;
  if (availableDevices.length === 1) {
    // 列表只有 1 个设备，自动使用它
    return availableDevices[0].value;
  }
  if (availableDevices.length === 0) {
    statusText.style.color = '#f38ba8';
    statusText.textContent = '未检测到设备，请先连接设备或手动输入';
    return null;
  }
  statusText.style.color = '#f38ba8';
  statusText.textContent = '检测到多个设备，请在下拉列表中选择一个';
  return null;
}

// 通用入口绑定：校验设备后跳转到目标页面
function bindEntry(btnId, path) {
  document.getElementById(btnId).addEventListener('click', function() {
    const deviceName = resolveDevice();
    if (!deviceName) return;
    // 跳转到对应页面（/home 完整控制台 /dev 开发页 /float 悬浮遥控·简易控制）
    setTimeout(() => {
      window.location.href = path + '?device=' + encodeURIComponent(deviceName);
    }, 100);
  });
}

bindEntry('loginBtn', '/home');   // 设备页（完整控制台）
bindEntry('devBtn', '/dev');      // 开发页

// 右上角切换图标 → 悬浮遥控(简易控制)：不强求先选设备，已在输入框填过就带上
document.getElementById('floatBtn').addEventListener('click', function (e) {
  e.preventDefault();
  const deviceName = deviceInput.value.trim();
  setTimeout(() => {
    window.location.href = '/float' + (deviceName ? '?device=' + encodeURIComponent(deviceName) : '');
  }, 100);
});