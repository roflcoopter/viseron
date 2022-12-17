const { createProxyMiddleware } = require("http-proxy-middleware");

module.exports = function (app) {
  app.use(
    createProxyMiddleware("/api", {
      target: `http://${process.env.REACT_APP_PROXY_HOST}`,
      changeOrigin: true,
    })
  );

  app.use(
    createProxyMiddleware("/websocket", {
      target: `ws://${process.env.REACT_APP_PROXY_HOST}`,
      ws: true,
      changeOrigin: true,
    })
  );

  app.use(
    createProxyMiddleware("/*/mjpeg-stream", {
      target: `http://${process.env.REACT_APP_PROXY_HOST}`,
      changeOrigin: true,
    })
  );
};
