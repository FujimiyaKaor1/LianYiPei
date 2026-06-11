# 政府产业监管数字化大屏调研与测试报告

生成日期：2026-06-10

## 1. GitHub 调研结论

调研方式：使用 GitHub 公开仓库页、GitHub star 徽章、仓库 Raw 文件和大屏相关关键词检索 `ECharts 大屏`、`可视化 大屏`、`中国地图 大屏` 等方向，并复核候选仓库 star 数、许可协议和项目定位。用户本轮明确指定 [nichan-13/Echarts-Demo](https://github.com/nichan-13/Echarts-Demo) 作为配置参考；截至 2026-06-10 通过 GitHub stars 徽章复核，该仓库为 568 stars。该仓库是典型 ECharts 数据大屏 Demo，核心页面由 `header`、`section.mainbox`、左中右三列、中心 `.no` 数字模块和 `.map` 三层旋转地图组成，适合作为本次政府产业监管端“投屏式数字大屏”的直接布局参考。

| 参考层级 | 仓库 | Stars | 许可 | 借鉴点 |
|---|---:|---:|---|---|
| 图表/地图基础能力最高星 | [apache/echarts](https://github.com/apache/echarts) | 约 67k | Apache-2.0 | 参考中国地图承载指标标注、区域态势和图表交互能力，但当前版本未引入 ECharts 依赖。 |
| 广义 BI / 嵌入式分析最高星 | [metabase/metabase](https://github.com/metabase/metabase) | 47,617 | NOASSERTION | 参考可刷新、可嵌入、可钻取的 BI 产品结构。 |
| 广义 BI / 查询看板 | [getredash/redash](https://github.com/getredash/redash) | 28,630 | BSD-2-Clause | 参考多数据源、查询可视化和共享看板能力。 |
| 本轮指定主参考 | [nichan-13/Echarts-Demo](https://github.com/nichan-13/Echarts-Demo) | 568 | 未声明 | 直接参考 `header + mainbox`、3/5/3 三栏、左右各三面板、中部 `.no` 数字块、三层旋转地图和 ECharts 图表配置形态。 |
| 中文开源 BI | [dataease/dataease](https://github.com/dataease/dataease) | 约 24k | GPL-3.0 | 作为政企 BI 后续配置化、嵌入式分析和权限治理参考；本轮不再作为主视觉参考。 |
| 数据大屏组件库最高星 | [DataV-Team/DataV](https://github.com/DataV-Team/DataV) | 约 9.7k | MIT | 直接参考大屏三栏布局、暗色网格、科技边框、装饰线和高密度图表组织。 |
| AI 报表与数据大屏 | [jeecgboot/jimureport](https://github.com/jeecgboot/jimureport) | 7,998 | GPL-3.0 | 参考“报表 + 大屏 + 多数据源”的后续配置化方向。 |
| 大屏 Demo | [yyhsong/iDataV](https://github.com/yyhsong/iDataV) | 5,684 | NOASSERTION | 参考大屏视觉节奏，但不作为代码依赖。 |
| 行业大屏模板集合 | [iGaoWei/BigDataView](https://github.com/iGaoWei/BigDataView) | 5,165 | NOASSERTION | 覆盖政务、交通、金融等模板，参考行业信息密度。 |
| 大屏实现样例 | [TurboWay/big_screen](https://github.com/TurboWay/big_screen) | 1,867 | MIT | 参考单页大屏结构。 |
| 低代码可视化方向 | [dromara/go-view](https://github.com/dromara/go-view) | 931 | MIT | 后续可参考可配置大屏编辑器方向。 |

实际开发策略：以 `nichan-13/Echarts-Demo` 作为主参考，按其大屏配置重组页面骨架：顶部标题与当前时间、左右三面板、中部 `.no` 数字块、中国地图主舞台、旋转环和图表矩阵。当前 React/Vite 项目内继续使用现有政府端 API、原生 SVG 中国地图和 Recharts 图表实现，避免直接复制外部静态资源和脚本；ECharts-Demo 的 `index.html`、`css/index.css`、`js/index.js` 仅用于结构、比例、面板和图表类型参考。

## 2. 已开发功能清单

新增页面：`/gov/screen`

已接入位置：

- 政府端侧边栏新增“数字大屏”入口。
- 政府端首页快捷操作新增“数字大屏”入口。
- `/gov/screen` 使用独立沉浸式布局，不再显示普通政府后台的侧边栏和顶部栏。
- 全页面统一蓝色视觉层级，弱化红黄绿告警色，贴近 Echarts-Demo 式投屏大屏。
- 页面按需懒加载，构建后产物为独立 `GovDigitalScreen.js` chunk。
- 按 Echarts-Demo 的 `mainbox` 配置重排为左/中/右三栏，桌面端比例近似 3/5/3，移动端纵向堆叠。
- 左右两列均为三块大屏面板，面板使用四角高亮边框、居中标题和暗色网格背景。
- 中部新增 `.no` 风格数字模块，显示链内企业数量、市场供需总量及四个监管状态小指标。
- 中部地图模块新增 `map1/map2/map3` 三层旋转环，对应 Echarts-Demo 的地图背景、外环和箭头环配置。

大屏功能：

1. 数据源在线状态：并行加载 7 个监管数据源，并显示在线数量。
2. 手动刷新：刷新按钮重新拉取全部大屏数据。
3. 自动刷新：页面停留期间每 120 秒自动同步一次。
4. 全屏投放：支持浏览器全屏展示。
5. 返回入口：提供返回政府监管首页的图标入口。
6. 顶部实时标题栏：居中显示“政府产业监管数字化大屏”，右侧按秒显示当前时间，左侧显示数据源在线状态。
7. 中部 `.no` 数字模块：显示链内企业数量、市场供需总量、活跃供应、活跃采购、风险预警和闭环完成率。
8. 左上“柱形图-供需趋势”：展示历史供需与未来预测曲线。
9. 左中“折线图-风险等级”：按高危/中级/低级展示预警数量。
10. 左下“饼形图-处置闭环”：展示待处理、处理中、已完成、退回工单状态。
11. 中部地图主舞台：自绘中国地图展示京津冀、长三角、粤港澳、成渝、中部枢纽等区域热点、流向线和区域健康指数。
12. Echarts-Demo 地图环配置：新增 `map1/map2/map3` 三层视觉环，包含静态背景环、顺时针旋转虚线环和反向箭头环。
13. 区域公司数量标注：接入 `/api/enterprises/directory?limit=200` 企业目录数据源，按企业 `province`、`city`、`address` 归属到京津冀、长三角、粤港澳、成渝、中部枢纽，并在中国地图和右侧面板显示“xx家”。
14. 企业数量兜底估算：当企业目录接口为空或没有可匹配地区时，按 `enterprise_count` 结合区域比例生成兜底标注，避免地图空屏。
15. 右上“柱形图-活跃预警”：展示最高优先级预警、风险等级、时间和消息摘要。
16. 右中“折线图-补链强链缺口”：展示高紧迫缺口、本地化比例、供应商数量、影响企业数、供需差和缺口方向。
17. 右下“饼形图-地区分布”：展示区域企业数量进度条，并附带关键节点 PageRank 排行。
18. 关键节点排行：展示 PageRank 关键产品/节点，用于识别产业链核心产品。
19. 监管运行研判：底部提示联动质量标签、招商任务和预警工单形成闭环。
20. 数据源失败提示：某个接口失败时给出“待恢复数据源”提示，不阻断其他模块展示；企业目录失败时单独标记为“企业地区分布”。

## 3. 功能测试结果

| 类型 | 命令 / 方法 | 结果 |
|---|---|---|
| TypeScript 类型检查 | `npm run lint` | 通过 |
| 生产构建 | `npm run build` | 通过，已更新 `app/static/frontend` |
| 前端依赖审计 | `npm audit --audit-level=high` | 通过，0 vulnerabilities |
| 懒加载拆包 | 构建产物检查 | 通过，新增/更新 `GovDigitalScreen.js`，政府大屏独立加载 |
| 桌面浏览器验证 | Playwright + API 拦截，1600x1000 | 通过，三栏大屏、顶部时间、中心数字模块、中国地图、地图旋转环、六个面板、刷新按钮均可见；无 console error、无失败请求、无横向溢出 |
| 移动浏览器验证 | Playwright + API 拦截，390x1050 | 通过，移动端纵向堆叠，顶部时间、地图模块、六个面板和底部研判均可见；无 console error、无失败请求、无横向溢出 |
| Echarts-Demo 结构验证 | Playwright DOM 检查 | 通过，已检查 `header`、`mainbox`、左中右三列、`.no` 数字模块、`map1/map2/map3`、中国地图和六个面板标题 |
| 区域公司数量验证 | Playwright + 企业目录 Mock | 通过，长三角 30 家、京津冀 15 家、粤港澳 12 家、成渝 9 家、中部枢纽 12 家均显示在地图或地区分布模块中 |
| 蓝色主题检查 | Playwright DOM class 扫描 | 通过，大屏 DOM 中无 `emerald/amber/rose/text-red/text-yellow` 等旧非蓝色视觉 class 残留 |

验证截图：

- `frontend/test-artifacts/gov-digital-screen-desktop-echarts-demo-config.png`
- `frontend/test-artifacts/gov-digital-screen-mobile-echarts-demo-config.png`
- `frontend/test-artifacts/gov-digital-screen-echarts-demo-config-validation.json`

## 4. 基于调研的改进建议

1. 增加聚合型大屏 API：当前前端并行请求 7 个接口，后续建议新增 `/api/gov/screen-summary`，一次返回大屏摘要，降低首屏抖动和接口失败面。
2. 增加只读投屏链接：参考 Metabase/DataEase 的嵌入思路，为会议室大屏提供短期令牌、只读链接和访问日志。
3. 增加指标钻取联动：点击预警、缺口、关键节点后跳转到预警中心、招商决策或产业链图谱，并自动带筛选条件。
4. 使用标准行政区边界：当前为轻量自绘 SVG 中国地图，后续若需要省级精确定位，可按 Echarts-Demo 的地图实现思路引入 ECharts map 或合规 GeoJSON，并做本地化缓存和许可证记录。
5. 增加数据新鲜度与血缘：每个模块显示最近同步时间、数据来源和异常原因，方便政府监管端追溯数据可信度。
6. 引入实时推送：高危预警和工单状态可使用 SSE/WebSocket，减少轮询并提升大屏即时性。
7. 做有限配置化：先把 Echarts-Demo 的“左右三面板 + 中部 no/map”抽成配置 JSON，允许管理员配置指标槽位、排序、刷新周期和阈值；不建议一开始做完整低代码编辑器。
8. 增强安全审计：对大屏访问、全屏投放、外部嵌入、异常刷新进行角色审计和操作日志记录。
9. 继续拆包优化：当前主包仍超过 500 kB，建议后续拆分企业端重图表页、ECharts/Recharts 公共 chunk。
