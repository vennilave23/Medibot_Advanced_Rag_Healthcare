# MediBot — Component 6: Frontend

A chat interface for MediBot that demonstrates the full RBAC-enforced RAG
system built in Components 1-5. Next.js 16 (App Router), TypeScript, Tailwind
v4. See the top-level `../README.md` for the overall project and the other
five components.

## What it does

- **Login** (`/`) — sign in with username/password, or one-click "demo
  account" buttons for the assignment's 5 roles. Calls `POST /login`.
- **Chat** (`/chat`) — the main interface:
  - Sidebar shows the signed-in username, a role badge, and the collections
    that role can access (`GET /collections/{role}`).
  - Each message is sent via `POST /chat`; the response's `answer`,
    `sources` (document + section title + collection), and `retrieval_type`
    ("Hybrid RAG" / "SQL RAG" badge) are all rendered per the assignment's
    requirements.
  - A role without analytics access (e.g. `nurse`) asking an analytical
    question gets the backend's refusal message rendered like any other
    reply — no special-casing needed on the frontend, since RBAC is enforced
    server-side (Components 2-5), not here.

Session (`{username, role, token}`) is kept in React context + `localStorage`
so a refresh doesn't force re-login; it's per-browser-tab client state, not a
security boundary (see the backend's documented simplification in
`../README.md`).

## Setup

Requires the Component 5 backend running first (it's the only data source
this app has — there's no server-side logic here beyond what Next.js needs
to serve the pages).

```bash
# 1. Backend (from the medibot/ folder, separate terminal)
cd ../medibot
fastapi dev api.py --no-reload
```

**Why `--no-reload`:** the backend holds Qdrant's local embedded store open
via `QdrantClient(path=...)`, which only permits **one process** to access
that storage folder at a time. `fastapi dev`'s default `--reload` behavior
can momentarily start a second worker process during reload, which then
fails to acquire the Qdrant lock (`RuntimeError: Storage folder ... is
already accessed by another instance`) — reproduced during this build.
`--no-reload` avoids the double-process window entirely. If you're actively
editing backend code, restart the server manually after each change instead.

```bash
# 2. Frontend (this folder)
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL, defaults to the line above
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Demo credentials

| Username | Password | Role |
|---|---|---|
| `dr.mehta` | `doctor` | doctor |
| `nurse.priya` | `nurse` | nurse |
| `billing.ravi` | `billing_executive` | billing_executive |
| `tech.anand` | `technician` | technician |
| `admin.sys` | `admin` | admin |

The login page has one-click buttons for all five — no need to type these in
for a demo.

## Verified working (real HTTP, both servers running)

- Login page renders and issues `POST /login` with CORS headers present
  (backend's `CORSMiddleware` allows `localhost:3000`).
- `GET /collections/nurse` → `{"collections": ["general", "nursing"]}`,
  rendered in the sidebar.
- Document question as `nurse` → `hybrid_rag` badge, sources from
  `nursing` only.
- Analytical question as `billing_executive` → `sql_rag` badge, correct
  answer ("17 pending claims").
- Same analytical question as `nurse` → refused, rendered as a normal
  assistant message (no crash, no special UI path needed).

## Project structure

```
src/
├── app/
│   ├── layout.tsx       # wraps the app in SessionProvider
│   ├── page.tsx         # login page
│   └── chat/page.tsx    # main chat interface
├── components/
│   ├── ChatMessage.tsx  # message bubble: answer, sources, retrieval-type badge
│   └── Sidebar.tsx      # role badge, accessible collections, logout
├── contexts/
│   └── SessionContext.tsx  # login state, persisted to localStorage
└── lib/
    └── api.ts           # typed fetch wrappers over the Component 5 API
```
