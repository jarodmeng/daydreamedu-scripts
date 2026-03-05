# AI Study Buddy — Technology Stack

> Status: **Exploratory** — options and recommendations, not final decisions.
>
> Sources: ChatGPT 5.2 Thinking conversation (3 Mar 2026), supplemented with independent research (Opus 4.6 Max, 4 Mar 2026).

---

## Recommended Stack (from ChatGPT)

The conversation explored three backend language options and converged on:

- **Frontend:** React + TypeScript (PWA)
- **Backend:** TypeScript (Next.js API routes or Fastify/NestJS)
- **Ingestion worker:** Python (PDF rendering, OCR, layout segmentation, embedding generation)
- **Database:** Postgres + pgvector
- **Agent runtime:** Google ADK (Agent Development Kit)
- **Storage:** Google Drive (raw PDFs) + optional GCS for derived artifacts

---

## Language Decision: TypeScript vs Go vs Python

The conversation explored three options for the backend. Here is a consolidated comparison:

### TypeScript (recommended by ChatGPT)

**Strengths:**
- One language across frontend + backend → shared types, faster iteration
- End-to-end schemas via Zod: validate API inputs/outputs, auto-type frontend calls, prevent drift
- Excellent ecosystem for Google Drive API, OAuth, webhooks, queues, PWA
- AI-assisted dev produces more correct code when types constrain the space
- Safer refactors as the codebase grows over multiple years

**Weaknesses:**
- PDF/image processing in Node is less robust than Python
- Requires maintaining a separate Python worker for ingestion regardless

### Go

**Strengths:**
- Reliability + performance: great for always-on API services
- Concurrency model suits job orchestration (dispatching ingestion, rate-limiting model calls)
- Static binaries, low memory, easy Cloud Run/K8s deploy
- Strong typing for structured objects

**Weaknesses:**
- No type sharing with the React frontend — need to maintain separate type systems (Go structs + TS types) or generate from a shared schema (e.g., protobuf, OpenAPI)
- Still needs Python for ingestion
- Slower to ship end-to-end product features than full-stack TS

### Python (full backend)

**Strengths:**
- Single language for backend + ingestion worker
- Best ecosystem for ML/vision/PDF work
- FastAPI is mature and well-documented

**Weaknesses:**
- Frontend is still TypeScript, so you're always two-language
- Type safety is weaker than TS or Go for large codebases
- Less natural fit for the UI-heavy, state-heavy product layer

### Summary

| Factor | TypeScript | Go | Python |
|--------|-----------|-----|--------|
| Frontend integration | Excellent (shared types) | Poor (separate type systems) | Moderate (separate) |
| Backend API development | Good | Excellent | Good |
| PDF/image processing | Weak | Weak | Excellent |
| Type safety | Strong (Zod, tsc) | Strong (static) | Moderate (mypy, optional) |
| Ecosystem for web app | Excellent | Good | Good |
| Operational simplicity | Good | Excellent (static binaries) | Good |
| Speed to MVP | Fastest (full-stack) | Moderate | Moderate |

---

## Google ADK (Agent Development Kit)

The conversation identified ADK as the **agent runtime/orchestration layer** for the AI agents. ADK provides: agent definition (LlmAgent), tool-calling, session + state management, memory services, multi-agent composition, event logging, and plugins.

### How the architecture maps to ADK concepts

| Architecture concept | ADK concept |
|---------------------|-------------|
| Tutor agent | `LlmAgent` |
| Backend functions (retrieve, log, plan) | ADK **Tools** (with `ToolContext`) |
| In-session tutoring state | ADK **Session + State** (with `{key}` templating) |
| Long-term student knowledge | ADK **MemoryService** (or tool wrapping your DB) |
| Question crops / images | ADK **Artifacts** (versioned binary data) |
| Tutor + Planner + Parent Coach | ADK **Multi-Agent System** (hierarchical composition) |
| Event logs | ADK **Events** (immutable records) |
| Answer-gating, cost budgets | ADK **Plugins** (cross-cutting concerns) |

### TypeScript ADK vs Go ADK

| Factor | TypeScript ADK | Go ADK |
|--------|---------------|--------|
| Version (as of Mar 2026) | v0.4.0 (Feb 25, 2026) | v0.5.0 (Feb 20, 2026) |
| Runtime | Node.js 24.13+ | Go 1.24.4+ |
| Dev UI | `npx adk web` (localhost:8000) | `go run agent.go web api webui` (localhost:8080) |
| Tool schemas | Zod (aligns with TS data contracts) | Go structs + interfaces |
| A2A support | Not documented yet | Experimental, first-class docs |
| Node req | npm 11.8+ | N/A |

---

