const urlParams = new URLSearchParams(window.location.search);
const deviceName = urlParams.get('device') || '未指定设备';
document.getElementById('device-name').textContent = deviceName;

fetch(`/api/start_stream?device_name=${deviceName}`).catch(err => console.error(err));

const sidebar = document.getElementById('sidebar');
const toggleBtn = document.getElementById('toggle-btn');
toggleBtn.addEventListener('click', () => {
    sidebar.classList.toggle('hidden');
    toggleBtn.textContent = sidebar.classList.contains('hidden') ? '显示工具栏' : '隐藏工具栏';
});

const streamContainer = document.getElementById('stream-container');
const streamImg = document.getElementById('stream-img');
const overlay = document.getElementById('selection-overlay');
const screenshotMode = document.getElementById('screenshot-mode');
const cropPreview = document.getElementById('crop-preview');
const folderPathInput = document.getElementById('folder-path');
const fileNameInput = document.getElementById('file-name');
const saveBtn = document.getElementById('save-btn');
const uploadBtn = document.getElementById('upload-btn');
const fileInput = document.getElementById('file-input');

if (overlay) {
    overlay.style.position = 'absolute';
    overlay.style.border = '2px solid #ff0000';
    overlay.style.backgroundColor = 'rgba(255, 0, 0, 0.2)';
    overlay.style.pointerEvents = 'none';
    overlay.style.display = 'none';
    overlay.style.zIndex = '100';
}

if (screenshotMode) {
    screenshotMode.addEventListener('change', () => {
        streamContainer.style.cursor = screenshotMode.checked ? 'crosshair' : 'default';
    });
}

const streamInterval = document.getElementById('stream-interval');
const streamIntervalValue = document.getElementById('stream-interval-value');
const btnSetInterval = document.getElementById('btn-set-interval');

if (streamInterval) {
    streamInterval.addEventListener('input', (e) => {
        const ms = parseInt(e.target.value);
        const fps = Math.round(1000 / ms);
        streamIntervalValue.textContent = `${ms}ms (约${fps}fps)`;
    });
}

if (btnSetInterval) {
    btnSetInterval.addEventListener('click', () => {
        const msValue = parseInt(streamInterval.value);
        if (isNaN(msValue) || msValue < 1 || msValue > 60) {
            alert('请输入1-60之间的数值');
            return;
        }
        const interval = msValue / 1000;
        const originalText = btnSetInterval.textContent;
        btnSetInterval.textContent = '设置中...';
        btnSetInterval.disabled = true;
        btnSetInterval.style.opacity = '0.6';
        
        fetch('/api/set_stream_interval', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ interval })
        }).then(res => res.json())
          .then(data => {
              btnSetInterval.textContent = '✓ 设置成功';
              btnSetInterval.style.backgroundColor = '#22c55e';
              statusDiv.textContent = '截图间隔已更新';
              setTimeout(() => {
                  btnSetInterval.textContent = originalText;
                  btnSetInterval.disabled = false;
                  btnSetInterval.style.opacity = '1';
                  btnSetInterval.style.backgroundColor = '#3b82f6';
                  updateStreamStatus();
              }, 1500);
          })
          .catch(err => {
              console.error('设置间隔失败:', err);
              btnSetInterval.textContent = '✗ 设置失败';
              btnSetInterval.style.backgroundColor = '#ef4444';
              statusDiv.textContent = '设置失败';
              setTimeout(() => {
                  btnSetInterval.textContent = originalText;
                  btnSetInterval.disabled = false;
                  btnSetInterval.style.opacity = '1';
                  btnSetInterval.style.backgroundColor = '#3b82f6';
                  updateStreamStatus();
              }, 1500);
          });
    });
}

const statusDiv = document.createElement('div');
Object.assign(statusDiv.style, {
    position: 'absolute',
    top: '10px',
    left: '10px',
    padding: '5px 12px',
    borderRadius: '4px',
    backgroundColor: 'rgba(0,0,0,0.6)',
    color: '#fff',
    fontSize: '13px',
    zIndex: '100',
    pointerEvents: 'none',
    transition: 'opacity 0.3s'
});
statusDiv.textContent = '正在初始化...';
streamContainer.appendChild(statusDiv);

