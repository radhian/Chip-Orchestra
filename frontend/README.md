# ChipFlowAI Frontend

A GitHub-ready React + TypeScript + Vite frontend for the **ChipFlowAI digital IC design platform** mockup.

This repo now includes:

- **Client-side routing** for each main product screen
- A typed **API service layer** aligned to the backend architecture doc
- **Mock/dev fallback data** so the frontend still runs without a live backend
- A clean local developer setup with standard `npm install && npm run dev`

---

## Features

### Routed screens

The app exposes the following client-side routes:

- `/` → redirects to `/overview`
- `/overview` → **Overview Console**
- `/tasks/new` → **Create Design Task**
- `/tasks/:id` → **Task Detail & Runbook**
- `/tasks/:id/rtl` → **RTL Workspace**
- `/tasks/:id/signoff` → **Signoff & Delivery**

### Backend API integration

The frontend is wired to a typed task service layer in `src/api/tasks.ts`.

Configured backend base URL:

- `VITE_API_BASE_URL`

Supported API surface implemented in the frontend service layer:

- `GET /api/tasks`
- `POST /api/tasks`
- `GET /api/tasks/:id`
- `GET /api/tasks/:id/stages`
- `POST /api/tasks/:id/retry`
- `GET /api/tasks/:id/attempts/latest/events`
- `GET /api/tasks/:id/attempts/latest/artifacts`
- `GET /api/tasks/:id/attempts/latest/diagnosis`
- `GET /api/tasks/:id/workspace/files`
- `GET /api/tasks/:id/workspace/file`
- `POST /api/tasks/:id/workspace/propose-patch`
- `GET /api/tasks/:id/signoff/status`
- `POST /api/tasks/:id/approvals/:stage`
- `POST /api/tasks/:id/waivers`
- `POST /api/tasks/:id/export-bundle`

### Mock fallback

If the backend is unavailable, the app can fall back to a local mock data layer.

This is controlled by:

- `VITE_USE_MOCKS=true` → allow fallback to mock/dev data
- `VITE_USE_MOCKS=false` → fail fast if the backend is unreachable

Mock data lives in:

- `src/mocks/chipflow.ts`

---

## Tech stack

- **Framework**: React 18
- **Language**: TypeScript
- **Bundler / dev server**: Vite 6
- **Routing**: React Router
- **Styling**: Tailwind CSS
- **UI primitives**: shadcn/ui + Radix UI
- **Icons**: lucide-react
- **Networking**: native `fetch` with typed service wrappers

---

## Prerequisites

- **Node.js** `>= 18`
- **npm** `>= 9`

This repository is npm-friendly. You can run it with standard npm commands.

---

## Local setup

### 1. Clone the repository

```bash
git clone <your-repo-url> chipflowai-frontend
cd chipflowai-frontend
```

### 2. Install dependencies

```bash
npm install
```

### 3. Configure environment variables

Copy the example env file:

```bash
cp .env.example .env
```

Default example values:

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_USE_MOCKS=true
```

Notes:

- Set `VITE_API_BASE_URL` to your backend host.
- Keep `VITE_USE_MOCKS=true` during frontend-only development.
- Set `VITE_USE_MOCKS=false` if you want the UI to require a real backend.

### 4. Start the dev server

```bash
npm run dev
```

Open the URL printed by Vite, usually:

- `http://localhost:5173`

---

## Available scripts

```bash
# start dev server
npm run dev

# type-check + production build
npm run build

# type-check only
npm run typecheck

# lint the repo
npm run lint

# preview production build locally
npm run preview
```

---

## Production build

Build the static app:

```bash
npm run build
```

Output will be generated in:

- `dist/`

Preview the production build locally:

```bash
npm run preview
```

---

## Project structure

```text
chipflowai-frontend/
├─ public/                      # Static public assets
├─ src/
│  ├─ api/
│  │  └─ tasks.ts               # Typed API service layer for task endpoints
│  ├─ components/
│  │  ├─ app/
│  │  │  ├─ app-shell.tsx       # Shared shell / chrome layout
│  │  │  └─ shared.tsx          # Shared app-level UI helpers
│  │  └─ ui/                    # shadcn/ui primitives
│  ├─ hooks/                    # Shared hooks
│  ├─ lib/                      # Utilities
│  ├─ mocks/
│  │  └─ chipflow.ts            # Local mock snapshot + fallback state
│  ├─ pages/
│  │  ├─ OverviewPage.tsx       # /overview
│  │  ├─ CreateTaskPage.tsx     # /tasks/new
│  │  └─ TaskDetailPage.tsx     # /tasks/:id, /rtl, /signoff
│  ├─ types/
│  │  └─ chipflow.ts            # Shared frontend domain types
│  ├─ App.tsx                   # Route definitions + sidebar nav
│  ├─ App.css                   # App-level styles
│  ├─ index.css                 # Tailwind base/styles
│  ├─ main.tsx                  # BrowserRouter entry point
│  └─ vite-env.d.ts             # Vite env typing
├─ .env.example                 # Example API env vars
├─ .gitignore                   # Git ignore rules
├─ package.json                 # Scripts and dependencies
├─ tailwind.config.js           # Tailwind config
├─ postcss.config.js            # PostCSS config
├─ vite.config.ts               # Vite config
└─ README.md                    # Repo guide
```

---

## Routing behavior

The task detail area uses route-based tabs instead of in-memory tab state:

- `/tasks/:id` → Runbook
- `/tasks/:id/rtl` → RTL Workspace
- `/tasks/:id/signoff` → Signoff & Delivery

This makes screens directly linkable and easier to integrate into a real app shell.

---

## API integration notes

The frontend uses `fetch` in `src/api/tasks.ts` and follows this strategy:

1. If `VITE_API_BASE_URL` is available, it tries the live backend.
2. If the request fails and `VITE_USE_MOCKS !== 'false'`, it falls back to mock data.
3. If mocks are disabled, the request error is surfaced in the UI.

This is useful for staged rollout:

- **Frontend-only work** → run with mocks enabled
- **Integration testing** → point `VITE_API_BASE_URL` at a real backend
- **Strict backend validation** → set `VITE_USE_MOCKS=false`

---

## How to extend

Common next steps:

- Replace the mock response shapes with exact backend payload contracts once the API is finalized.
- Add React Query or SWR for request caching and mutation handling.
- Split the larger page components into smaller feature modules.
- Add auth/session handling once the backend is exposed behind a real identity layer.

---

## License

Add your preferred license for GitHub distribution, for example MIT.
