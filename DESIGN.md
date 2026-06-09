---
name: LianYiPei Precision Operations Design System
version: 2.0
source_references:
  - docs/design-references/awesome-design-md
  - docs/design-references/frontend-design-md
---

# 链易配 DESIGN.md

链易配是面向企业、政府监管与平台运营方的供应链协同系统。界面应像“精密供应链指挥中心”：冷静、可信、数据密集、边界清楚，而不是营销页、插画页或单纯炫技的渐变界面。

本文件按 `awesome-design-md` 的使用方式放在项目根目录，供 AI 编码与设计代理优先读取。`frontend/DESIGN.md` 作为前端目录内的补充规范，必须与本文件保持一致。

## Reference Blend

- 主参考：`VoltAgent/awesome-design-md` 中的 IBM、Linear、Vercel、ClickHouse、Sentry。
- 补充参考：`Cozythecoder/frontend-design-md` 中的 Web 前端设计系统集合。
- 取法：IBM 的企业级克制、Linear 的精确层级、Vercel 的边界与排版、ClickHouse 的技术数据密度、Sentry 的风险监控语义。
- 禁止：大面积装饰渐变、漂浮光球、营销落地页 hero、卡片套卡片、过度圆润、纯蓝/纯紫单色主题。

## Visual Theme

- Atmosphere: precise, operational, premium, sober.
- Density: medium-high. 页面应支持快速扫描、比较和重复操作。
- Surfaces: off-white app canvas, white raised panels, graphite navigation, subtle grid/noise only through CSS.
- Shape: cards and controls use 6-8px radius; major shells may use 10px max.
- Motion: restrained 120-180ms hover/focus transitions; no playful bounce.

## Color Tokens

Use semantic tokens, not raw brand colors in components.

| Token | Value | Role |
| --- | --- | --- |
| `--color-brand` | `#155EEF` | Primary command, active route, focused controls |
| `--color-brand-hover` | `#0F46C7` | Primary hover |
| `--color-brand-soft` | `#EAF1FF` | Primary soft fill |
| `--color-brand-muted` | `#7EA6F8` | Low priority brand accent |
| `--color-trust` | `#0E9F6E` | Verified, healthy, green supply |
| `--color-trust-soft` | `#E8F8F1` | Trust background |
| `--color-risk` | `#D97706` | Warning/risk |
| `--color-risk-soft` | `#FFF4DE` | Warning background |
| `--color-critical` | `#D92D20` | Error/critical |
| `--color-critical-soft` | `#FEECEC` | Error background |
| `--color-canvas` | `#F6F7F9` | App background |
| `--color-canvas-grid` | `#EEF1F5` | Subtle grid line |
| `--color-surface` | `#FFFFFF` | Standard panel |
| `--color-surface-raised` | `#FFFFFF` | Raised panel |
| `--color-surface-subtle` | `#F9FAFB` | Nested bands, table heads |
| `--color-ink` | `#111827` | Primary text |
| `--color-ink-soft` | `#374151` | Body text |
| `--color-ink-muted` | `#6B7280` | Secondary text |
| `--color-ink-faint` | `#9CA3AF` | Hints |
| `--color-line` | `#E5E7EB` | Default border |
| `--color-line-strong` | `#D1D5DB` | Inputs, selected boundaries |
| `--color-sidebar-bg` | `#0B1220` | Enterprise/admin navigation |
| `--color-sidebar-panel` | `#111A2B` | Navigation item hover/active well |
| `--color-sidebar-text` | `#A7B0C0` | Navigation text |
| `--color-sidebar-text-active` | `#FFFFFF` | Active navigation text |

## Typography

- Font stack: Inter, system UI, PingFang SC, Microsoft YaHei, sans-serif.
- Data and technical labels: JetBrains Mono, ui-monospace.
- Letter spacing is 0 by default. Do not scale font size with viewport width.
- Page title: 22-26px, 700, line-height 1.2.
- Section title: 16-18px, 650.
- Card title: 14-16px, 650.
- Body: 14px, 400/500.
- Caption: 12px.
- Metric: use tabular numbers; large metrics max 44px inside cards.

## Layout

- App shell: sticky left navigation, sticky top bar, scrollable content.
- Content width: full available width for operational pages; no centered marketing layout except focused tools.
- Page padding: 24px desktop, 16px tablet/mobile.
- Grid gap: 16px or 20px.
- Repeated panels: use CSS grid with stable tracks and minmax constraints.
- Avoid cards inside cards. If detail must be grouped inside a panel, use bands, dividers, or table rows.

## Components

### Card

- Radius: 8px.
- Border: 1px solid line.
- Shadow: very subtle layered shadow only for raised panels.
- Header: compact, with optional icon and status badge.
- Hover: border darkens, translateY(-1px) optional.

### Button

- Radius: 7-8px.
- Height: 36px standard, 32px compact, 40px primary task.
- Primary: brand fill, white text.
- Secondary: white fill, strong border, ink text.
- Ghost/icon: no fill until hover.
- Icon buttons should be square with lucide icons and accessible title/aria-label.

### Navigation

- Sidebar is graphite, not pure black. Active items use a subtle brand rail or active well.
- Group long navigation into operational clusters when possible.
- User block should look like account context, not a marketing profile card.

### Data Panels

- Use compact labels, tabular numbers, progress bars, sparklines, small badges.
- Healthy/risk/critical states use semantic colors; do not use brand blue for every status.
- Empty states are quiet and actionable; no oversized illustrations.

### Forms & Filters

- Filters sit in a command/search panel with stable height.
- Inputs must have visible focus rings.
- Pills/tags are allowed only for filters/status, not as decorative text blocks.

## Responsive Behavior

- At <= 1024px, sidebars may collapse or stack; content grids collapse to 1 column.
- At <= 768px, top search width becomes fluid and navigation should not obscure content.
- Text must not overflow buttons or cards; prefer wrapping, min-width: 0, truncate for entity names.

## Implementation Rules

- Prefer Tailwind semantic classes backed by `frontend/src/index.css` tokens.
- Use lucide icons for recognizable actions.
- Do not introduce remote fonts or third-party tracking scripts.
- Do not expose real credentials or API keys in frontend bundles.
- Every major visual change must pass `npm run lint` and be checked in a browser screenshot.
