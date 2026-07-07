const urlParams = new URLSearchParams(window.location.search);
const deviceName = urlParams.get('device') || '未指定设备';
document.getElementById('device-name').textContent = deviceName;

// 启动后端拉流线程
fetch(`/api/start_stream?device_name=${deviceName}`).catch(err => console.error(err));

const sidebar = document.getElementById('sidebar');
const toggleBtn = document.getElementById('toggle-btn');
toggleBtn.addEventListener('click', () => {
    sidebar.classList.toggle('hidden');
    toggleBtn.textContent = sidebar.classList.contains('hidden') ? '显示工具栏' : '隐藏工具栏';
});

// ==================== 统一获取 DOM 元素 ====================
const streamContainer = document.getElementById('stream-container');
const streamImg = document.getElementById('stream-img');
const overlay = document.getElementById('overlay');
const screenshotMode = document.getElementById('screenshot-mode');
const cropPreview = document.getElementById('crop-preview');
const folderPathInput = document.getElementById('folder-path');
const fileNameInput = document.getElementById('file-name');
const saveBtn = document.getElementById('save-btn');
const uploadBtn = document.getElementById('upload-btn');
const fileInput = document.getElementById('file-input');

// 确保 overlay 样式
if (overlay) {
    overlay.style.position = 'absolute';
    overlay.style.border = '2px solid #ff0000';
    overlay.style.backgroundColor = 'rgba(255, 0, 0, 0.2)';
    overlay.style.pointerEvents = 'none';
    overlay.style.display = 'none';
    overlay.style.zIndex = '100';
}

// ==================== 状态显示浮层 ====================
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

// ==================== 核心逻辑（最终修正版：扣除黑边偏移）========================

let isDrawing = false;
let startX = 0, startY = 0;
let startClientX = 0, startClientY = 0; // 保存真实的 clientX/Y 用于计算
let croppedBlob = null;
let mouseDownTime = 0;
let mouseDownCoords = {x: 0, y: 0};

// 缓存视频的边界信息，避免每帧都计算
let cachedVideoBounds = null;
let lastWindowSize = '';

function updateCachedBounds() {
    cachedVideoBounds = getVideoBounds();
}

window.addEventListener('resize', updateCachedBounds);
streamImg.onload = updateCachedBounds;

// 计算视频内容在页面上的实际矩形（扣除 object-fit: contain 产生的黑边）
function getVideoBounds() {
    const rect = streamImg.getBoundingClientRect();
    const nw = streamImg.naturalWidth;
    const nh = streamImg.naturalHeight;
    
    if (nw === 0 || nh === 0) return null;

    const containerW = rect.width;
    const containerH = rect.height;
    
    // 宽高比
    const videoRatio = nw / nh;
    const containerRatio = containerW / containerH;
    
    let contentW, contentH, offsetX, offsetY;

    if (containerRatio > videoRatio) {
        // 容器比视频宽 -> 黑边在左右
        contentH = containerH;
        contentW = containerH * videoRatio;
        offsetX = (containerW - contentW) / 2;
        offsetY = 0;
    } else {
        // 容器比视频高 -> 黑边在上下
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

// 将屏幕点击坐标转换为流的真实坐标
function getRealCoords(clientX, clientY) {
    const bounds = cachedVideoBounds || getVideoBounds();
    if (!bounds) return { x: 0, y: 0 };

    // 1. 相对于内容左上角的坐标
    let x = clientX - bounds.left;
    let y = clientY - bounds.top;
    
    // 2. 限制在内容范围内
    x = Math.max(0, Math.min(x, bounds.width));
    y = Math.max(0, Math.min(y, bounds.height));
    
    // 3. 映射到真实分辨率
    const realX = Math.round(x * (bounds.naturalW / bounds.width));
    const realY = Math.round(y * (bounds.naturalH / bounds.height));
    
    return { x: realX, y: realY };
}

// --- 1. 本地上传逻辑 ---
uploadBtn.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
        cropPreview.src = event.target.result;
        cropPreview.style.display = 'block';
        croppedBlob = file;
        console.log("已加载本地图片");
    };
    reader.readAsDataURL(file);
});

