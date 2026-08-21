const urlParams = new URLSearchParams(window.location.search);
const deviceName = urlParams.get('device') || '未指定设备';
document.getElementById('device-name').textContent = deviceName;

// 启动后端视频流（scrcpy 模式由 WebSocket 端点按需启动，MJPEG 模式在此启动）
if (!(typeof ScrcpyWebCodecs !== 'undefined' && ScrcpyWebCodecs.isSupported())) {
    fetch(`/api/start_stream?device_name=${deviceName}`).catch(err => console.error(err));
}

const sidebar = document.getElementById('sidebar');
const toggleBtn = document.getElementById('toggle-btn');
toggleBtn.addEventListener('click', () => {
    sidebar.classList.toggle('hidden');
    toggleBtn.textContent = sidebar.classList.contains('hidden') ? '显示工具栏' : '隐藏工具栏';
});

const streamContainer = document.getElementById('stream-container');
const streamImg = document.getElementById('stream-img');
const streamCanvas = document.getElementById('stream-canvas');
const overlay = document.getElementById('selection-overlay');

// ===== WebCodecs / scrcpy 诊断 =====
// WebCodecs API (VideoDecoder) 要求 安全上下文（HTTPS 或 localhost/127.0.0.1）
// 使用局域网 IP 或 0.0.0.0 访问时，即使浏览器支持 VideoDecoder 也会返回 undefined
//
// 特殊处理：若主机名是 0.0.0.0，自动重定向到 localhost（同机同端口同路径），
// 这是启用 scrcpy 的最低成本方案。
if (location.hostname === '0.0.0.0' && location.protocol === 'http:') {
    const newUrl = `http://localhost:${location.port}${location.pathname}${location.search}${location.hash}`;
    console.warn('[scrcpy] 检测到 0.0.0.0 访问，无法启用 WebCodecs，自动重定向到 localhost:', newUrl);
    location.replace(newUrl);
}

const _scrcpyDiagnostics = {
    scrcpyModuleLoaded: typeof ScrcpyWebCodecs !== 'undefined',
    secureContext: window.isSecureContext,
    location: `${location.protocol}//${location.hostname}${location.port ? ':' + location.port : ''}`,
    videoDecoder: typeof VideoDecoder !== 'undefined',
    ua: navigator.userAgent.split(') ')[0] + ')',
};

const _canUseScrcpy = (() => {
    if (!_scrcpyDiagnostics.scrcpyModuleLoaded) return { ok: false, reason: 'scrcpy 模块未加载' };
    if (!_scrcpyDiagnostics.videoDecoder) {
        if (!_scrcpyDiagnostics.secureContext) {
            return { ok: false, reason: '非安全上下文(需 localhost/HTTPS)' };
        }
        return { ok: false, reason: '浏览器不支持 WebCodecs' };
    }
    return { ok: true, reason: '' };
})();

// 控制台诊断（F12 可查看）
console.log('[scrcpy] 诊断:', _scrcpyDiagnostics, '可用性:', _canUseScrcpy);

const useScrcpy = _canUseScrcpy.ok;

// 视频流模式徽章
const streamModeBadge = document.getElementById('stream-mode-badge');
// MJPEG 截图间隔控件组（scrcpy 模式下隐藏）
const mjpegIntervalGroup = document.getElementById('mjpeg-interval-group');

/** 设置视频流模式徽章 (正常状态半透明, 避免遮挡视频流; 异常状态高亮显示) */
function setStreamModeBadge(text, color) {
    if (!streamModeBadge) return;
    streamModeBadge.textContent = `流模式: ${text}`;
    streamModeBadge.style.backgroundColor = color;
    // 绿色 = 正常, 半透明不遮挡; 其他颜色 = 异常, 完全显示
    const isNormal = color === '#22c55e';
    streamModeBadge.style.opacity = isNormal ? '0.25' : '1';
    streamModeBadge.style.pointerEvents = 'none';
}

// 初始化模式徽章和控件可见性（在 initStream 调用前先展示一次状态）
if (useScrcpy) {
    setStreamModeBadge('scrcpy H.264 硬解', '#22c55e');
    if (mjpegIntervalGroup) mjpegIntervalGroup.style.display = 'none';
} else {
    // MJPEG 模式下，徽章直接显示未启用 scrcpy 的原因，方便排查
    setStreamModeBadge(`MJPEG 截图 (${_canUseScrcpy.reason})`, '#3b82f6');
    // 让徽章上原因长文字不换行，用更小字号展示
    if (streamModeBadge) streamModeBadge.style.whiteSpace = 'nowrap';
}

/** 获取当前激活的流元素（img 或 canvas） */
function getStreamElement() {
    return useScrcpy ? streamCanvas : streamImg;
}

