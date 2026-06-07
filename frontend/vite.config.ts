import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig, loadEnv} from 'vite';

export default defineConfig(({mode}) => {
  const env = loadEnv(mode, '.', '');
  const flaskProxyTarget =
    env.VITE_FLASK_PROXY_TARGET ||
    env.FLASK_PROXY_TARGET ||
    'http://127.0.0.1:5000';

  // 生产构建输出到 Flask static 目录（便于 Flask 直接服务）
  const isProd = mode === 'production';
  const outDir = isProd
    ? path.resolve(__dirname, '../app/static/frontend')
    : 'dist';

  return {
    plugins: [react(), tailwindcss()],
    base: isProd ? '/static/frontend/' : '/',
    build: {
      outDir,
      emptyOutDir: true,
      rollupOptions: {
        input: {
          main: path.resolve(__dirname, 'index.html'),
        },
        output: {
          // 无哈希文件名，便于 spa.html 模板稳定引用
          entryFileNames: 'assets/[name].js',
          chunkFileNames: 'assets/[name].js',
          assetFileNames: 'assets/[name].[ext]',
        },
      },
    },
    define: {
      'process.env.GEMINI_API_KEY': JSON.stringify(env.GEMINI_API_KEY),
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, '.'),
      },
    },
    server: {
      // 设置 DISABLE_HMR=true 可关闭 HMR（例如远程/代理环境）
      hmr: process.env.DISABLE_HMR !== 'true',
      proxy: {
        '/api': {
          target: flaskProxyTarget,
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path,
          // 本地匹配/大模型冷启动可能超过默认代理超时，避免 Dev Server 提前断连
          timeout: 180_000,
          proxyTimeout: 180_000,
        },
        // Flask-Login：登录 / 注销须与 SPA 同域（5173），浏览器才会在后续 /api 请求里带上 session Cookie
        '/auth': {
          target: flaskProxyTarget,
          changeOrigin: true,
          secure: false,
          timeout: 180_000,
          proxyTimeout: 180_000,
        },
        // 管理员后台 API（/admin/* 由 admin_panel_bp 提供）
        '/admin': {
          target: flaskProxyTarget,
          changeOrigin: true,
          secure: false,
          timeout: 180_000,
          proxyTimeout: 180_000,
        },
        // 政府大屏 / 管理端：Flask dashboard 蓝图下的 JSON（stats、graph-data、alerts 等）
        '/dashboard': {
          target: flaskProxyTarget,
          changeOrigin: true,
          secure: false,
          timeout: 180_000,
          proxyTimeout: 180_000,
        },
        // 政府监管路由（/gov/* 由 SPA 内部处理，前端路由无 /gov 后端路径）
        '/gov': {
          target: flaskProxyTarget,
          changeOrigin: true,
          secure: false,
          timeout: 180_000,
          proxyTimeout: 180_000,
        },
      }
    },
  };
});