// --- 2. 鼠标交互 ---
streamContainer.addEventListener('mousedown', (e) => {
    e.preventDefault();
    // 立即更新一次边界，防止延迟
    if (!cachedVideoBounds) updateCachedBounds();

    if (e.button === 1) {
        screenshotMode.checked = !screenshotMode.checked;
        streamContainer.style.cursor = screenshotMode.checked ? 'crosshair' : 'default';
        return;
    }
    if (e.button !== 0) return;

    mouseDownTime = Date.now();
    
    // 计算点击的 ADB 坐标
    mouseDownCoords = getRealCoords(e.clientX, e.clientY);

    if (screenshotMode.checked) {
        isDrawing = true;
        
        // 保存原始 Client 坐标用于后续绘图
        startClientX = e.clientX;
        startClientY = e.clientY;
        
        const bounds = cachedVideoBounds;
        const cRect = streamContainer.getBoundingClientRect();

        // 将屏幕坐标转换为容器内坐标
        let rawX = e.clientX - cRect.left;
        let rawY = e.clientY - cRect.top;

        // 限制在容器内（而不是视频内容内，允许用户画框框住黑边，但后续裁剪会自动修正）
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

    // 限制终点在容器内
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
        // --- 截图裁剪 ---
        isDrawing = false;
        overlay.style.display = 'none';

        // 使用保存的 Client 坐标计算 ADB 坐标（这样最精准）
        const startReal = getRealCoords(startClientX, startClientY);
        const endReal = getRealCoords(e.clientX, e.clientY);

        // 计算差值
        const realX = Math.min(startReal.x, endReal.x);
        const realY = Math.min(startReal.y, endReal.y);
        const cropW = Math.abs(endReal.x - startReal.x);
        const cropH = Math.abs(endReal.y - startReal.y);

        if (cropW < 5 || cropH < 5) return;

        // 获取高清帧
        const frameImg = new Image();
        frameImg.crossOrigin = "Anonymous";
        frameImg.onload = () => {
            const realW = frameImg.naturalWidth;
            const realH = frameImg.naturalHeight;
            
            // 直接使用转换好的真实坐标进行裁剪
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
                }, 'image/png');
            } catch (err) {
                console.error("Canvas error:", err);
            }
        };
        frameImg.src = `/api/current_frame?device_name=${encodeURIComponent(deviceName)}&_t=${Date.now()}`;

    } else {
        // --- 点击/滑动控制 ---
        const endCoords = getRealCoords(e.clientX, e.clientY);
        const duration = Date.now() - mouseDownTime;
        const distX = Math.abs(endCoords.x - mouseDownCoords.x);
        const distY = Math.abs(endCoords.y - mouseDownCoords.y);

        const formData = new FormData();
        formData.append('device_name', deviceName);

        if (distX < 15 && distY < 15) {
            formData.append('action', 'tap');
            formData.append('x1', mouseDownCoords.x);
            formData.append('y1', mouseDownCoords.y);
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
});

// --- 3. 文件夹选择逻辑 ---
folderPathInput.addEventListener('click', async () => {
    try {
        const res = await fetch('/api/pick_folder');
        const data = await res.json();
        if (data.success && data.path) {
            folderPathInput.value = data.path;
        } else {
            alert(data.message || '选择文件夹失败');
        }
    } catch (err) {
        console.error(err);
        alert('选择文件夹失败: ' + err.message);
    }
});

// --- 4. 保存截图逻辑 ---
saveBtn.addEventListener('click', async () => {
    if (!croppedBlob) { alert('请先框选截图或上传图片'); return; }
    const folderPath = folderPathInput.value;
    const fileName = fileNameInput.value;
    if (!folderPath) { alert('请点击上方输入框选择保存文件夹'); return; }
    if (!fileName) { alert('请输入文件名'); return; }

    const formData = new FormData();
    formData.append('device_name', deviceName);
    formData.append('folder_path', folderPath);
    formData.append('file_name', fileName);
    formData.append('image', croppedBlob, fileName);

    try {
        const res = await fetch('/api/screenshot', { method: 'POST', body: formData });
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

// --- 5. 找图/找字功能 ---
const btnFindImage = document.getElementById('btn-find-image');
const btnFindText = document.getElementById('btn-find-text');
const resultOutput = document.getElementById('recognition-result');

if (btnFindImage) {
    btnFindImage.addEventListener('click', async () => {
        if (!croppedBlob) { alert('请先截图或上传图片作为模板'); return; }
        resultOutput.value = '正在找图...';
        const formData = new FormData();
        formData.append('device_name', deviceName);
        formData.append('image', croppedBlob, 'search.png');
        try {
            const res = await fetch('/api/find_image', { method: 'POST', body: formData });
            const data = await res.json();
            resultOutput.value = data.found ? `找到目标! 坐标: (${data.x}, ${data.y})` : '未找到';
        } catch (e) { resultOutput.value = '找图失败'; }
    });
}

if (btnFindText) {
    btnFindText.addEventListener('click', async () => {
        if (!croppedBlob) { alert('请先截图或上传图片'); return; }
        resultOutput.value = '正在OCR识别...';
        const formData = new FormData();
        formData.append('device_name', deviceName);
        formData.append('image', croppedBlob, 'ocr.png');
        try {
            const res = await fetch('/api/ocr_text', { method: 'POST', body: formData });
            const data = await res.json();
            resultOutput.value = data.text || '未识别到文字';
        } catch (e) { resultOutput.value = '识别失败'; }
    });
}
