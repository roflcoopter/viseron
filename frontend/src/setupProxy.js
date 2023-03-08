const { createProxyMiddleware } = require("http-proxy-middleware");

const proxyOptions = {
  changeOrigin: true,
  timeout: 5000,
  proxyTimeout: 5000,
};

module.exports = function (app) {
  app.use(
    createProxyMiddleware("/api", {
      target: `http://${process.env.REACT_APP_PROXY_HOST}`,
      ...proxyOptions,
    })
  );

  app.use(
    createProxyMiddleware("/websocket", {
      target: `ws://${process.env.REACT_APP_PROXY_HOST}`,
      ws: true,
      ...proxyOptions,
    })
  );

  app.use(
    createProxyMiddleware("/recordings", {
      target: `http://${process.env.REACT_APP_PROXY_HOST}`,
      ...proxyOptions,
    })
  );

  app.use(
    createProxyMiddleware("/*/mjpeg-stream", {
      target: `http://${process.env.REACT_APP_PROXY_HOST}`,
      ...proxyOptions,
    })
  );
};