function updateStreamStatus() {
    fetch('/api/stream_status')
        .then(res => res.json())
        .then(data => {
            statusDiv.textContent = data.message || '未知状态';
            if (data.connected) {
                statusDiv.style.backgroundColor = 'rgba(40, 167, 69, 0.9)';
                setTimeout(() => { statusDiv.style.opacity = '0'; }, 2000);
            } else {
                statusDiv.style.opacity = '1';
                if (data.message.includes('失败') || data.message.includes('停止')) {
                    statusDiv.style.backgroundColor = 'rgba(220, 53, 69, 0.9)';
                } else {
                    statusDiv.style.backgroundColor = 'rgba(255, 193, 7, 0.9)';
                }
            }
        })
        .catch(err => {
            statusDiv.textContent = '状态获取失败';
            statusDiv.style.backgroundColor = 'rgba(220, 53, 69, 0.9)';
        });
}
setInterval(updateStreamStatus, 2000);
updateStreamStatus();


// =================== 视频流重连机制 ===================
let streamRetryCount = 0;
const MAX_RETRY_COUNT = 5;

function initStream() {
    streamImg.onerror = function() {
        streamRetryCount++;
        if (streamRetryCount <= MAX_RETRY_COUNT) {
            statusDiv.textContent = `连接失败，${streamRetryCount}/${MAX_RETRY_COUNT} 重试中...`;
            statusDiv.style.backgroundColor = 'rgba(255, 193, 7, 0.9)';
            statusDiv.style.opacity = '1';
            
            setTimeout(() => {
                streamImg.src = `/api/stream?device=${deviceName}&_t=${Date.now()}`;
            }, 2000);
        } else {
            statusDiv.textContent = '连接失败，请刷新页面';
            statusDiv.style.backgroundColor = 'rgba(220, 53, 69, 0.9)';
        }
    };
    
    streamImg.onload = function() {
        streamRetryCount = 0;
        if (statusDiv.textContent.includes('重试') || statusDiv.textContent.includes('失败')) {
            statusDiv.textContent = '画面恢复';
            statusDiv.style.backgroundColor = 'rgba(40, 167, 69, 0.9)';
        }
    };
    
    streamImg.src = `/api/stream?device=${deviceName}&_t=${Date.now()}`;
}

initStream();

// =================== 横屏检测 ===================
function isMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

function checkOrientation() {
    if (isMobile()) {
        document.body.classList.add('mobile-device');
    }
}

checkOrientation();
let isDrawing = false;
let startX = 0, startY = 0;
let startClientX = 0, startClientY = 0;
let croppedBlob = null;
let mouseDownTime = 0;
let mouseDownCoords = {x: 0, y: 0};

let deviceResolution = { width: 0, height: 0 };

async function fetchDeviceResolution() {
    try {
        const res = await fetch(`/api/device_resolution?device_name=${encodeURIComponent(deviceName)}`);
        const data = await res.json();
        if (data.success) {
            deviceResolution.width = data.width;
            deviceResolution.height = data.height;
        }
    } catch (err) {
        console.error("获取设备分辨率失败:", err);
    }
}
fetchDeviceResolution();

function getVideoBounds() {
    const rect = streamImg.getBoundingClientRect();
    const nw = streamImg.naturalWidth;
    const nh = streamImg.naturalHeight;
    
    if (nw === 0 || nh === 0) return null;

    const containerW = rect.width;
    const containerH = rect.height;
    
    const videoRatio = nw / nh;
    const containerRatio = containerW / containerH;
    
    let contentW, contentH, offsetX, offsetY;

    if (containerRatio > videoRatio) {
        contentH = containerH;
        contentW = containerH * videoRatio;
        offsetX = (containerW - contentW) / 2;
        offsetY = 0;
    } else {
        contentW = containerW;
        contentH = containerW / videoRatio;
        offsetX = 0;
        offsetY = (containerH - contentH) / 2;
    }

    return {
        left: rect.left + offsetX,
        top: rect.top + offsetY,
        width: contentW,
        height: contentH,
        naturalW: nw,
        naturalH: nh
    };
}

