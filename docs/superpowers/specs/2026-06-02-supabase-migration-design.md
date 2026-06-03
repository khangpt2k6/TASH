# TASH Supabase Migration - Design Spec

Date: 2026-06-02
Status: Approved
Supabase project: `tash` (ref `iotbekdizucalvjqoebr`, region us-east-1)

## Goal

Move TASH from local SQLite + a global `settings.json` file to a scalable, multi-user
cloud architecture on Supabase (Postgres + Auth), so that each user has their own
private chat history, sessions persist across devices, and the system can scale
toward an OpenAI-style multi-tenant chat product.

## Architecture

```
React frontend ──> Supabase Auth (login/signup, JWT held in browser)
       │
       ├──> Supabase JS client ──> Postgres (RLS-protected reads: conversations, messages)
       │
       └──> FastAPI /api/chat ──> verifies JWT ──> streams LLM ──> writes messages
                  (server uses service_role key, bypasses RLS for writes)
```

- **Auth**: Supabase Auth, email/password + Google OAuth. Frontend holds the session.
- **Reads** (sidebar conversation list, message history): direct from Supabase with
  RLS enforcing per-user isolation. Offloads read traffic from the Python server.
- **Writes during chat**: go through FastAPI, where LLM streaming happens. The backend
  authenticates the user via JWT and writes using the service_role key.
- **Settings**: per-user `user_settings` table replaces the global JSON file.

## Database Schema (`public`, all RLS-enabled)

### profiles
Created via trigger on `auth.users` insert.
- `id` uuid PK -> `auth.users(id)` on delete cascade
- `email` text
- `display_name` text
- `created_at` timestamptz default now()

### conversations
- `id` uuid PK default gen_random_uuid()
- `user_id` uuid not null -> `auth.users(id)` on delete cascade
- `title` text not null default 'New Chat'
- `model` text not null default 'mock'
- `created_at` timestamptz default now()
- `updated_at` timestamptz default now()
- Index: `(user_id, updated_at desc)`

### messages
- `id` uuid PK default gen_random_uuid()
- `conversation_id` uuid not null -> `conversations(id)` on delete cascade
- `user_id` uuid not null -> `auth.users(id)` (denormalized for fast RLS)
- `role` text not null check (role in ('user','assistant','system'))
- `content` text not null
- `tool_steps` jsonb
- `token_count` int
- `created_at` timestamptz default now()
- Index: `(conversation_id, created_at asc)`

### user_settings
- `user_id` uuid PK -> `auth.users(id)` on delete cascade
- `provider` text default 'mock'
- `model` text default 'mock'
- `base_url` text
- `updated_at` timestamptz default now()
- NOTE: no plaintext API keys stored here.

### usage_events (append-only, for usage tracking / quotas / billing)
- `id` uuid PK default gen_random_uuid()
- `user_id` uuid not null -> `auth.users(id)` on delete cascade
- `conversation_id` uuid -> `conversations(id)` on delete set null
- `model` text
- `prompt_tokens` int
- `completion_tokens` int
- `created_at` timestamptz default now()

### RLS pattern
All tables: policies `to authenticated using ((select auth.uid()) = user_id)`,
with both `USING` and `WITH CHECK` on writes. `profiles` keys on `id`. The backend's
`service_role` key bypasses RLS for trusted server-side writes.

## Security

- LLM API keys are NEVER stored in plaintext in the DB. The server's own provider key
  lives in the FastAPI `.env`. A user-supplied key is sent per-request over HTTPS and
  used transiently, never persisted.
- Frontend receives only the Supabase publishable/anon key (RLS-protected).
- The service_role key lives only in the FastAPI server env, never in the browser.

## Backend changes

- Replace `aiosqlite` with `supabase-py` (service_role key).
- Add `auth.py`: FastAPI dependency that verifies the Supabase JWT and extracts `user_id`.
- All conversation/message endpoints require auth and scope queries to `user_id`.

## Frontend changes

- Add `@supabase/supabase-js`, `supabaseClient.ts`, an `AuthContext`, and a login/signup screen.
- `useConversations` / `useChat` read directly from Supabase (RLS-enforced) and attach the
  JWT when calling `/api/chat`.

## Data migration

Existing `tash.db` has no users; not migrated. New chats start fresh in Supabase.

## Out of scope (YAGNI for now)

Folders/projects, message editing/regeneration, soft-delete, billing UI. The
`usage_events` table is created so usage data accrues, but no billing logic is built yet.
