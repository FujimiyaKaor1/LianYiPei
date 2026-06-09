---
name: LianYiPei Frontend Design System
version: 2.0
authority: ../DESIGN.md
---

# Frontend Design Notes

The root `../DESIGN.md` is the authoritative project design system. This file records frontend implementation rules for the React/Vite app.

## Direction

Build a precision operations console for supply-chain work:

- Graphite sidebar, white operational panels, cobalt primary commands.
- Emerald means healthy/trusted/verified; amber means risk or attention; red means critical.
- Use 6-8px radius for cards, buttons, inputs, lists, badges, and modals unless a third-party component requires otherwise.
- Prefer compact scan-friendly panels, dividers, tables, list rows, progress bars, and metric cards.
- Avoid decorative gradients, oversized hero sections, nested cards, large rounded bubbles, emoji labels, and marketing page composition.

## Tailwind Tokens

Use semantic tokens from `src/index.css`:

- Surfaces: `bg-canvas`, `bg-surface`, `bg-surface-subtle`, `panel`, `card`, `card-hover`
- Text: `text-ink`, `text-ink-soft`, `text-ink-muted`, `text-ink-faint`
- Borders: `border-border`, `border-border-strong`
- Brand: `bg-brand`, `text-brand`, `bg-brand-soft`
- State: `bg-trust-soft text-trust`, `bg-risk-soft text-risk`, `bg-critical-soft text-critical`
- Controls: `btn-primary`, `btn-secondary`, `btn-ghost`, `input`, `input-search`

## Layout Rules

- Use the shared `Layout`, `GovLayout`, and `AdminLayout` shells.
- Keep high-frequency pages full-width with `max-w-[1440px]` when they need readable structure.
- Page padding should be `p-4 md:p-6`.
- Scrollable panels should use `scrollbar-thin`.
- Use `metric-number` for KPI values and scores.

## Component Rules

- Buttons should include lucide icons only when the action benefits from recognition.
- Icon-only buttons need `title` or `aria-label`.
- Entity names need `min-w-0` and `truncate`.
- Status badges should be short and semantic.
- Long explanatory text belongs in body copy, not inside pill labels.

## Verification

After meaningful UI edits:

1. Run `npm run lint -- --pretty false`.
2. Start the Vite dev server.
3. Inspect desktop and mobile-ish widths in the browser.
4. Check for blank pages, horizontal overflow, overlapping text, and unreadable low-contrast states.