function getRealCoords(clientX, clientY) {
    const bounds = getVideoBounds();
    if (!bounds) return { x: 0, y: 0 };

    let x = clientX - bounds.left;
    let y = clientY - bounds.top;
    
    x = Math.max(0, Math.min(x, bounds.width));
    y = Math.max(0, Math.min(y, bounds.height));
    
    const displayToVideoX = bounds.naturalW / bounds.width;
    const displayToVideoY = bounds.naturalH / bounds.height;
    
    let videoToDeviceX = 1;
    let videoToDeviceY = 1;
    
    if (deviceResolution.width > 0 && deviceResolution.height > 0) {
        const isVideoLandscape = bounds.naturalW > bounds.naturalH;
        const isDeviceLandscape = deviceResolution.width > deviceResolution.height;
        
        if (isVideoLandscape === isDeviceLandscape) {
            videoToDeviceX = deviceResolution.width / bounds.naturalW;
            videoToDeviceY = deviceResolution.height / bounds.naturalH;
        } else {
            videoToDeviceX = deviceResolution.height / bounds.naturalW;
            videoToDeviceY = deviceResolution.width / bounds.naturalH;
        }
    }
    
    const realX = Math.round(x * displayToVideoX * videoToDeviceX);
    const realY = Math.round(y * displayToVideoY * videoToDeviceY);
    
    return { x: realX, y: realY };
}

// =================== adb操作 ===================
uploadBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
        cropPreview.src = event.target.result;
        cropPreview.style.display = 'block';
        croppedBlob = file;
    };
    reader.readAsDataURL(file);
});

streamContainer.addEventListener('mousedown', (e) => {
    e.preventDefault();

    if (e.button === 1) {
        screenshotMode.checked = !screenshotMode.checked;
        streamContainer.style.cursor = screenshotMode.checked ? 'crosshair' : 'default';
        return;
    }
    if (e.button !== 0) return;

    mouseDownTime = Date.now();
    mouseDownCoords = getRealCoords(e.clientX, e.clientY);

    if (screenshotMode.checked) {
        isDrawing = true;
        startClientX = e.clientX;
        startClientY = e.clientY;
        
        const cRect = streamContainer.getBoundingClientRect();
        let rawX = e.clientX - cRect.left;
        let rawY = e.clientY - cRect.top;

        startX = Math.max(0, Math.min(rawX, cRect.width));
        startY = Math.max(0, Math.min(rawY, cRect.height));

        overlay.style.left = startX + 'px';
        overlay.style.top = startY + 'px';
        overlay.style.width = '0px';
        overlay.style.height = '0px';
        overlay.style.display = 'block';
    }
});

streamContainer.addEventListener('mousemove', (e) => {
    if (!isDrawing) return;
    const cRect = streamContainer.getBoundingClientRect();

    let currentX = e.clientX - cRect.left;
    let currentY = e.clientY - cRect.top;

    currentX = Math.max(0, Math.min(currentX, cRect.width));
    currentY = Math.max(0, Math.min(currentY, cRect.height));

    const width = currentX - startX;
    const height = currentY - startY;

    overlay.style.left = (width < 0 ? currentX : startX) + 'px';
    overlay.style.top = (height < 0 ? currentY : startY) + 'px';
    overlay.style.width = Math.abs(width) + 'px';
    overlay.style.height = Math.abs(height) + 'px';
});

streamContainer.addEventListener('mouseup', async (e) => {
    if (e.button !== 0) return;

    if (screenshotMode.checked && isDrawing) {
        isDrawing = false;
        overlay.style.display = 'none';

        const startReal = getRealCoords(startClientX, startClientY);
        const endReal = getRealCoords(e.clientX, e.clientY);

        const realX = Math.min(startReal.x, endReal.x);
        const realY = Math.min(startReal.y, endReal.y);
        const cropW = Math.abs(endReal.x - startReal.x);
        const cropH = Math.abs(endReal.y - startReal.y);

        if (cropW < 5 || cropH < 5) return;

        const frameImg = new Image();
        frameImg.crossOrigin = "Anonymous";
        frameImg.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = cropW;
            canvas.height = cropH;
            const ctx = canvas.getContext('2d');
            
            try {
                ctx.drawImage(frameImg, realX, realY, cropW, cropH, 0, 0, cropW, cropH);
                canvas.toBlob((blob) => {
                    if (!blob) return;
                    croppedBlob = blob;
                    const url = URL.createObjectURL(blob);
                    cropPreview.src = url;
                    cropPreview.style.display = 'block';
                    
                    document.getElementById('region-x1').value = realX;
                    document.getElementById('region-y1').value = realY;
                    document.getElementById('region-x2').value = realX + cropW;
                    document.getElementById('region-y2').value = realY + cropH;
                }, 'image/png');
            } catch (err) {
                console.error("Canvas error:", err);
            }
        };
        frameImg.src = `/api/current_frame?device_name=${encodeURIComponent(deviceName)}&_t=${Date.now()}`;

    } else {
        const endCoords = getRealCoords(e.clientX, e.clientY);
        const duration = Date.now() - mouseDownTime;
        const distX = Math.abs(endCoords.x - mouseDownCoords.x);
        const distY = Math.abs(endCoords.y - mouseDownCoords.y);

        sendInputAction(endCoords, duration, distX, distY);
    }
});