> [!NOTE]
> **Opus 4.6 Max analysis** — independent assessment of ADK maturity and alternatives.

### ADK TypeScript maturity assessment

Based on independent research (not from the ChatGPT conversation):

**ADK TypeScript (adk-js) is still pre-1.0 and has notable production readiness gaps:**

1. **Missing persistent session services.** Unlike the Python SDK, the TypeScript SDK lacks built-in persistent session storage. The framework relies on in-memory storage by default, which cannot survive server restarts or container scaling. Production use requires a custom PostgreSQL-backed session service. ([Coder Legion, 2026](https://coderlegion.com/11368/patching-the-gaps-a-production-ready-guide-to-googles-adk-with-typescript); [Baly's Notes, 2026](https://www.balysnotes.com/a-production-ready-guide-to-google-adk-with-typescript))

2. **ESM/CommonJS conflicts.** The published npm package has a dependency issue where the CommonJS build incorrectly imports the ESM-only `lodash-es` package, breaking standard builds. ([Baly's Notes, 2026](https://www.balysnotes.com/a-production-ready-guide-to-google-adk-with-typescript))

3. **Documentation is thinner than Python's.** Developers are often directed to "ADK Devtools" which are suitable only for local prototyping, not hardened production deployments.

4. **845 GitHub stars, 30 contributors** — active but still a young project.

**Risk assessment:** Adopting ADK TypeScript today means committing to building custom infrastructure (persistent sessions, memory services) that the framework doesn't yet provide. This is feasible but adds scope. The framework could mature significantly by the time the MVP ships, but it's a bet.

### Alternative agent frameworks to consider

| Framework | Language | Maturity | Notes |
|-----------|----------|----------|-------|
| **Google ADK** (TS/Go) | TS, Go, Python | Pre-1.0 | Google-backed, Vertex AI-native, multi-agent support |
| **LangGraph** | Python, JS/TS | Stable | Mature, large community, graph-based agent orchestration |
| **Vercel AI SDK** | TypeScript | Stable | Focused on streaming + tool-calling in Next.js; simpler but less "agent" |
| **Custom (LLM + tool-calling loop)** | Any | N/A | Full control; more code to write, but no framework lock-in |

**Recommendation:** If the project is Google Cloud-native and you expect to use Vertex AI + Gemini models, ADK is the natural fit despite its immaturity. However, starting with a **thin custom agent loop** (LLM + tool-calling + session state in Postgres) and migrating to ADK when it stabilizes is a lower-risk path. The core abstractions (tools, sessions, events) are straightforward enough to implement directly.

---

## Database

**Recommended: Postgres + pgvector** (from ChatGPT).

Options:
- **Supabase** — managed Postgres, starts at $10/mo, includes auth and realtime
- **Neon** — serverless Postgres, generous free tier, scales to zero
- **Cloud SQL** — GCP-native, more operational control

Postgres handles both structured data (student model, plans, rewards) and vector search (pgvector for embeddings), keeping the stack simple.

---

## Recommended "V1" Stack (ChatGPT)

For a "Google-native" setup (since PDFs are already in Drive):

- **Backend:** Cloud Run (serverless, scales to zero)
- **Database:** Postgres (Cloud SQL or Supabase) + pgvector
- **Jobs:** Pub/Sub + Cloud Tasks (ingestion queue)
- **OCR:** Cloud Vision (only when needed)
- **Storage:** Drive for raw PDFs; GCS only for derived crops if required
- **LLM:** Vertex AI Gemini (via ADK or direct API)
- **Frontend:** React + TypeScript PWA

---

## Deployment Options

(From ChatGPT.)

| Option | Description | Trade-offs |
|--------|-------------|------------|
| **Fast + practical** (recommended start) | Postgres + pgvector, GCS, Cloud Run, hosted multimodal LLM, simple web UI | Fastest to MVP; some cloud dependency |
| **Max privacy / self-host** | Local OCR + local embedding + local LLM, own server/NAS | Full control; quality may be lower, more ops burden |
| **Hybrid** | All data local; send only minimal de-identified snippets to cloud LLM; cache aggressively | Good balance; more complex to build |

---

## Open Questions

1. **Next.js vs separate backend?** Next.js gives fastest MVP (shared frontend/backend); a separate Fastify/NestJS service gives cleaner boundaries if the backend grows complex.
2. **ADK adoption timing:** Adopt now (and build custom infrastructure for gaps) or build a thin custom agent loop and migrate later?
3. **Monorepo vs multi-repo?** A monorepo (e.g., Turborepo) is recommended for a family-scale project to keep things simple.
4. **Python worker deployment:** Cloud Run job, Cloud Functions, or a simple container?
