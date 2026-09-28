# 链易配完整演示录制

录制时间：2026-09-23

## 一体化总视频

观看这个文件即可连续查看全部功能和角色流程：

- `lianyipei-full-demo.webm`：约 3 分 50 秒，包含公开平台、买方企业、卖方企业和管理员端。

如果需要单独定位页面，也保留了以下原始分段：

- `01-public-platform.webm`：公开首页、Indisea 首页、工厂搜索、AI 找工厂、行业资讯、Agent 市场、企业名录、企业详情、资讯详情。
- `02-enterprise-platform.webm`：买方演示企业看板、供需匹配、名录筛选、集采拼单、履约看板、产能日历、订单工作流、资产管理、设置、销售控制台、风险监测、预警工作流、报价池。
- `03-seller-demo-platform.webm`：卖方演示企业销售协同、订单工作流、履约看板和报价池。
- `04-admin-platform.webm`：管理首页、控制台大屏、入驻审核、规则配置、风控中心、API 管理、审计日志、行业资讯管理。

本次录制使用本地开发演示账号：

- 买方演示企业：`长沙德远智造科技有限公司 / demo123456`
- 卖方演示企业：`湖南星瀚精密制造有限公司 / seller123456`
- 管理端：`admin / admin`

政府端已下线，历史政府账号不再允许登录；管理员端继续通过审核、风控、规则、审计和资讯接口管理企业端数据。

重新排练（不生成视频）：

```bash
node scripts/verify/record_full_demo.mjs --rehearse
```

重新录制：

```bash
node scripts/verify/record_full_demo.mjs
```
