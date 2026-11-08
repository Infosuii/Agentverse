# Jane Avenue UI (Forecast Confidence Studio design)

The frontend uses the visual system and interaction patterns of the **Forecast Confidence Studio**
prototype, applied to the real Jane Avenue app. Everything the studio mocked (streamed reports,
section feedback) is driven here by the real API: `useAnalysis`, the SSE event stream, and the
contracts in `src/api/schema.d.ts`. No dependencies were added.

## Design system

| Piece | Where | Notes |
|---|---|---|
| Tokens | `src/index.css` | Dark forest palette (oklch) on `:root`, mapped to utilities in `@theme inline` (`bg-background`, `text-muted-foreground`, `border-border`, `bg-primary`, …). Radii are small (`--radius: 0.25rem`). |
| Type | `index.html`, `src/index.css` | IBM Plex Sans (text and display) and IBM Plex Mono (numbers, section indices, labels), loaded with a `<link>`. |
| Print | `src/index.css` (`@media print`) | Switches every token to a light, ink-friendly palette, darkens tinted status text, hides navigation and stacks the analysis layout. |
| Domain colours | `src/lib/theme.ts` | Scenario colours keep the contract hex values. Evidence-class and verification colours keep their hue families, in lighter shades so they stay legible on dark surfaces. `CHART_THEME` drives Recharts grid, axis and tooltip chrome from the CSS variables. |
| Primitives | `src/components/ui/` | `Card`, `Badge`, `Stat`, `Tabs`, `Tooltip`, etc. keep their props, roles and labels. New: `buttonClasses()`, `Eyebrow`, `Wordmark`, inline SVG icons (`icons.tsx`). `Tabs` adds `number`, `status` and a `responsive` orientation (horizontal rail on small screens, vertical contents list from `lg`). |

## Light and dark

The header toggle (`components/ui/ThemeToggle.tsx`) sets `data-theme` on `<html>` and saves the choice in `localStorage`. Dark
is the default. `:root[data-theme="light"]` in `src/index.css` swaps every token, the tinted status shades and the chart
colours; an inline script in `index.html` applies a saved choice before first paint. Colours that depend on the theme must be
CSS variables, never hex values: `src/lib/theme.ts` holds only variables, except the scenario colours fixed by the contract.

## Screens

- **New analysis (`/`)**: a search-first landing page with the wordmark hero, a typing-indicator
  prompt box (`components/search/SearchBar.tsx`) and ruled example prompts. Enter or the arrow
  runs the analysis. The parsed policy, scope gate and options appear below for review. Only a
  specification parsed from the current query is sent as `policy_override`.
- **Analysis shell (`/analyses/:id/*`)**: a publication-style header plus a sticky contents rail
  with numbered views. While the pipeline runs, each view shows studio generation feedback
  (Waiting, Generating, Complete), derived from SSE stages in `features/analysis/liveStatus.ts`.
  The rail also shows the six-stage pipeline list and a polite live status line. When a run
  finishes while you watch, a dismissible "Your policy assessment is ready" notice appears.
- **Report tab**: an editorial article with numbered sections (01 Executive summary with key
  figures, then the generated sections, a scenario comparison and a numbered source directory).
  Its contents list is portalled into the shell rail and highlights the section being read.
  `[S#]` citations link to the source directory, and `[E#]` citations link to the evidence item.
- **Other views** use the same tokens and studio typography: numbered section headings, ruled
  rows, mono figures, dark cards and dark chart chrome.

## Deep links

- `/analyses/:id/research?evidence=E3` clears the evidence filters, then scrolls to and
  highlights E3. Assumption, verification and report links use this.
- `/analyses/:id/scenarios?metric=gdp_level_pct` preselects a metric. Verification findings use
  this.
- `/analyses/:id/assumptions?metric=…&year=…` behaves as before (calculation inspector).
