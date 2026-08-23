# Design: Emergent.sh Clone — UI/UX & Frontend Design System

> Source of truth for the frontend. Every screen, component, token, state, and interaction needed to match emergent.sh quality. Implementation in `src/ui/` (PySide6 desktop shell) and the generated preview apps (React/Next.js). All inference routed exclusively through NVIDIA NIM.

---

## 1. Design Principles

1. **Conversational first** — the chat surface is the product. Everything else serves the conversation.
2. **Always alive** — agents stream progress in real time; no silent waiting states.
3. **Developer-grade aesthetic** — dark, dense, high-contrast, monospace accents. Feels like a pro IDE, not a no-code toy.
4. **Honesty** — show real code diffs, real agent steps, real errors. No fake progress bars.
5. **NVIDIA identity** — brand accent is NVIDIA green (#76B900) on near-black; signals the NIM-only inference path.

---

## 2. Color Tokens (CSS variables / Qt stylesheet)

### Dark theme (default)
| Token | Value | Usage |
|---|---|---|
| `--bg-base` | `#0A0A0B` | App background |
| `--bg-surface` | `#131316` | Panels, cards, sidebar |
| `--bg-surface-2` | `#1B1B20` | Hover, inputs |
| `--bg-elevated` | `#222228` | Modals, popovers |
| `--border-subtle` | `#26262C` | Dividers, default borders |
| `--border-strong` | `#3A3A44` | Focused inputs |
| `--text-primary` | `#F5F5F7` | Headings, primary text |
| `--text-secondary` | `#A1A1AA` | Body, labels |
| `--text-muted` | `#6B6B73` | Placeholders, timestamps |
| `--accent` | `#76B900` | NVIDIA green — primary actions, active agent |
| `--accent-hover` | `#8FD400` | Hover on primary |
| `--accent-muted` | `rgba(118,185,0,0.12)` | Active agent glow, selection |
| `--info` | `#3B82F6` | Planning agent, links |
| `--warning` | `#F59E0B` | Tester agent, in-progress |
| `--danger` | `#EF4444` | Errors, failed tests |
| `--success` | `#22C55E` | Deployed, tests pass |
| `--code-bg` | `#0F0F12` | Code blocks |

### Light theme (toggle in settings)
| Token | Value |
|---|---|
| `--bg-base` | `#FAFAFA` |
| `--bg-surface` | `#FFFFFF` |
| `--bg-surface-2` | `#F4F4F5` |
| `--bg-elevated` | `#FFFFFF` |
| `--border-subtle` | `#E4E4E7` |
| `--border-strong` | `#A1A1AA` |
| `--text-primary` | `#18181B` |
| `--text-secondary` | `#52525B` |
| `--text-muted` | `#A1A1AA` |
| `--accent` | `#76B900` |
| `--code-bg` | `#F4F4F5` |

Theme is applied via a single `data-theme` attribute on the root widget; tokens cascade. Generated preview apps inherit a parallel token set so previews match the platform chrome.

---

## 3. Typography

- **UI sans:** `Inter` — 400/500/600/700. Headings 600, body 400, labels 500.
- **Mono:** `JetBrains Mono` — agent names, code, file paths, diffs. 400/500.
- **Display (landing):** `Inter` 700, tight tracking (-0.02em), sizes 48–72px.

Scale (8px rhythm): `xs 12 / sm 13 / base 14 / md 16 / lg 20 / xl 24 / 2xl 32 / 3xl 48 / 4xl 72`.
Line-height: 1.5 body, 1.2 headings, 1.4 mono.

---

## 4. Spacing, Radius, Elevation

- **Spacing:** `4 8 12 16 20 24 32 40 48 64` (px).
- **Radius:** `sm 6 / md 10 / lg 14 / pill 9999`. Inputs `md`, cards `lg`, buttons `md`, avatars `pill`.
- **Elevation (dark):** `e1 0 1px 0 rgba(255,255,255,0.04) inset; e2 0 4px 12px rgba(0,0,0,0.4); e3 0 12px 32px rgba(0,0,0,0.5)`.
- **Motion:** `fast 120ms ease-out` (hover), `base 200ms ease-out` (panels), `slow 320ms cubic-bezier(0.22,1,0.36,1)` (view transitions). Agent activity uses a 1.4s ease-in-out pulse on the active agent ring.

---

## 5. Information Architecture

```
Landing (unauthenticated)
└── Auth (Sign in / Continue with Google|Email|Phone / SSO)
    └── App Shell (authenticated)
        ├── Sidebar (left, 260px, collapsible to 64px)
        │   ├── New project
        │   ├── Recents (project list, status dots)
        │   ├── Integrations (GitHub, Supabase, Stripe)
        │   ├── Credits (balance / usage)
        │   └── Settings (theme, NIM key, model selector)
        ├── Workspace (center, flex)
        │   ├── Top bar (project name, branch, deploy URL, share)
        │   ├── Tab strip [Chat | Preview | Code | Logs]
        │   ├── Chat surface (default)
        │   ├── Preview pane (iframe + device toggle)
        │   ├── Code pane (file tree + Monaco-style viewer)
        │   └── Logs pane (agent run log, raw NIM calls)
        └── Agent Activity Rail (right, 320px, collapsible)
            ├── Active agent card (animated)
            ├── Step timeline (plan→code→test→deploy)
            └── Credit burn meter
```

---

## 6. Screen Specifications

### 6.1 Landing Page
- **Hero:** Full-bleed dark. Headline "Build Full-Stack Web & mobile apps in minutes" (display 4xl). Subhead one line. Primary CTA "Start building" (accent pill). Secondary "Sign in".
- **Auth modal:** Centered card, `e3` elevation. Three buttons: Continue with Google / Email / Phone. SSO link. Terms copy. Matches emergent.sh's modal exactly.
- **Pricing:** Four tiers (Free / Standard $17 / Pro $167 / Enterprise Custom) in a responsive grid; annual toggle. Feature lists with check icons.
- **FAQ:** Accordion, 6 items, single-open.
- **Footer:** 4 columns (Product / Solutions / Resources / Company) + copyright.
- **No lorem ipsum.** All copy pulled from the real site (captured in working memory).

### 6.2 Project Dashboard (home after auth)
- Greeting + "What do you want to build?" prompt box (large, accent border on focus).
- Recent projects grid: cards show name, stack badges, status pill (Building / Deployed / Error), last edit, thumbnail of preview.
- Empty state: single centered prompt with example chips ("SaaS task manager", "Portfolio site", "Internal CRM").

### 6.3 Conversational Workspace (core screen)
Three-column layout: Sidebar | Chat/Preview/Code tabs | Agent Rail.

**Chat tab**
- Message list: user bubbles (right, surface-2) and agent messages (left, surface, with agent avatar + name + role color dot).
- Agent messages can contain: prose, **code diff blocks** (mono, syntax highlighted, file path header, copy button), **file tree chips**, and **plan cards** (checklist of steps with status).
- Streaming: tokens append live; a blinking caret while `streaming=true`.
- Composer: multi-line input, `Enter` sends / `Shift+Enter` newline, attachment (image/spec) button, model selector dropdown (NIM models only), send button (accent, disabled while empty or while a build is running).

**Preview tab**
- Device toggle: Desktop / Tablet / Mobile (changes iframe size).
- Address bar showing the live preview URL; refresh; open-in-new-tab.
- iframe renders the running generated app; updates push via WebSocket (reload on `preview:updated` event).
- Build overlay: when agents are working, a translucent scrim with the active step + spinner; preview dims but stays visible.

**Code tab**
- Left: file tree (generated project). Right: code viewer with line numbers, syntax highlight, diff highlight for changed files.
- "Export" button → zip download; "Push to GitHub" button (shows sync status).

**Logs tab**
- Raw agent run log: timestamped lines, agent name, action, NIM model used, token count. Collapsible JSON for each NIM call. This is the audit trail proving NIM-exclusivity.

### 6.4 Agent Activity Rail (right)
- **Active agent card:** avatar (role color ring, pulsing when active), agent name, current task one-liner, elapsed time.
- **Step timeline:** vertical timeline with 6 nodes — Orchestrator → Frontend → Backend → Database → Tester → Deployer. Each node: icon, label, status (pending/active/done/error), expandable to show sub-steps and the NIM model used.
- **Credit meter:** linear bar of credits consumed this build vs. budget; numeric `used / total`.
- Collapsible to a 48px icon rail.

### 6.5 Settings
- **Profile:** name, email, avatar.
- **NVIDIA NIM:** API key (masked, reveal toggle), base URL (default `https://integrate.api.nvidia.com/v1`), default model, test-connection button (calls `/v1/models`, shows green check or red error).
- **Integrations:** GitHub (connect → OAuth), Supabase, Stripe (connect flows).
- **Appearance:** theme toggle, density (comfortable/compact).
- **Credits & billing:** current plan, usage, buy credits.

---

## 7. Component Inventory (`src/ui/`)

| Component | File | Responsibility |
|---|---|---|
| `AppShell` | `app_shell.py` | Root window, theme, 3-column layout, routing |
| `Sidebar` | `sidebar.py` | Nav, recents, integrations, credits, settings entry |
| `TopBar` | `top_bar.py` | Project name, branch, deploy URL, share, run |
| `ChatArea` | `chat_area.py` | Message list, streaming, composer |
| `MessageBubble` | `chat_area.py` | User/agent bubble, code diff, plan card |
| `CodeDiffBlock` | `code_diff.py` | Syntax-highlighted diff with file header |
| `PlanCard` | `plan_card.py` | Step checklist with live status |
| `PreviewPane` | `preview/preview_pane.py` | iframe host, device toggle, address bar |
| `CodePane` | `code/code_pane.py` | File tree + code viewer |
| `LogsPane` | `logs/logs_pane.py` | Agent run log, NIM call audit |
| `AgentRail` | `agent_rail.py` | Active agent + step timeline + credit meter |
| `AgentCard` | `agent_card.py` | Single agent avatar/status |
| `StepTimeline` | `step_timeline.py` | 6-node vertical timeline |
| `CreditMeter` | `credit_meter.py` | Linear credit usage bar |
| `ProjectDashboard` | `project/project_dashboard.py` | Home grid + prompt box |
| `ProjectCard` | `project/project_card.py` | Project tile |
| `ProjectWizard` | `project_wizard.py` | New-project modal (prompt → stack pick → start) |
| `SettingsDialog` | `settings/settings_dialog.py` | Tabbed settings |
| `NimSettingsPanel` | `settings/nim_settings.py` | NIM key/URL/model + test connection |
| `ProfileDialog` | `profile_dialog.py` | User profile |
| `ExecutionDrawer` | `execution_drawer.py` | Slide-up build console |
| `LandingWindow` | `landing/landing_window.py` | Unauthenticated landing + auth modal |
| `AuthModal` | `landing/auth_modal.py` | Sign-in card |

---

## 8. Agent Visual Language

Each agent has a fixed role color and glyph used consistently in the rail, chat avatars, and logs:

| Agent | Color | Glyph | NIM role |
|---|---|---|---|
| Orchestrator | `--info` #3B82F6 | 🧭 | Plans + task breakdown |
| Frontend | `#EC4899` | 🎨 | React/Next UI |
| Backend | `#8B5CF6` | ⚙️ | API/auth/logic |
| Database | `#14B8A6` | 🗄️ | Schema/migrations |
| Tester | `--warning` #F59E0B | 🧪 | Tests + self-heal |
| Deployer | `--accent` #76B900 | 🚀 | Preview + artifact |

Active agent: ring pulses (1.4s), card lifts to `e2`, accent-muted background. Done: solid check. Error: red ring + retry affordance.

---

## 9. Interaction States

- **Buttons:** default (surface-2 bg, text-primary), hover (border-strong), active (inset), disabled (opacity 0.4, no cursor). Primary = accent bg + near-black text.
- **Inputs:** default (surface-2, border-subtle), focus (border-strong + accent-muted glow), error (danger border + helper text), disabled (muted).
- **Streaming message:** caret blink; composer disabled; send button becomes "Stop" (danger outline) to cancel the NIM stream.
- **Build running:** preview scrim + rail active; top bar shows pulsing "Building…" with elapsed time; sidebar project dot = warning.
- **Build done:** rail steps all green; preview reloads; top bar shows deploy URL + "Open"; sidebar dot = success.
- **Build error:** failed step red; chat shows error message with "Retry step" button; logs pane surfaces the NIM error payload.

---

## 10. Accessibility

- WCAG 2.1 AA: 4.5:1 text contrast (verified against tokens above).
- All actions keyboard reachable; visible focus ring (2px accent).
- Agent status conveyed by color **and** icon/label (not color alone).
- `aria-live="polite"` on chat list and agent rail for screen readers.
- Reduced-motion: disable pulse/scrim animations.
- Min target size 40×40px.

---

## 11. Responsive Behavior

Desktop ≥1280: full 3-column. 1024–1279: agent rail collapses to icon rail. 768–1023: sidebar overlays, preview stacks under chat. <768: single column, tabs become a bottom nav, preview full-screen on tap. (Desktop shell is primary; responsive rules apply to generated preview apps and any web view of the platform.)

---

## 12. Generated Preview App Style Guide

Preview apps the agents generate should follow a parallel system so output looks finished:
- Default stack: Next.js (App Router) + Tailwind + shadcn/ui primitives + FastAPI backend + Postgres/SQLite.
- Tokens mirror the platform (same accent, neutral ramp) but the user's app owns its own theme.
- Every generated app ships with: a real layout, working auth (email + OAuth), a database-backed CRUD surface, and a deployable `Dockerfile` + `docker-compose.yml`.
- No placeholder text — agents must fill real copy; the Tester agent fails builds containing `lorem`, `TODO`, or `coming soon`.

---

## 13. Design-to-Implementation Mapping

- T004 (frontend UI): components in §7 are the build list. Order: `AppShell` → `Sidebar` → `ProjectDashboard` → `ChatArea` → `PreviewPane` → `AgentRail` → `CodePane`/`LogsPane` → `Settings` → `Landing`.
- T006 (prompt→preview loop): the Chat tab + Preview tab + Agent Rail are the visible surface of the streaming pipeline; the Logs tab is the NIM-exclusivity audit.
- All agent avatars/labels in the UI pull from the same agent registry the orchestrator uses, so UI and backend never drift.

---

## 14. Open Design Questions (resolved)

- **Q: Web or desktop shell?** A: PySide6 desktop shell per existing `src/ui/` scaffold; web-grade styling via Qt stylesheets mirroring the tokens above. Generated apps are web.
- **Q: How to prove NIM-exclusivity in UI?** A: Logs tab shows every inference call's NIM model + endpoint; no other provider appears anywhere.
- **Q: Credits?** A: Simple meter in the rail + settings; consumed per NIM call, tracked by the orchestrator.
