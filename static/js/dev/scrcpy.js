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

let isDrawing = false;
let startX = 0, startY = 0;
let croppedBlob = null;
let mouseDownTime = 0;
let mouseDownCoords = {x: 0, y: 0};

// 存储视频流的真实分辨率
let currentNaturalW = 1080;
let currentNaturalH = 1920;

// 更新鼠标样式
function updateCursor() {
    streamContainer.style.cursor = screenshotMode.checked ? 'crosshair' : 'default';
}
screenshotMode.addEventListener('change', updateCursor);
updateCursor();

// 手动模拟 object-fit: contain，计算真实画面显示区域和黑边偏移
function getImgBounds() {
    // 核心修改：优先从流图片本身获取真实分辨率，解决初始比例不对导致的黑边计算错误
    const nw = streamImg.naturalWidth || currentNaturalW;
    const nh = streamImg.naturalHeight || currentNaturalH;
    currentNaturalW = nw;
    currentNaturalH = nh;

    const containerRect = streamContainer.getBoundingClientRect();
    const cW = containerRect.width;
    const cH = containerRect.height;
    const iR = nw / nh;
    const cR = cW / cH;
    
    let dW, dH, offsetX, offsetY;
    if (iR > cR) {
        // 图片更宽，左右撑满，上下留黑边
        dW = cW;
        dH = cW / iR;
        offsetX = 0;
        offsetY = (cH - dH) / 2;
    } else {
        // 图片更高，上下撑满，左右留黑边
        dH = cH;
        dW = cH * iR;
        offsetX = (cW - dW) / 2;
        offsetY = 0;
    }
    return { offsetX, offsetY, dispWidth: dW, dispHeight: dH };
}

function getRealCoords(clientX, clientY) {
    const bounds = getImgBounds();
    const containerRect = streamContainer.getBoundingClientRect();
    let x = clientX - containerRect.left - bounds.offsetX;
    let y = clientY - containerRect.top - bounds.offsetY;
    
    x = Math.max(0, Math.min(x, bounds.dispWidth));
    y = Math.max(0, Math.min(y, bounds.dispHeight));
    
    return {
        x: Math.round(x * (currentNaturalW / bounds.dispWidth)),
        y: Math.round(y * (currentNaturalH / bounds.dispHeight))
    };
}

streamContainer.addEventListener('mousedown', (e) => {
    e.preventDefault();
    
    // 鼠标中键切换模式
    if (e.button === 1) {
        screenshotMode.checked = !screenshotMode.checked;
        updateCursor();
        return;
    }

    // 右键不处理
    if (e.button !== 0) return;

    mouseDownTime = Date.now();
    mouseDownCoords = getRealCoords(e.clientX, e.clientY);
    
    if (screenshotMode.checked) {
        isDrawing = true;
        const r = streamContainer.getBoundingClientRect();
        const bounds = getImgBounds();
        
        // 限制起点在真实画面区域内，不能画到黑边上
        startX = Math.max(bounds.offsetX, Math.min(e.clientX - r.left, bounds.offsetX + bounds.dispWidth));
        startY = Math.max(bounds.offsetY, Math.min(e.clientY - r.top, bounds.offsetY + bounds.dispHeight));
        
        overlay.style.left = startX + 'px';
        overlay.style.top = startY + 'px';
        overlay.style.width = '0px';
        overlay.style.height = '0px';
        overlay.style.display = 'block';
    }
});

streamContainer.addEventListener('mousemove', (e) => {
    if (!isDrawing) return;
    const r = streamContainer.getBoundingClientRect();
    const bounds = getImgBounds();
    
    let cx = e.clientX - r.left;
    let cy = e.clientY - r.top;
    
    // 核心修改：将鼠标坐标死死限制在真实画面显示区域内
    cx = Math.max(bounds.offsetX, Math.min(cx, bounds.offsetX + bounds.dispWidth));
    cy = Math.max(bounds.offsetY, Math.min(cy, bounds.offsetY + bounds.dispHeight));

    const w = cx - startX;
    const h = cy - startY;
    overlay.style.left = (w < 0 ? cx : startX) + 'px';
    overlay.style.top = (h < 0 ? cy : startY) + 'px';
    overlay.style.width = Math.abs(w) + 'px';
    overlay.style.height = Math.abs(h) + 'px';
});