// =================== Touch Events for Mobile ===================
streamContainer.addEventListener('touchstart', (e) => {
    e.preventDefault();
    const touch = e.touches[0];
    
    mouseDownTime = Date.now();
    mouseDownCoords = getRealCoords(touch.clientX, touch.clientY);

    if (screenshotMode.checked) {
        isDrawing = true;
        startClientX = touch.clientX;
        startClientY = touch.clientY;
        
        const cRect = streamContainer.getBoundingClientRect();
        let rawX = touch.clientX - cRect.left;
        let rawY = touch.clientY - cRect.top;

        startX = Math.max(0, Math.min(rawX, cRect.width));
        startY = Math.max(0, Math.min(rawY, cRect.height));

        overlay.style.left = startX + 'px';
        overlay.style.top = startY + 'px';
        overlay.style.width = '0px';
        overlay.style.height = '0px';
        overlay.style.display = 'block';
    }
}, { passive: false });

streamContainer.addEventListener('touchmove', (e) => {
    if (!isDrawing) return;
    e.preventDefault();
    
    const touch = e.touches[0];
    const cRect = streamContainer.getBoundingClientRect();

    let currentX = touch.clientX - cRect.left;
    let currentY = touch.clientY - cRect.top;

    currentX = Math.max(0, Math.min(currentX, cRect.width));
    currentY = Math.max(0, Math.min(currentY, cRect.height));

    const width = currentX - startX;
    const height = currentY - startY;

    overlay.style.left = (width < 0 ? currentX : startX) + 'px';
    overlay.style.top = (height < 0 ? currentY : startY) + 'px';
    overlay.style.width = Math.abs(width) + 'px';
    overlay.style.height = Math.abs(height) + 'px';
}, { passive: false });

streamContainer.addEventListener('touchend', async (e) => {
    e.preventDefault();
    const touch = e.changedTouches[0];

    if (screenshotMode.checked && isDrawing) {
        isDrawing = false;
        overlay.style.display = 'none';

        const startReal = getRealCoords(startClientX, startClientY);
        const endReal = getRealCoords(touch.clientX, touch.clientY);

        const realX = Math.min(startReal.x, endReal.x);
        const realY = Math.min(startReal.y, endReal.y);
        const cropW = Math.abs(endReal.x - startReal.x);
        const cropH = Math.abs(endReal.y - startReal.y);

        if (cropW < 5 || cropH < 5) return;

        const frameImg = new Image();
        frameImg.crossOrigin = "Anonymous";
        frameImg.onload = () => {
            const canvas = document.createElement('canvas');
            canvas.width = cropW;
            canvas.height = cropH;
            const ctx = canvas.getContext('2d');
            
            try {
                ctx.drawImage(frameImg, realX, realY, cropW, cropH, 0, 0, cropW, cropH);
                canvas.toBlob((blob) => {
                    if (!blob) return;
                    croppedBlob = blob;
                    const url = URL.createObjectURL(blob);
                    cropPreview.src = url;
                    cropPreview.style.display = 'block';
                    
                    document.getElementById('region-x1').value = realX;
                    document.getElementById('region-y1').value = realY;
                    document.getElementById('region-x2').value = realX + cropW;
                    document.getElementById('region-y2').value = realY + cropH;
                }, 'image/png');
            } catch (err) {
                console.error("Canvas error:", err);
            }
        };
        frameImg.src = `/api/current_frame?device_name=${encodeURIComponent(deviceName)}&_t=${Date.now()}`;

    } else {
        const endCoords = getRealCoords(touch.clientX, touch.clientY);
        const duration = Date.now() - mouseDownTime;
        const distX = Math.abs(endCoords.x - mouseDownCoords.x);
        const distY = Math.abs(endCoords.y - mouseDownCoords.y);

        sendInputAction(endCoords, duration, distX, distY);
    }
}, { passive: false });

