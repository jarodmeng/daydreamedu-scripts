# AI Study Buddy — Cost Analysis

> Status: **Exploratory** — estimates based on current pricing; will need updating as the project evolves.
>
> Sources: ChatGPT 5.2 Thinking conversation (3 Mar 2026), supplemented with independent research (Opus 4.6 Max, 4 Mar 2026).

---

## Cost Buckets

Costs break into three categories:
1. **Fixed monthly** (infrastructure baseline)
2. **Variable — ingestion** (OCR, embeddings, AI extraction)
3. **Variable — tutoring** (LLM token usage during sessions)

ADK itself is open-source (Apache 2.0) — no license fee.

---

## 1. Fixed Monthly Infrastructure

| Component | Option | Estimated cost |
|-----------|--------|---------------|
| **Database** (Postgres + pgvector) | Supabase starter | ~$10/mo ([Supabase pricing](https://supabase.com/pricing)) |
| | Neon (serverless) | Free tier → ~$0–19/mo |
| | Cloud SQL (GCP) | ~$10–30/mo depending on instance |
| **Backend hosting** | Cloud Run (serverless, scales to zero) | Often $0–5/mo at family scale (generous free tier: 240K vCPU-sec + 450K GiB-sec/mo) ([Cloud Run pricing](https://cloud.google.com/run/pricing)) |
| **Storage (raw PDFs)** | Google Drive (existing plan) | Whatever you already pay; 2TB Google One in SG is SGD 28.99/mo |
| **Storage (derived crops)** | GCS (optional) | Pennies–$1–2/mo at a few GB |

**Estimated fixed baseline: ~$15–40 USD/month** (excluding your existing Drive plan).

---

## 2. Variable — Ingestion Costs

### Current inventory: ~4,000 pages; growth: ~500 pages/month

### OCR (Cloud Vision Document Text Detection)

Pricing: first 1,000 pages/month free, then $1.50 per 1,000 pages. ([Cloud Vision pricing](https://cloud.google.com/vision/pricing))

| Scenario | Pages | Cost |
|----------|-------|------|
| **One-time backfill (all 4,000 pages in one month)** | 4,000 | 1,000 free + 3,000 billable → **$4.50** |
| **Spread over 4 months (1,000/month)** | 1,000/mo | **$0** (within free tier) |
| **Ongoing monthly (500 new pages)** | 500 | **$0** (within free tier) |
| **Heavy month (1,500 pages)** | 1,500 | 500 billable → **$0.75** |

**Key cost levers:**
- OCR only scanned pages (skip digital PDFs)
- OCR only once per page; cache results
- Don't use multiple Vision features per page (billing is per feature per page)

### Embeddings (Gemini Embedding via Vertex AI)

Pricing from the ChatGPT conversation: $0.00015 per 1,000 input tokens ($0.15 / 1M tokens).

| Scenario | Tokens | Cost |
|----------|--------|------|
| **Backfill 4,000 pages @ 400 tokens/page** | 1.6M | **$0.24** |
| **Backfill 4,000 pages @ 1,000 tokens/page** | 4.0M | **$0.60** |
| **Monthly 500 pages @ 400 tokens/page** | 200K | **$0.03** |

Embeddings are negligible at this scale.

### AI extraction calls (vision model on crops)

Variable — depends on how many pages need AI-assisted extraction. Cropping to question regions (not full pages) keeps token usage low. Expect a few cents to low single-digit dollars per batch.

---

## 3. Variable — Tutoring LLM Costs

### Token budget per tutoring hour

The ChatGPT conversation estimated a moderate tutoring session at **~100K input tokens + 20K output tokens per hour** (short turns + small retrieved context).

### Pricing (from ChatGPT conversation — Gemini 2.5 models)

| Model | Input (per 1M tokens) | Output (per 1M tokens) | Cost per tutoring hour | 30 hours/month |
|-------|----------------------|----------------------|----------------------|----------------|
| **Gemini 2.5 Flash Lite** | $0.10 | $0.40 | ~$0.018/hr | **~$0.54/mo** |
| **Gemini 2.5 Flash** | $0.30 | $2.50 | ~$0.08/hr | **~$2.40/mo** |
| **Gemini 2.5 Pro** | $1.25 | $10.00 | ~$0.325/hr | **~$9.75/mo** |

**Recommended model mix:** Flash Lite for most tutoring; Flash or Pro only for harder reasoning tasks. Even at 10% Pro + 90% Flash Lite, costs stay in low single-digit dollars/month.

For offline tasks (tagging, summarizing logs), Flex/Batch pricing is even cheaper (e.g., Flash Lite Flex: $0.05 input / $0.20 output per 1M tokens).

---

> [!IMPORTANT]
> **Opus 4.6 Max analysis** — pricing may have shifted since the ChatGPT conversation.
>
> As of early March 2026, Vertex AI pricing pages show **Gemini 3 and Gemini 3.1** models, suggesting Gemini 2.5 may be entering deprecation or price changes. The Gemini 2.5 prices cited above were accurate at the time of the ChatGPT conversation but should be **re-verified** before making budgeting commitments.
>
> If Gemini 3.x pricing is similar or lower (likely, given the trend of decreasing per-token costs), the estimates above remain conservative (i.e., actual costs may be lower).

---

## 4. Total Monthly Estimate (Family Scale)

### Assumptions
- 3 children, ~30 hours/month total tutoring
- ~500 new pages/month ingested
- Flash Lite as default model, Flash/Pro for 10% of turns

| Category | Monthly estimate |
|----------|-----------------|
| Fixed infrastructure | $15–40 |
| OCR | $0–1 |
| Embeddings | < $0.10 |
| LLM tutoring (30 hrs) | $1–5 |
| AI extraction calls | $1–3 |
| **Total** | **~$17–50/month** |

Plus your existing Google Drive/One plan.

---

## 5. Cost Gotchas to Avoid

(From ChatGPT, with additional notes.)

| Gotcha | How it happens | Mitigation |
|--------|---------------|------------|
| **Over-OCRing** | OCR same pages multiple times, or use multiple Vision features per page | OCR once, cache results; use one feature per page |
| **Huge context windows** | Each tutor turn includes tens of thousands of tokens unnecessarily | Keep retrieval top-k small; prefer question crops + short snippets |
| **Context cache misuse** | Vertex context caching is priced per token-hour; caching large contexts for long periods is expensive | Use caching carefully; understand the per-hour storage cost |
| **Grounding with Google Search** | Exceeding free grounding limits ($35/1,000 grounded prompts) | Usually unnecessary for worksheet/textbook content; disable |
| **Surprise bills** | Unbounded API usage | Set hard caps + alerts on all APIs ([API usage caps](https://docs.google.com/apis/docs/capping-api-usage)) |

---

> [!NOTE]
> **Opus 4.6 Max analysis** — additional cost considerations.

### One-time build cost

The ChatGPT conversation correctly notes that the main build cost is engineering time (you + AI-assisted development). There is no licensing cost for ADK, Postgres, or the open-source components. Consider budgeting build effort in two layers:

1. **MVP (Winston-first):** ingestion → question objects → tutor loop → logging → quest board. Estimated: 4–8 weeks of focused part-time development with AI assistance.
2. **Scale-up:** Emma/Abigail UX, voice, richer gamification, analytics, template learning. Ongoing incremental work.

### Cost scaling: what happens if usage grows

| Scenario | Change | Cost impact |
|----------|--------|-------------|
| Double tutoring hours (60 hrs/mo) | 2× LLM tokens | +$1–5/mo (still cheap) |
| Double PDF volume (1,000 pages/mo) | More OCR + embeddings | +$0–2/mo |
| Add voice input/output | Speech-to-text + text-to-speech API costs | +$5–15/mo depending on volume |
| Add image generation (for custom practice) | Image model API costs | Variable, potentially +$5–20/mo |

At family scale, **LLM token costs are not the bottleneck.** The real cost risk is feature creep that adds expensive API calls without clear learning value.

### Open Questions

1. **Target monthly budget?** Setting an explicit ceiling (e.g., $50/mo) helps make technology choices concrete.
2. **Weekly tutoring minutes per child?** Refines the LLM cost estimate.
3. **Voice usage?** Voice input (especially for Abigail) adds speech-to-text costs that aren't modeled above.
