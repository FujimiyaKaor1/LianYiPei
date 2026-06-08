---
name: 链易配 (LianYiPei) Design System
description: 产业链供需智能匹配平台 B2B SaaS 设计规范。融合 Linear 的精准极简 + Vercel 的黑白精炼 + Notion 的温暖工具体验。
version: 1.0
---

## Design Philosophy

链易配是 B2B 供应链智能匹配平台，面向企业用户和政府监管方。设计核心：
- **信任感**：专业蓝色系 + 足够留白传达可靠
- **高效**：数据密集场景下保持清晰层次
- **温暖**：微妙的圆角 + 柔和阴影让工具感不那么冰冷

融合三大设计元：
- **Linear 式精准**：清晰的信息层级、克制的色彩
- **Vercel 式精炼**：堆叠阴影、负字距标题、通用 sans + mono 双字体
- **Notion 式温暖**：soft surface 底色、圆角卡片系统

---

## Colors

所有颜色基于 Tailwind v4 @theme 语义化 token。

### Brand
| Token | Value | Role |
|-------|-------|------|
| `--color-brand` | `#1A56DB` | 主品牌色 - 按钮、链接、强调 |
| `--color-brand-hover` | `#1E40AF` | Brand hover/pressed |
| `--color-brand-soft` | `#EFF6FF` | 品牌色浅底 |
| `--color-brand-muted` | `#93C5FD` | 品牌色装饰 |

### Surfaces
| Token | Value | Role |
|-------|-------|------|
| `--color-canvas` | `#FFFFFF` | 纯白卡片/模态框底面 |
| `--color-canvas-soft` | `#FAFAFA` | 页面默认底色 |
| `--color-canvas-muted` | `#F5F5F5` | 次级分区底色 |
| `--color-canvas-raised` | `#FFFFFF` | 悬浮卡片 |

### Text
| Token | Value | Role |
|-------|-------|------|
| `--color-ink` | `#0A0A0A` | 标题、强调文字 |
| `--color-ink-soft` | `#404040` | 正文 |
| `--color-ink-muted` | `#737373` | 辅助文字、placeholder |
| `--color-ink-disabled` | `#A3A3A3` | 禁用态文字 |
| `--color-on-brand` | `#FFFFFF` | 品牌色上的文字 |

### Borders
| Token | Value | Role |
|-------|-------|------|
| `--color-border` | `#E5E5E5` | 默认边框 |
| `--color-border-strong` | `#D4D4D4` | 强边框（输入框等） |
| `--color-border-hover` | `#A3A3A3` | 悬停边框 |

### Semantic
| Token | Value | Role |
|-------|-------|------|
| `--color-success` | `#059669` | 成功 |
| `--color-success-soft` | `#ECFDF5` | 成功浅底 |
| `--color-warning` | `#D97706` | 警告 |
| `--color-warning-soft` | `#FFFBEB` | 警告浅底 |
| `--color-error` | `#DC2626` | 错误 |
| `--color-error-soft` | `#FEF2F2` | 错误浅底 |
| `--color-info` | `#2563EB` | 信息 |

### Data Visualization
| Token | Value | Role |
|-------|-------|------|
| `--color-chart-1` | `#1A56DB` | 图表主色 |
| `--color-chart-2` | `#059669` | 图表辅色 |
| `--color-chart-3` | `#D97706` | 图表第三色 |
| `--color-chart-4` | `#7C3AED` | 图表第四色 |
| `--color-chart-5` | `#DC2626` | 图表第五色 |

### Side Navigation
| Token | Value | Role |
|-------|-------|------|
| `--color-sidebar-bg` | `#0F172A` | 侧栏底色 (深色模式侧栏) |
| `--color-sidebar-text` | `#94A3B8` | 侧栏文字 |
| `--color-sidebar-text-active` | `#FFFFFF` | 侧栏激活文字 |
| `--color-sidebar-item-active` | `rgba(255,255,255,0.1)` | 侧栏激活项 |
| `--color-sidebar-item-hover` | `rgba(255,255,255,0.05)` | 侧栏悬停 |

---

## Typography

### Font Family
- **Sans**: Inter, -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif
- **Mono**: JetBrains Mono, ui-monospace, "Cascadia Code", monospace

### Scale
| Token | Size | Weight | Line Height | Letter Spacing | Usage |
|-------|------|--------|-------------|----------------|-------|
| `display-lg` | 32px | 700 | 1.15 | -0.5px | 大屏看板标题 |
| `display-md` | 24px | 700 | 1.2 | -0.3px | 页面标题 |
| `display-sm` | 20px | 600 | 1.25 | -0.2px | 区域标题 |
| `heading` | 18px | 600 | 1.35 | 0 | 卡片标题 |
| `subheading` | 15px | 500 | 1.4 | 0 | 次级标题 |
| `body` | 14px | 400 | 1.5 | 0 | 正文 |
| `body-medium` | 14px | 500 | 1.5 | 0 | 正文强调 |
| `caption` | 12px | 400 | 1.45 | 0 | 辅助说明 |
| `caption-bold` | 12px | 600 | 1.45 | 0 | 标签、徽章 |
| `micro` | 10px | 500 | 1.4 | 0.5px | 极小标注 |
| `button` | 14px | 500 | 1.2 | 0 | 按钮文字 |

