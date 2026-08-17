/**
 * scrcpy H.264 视频流解码器（WebCodecs API）
 * 通过 WebSocket 接收 H.264 Annex B 数据，用浏览器硬件解码渲染到 canvas
 *
 * 关键点：
 * - VideoDecoder 配置时用 description (avcC)，data 必须是 AVCC 格式（4字节大端长度前缀）
 * - 不能传 Annex B 格式（start code 00 00 00 01），否则解码器静默失败导致黑屏
 * - NAL unit 解析: 找到所有 start code，分割成 NAL units，最后一个可能不完整需保留
 */
const ScrcpyWebCodecs = {
  ws: null,
  decoder: null,
  canvas: null,
  ctx: null,
  running: false,
  buffer: new Uint8Array(0),
  sps: null,
  pps: null,
  decoderConfigured: false,
  frameCount: 0,
  lastFpsTime: 0,
  lastLogTime: 0,
  deviceInfo: null,
  nalCount: 0,
  baseTimestamp: 0,
  tsCounter: 0,

  /** 检查浏览器是否支持 WebCodecs */
  isSupported() {
    return typeof VideoDecoder !== 'undefined';
  },

  /** 初始化并连接 */
  start(device, canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) {
      console.error('[scrcpy] canvas 不存在:', canvasId);
      return false;
    }
    this.ctx = this.canvas.getContext('2d', { alpha: false });
    this.running = true;
    this.buffer = new Uint8Array(0);
    this.sps = null;
    this.pps = null;
    this.decoderConfigured = false;
    this.frameCount = 0;
    this.nalCount = 0;
    this.lastFpsTime = performance.now();
    this.lastLogTime = performance.now();
    this.baseTimestamp = performance.now();
    this.tsCounter = 0;

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}/ws/scrcpy_stream?device=${encodeURIComponent(device)}`;

    this.ws = new WebSocket(url);
    this.ws.binaryType = 'arraybuffer';

    this.ws.onopen = () => {
      console.log('[scrcpy] WebSocket 已连接, device=' + device);
    };

    this.ws.onmessage = async (event) => {
      if (typeof event.data === 'string') {
        const msg = JSON.parse(event.data);
        if (msg.type === 'meta') {
          this.deviceInfo = msg.device_info;
          this.canvas.width = this.deviceInfo.width || 1920;
          this.canvas.height = this.deviceInfo.height || 1080;
          console.log('[scrcpy] 设备信息:', this.deviceInfo);
        } else if (msg.type === 'error') {
          console.error('[scrcpy] 服务端错误:', msg.message);
        }
      } else {
        const chunk = new Uint8Array(event.data);
        this._feedData(chunk);
      }
    };

    this.ws.onerror = (e) => {
      console.error('[scrcpy] WebSocket 错误:', e);
    };

    this.ws.onclose = () => {
      console.log('[scrcpy] WebSocket 已断开');
      this.running = false;
      if (this.decoder) {
        try { this.decoder.close(); } catch(e) {}
        this.decoder = null;
      }
    };

    return true;
  },

  /** 停止 */
  stop() {
    this.running = false;
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    if (this.decoder) {
      try { this.decoder.close(); } catch(e) {}
      this.decoder = null;
    }
    this.decoderConfigured = false;
  },

  /** 将 H.264 数据追加到缓冲区并解析 */
  _feedData(data) {
    const newBuf = new Uint8Array(this.buffer.length + data.length);
    newBuf.set(this.buffer);
    newBuf.set(data, this.buffer.length);
    this.buffer = newBuf;
    this._parseNalUnits();
  },

  /** 解析 Annex B 流: 找出所有 start code, 分割 NAL units, 处理完整的, 保留最后一个(可能不完整) */
  _parseNalUnits() {
    const buf = this.buffer;
    if (buf.length < 5) return;

    // 找出所有 start code 起始位置 (返回每个 NAL unit 的数据起点)
    const nalStarts = [];
    for (let i = 0; i < buf.length - 3; i++) {
      if (buf[i] === 0 && buf[i + 1] === 0 && buf[i + 2] === 1) {
        nalStarts.push({ scPos: i, dataStart: i + 3 });
        i += 2;
      } else if (buf[i] === 0 && buf[i + 1] === 0 && buf[i + 2] === 0 && i + 3 < buf.length && buf[i + 3] === 1) {
        nalStarts.push({ scPos: i, dataStart: i + 4 });
        i += 3;
      }
    }

    if (nalStarts.length === 0) return;

    // 处理除最后一个外的所有 NAL unit (最后一个是完整的)
    for (let k = 0; k < nalStarts.length - 1; k++) {
      const dataStart = nalStarts[k].dataStart;
      const dataEnd = nalStarts[k + 1].scPos;  // 到下一个 start code 之前
      const nalData = buf.subarray(dataStart, dataEnd);
      // 去掉尾部可能的 padding zero bytes (NAL 之间的 0x00 用于对齐)
      let realEnd = nalData.length;
      while (realEnd > 0 && nalData[realEnd - 1] === 0) realEnd--;
      if (realEnd > 0) {
        this._handleNalUnit(nalData.subarray(0, realEnd));
      }
    }

    // 保留从最后一个 start code 开始的数据 (最后一个 NAL 可能不完整)
    const lastScPos = nalStarts[nalStarts.length - 1].scPos;
    this.buffer = buf.slice(lastScPos);
  },

  /** 处理单个 NAL unit */
  _handleNalUnit(nalData) {
    if (nalData.length === 0) return;
    this.nalCount++;

    const nalType = nalData[0] & 0x1F;

    // 每 2 秒打印一次诊断信息
    const now = performance.now();
    if (now - this.lastLogTime > 2000) {
      console.log(`[scrcpy] NAL total=${this.nalCount}, type=${nalType}, len=${nalData.length}, decoderState=${this.decoder ? this.decoder.state : 'null'}, configured=${this.decoderConfigured}, frames=${this.frameCount}`);
      this.lastLogTime = now;
    }

    switch (nalType) {
      case 7: // SPS
        this.sps = nalData.slice();
        this.decoderConfigured = false;
        break;
      case 8: // PPS
        this.pps = nalData.slice();
        if (this.sps) {
          this._configureDecoder();
        }
        break;
      case 5: // IDR slice (keyframe)
      case 1: // Non-IDR slice
        if (this.decoderConfigured && this.decoder && this.decoder.state === 'configured') {
          this._decode(nalData, nalType === 5);
        }
        break;
      case 9: // AUD
      case 6: // SEI
        break;
      default:
        break;
    }
  },

  /** 配置解码器 */
  _configureDecoder() {
    if (!this.sps || !this.pps) return;

    const avcC = this._buildAvcC(this.sps, this.pps);
    if (!avcC) return;

    const profile = this.sps[1];
    const constraint = this.sps[2];
    const level = this.sps[3];
    const codecStr = `avc1.${profile.toString(16).padStart(2, '0')}${constraint.toString(16).padStart(2, '0')}${level.toString(16).padStart(2, '0')}`;

    try {
      if (this.decoder) {
        try { this.decoder.close(); } catch(e) {}
      }
      this.decoder = new VideoDecoder({
        output: (frame) => this._renderFrame(frame),
        error: (e) => console.error('[scrcpy] 解码器错误:', e.message, e),
      });

      const config = {
        codec: codecStr,
        description: avcC,
        optimizeForLatency: true,
      };
      this.decoder.configure(config);
      this.decoderConfigured = true;
      console.log(`[scrcpy] 解码器已配置: codec=${codecStr}, sps=${this.sps.length}B, pps=${this.pps.length}B`);
    } catch (e) {
      console.error('[scrcpy] 配置解码器失败:', e);
      this.decoderConfigured = false;
    }
  },

  /** 构建 avcC box (decoder configuration record) */
  _buildAvcC(sps, pps) {
    const buf = new Uint8Array(11 + sps.length + pps.length);
    let i = 0;
    buf[i++] = 1;              // version
    buf[i++] = sps[1];         // profile
    buf[i++] = sps[2];         // compatibility
    buf[i++] = sps[3];         // level
    buf[i++] = 0xFF;           // 0xFF: NALU length size = 4 (大端)
    buf[i++] = 0xE1;           // 0xE1: num SPS = 1
    buf[i++] = (sps.length >> 8) & 0xFF;
    buf[i++] = sps.length & 0xFF;
    buf.set(sps, i); i += sps.length;
    buf[i++] = 1;              // num PPS = 1
    buf[i++] = (pps.length >> 8) & 0xFF;
    buf[i++] = pps.length & 0xFF;
    buf.set(pps, i);
    return buf;
  },

  /** 解码一个 NAL unit (用 AVCC 格式: 4 字节大端长度前缀 + NAL data, 不含 start code) */
  _decode(nalData, isKeyFrame) {
    if (!this.decoder || this.decoder.state !== 'configured') return;

    // 保守丢帧策略: 队列深度极高时才丢帧, 优先丢 delta 但保留参考链完整性
    // 阈值过低 (如 5) 会破坏 P 帧参考链导致马赛克/糊
    const qs = this.decoder.decodeQueueSize;
    if (qs >= 15) {
      // 队列严重积压, 必须丢帧追赶
      if (!isKeyFrame) {
        // 丢 delta 帧, 但要小心: 连续丢太多 delta 后, 下一个 delta 也无法正确解码
        // 所以这里只丢一个, 等待 IDR 到来时自然恢复
        return;
      }
      // IDR 帧不丢, 它能重置参考链
    }

    try {
      // AVCC 格式: [4字节大端长度][NAL data]  (不加 start code!)
      const chunk = new Uint8Array(4 + nalData.length);
      const view = new DataView(chunk.buffer);
      view.setUint32(0, nalData.length);  // 大端长度
      chunk.set(nalData, 4);

      this.decoder.decode(new EncodedVideoChunk({
        type: isKeyFrame ? 'key' : 'delta',
        // 用递增计数器生成 timestamp, 避免重复 timestamp 导致丢帧
        // scrcpy 不传 PTS, 用 1/60s (约 16.67ms) 作为虚拟帧间隔
        timestamp: this.tsCounter++ * 16667,
        data: chunk,
      }));

      this.frameCount++;
    } catch (e) {
      // 队列满或其他错误, 忽略
    }
  },

  /** 渲染解码后的帧到 canvas */
  _renderFrame(frame) {
    if (!this.ctx || !this.running) {
      frame.close();
      return;
    }
    try {
      this.ctx.drawImage(frame, 0, 0, this.canvas.width, this.canvas.height);
    } catch (e) {
      // 渲染失败
    }
    frame.close();
  },
};
