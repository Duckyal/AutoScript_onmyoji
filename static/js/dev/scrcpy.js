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
let isSwiping = false;          // 非截图模式下实时手势进行中（按下 → 移动 → 抬起）
const GESTURE_MIN_MOVE = 2;     // 设备坐标：实时手势最小移动步长，滤除鼠标/触摸抖动
let startX = 0, startY = 0;
let startClientX = 0, startClientY = 0;
let croppedBlob = null;
// 当前 croppedBlob 的来源分辨率（= 模板基准分辨率）：框选时是视频流分辨率，上传文件时是文件名里的 _WxH。
// 找图时随请求传给后端，用于算缩放比、判断该“放大模板”还是“放大截图”；拿不到就不传，由后端按设备分辨率兜底。
let cropBaseSize = null;

/** 从素材文件名解析基准分辨率（项目约定：xxx_WxH.png）；解析不到返回 null */
function parseBaseSizeFromName(name) {
    const m = /_(\d{3,5})x(\d{3,5})(?=\.[a-zA-Z0-9]+$|$)/.exec(name || '');
    return m ? { width: parseInt(m[1], 10), height: parseInt(m[2], 10) } : null;
}

// ---- 实时手势（拖动遥控）状态机 ----
// 拖动中不再"采集整条轨迹、松手后回放"，而是把 down/move/up 实时发给设备，做到"按住即跟手"。
// 为保证事件不乱序：同一时刻只允许一个请求在途（gestureBusy），移动点只保留"最新一个"，
// 发送间隙产生的新点自动合并，注入速率由网络往返 + 后端触摸锁自然限制。
let gesture = null;             // 当前手势 {downX,downY,lastX,lastY,pendingX,pendingY,ended,endX,endY}
let gestureBusy = false;

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

// =================== 实时手势发送 ===================
async function postGesture(action, x, y) {
    const formData = new FormData();
    formData.append('device_name', deviceName);
    formData.append('action', action);
    formData.append('x1', Math.round(x));
    formData.append('y1', Math.round(y));
    const res = await fetch('/api/input', { method: 'POST', body: formData });
    if (!res.ok) throw new Error(`${action} HTTP ${res.status}`);
    return res;
}

const _sleep = (ms) => new Promise(r => setTimeout(r, ms));

/** 手势开始（按下）。立即触发泵发送 gesture_down。 */
function gestureStart(x, y) {
    if (gesture) return;   // 防御：理论不会出现
    gesture = { downX: x, downY: y, lastX: x, lastY: y, pendingX: null, pendingY: null, ended: false, endX: x, endY: y };
    gesturePump();
}

/** 手势移动（拖动过程高频调用）：只记录最新坐标，由泵限速发送。 */
function gestureMove(x, y) {
    const g = gesture;
    if (!g || g.ended) return;
    const dx = x - g.lastX, dy = y - g.lastY;
    if (dx * dx + dy * dy < GESTURE_MIN_MOVE * GESTURE_MIN_MOVE) return;
    g.lastX = x;
    g.lastY = y;
    g.pendingX = x;   // 只保留最新未发送点
    g.pendingY = y;
}

/** 手势结束（松手）：发掉残留点并 gesture_up。 */
function gestureEnd(x, y) {
    const g = gesture;
    if (!g || g.ended) return;
    g.ended = true;
    g.endX = x;
    g.endY = y;
    gesturePump();
}

/** 手势异常取消（touchcancel 等）：按最后位置直接抬起，避免设备端卡在按住状态。 */
function gestureCancel() {
    isSwiping = false;
    const g = gesture;
    if (!g || g.ended) return;
    g.ended = true;
    g.endX = g.lastX;
    g.endY = g.lastY;
    gesturePump();
}

/**
 * 手势泵：串行消费 按下 → 移动(最新点) → 抬起。
 * 同一时刻至多一个请求在途，从根源上保证 down/move/up 严格按序到达后端。
 */
