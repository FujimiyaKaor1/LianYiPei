# 链易配完整演示录制

录制时间：2026-09-20

视频按角色拆分，便于逐段查看：

- `01-public-platform.webm`：公开首页、Indisea 首页、工厂搜索、AI 找工厂、行业资讯、Agent 市场、企业名录、企业详情、资讯详情。
- `02-enterprise-platform.webm`：买方演示企业看板、供需匹配、名录筛选、集采拼单、履约看板、产能日历、订单工作流、资产管理、设置、销售控制台、风险监测、预警工作流、报价池。
- `03-seller-demo-platform.webm`：卖方演示企业销售协同、订单工作流、履约看板和报价池。
- `04-government-platform.webm`：监管首页、数字大屏、质量标签、预警中心、产业链图谱、招商决策。
- `05-admin-platform.webm`：管理首页、控制台大屏、入驻审核、规则配置、风控中心、API 管理、审计日志、行业资讯管理。

本次录制使用本地开发演示账号：

- 买方演示企业：`长沙德远智造科技有限公司 / demo123456`
- 卖方演示企业：`湖南星瀚精密制造有限公司 / seller123456`
- 政府端：`成都市产业链协同专班 / 123456`
- 管理端：`admin / admin`

重新排练（不生成视频）：

```bash
node scripts/verify/record_full_demo.mjs --rehearse
```

重新录制：

```bash
node scripts/verify/record_full_demo.mjs
```
