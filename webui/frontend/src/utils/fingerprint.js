/**
 * 设备指纹生成工具
 * 基于浏览器硬件特征生成唯一指纹，不依赖IP地址
 * 确保同一WiFi下不同设备不会被误识别
 */

async function getWebGLInfo() {
  try {
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
    if (!gl) return { vendor: '', renderer: '' };
    const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
    return {
      vendor: debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : '',
      renderer: debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : '',
    };
  } catch {
    return { vendor: '', renderer: '' };
  }
}

async function getCanvasHash() {
  try {
    const canvas = document.createElement('canvas');
    canvas.width = 200;
    canvas.height = 50;
    const ctx = canvas.getContext('2d');
    ctx.textBaseline = 'top';
    ctx.font = '14px Arial';
    ctx.fillStyle = '#f60';
    ctx.fillRect(125, 1, 62, 20);
    ctx.fillStyle = '#069';
    ctx.fillText('ExplainV!', 2, 15);
    ctx.fillStyle = 'rgba(102, 204, 0, 0.7)';
    ctx.fillText('ExplainV!', 4, 17);
    return canvas.toDataURL().slice(-50);
  } catch {
    return '';
  }
}

/**
 * 简单的字符串哈希函数
 */
function hashCode(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash).toString(36);
}

/**
 * 生成设备指纹
 * 组合多种硬件和浏览器特征，确保同一WiFi下不同设备不会误识别
 */
export async function generateFingerprint() {
  const webgl = await getWebGLInfo();
  const canvasHash = await getCanvasHash();

  const components = [
    // 屏幕特征（硬件级别）
    `screen:${screen.width}x${screen.height}`,
    `avail:${screen.availWidth}x${screen.availHeight}`,
    `colorDepth:${screen.colorDepth}`,
    `pixelRatio:${window.devicePixelRatio}`,

    // 浏览器/系统特征
    `platform:${navigator.platform}`,
    `hardwareConcurrency:${navigator.hardwareConcurrency}`,
    `deviceMemory:${navigator.deviceMemory || 'N/A'}`,
    `maxTouchPoints:${navigator.maxTouchPoints}`,
    `language:${navigator.language}`,
    `languages:${(navigator.languages || []).join(',')}`,

    // 时区（精确到分钟偏移）
    `timezone:${Intl.DateTimeFormat().resolvedOptions().timeZone}`,
    `tzOffset:${new Date().getTimezoneOffset()}`,

    // WebGL 硬件渲染信息（GPU级别特征）
    `webglVendor:${webgl.vendor}`,
    `webglRenderer:${webgl.renderer}`,

    // Canvas 渲染指纹
    `canvas:${canvasHash}`,
  ];

  const raw = components.join('|');
  return hashCode(raw);
}