/** 获取流的原始（视频/位图）分辨率 */
function getStreamNaturalSize() {
    if (useScrcpy) {
        return { width: streamCanvas.width || 0, height: streamCanvas.height || 0 };
    }
    return { width: streamImg.naturalWidth || 0, height: streamImg.naturalHeight || 0 };
}
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
    if (useScrcpy) {
        // scrcpy 模式: 用 ScrcpyWebCodecs 实际状态, 不查询 MJPEG 截图流
        const running = ScrcpyWebCodecs.running;
        const decoderState = ScrcpyWebCodecs.decoder ? ScrcpyWebCodecs.decoder.state : 'null';
        const frames = ScrcpyWebCodecs.frameCount;

        if (running && ScrcpyWebCodecs.decoderConfigured && decoderState === 'configured') {
            statusDiv.textContent = `scrcpy 已连接 (${frames}帧)`;
            statusDiv.style.backgroundColor = 'rgba(40, 167, 69, 0.9)';
            statusDiv.style.opacity = '0';  // 正常时隐藏
            setStreamModeBadge('scrcpy H.264 硬解', '#22c55e');
        } else if (running && !ScrcpyWebCodecs.decoderConfigured) {
            statusDiv.textContent = 'scrcpy 等待关键帧...';
            statusDiv.style.backgroundColor = 'rgba(255, 193, 7, 0.9)';
            statusDiv.style.opacity = '1';
            setStreamModeBadge('scrcpy 等待关键帧', '#f59e0b');
        } else if (!running) {
            statusDiv.textContent = 'scrcpy 流已断开';
            statusDiv.style.backgroundColor = 'rgba(220, 53, 69, 0.9)';
            statusDiv.style.opacity = '1';
            setStreamModeBadge('scrcpy 已断开', '#ef4444');
        } else {
            statusDiv.textContent = `scrcpy 解码器: ${decoderState}`;
            statusDiv.style.backgroundColor = 'rgba(255, 193, 7, 0.9)';
            statusDiv.style.opacity = '1';
            setStreamModeBadge('scrcpy 解码中', '#f59e0b');
        }
        return;
    }

    // MJPEG 模式: 查询截图流状态
    fetch(`/api/stream_status?device_name=${deviceName}`)
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
    if (useScrcpy) {
        // scrcpy H.264 模式
        streamImg.style.display = 'none';
        streamCanvas.style.display = 'block';
        if (mjpegIntervalGroup) mjpegIntervalGroup.style.display = 'none';
        setStreamModeBadge('scrcpy 连接中', '#f59e0b');
        statusDiv.textContent = 'scrcpy 连接中...';
        statusDiv.style.backgroundColor = 'rgba(255, 193, 7, 0.9)';
        statusDiv.style.opacity = '1';

        const started = ScrcpyWebCodecs.start(deviceName, 'stream-canvas');
        if (!started) {
            // 启动失败，回退到 MJPEG
            console.warn('[scrcpy] 启动失败，回退到 MJPEG');
            streamCanvas.style.display = 'none';
            streamImg.style.display = 'block';
            if (mjpegIntervalGroup) mjpegIntervalGroup.style.display = '';
            setStreamModeBadge('MJPEG 截图 (回退)', '#f59e0b');
            _initMjpegStream();
        } else {
            setStreamModeBadge('scrcpy H.264 硬解', '#22c55e');
            // 状态由 updateStreamStatus() 统一管理, 不再重复轮询
        }
        return;
    }
    setStreamModeBadge('MJPEG 截图', '#3b82f6');
    _initMjpegStream();
}

