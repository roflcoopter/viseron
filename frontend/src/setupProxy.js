const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  app.use(
    createProxyMiddleware("/api", {
      target: `http://${process.env.REACT_APP_PROXY_HOST}`,
      changeOrigin: true,
      timeout: 5000,
      proxyTimeout: 5000,
    })
  );

  app.use(
    createProxyMiddleware("/websocket", {
      target: `ws://${process.env.REACT_APP_PROXY_HOST}`,
      ws: true,
      changeOrigin: true,
      timeout: 5000,
      proxyTimeout: 5000,
    })
  );

  app.use(
    createProxyMiddleware("/*/mjpeg-stream", {
      target: `http://${process.env.REACT_APP_PROXY_HOST}`,
      changeOrigin: true,
      timeout: 5000,
      proxyTimeout: 5000,
    })
  );
};