### Principles
- 标题统一用负字距（tight tracking），增强精致感（参考 Vercel）
- 中英文混排使用 Inter + 系统中文回退字体
- Mono 仅用于技术标注、代码片段、数据指标
  
---

## Spacing

基于 4px 系统：

| Token | Value |
|-------|-------|
| `space-0.5` | 2px |
| `space-1` | 4px |
| `space-2` | 8px |
| `space-3` | 12px |
| `space-4` | 16px |
| `space-5` | 20px |
| `space-6` | 24px |
| `space-8` | 32px |
| `space-10` | 40px |
| `space-12` | 48px |
| `space-16` | 64px |

- 页面内容区内边距：`24px`
- 卡片内边距：`20px` (标准) / `16px` (紧凑)
- 侧栏宽度：`240px` (展开) / `64px` (折叠)

---

## Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `radius-xs` | 4px | 标签、徽章、代码块 |
| `radius-sm` | 6px | 输入框、小按钮 |
| `radius-md` | 8px | 卡片、模态框、标准按钮 |
| `radius-lg` | 12px | 大卡片、特色面板 |
| `radius-xl` | 16px | 超大面板 |
| `radius-full` | 9999px | 圆形头像、pill 标签 |

- **按钮用 `radius-md` (8px)** — 非 pill 形状，保持专业感（参考 Linear）
- **卡片用 `radius-lg` (12px)** — 柔和的视觉重量
- **输入框用 `radius-sm` (6px)** — 紧凑高效

---

## Elevation (Shadow)

参考 Vercel 的堆叠阴影系统：

| Level | Token | Usage |
|-------|-------|-------|
| 0 | `none` | 全宽 band、表格行 |
| 1 | `0 1px 2px rgba(0,0,0,0.04)` | 默认卡片、悬浮卡片 |
| 2 | `0 1px 1px rgba(0,0,0,0.02), 0 4px 8px rgba(0,0,0,0.04)` | 中等悬浮（下拉菜单） |
| 3 | `0 1px 1px rgba(0,0,0,0.02), 0 8px 16px -4px rgba(0,0,0,0.06)` | 高悬浮（模态框） |

- 不使用 Material 风格的单一大阴影
- 所有悬浮卡片配 `1px solid border` 保持边缘清晰

---

## Components

### Button
```
button-primary:
  bg: brand, text: on-brand, radius: md, padding: 0 20px, height: 40px
  hover: brand-hover, font: button (14px/500)
  disabled: bg-muted, text-disabled

button-secondary:
  bg: canvas, text: ink, border: 1px border-strong, radius: md
  padding: 0 20px, height: 40px
  hover: bg-canvas-muted

button-ghost:
  bg: transparent, text: ink-soft, radius: sm
  padding: 0 12px, height: 36px
  hover: bg-canvas-muted

button-danger:
  bg: error, text: white, radius: md, padding: 0 20px, height: 40px
```

### Card
```
card-default:
  bg: canvas, radius: lg, border: 1px border
  padding: 20px, shadow: level-1

card-hover:
  extends card-default
  hover: shadow-level-2, border-hover

card-muted:
  bg: canvas-soft, radius: lg, padding: 20px
```

### Input
```
input-default:
  bg: canvas, text: ink, border: 1px border-strong
  radius: sm, padding: 0 12px, height: 40px
  placeholder: ink-muted
  focus: border-brand, ring: 2px brand-soft

input-search:
  extends input-default
  bg: canvas-muted, border: transparent
  focus: bg-canvas, border-brand
```

### Badge / Tag
```
badge-default:
  bg: canvas-muted, text: ink-soft
  radius: full, padding: 2px 10px, font: caption-bold

badge-success: bg-success-soft, text: success
badge-warning: bg-warning-soft, text: warning
badge-error: bg-error-soft, text: error
badge-brand: bg-brand-soft, text: brand
```

### Sidebar
```
sidebar:
  bg: sidebar-bg (dark: #0F172A)
  width: 240px (expanded) / 64px (collapsed)
  nav-item: text-sidebar-text, radius-sm, padding: 8px 12px
  nav-item-active: bg-sidebar-item-active, text-sidebar-text-active
  nav-item-hover: bg-sidebar-item-hover
```

### Table / Data Grid
```
table-header:
  bg: canvas-muted, font: caption-bold (12px/600)
  border-bottom: 1px border

table-row:
  bg: canvas, border-bottom: 1px border
  hover: bg-canvas-soft

table-cell:
  padding: 12px 16px, font: body (14px)
```

---

## Do's and Don'ts

### Do
- 品牌色 `#1A56DB` 仅用于 CTA 按钮、激活态、链接
- 页面底色统一用 `canvas-soft` (`#FAFAFA`)
- 卡片用 `radius-lg` + `level-1` 堆叠阴影
- 按钮统一 8px 圆角（非 pill）
- 数据密集表格保持紧凑间距
- 标题统一负字距

### Don't
- 不要直接在卡片上使用 Material 风格单一阴影（用堆叠式）
- 不要在正文使用 brand 蓝色（仅在链接和 CTA 上）
- 不要混合多种圆角值在同一个区域
- 不要在深色侧栏外再使用深色大面积背景
- 中英文不要设不同字号