async function gesturePump() {
    if (gestureBusy) return;
    gestureBusy = true;
    try {
        const g = gesture;
        if (!g) return;
        try {
            await postGesture('gesture_down', g.downX, g.downY);
            // 移动循环：有最新点就发，没有就空转等新事件
            while (gesture === g && !g.ended) {
                if (g.pendingX !== null) {
                    const px = g.pendingX, py = g.pendingY;
                    g.pendingX = g.pendingY = null;
                    await postGesture('gesture_move', px, py);
                } else {
                    await _sleep(3);
                }
            }
            if (gesture === g) {
                if (g.pendingX !== null) {
                    await postGesture('gesture_move', g.pendingX, g.pendingY);
                    g.pendingX = g.pendingY = null;
                }
                await postGesture('gesture_up', g.endX, g.endY);
            }
        } catch (err) {
            // 中途失败：尽力抬起，防止设备端一直处于按下状态
            console.error('实时手势中断:', err);
            try { await postGesture('gesture_up', g.lastX, g.lastY); } catch (_) { /* 忽略 */ }
        } finally {
            if (gesture === g) gesture = null;
        }
    } finally {
        gestureBusy = false;
    }
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
        // 框选区域的像素是按视频流分辨率裁下来的 → 这张模板的基准就是流的自然尺寸
        const baseSize = getStreamNaturalSize();
        cropBaseSize = (baseSize.width && baseSize.height)
            ? { width: baseSize.width, height: baseSize.height } : null;
        const url = URL.createObjectURL(blob);
        cropPreview.src = url;
        cropPreview.style.display = 'block';
        // 区域框一律写 0~1 比例（与后端 /api/find_image、ADB.找图 的区域语义一致）：
        // 写像素会被后端当成比例再乘屏幕宽高，坐标偏移会错到屏幕外
        const regionSize = getStreamNaturalSize();
        const regionW = regionSize.width || (realX + cropW) || 1;
        const regionH = regionSize.height || (realY + cropH) || 1;
        document.getElementById('region-x1').value = (realX / regionW).toFixed(4);
        document.getElementById('region-y1').value = (realY / regionH).toFixed(4);
        document.getElementById('region-x2').value = ((realX + cropW) / regionW).toFixed(4);
        document.getElementById('region-y2').value = ((realY + cropH) / regionH).toFixed(4);
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
        // 素材图靠文件名里的 _WxH 标识基准分辨率；没写就留空，交由后端按设备分辨率兜底
        cropBaseSize = parseBaseSizeFromName(file.name);
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
        // 非截图模式：实时手势开始——立即把"按下"发给设备（按住即跟手）
        isSwiping = true;
        const c = getRealCoords(e.clientX, e.clientY);
        gestureStart(c.x, c.y);
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

    // 实时拖动：把最新坐标交给泵发送（move 为绝对坐标，泵会自动合并过快的新点）
    const c = getRealCoords(e.clientX, e.clientY);
    gestureMove(c.x, c.y);
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
        // 实时手势结束：松手 → 抬起（点击/长按也在此表达：按下后停留多久，设备就按多久再抬起）
        isSwiping = false;
        const c = getRealCoords(e.clientX, e.clientY);
        gestureEnd(c.x, c.y);
    }
});

// 兜底：按住拖出画面/在窗口外松手时结束手势，防止设备端一直处于按下状态
streamContainer.addEventListener('mouseleave', (e) => {
    if (isSwiping && (e.buttons & 1) === 0) {
        isSwiping = false;
        const c = getRealCoords(e.clientX, e.clientY);
        gestureEnd(c.x, c.y);
    }
});
window.addEventListener('mouseup', (e) => {
    if (isSwiping) {
        isSwiping = false;
        const c = getRealCoords(e.clientX, e.clientY);
        gestureEnd(c.x, c.y);
    }
});

// =================== Touch Events for Mobile ===================
streamContainer.addEventListener('touchstart', (e) => {
    e.preventDefault();
    const touch = e.touches[0];

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
        // 非截图模式：实时手势开始——立即把"按下"发给设备
        isSwiping = true;
        const c = getRealCoords(touch.clientX, touch.clientY);
        gestureStart(c.x, c.y);
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

    // 实时拖动：把最新坐标交给泵发送
    const touch = e.touches[0];
    const c = getRealCoords(touch.clientX, touch.clientY);
    gestureMove(c.x, c.y);
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
        // 实时手势结束：松手 → 抬起
        isSwiping = false;
        const c = getRealCoords(touch.clientX, touch.clientY);
        gestureEnd(c.x, c.y);
    }
}, { passive: false });

// 触摸被系统打断（来电/手势/滚动）时按当前位置结束手势，避免设备端卡在按住状态
streamContainer.addEventListener('touchcancel', () => {
    gestureCancel();
}, { passive: false });

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
    
    // 屏幕尺寸 = 这张图的来源分辨率：框选时等于视频流尺寸，上传素材图时取文件名里的 _WxH。
    // 后端会把它拼进文件名（xxx_WxH.png），成为该模板以后算缩放比的基准，取错会让脚本找不到图。
    const sz = cropBaseSize || getStreamNaturalSize();
    if (sz && sz.width && sz.height) {
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
        // 模板来源分辨率：后端据此算缩放比、判断该“放大模板”还是“放大截图”（不传则按设备分辨率兜底）
        if (cropBaseSize && cropBaseSize.width && cropBaseSize.height) {
            formData.append('screen_width', cropBaseSize.width);
            formData.append('screen_height', cropBaseSize.height);
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
        cropBaseSize = null;
        cropPreview.src = '';
        cropPreview.style.display = 'none';
        document.getElementById('region-x1').value = '0';
        document.getElementById('region-y1').value = '0';
        document.getElementById('region-x2').value = '1';
        document.getElementById('region-y2').value = '1';
    });
}

// 预览区域：region-x1/y1/x2/y2 一律是 0~1 比例（留空 / 负数 = 未指定，用默认边界）
// 从视频流截取对应区域并显示到 crop-preview，与后端 /api/find_image 的区域语义保持一致
// 返回 Promise<Blob|null>：成功截取返回 blob（并已更新 croppedBlob/预览图/坐标框），失败返回 null
function captureRegionFromStream() {
    return new Promise((resolve) => {
        const parseRegionVal = (id) => {
            const str = document.getElementById(id).value.trim();
            if (str === '') return null;
            const v = parseFloat(str);
            // 空值 / 非数字 / 负数（旧的 -1 写法）都视为“未指定”
            return (isNaN(v) || v < 0) ? null : v;
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

        // 0~1 比例 → 像素；未指定时起点取 0、终点取满宽/高
        const toStart = (v, max) => Math.round((v === null ? 0 : v) * max);
        const toEnd = (v, max) => Math.round((v === null ? 1 : v) * max);

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
