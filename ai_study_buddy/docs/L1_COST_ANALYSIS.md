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

See [INGESTION_PIPELINE](./L4_INGESTION_PIPELINE.md) for the full pipeline design.

### Current inventory: ~4,000 pages; growth: ~500 pages/month

The ingestion pipeline is **vision-LLM-first** — most worksheets are scanned images with overlapping layers (printed text, child's handwriting, teacher's red ink, correction workings in green). A vision LLM (Gemini Flash) is the primary extraction tool. OCR is supplementary (useful for keyword search but not for score/boundary extraction).

### Vision LLM extraction (Gemini 2.5 Flash — primary cost)

The pipeline makes roughly 3–5 Gemini Vision calls per page:

| Step | LLM calls per page | What it does |
|------|-------------------|-------------|
| Page-level score extraction | 1 | Read score box at bottom-right of page |
| Question structure extraction | 1 | Identify questions, sub-parts, marks, boundaries |
| Per-question result extraction | 1–2 (one per question on the page) | Read ticks/crosses, child's answer, teacher corrections |
| Skill + error tagging | 1–2 (per question, batched) | Suggest skill tags and error categories |

**Per document (typical 8-page scored paper, ~15 questions):**

| | Input tokens | Output tokens |
|-|-------------|-------------|
| Page-level calls (8 pages × 2 calls) | ~12,000 | ~2,000 |
| Per-question calls (~15 questions × 2 calls) | ~12,000 | ~3,000 |
| **Total per document** | **~24,000** | **~5,000** |

**Cost at Gemini 2.5 Flash pricing ($0.30/1M input, $2.50/1M output):**

| Scenario | Documents | LLM cost |
|----------|-----------|---------|
| **Single document** | 1 | ~$0.02 |
| **Initial backlog (50 scored papers)** | 50 | **~$1.00** |
| **Ongoing monthly (~10–15 new scored papers)** | 10–15 | **~$0.20–0.30** |
| **Heavy month (30 papers + backfill batch)** | 30 | **~$0.60** |

At Flex/Batch pricing (off-peak): roughly half the above.

**Key cost lever:** The pipeline sends full page images for structural extraction but can send *cropped regions* (smaller images, fewer tokens) for per-question result extraction. Cropping reduces per-question input tokens by ~60%.

### OCR (Cloud Vision — supplementary)

OCR provides searchable text per page for keyword queries but is not the primary extraction method.

Pricing: first 1,000 pages/month free, then $1.50 per 1,000 pages. ([Cloud Vision pricing](https://cloud.google.com/vision/pricing))

| Scenario | Pages | Cost |
|----------|-------|------|
| **Backfill 4,000 pages across 4 months** | 1,000/mo | **$0** (within free tier) |
| **Ongoing monthly (500 new pages)** | 500 | **$0** (within free tier) |
| **Heavy month (1,500 pages)** | 1,500 | 500 billable → **$0.75** |

### Embeddings (Gemini Embedding via Vertex AI)

Pricing: $0.15 per 1M input tokens.

| Scenario | Tokens | Cost |
|----------|--------|------|
| **Backfill 4,000 pages @ 400 tokens/page** | 1.6M | **$0.24** |
| **Monthly 500 pages @ 400 tokens/page** | 200K | **$0.03** |

Embeddings are negligible at this scale.

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

| Category | Monthly estimate | Notes |
|----------|-----------------|-------|
| Fixed infrastructure | $15–40 | Database + hosting + storage |
| Vision LLM extraction (ingestion) | $0.20–0.60 | ~10–30 papers/month via Gemini Flash |
| OCR (supplementary) | $0 | Within Cloud Vision free tier at this volume |
| Embeddings | < $0.10 | Negligible at family scale |
| LLM tutoring (30 hrs) | $1–5 | Flash Lite default, Flash/Pro for 10% of turns |
| **Total** | **~$17–46/month** | |

**One-time backfill costs** (ingesting Winston's historical papers):

| Item | Cost |
|------|------|
| Vision LLM extraction (~50 papers) | ~$1.00 |
| OCR (~4,000 pages across 4 months) | $0 (free tier) |
| Embeddings (~4,000 pages) | ~$0.25 |
| **Backfill total** | **~$1.25** |

Plus your existing Google Drive/One plan.

---

## 5. Cost Gotchas to Avoid

(From ChatGPT, with additional notes.)

| Gotcha | How it happens | Mitigation |
|--------|---------------|------------|
| **Sending full pages when crops suffice** | Per-question extraction sends full page images instead of cropped regions | Crop to question region before sending — reduces image tokens by ~60% |
| **Re-processing already-ingested pages** | Pipeline re-runs on unchanged documents | Track document fingerprints; skip already-processed pages |
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
| Double PDF volume (1,000 pages/mo) | More vision LLM + OCR | +$0.50–1/mo (vision LLM is the main cost; OCR stays in free tier up to 1,000 pages) |
| Heavy ingestion month (100 papers) | Burst of vision LLM calls | ~$2 one-time (still negligible) |
| Add voice input/output | Speech-to-text + text-to-speech API costs | +$5–15/mo depending on volume |
| Add image generation (for custom practice) | Image model API costs | Variable, potentially +$5–20/mo |

At family scale, **LLM token costs are not the bottleneck.** The real cost risk is feature creep that adds expensive API calls without clear learning value.

### Open Questions

1. **Target monthly budget?** Setting an explicit ceiling (e.g., $50/mo) helps make technology choices concrete.
2. **Weekly tutoring minutes per child?** Refines the LLM cost estimate.
3. **Voice usage?** Voice input (especially for Abigail) adds speech-to-text costs that aren't modeled above.
