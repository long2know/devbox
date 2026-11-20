let socket;

(async () => {
  let target;
  for (let attempt = 0; attempt < 40; attempt++) {
    try {
      const pages = await (await fetch('http://127.0.0.1:9222/json/list', {
        signal: AbortSignal.timeout(3000),
      })).json();
      target = pages.find(page => page.type === 'page' && page.url.startsWith('https://www.google.com/'));
      if (target) break;
    } catch (error) {
      if (error.cause?.code !== 'ECONNREFUSED') throw error;
    }
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  if (!target) throw new Error('Official Chrome did not open the configured Google startup page');

  socket = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('DevTools connection timed out')), 10000);
    socket.addEventListener('open', () => { clearTimeout(timer); resolve(); }, { once: true });
    socket.addEventListener('error', error => { clearTimeout(timer); reject(error); }, { once: true });
  });
  const request = (id, method, params) => new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${method} timed out`)), 20000);
    const listener = ({ data }) => {
      const message = JSON.parse(data);
      if (message.id !== id) return;
      clearTimeout(timer);
      socket.removeEventListener('message', listener);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result);
    };
    socket.addEventListener('message', listener);
    socket.send(JSON.stringify({ id, method, params }));
  });
  // Keep the GPU probe independent of Google page navigation and scripts.
  await request(1, 'Page.navigate', { url: 'about:blank' });
  let navigated = false;
  for (let attempt = 0; attempt < 30; attempt++) {
    const pages = await (await fetch('http://127.0.0.1:9222/json/list', {
      signal: AbortSignal.timeout(3000),
    })).json();
    if (pages.some(page => page.id === target.id && page.url === 'about:blank')) {
      navigated = true;
      break;
    }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  if (!navigated) throw new Error('Chrome did not finish preparing the WebGL test page');
  const result = await request(2, 'Runtime.evaluate', {
    expression: `(() => {
      const gl = document.createElement('canvas').getContext('webgl2');
      if (!gl) return { error: 'WebGL2 is unavailable' };
      const debug = gl.getExtension('WEBGL_debug_renderer_info');
      return {
        renderer: gl.getParameter(debug.UNMASKED_RENDERER_WEBGL),
        version: gl.getParameter(gl.VERSION)
      };
    })()`,
    returnByValue: true,
  });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  console.log(JSON.stringify({ ...result.result.value, startupUrl: target.url }));
})().then(() => {
  socket?.close();
  process.exit(0);
}).catch(error => {
  console.error(error);
  socket?.close();
  process.exit(1);
});
