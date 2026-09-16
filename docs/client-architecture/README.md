# 链易配客户端与 Agent 架构图

本目录中的四张 PNG 是本次汇报用的正式图：

1. `01-buyer-functions-and-architecture.png`：企业采购客户端
2. `02-supplier-functions-and-architecture.png`：供应商经营客户端
3. `03-platform-operations-functions-and-architecture.png`：平台 / 园区运营客户端
4. `04-agent-orchestration-design.png`：Agent 共用编排层设计

图片根据当前项目实际模块归类。Agent 只服务企业采购端和供应商端；平台 / 园区运营端坚持人工研判、人工处置和人工担责。Agent 图中的编排层、工具注册表、权限闸门、确认机制和审计事件属于新增设计；其下方的匹配、企业画像、询价报价、订单履约、风险预警、知识图谱和预测等是对现有业务能力的复用。

## 本地重新生成

项目已提供独立的轻量图片生成环境说明：

```bash
python3 -m pip install -r requirements-diagrams.txt
python3 scripts/generate_client_architecture_diagrams.py
```

输出目录为当前目录。生成器使用 Pillow 绘制确定性 PNG，不依赖外部图片 API，适合比赛答辩材料反复修改和离线生成。