function _initMjpegStream() {
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
let isSwiping = false;          // 非截图模式下的手绘滑动状态
let swipePath = [];             // 手绘轨迹点数组（设备真实坐标 {x, y}）
const SWIPE_MIN_POINT_DIST = 5; // 轨迹采样最小间距（设备坐标 px），小于此距离不记录
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
    const elem = getStreamElement();
    const rect = elem.getBoundingClientRect();
    const sz = getStreamNaturalSize();
    const nw = sz.width;
    const nh = sz.height;

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

/**
 * 截取当前帧的指定区域为 PNG blob
 * - scrcpy 模式：直接从 stream-canvas 截取（无网络请求，零延迟）
 * - MJPEG 模式：从 /api/current_frame 获取截图再裁剪
 */
function performCrop(realX, realY, cropW, cropH, callback) {
    const onBlob = (blob) => {
        if (!blob) { callback(null); return; }
        croppedBlob = blob;
        const url = URL.createObjectURL(blob);
        cropPreview.src = url;
        cropPreview.style.display = 'block';
        document.getElementById('region-x1').value = realX;
        document.getElementById('region-y1').value = realY;
        document.getElementById('region-x2').value = realX + cropW;
        document.getElementById('region-y2').value = realY + cropH;
        callback(blob);
    };

    if (useScrcpy && streamCanvas.width > 0) {
        // scrcpy 模式：从当前解码帧的 canvas 直接截取
        try {
            const c = document.createElement('canvas');
            c.width = cropW;
            c.height = cropH;
            const ctx = c.getContext('2d');
            ctx.drawImage(streamCanvas, realX, realY, cropW, cropH, 0, 0, cropW, cropH);
            c.toBlob(onBlob, 'image/png');
        } catch (err) {
            console.error('Canvas crop error:', err);
            callback(null);
        }
    } else {
        // MJPEG 模式：从 /api/current_frame 获取当前帧
        const frameImg = new Image();
        frameImg.crossOrigin = 'Anonymous';
        frameImg.onload = () => {
            try {
                const c = document.createElement('canvas');
                c.width = cropW;
                c.height = cropH;
                const ctx = c.getContext('2d');
                ctx.drawImage(frameImg, realX, realY, cropW, cropH, 0, 0, cropW, cropH);
                c.toBlob(onBlob, 'image/png');
            } catch (err) {
                console.error('Canvas error:', err);
                callback(null);
            }
        };
        frameImg.onerror = () => {
            console.error('current_frame 加载失败');
            callback(null);
        };
        frameImg.src = `/api/current_frame?device_name=${encodeURIComponent(deviceName)}&_t=${Date.now()}`;
    }
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
    } else {
        // 非截图模式：开始采集手绘滑动轨迹（起点先入数组）
        isSwiping = true;
        swipePath = [{ x: mouseDownCoords.x, y: mouseDownCoords.y }];
    }
});

streamContainer.addEventListener('mousemove', (e) => {
    if (isDrawing) {
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
        return;
    }
    if (!isSwiping) return;

    // 采集手绘轨迹点（真实设备坐标），按最小距离过滤，避免点过密
    const c = getRealCoords(e.clientX, e.clientY);
    const last = swipePath[swipePath.length - 1];
    const dx = c.x - last.x;
    const dy = c.y - last.y;
    if (dx * dx + dy * dy < SWIPE_MIN_POINT_DIST * SWIPE_MIN_POINT_DIST) return;
    swipePath.push({ x: c.x, y: c.y });
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

        performCrop(realX, realY, cropW, cropH, () => {});

    } else if (isSwiping) {
        isSwiping = false;
        const endCoords = getRealCoords(e.clientX, e.clientY);
        const duration = Date.now() - mouseDownTime;
        const distX = Math.abs(endCoords.x - mouseDownCoords.x);
        const distY = Math.abs(endCoords.y - mouseDownCoords.y);

        // 轨迹点足够且位移足够 → 曲线滑动；否则回退到 tap/longpress/短滑动
        if (swipePath.length >= 2 && (distX >= 15 || distY >= 15)) {
            // 确保终点纳入轨迹（mouseup 的最后一次采样可能被最小距离过滤掉）
            const last = swipePath[swipePath.length - 1];
            if (last.x !== endCoords.x || last.y !== endCoords.y) {
                swipePath.push({ x: endCoords.x, y: endCoords.y });
            }
            sendSwipePath(swipePath);
        } else {
            sendInputAction(endCoords, duration, distX, distY);
        }
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
    } else {
        // 非截图模式：开始采集手绘滑动轨迹
        isSwiping = true;
        swipePath = [{ x: mouseDownCoords.x, y: mouseDownCoords.y }];
    }
}, { passive: false });

streamContainer.addEventListener('touchmove', (e) => {
    if (isDrawing) {
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
        return;
    }
    if (!isSwiping) return;
    e.preventDefault();

    // 采集手绘轨迹点（真实设备坐标），按最小距离过滤
    const touch = e.touches[0];
    const c = getRealCoords(touch.clientX, touch.clientY);
    const last = swipePath[swipePath.length - 1];
    const dx = c.x - last.x;
    const dy = c.y - last.y;
    if (dx * dx + dy * dy < SWIPE_MIN_POINT_DIST * SWIPE_MIN_POINT_DIST) return;
    swipePath.push({ x: c.x, y: c.y });
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

        performCrop(realX, realY, cropW, cropH, () => {});

    } else if (isSwiping) {
        isSwiping = false;
        const endCoords = getRealCoords(touch.clientX, touch.clientY);
        const duration = Date.now() - mouseDownTime;
        const distX = Math.abs(endCoords.x - mouseDownCoords.x);
        const distY = Math.abs(endCoords.y - mouseDownCoords.y);

        // 轨迹点足够且位移足够 → 曲线滑动；否则回退到 tap/longpress/短滑动
        if (swipePath.length >= 2 && (distX >= 15 || distY >= 15)) {
            const last = swipePath[swipePath.length - 1];
            if (last.x !== endCoords.x || last.y !== endCoords.y) {
                swipePath.push({ x: endCoords.x, y: endCoords.y });
            }
            sendSwipePath(swipePath);
        } else {
            sendInputAction(endCoords, duration, distX, distY);
        }
    }
}, { passive: false });