streamContainer.addEventListener('mouseup', async (e) => {
    if (e.button !== 0) return;

    if (screenshotMode.checked) {
        if (!isDrawing) return;
        isDrawing = false;
        overlay.style.display = 'none';

        const bounds = getImgBounds();
        const r = streamContainer.getBoundingClientRect();
        
        let endX = Math.max(bounds.offsetX, Math.min(e.clientX - r.left, bounds.offsetX + bounds.dispWidth));
        let endY = Math.max(bounds.offsetY, Math.min(e.clientY - r.top, bounds.offsetY + bounds.dispHeight));

        // 换算为真实像素比例
        let ratioX1 = (startX - bounds.offsetX) / bounds.dispWidth;
        let ratioY1 = (startY - bounds.offsetY) / bounds.dispHeight;
        let ratioX2 = (endX - bounds.offsetX) / bounds.dispWidth;
        let ratioY2 = (endY - bounds.offsetY) / bounds.dispHeight;

        ratioX1 = Math.max(0, Math.min(1, ratioX1));
        ratioY1 = Math.max(0, Math.min(1, ratioY1));
        ratioX2 = Math.max(0, Math.min(1, ratioX2));
        ratioY2 = Math.max(0, Math.min(1, ratioY2));

        if (Math.abs(ratioX2 - ratioX1) < 0.02 || Math.abs(ratioY2 - ratioY1) < 0.02) return;

        const frameImg = new Image();
        frameImg.onload = () => {
            // 更新真实分辨率，确保下次计算黑边时绝对准确
            currentNaturalW = frameImg.naturalWidth;
            currentNaturalH = frameImg.naturalHeight;
            
            const realW = frameImg.naturalWidth;
            const realH = frameImg.naturalHeight;
            
            const realX = Math.round(Math.min(ratioX1, ratioX2) * realW);
            const realY = Math.round(Math.min(ratioY1, ratioY2) * realH);
            const cropW = Math.round(Math.abs(ratioX2 - ratioX1) * realW);
            const cropH = Math.round(Math.abs(ratioY2 - ratioY1) * realH);

            const canvas = document.createElement('canvas');
            canvas.width = cropW;
            canvas.height = cropH;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(frameImg, realX, realY, cropW, cropH, 0, 0, cropW, cropH);

            const dataURL = canvas.toDataURL('image/png');
            cropPreview.src = dataURL;
            cropPreview.style.display = 'block';

            fetch(dataURL).then(res => res.blob()).then(b => croppedBlob = b);
        };
        frameImg.src = `/api/current_frame?device_name=${encodeURIComponent(deviceName)}&_t=${Date.now()}`;

    } else {
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

streamContainer.addEventListener('auxclick', (e) => e.preventDefault());
streamContainer.addEventListener('wheel', (e) => e.preventDefault(), { passive: false });

saveBtn.addEventListener('click', async () => {
    if (!croppedBlob) { alert('请先在左侧画面上拉框选择截图区域！'); return; }
    const folderPath = folderPathInput.value;
    const fileName = fileNameInput.value;
    if (!folderPath) { alert('请先输入文件夹路径'); return; }
    if (!fileName) { alert('请输入保存文件名'); return; }

    const formData = new FormData();
    formData.append('device_name', deviceName);
    formData.append('folder_path', folderPath);
    formData.append('file_name', fileName);
    formData.append('image', croppedBlob, fileName);

    try {
        const res = await fetch('/api/screenshot', { method: 'POST', body: formData });
        const data = await res.json();
        alert(data.success ? `截屏成功！\n已保存至: ${data.path}` : `截屏失败: ${data.message}`);
    } catch (err) {
        alert('请求后台失败: ' + err.message);
    }
});

// 点击输入框，调用后端弹出系统选目录窗口
folderPathInput.addEventListener('click', async () => {
    try {
        const res = await fetch('/api/pick_folder');
        const data = await res.json();
        if (data.success && data.path) {
            folderPathInput.value = data.path;
        }
    } catch (err) {
        alert('选择文件夹失败: ' + err.message);
    }
});