function sendInputAction(endCoords, duration, distX, distY) {
    const formData = new FormData();
    formData.append('device_name', deviceName);

    if (distX < 15 && distY < 15) {
        if (duration >= 500) {
            formData.append('action', 'longpress');
            formData.append('x1', mouseDownCoords.x);
            formData.append('y1', mouseDownCoords.y);
            formData.append('duration', duration);
        } else {
            formData.append('action', 'tap');
            formData.append('x1', mouseDownCoords.x);
            formData.append('y1', mouseDownCoords.y);
        }
    } else {
        formData.append('action', 'swipe');
        formData.append('x1', mouseDownCoords.x);
        formData.append('y1', mouseDownCoords.y);
        formData.append('x2', endCoords.x);
        formData.append('y2', endCoords.y);
        formData.append('duration', Math.min(duration, 500));
    }
    fetch('/api/input', { method: 'POST', body: formData });
}

saveBtn.addEventListener('click', async () => {
    if (!croppedBlob) { alert('请先框选截图或上传图片'); return; }
    const folderPath = folderPathInput.value;
    const fileName = fileNameInput.value;

    const formData = new FormData();
    formData.append('folder_path', folderPath);
    formData.append('file_name', fileName);
    formData.append('image', croppedBlob, fileName || 'screenshot.png');
    
    // 获取设备屏幕尺寸（从视频流图片获取实际尺寸）
    const streamImg = document.getElementById('stream-img');
    if (streamImg && streamImg.naturalWidth && streamImg.naturalHeight) {
        formData.append('screen_width', streamImg.naturalWidth);
        formData.append('screen_height', streamImg.naturalHeight);
    }

    try {
        const res = await fetch('/api/save_screenshot', { method: 'POST', body: formData });
        const data = await res.json();
        if (data.success) {
            alert(`保存成功！\n路径: ${data.path}`);
        } else {
            alert(`保存失败: ${data.message}`);
        }
    } catch (err) {
        alert('请求后台失败: ' + err.message);
    }
});

const btnFindImage = document.getElementById('btn-find-image');
const btnFindText = document.getElementById('btn-find-text');
const resultOutput = document.getElementById('recognition-result');

if (btnFindImage) {
    btnFindImage.addEventListener('click', async () => {
        resultOutput.value = '正在找图...';
        
        const sim = parseFloat(document.getElementById('find-img-sim').value);
        const corner = document.getElementById('find-img-corner').value;
        const x1 = document.getElementById('region-x1').value;
        const y1 = document.getElementById('region-y1').value;
        const x2 = document.getElementById('region-x2').value;
        const y2 = document.getElementById('region-y2').value;
        
        const formData = new FormData();
        formData.append('device_name', deviceName);
        formData.append('sim', sim);
        formData.append('priority_corner', corner);
        formData.append('x1', x1);
        formData.append('y1', y1);
        formData.append('x2', x2);
        formData.append('y2', y2);
        
        if (croppedBlob) {
            formData.append('image', croppedBlob, 'search.png');
        }
        
        try {
            const res = await fetch('/api/find_image', { method: 'POST', body: formData });
            const data = await res.json();
            resultOutput.value = data.result || '未找到';
        } catch (e) { resultOutput.value = '找图失败'; }
    });
}

if (btnFindText) {
    btnFindText.addEventListener('click', async () => {
        resultOutput.value = '正在OCR识别...';
        
        const targetTxt = document.getElementById('find-text-target').value;
        const useRegex = document.getElementById('find-text-regex').checked;
        const x1 = document.getElementById('region-x1').value;
        const y1 = document.getElementById('region-y1').value;
        const x2 = document.getElementById('region-x2').value;
        const y2 = document.getElementById('region-y2').value;
        
        const formData = new FormData();
        formData.append('device_name', deviceName);
        formData.append('target_txt', targetTxt);
        formData.append('use_regex', useRegex);
        formData.append('x1', x1);
        formData.append('y1', y1);
        formData.append('x2', x2);
        formData.append('y2', y2);
        
        if (croppedBlob) {
            formData.append('image', croppedBlob, 'ocr.png');
        }
        
        try {
            const res = await fetch('/api/ocr_text', { method: 'POST', body: formData });
            const data = await res.json();
            resultOutput.value = data.result || '未识别到文字';
        } catch (e) { resultOutput.value = '识别失败'; }
    });
}

const btnClearRegion = document.getElementById('btn-clear-region');
if (btnClearRegion) {
    btnClearRegion.addEventListener('click', () => {
        croppedBlob = null;
        cropPreview.src = '';
        cropPreview.style.display = 'none';
        document.getElementById('region-x1').value = '-1';
        document.getElementById('region-y1').value = '-1';
        document.getElementById('region-x2').value = '-1';
        document.getElementById('region-y2').value = '-1';
    });
}