/** 将手绘轨迹点发送到后端 /api/input（action=swipe_path）执行曲线滑动 */
function sendSwipePath(path) {
    if (!path || path.length < 2) return;
    const points = path.map(p => [p.x, p.y]);
    const formData = new FormData();
    formData.append('device_name', deviceName);
    formData.append('action', 'swipe_path');
    formData.append('points', JSON.stringify(points));
    formData.append('delay', '0');   // 0 = 不额外 sleep，回放只受 touch.move 网络耗时限制，最跟手
    fetch('/api/input', { method: 'POST', body: formData }).catch(err => console.error('曲线滑动发送失败:', err));
}

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
    const folderPath = folderPathInput.value.trim();
    const fileName = fileNameInput.value.trim();

    if (!fileName) { alert('请输入保存文件名'); return; }
    if (folderPath && !/^[a-zA-Z0-9_\u4e00-\u9fa5\-\/.]+$/.test(folderPath)) {
        alert('文件夹路径只能包含中英文、数字、下划线、连字符、斜杠和点');
        return;
    }

    const formData = new FormData();
    formData.append('folder_path', folderPath);
    formData.append('file_name', fileName);
    formData.append('image', croppedBlob, fileName);
    
    // 获取设备屏幕尺寸（从当前视频流元素获取实际尺寸）
    const sz = getStreamNaturalSize();
    if (sz.width && sz.height) {
        formData.append('screen_width', sz.width);
        formData.append('screen_height', sz.height);
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
        
        // 未框选/上传图片时，自动按当前区域坐标从视频流截取一帧用于 OCR
        if (!croppedBlob) {
            resultOutput.value = '未框选区域，正在自动截取当前区域...';
            const autoBlob = await captureRegionFromStream();
            if (autoBlob) formData.append('image', autoBlob, 'ocr.png');
        } else {
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

// 预览区域：根据 region-x1/y1/x2/y2 的当前值（-1=全屏，小数=长/宽比值，整数=像素）
// 从视频流截取对应区域并显示到 crop-preview，与后端 /api/find_image 的小数语义保持一致
// 返回 Promise<Blob|null>：成功截取返回 blob（并已更新 croppedBlob/预览图/坐标框），失败返回 null
function captureRegionFromStream() {
    return new Promise((resolve) => {
        const parseRegionVal = (id) => {
            const str = document.getElementById(id).value.trim();
            if (str === '' || isNaN(parseFloat(str))) return -1;
            // 与后端一致：含小数点按比值处理，否则按像素
            return str.includes('.') ? parseFloat(str) : parseInt(str, 10);
        };
        const x1v = parseRegionVal('region-x1');
        const y1v = parseRegionVal('region-y1');
        const x2v = parseRegionVal('region-x2');
        const y2v = parseRegionVal('region-y2');

        const size = getStreamNaturalSize();
        if (!size.width || !size.height) {
            alert('视频流尚未加载，无法预览');
            resolve(null);
            return;
        }
        const W = size.width;
        const H = size.height;

        // 起点坐标 -1 表示 0，终点坐标 -1 表示宽/高；小数按比例换算
        const toStart = (v, max) => v === -1 ? 0 : (Number.isInteger(v) ? v : Math.round(v * max));
        const toEnd = (v, max) => v === -1 ? max : (Number.isInteger(v) ? v : Math.round(v * max));

        let x1 = Math.max(0, Math.min(toStart(x1v, W), W));
        let y1 = Math.max(0, Math.min(toStart(y1v, H), H));
        let x2 = Math.max(0, Math.min(toEnd(x2v, W), W));
        let y2 = Math.max(0, Math.min(toEnd(y2v, H), H));

        if (x2 < x1) { const t = x1; x1 = x2; x2 = t; }
        if (y2 < y1) { const t = y1; y1 = y2; y2 = t; }

        const realX = Math.round(x1);
        const realY = Math.round(y1);
        const cropW = Math.round(x2 - x1);
        const cropH = Math.round(y2 - y1);
        if (cropW <= 0 || cropH <= 0) {
            alert('区域无效（宽或高为 0）');
            resolve(null);
            return;
        }

        performCrop(realX, realY, cropW, cropH, (blob) => {
            if (!blob) alert('预览失败：无法截取当前帧');
            resolve(blob);
        });
    });
}

const btnPreviewRegion = document.getElementById('btn-preview-region');
if (btnPreviewRegion) {
    btnPreviewRegion.addEventListener('click', () => captureRegionFromStream());
}
