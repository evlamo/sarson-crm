# CRM Build Orchestrator — Raider Routing Plan

## Model Routing Logic
- **Opus**: Complex architecture, security-critical code, dynamic query builders, external API integrations, systems requiring deep reasoning
- **Sonnet**: Mechanical scaffolding, CRUD endpoints, UI components following established patterns, config/deployment, template-based work

## Remaining Build Queue (after CRM-3)

| Raider | Task | Model | Reasoning |
|--------|------|-------|-----------|
| EMAIL-1 | Campaigns + SendGrid batch send | **Opus** | External API integration, batch queuing logic, rate limiting, error handling across 30k recipients |
| EMAIL-2 | SendGrid webhook handler | **Sonnet** | Mechanical — parse known webhook payloads, update contact records, well-documented event types |
| EMAIL-3 | Email templates + merge fields | **Sonnet** | CRUD + template rendering — straightforward Jinja2/string interpolation |
| FRONT-1 | React scaffold + auth UI | **Sonnet** | Boilerplate — Vite + React + shadcn/ui setup, login form, JWT token management |
| FRONT-2 | Contacts table (main list view) | **Sonnet** | TanStack Table + react-window virtualization — follows established patterns |
| FRONT-3 | Contact detail page | **Sonnet** | CRUD form + activity timeline — standard UI work |
| FRONT-4 | Pipeline Kanban (deals) | **Sonnet** | Drag-and-drop board — well-documented dnd-kit patterns |
| FRONT-5 | Campaign builder UI | **Opus** | Complex multi-step flow: segment selection → template → preview → send. State management across steps, real-time validation |
| FRONT-6 | Import wizard UI | **Sonnet** | File upload + column mapping + preview — follows import patterns |
| DEPLOY-1 | Docker Compose + nginx + prod config | **Sonnet** | Mechanical — Dockerfiles, compose, nginx reverse proxy, env vars |

## Cost Estimate
- Opus Raiders (3): ~$8-12
- Sonnet Raiders (7): ~$5-10
- **Total estimate: ~$13-22** (vs ~$40-75 all-Opus)

## Orchestrator Rules
1. Wait for current Raider to COMPLETE before firing next
2. Review output quality — if Sonnet delivers subpar code, escalate to Opus for a fix pass
3. All Raiders get the Lead Systems Architect protocol (3-iteration + integrity check)
4. Sequential execution — no parallel Raiders touching same files
5. Each Raider reads BUILD_STATUS.md first for context
6. Announce progress to Ev via Telegram after each extraction
