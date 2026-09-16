# React 前端

`frontend/` 保存 React/Vite 前端的唯一源码。Flask 生产运行时使用构建输出目录 `app/static/frontend/`，不要直接修改其中的打包 JS/CSS。

## 本地开发

```bash
npm install
npm run dev
```

## 检查和构建

```bash
npm run lint   # TypeScript 类型检查
npm run build  # 构建到 ../app/static/frontend
```

资源入口在 `src/main.tsx`，路由和页面在 `src/App.tsx`、`src/pages/`，通用组件在 `src/components/`，API 封装在 `src/services/`。

## 公共首页入口

`src/pages/PublicHome.tsx` 是未登录用户的统一入口：提供关键词搜索与 AI 找工厂双模式、行业/地区/常用条件发现、Agent 能力矩阵，以及基于 `/api/public/home` 和 `/api/public/search` 的脱敏资源展示。首页只展示公开摘要，完整企业能力与协同动作仍通过登录后的工作台完成。

```bash
npm run verify:public-home
```

`public/` 中的资源会随构建复制到 Flask 静态目录；因此 `frontend/public/` 与 `app/static/frontend/` 出现相同资源是预期的，不是需要删除的临时副本。
