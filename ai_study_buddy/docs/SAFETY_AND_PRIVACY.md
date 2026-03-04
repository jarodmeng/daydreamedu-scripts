# AI Study Buddy — Safety & Privacy

> Status: **Exploratory** — options and recommendations, not final decisions.
>
> Sources: ChatGPT 5.2 Thinking conversation (3 Mar 2026), supplemented with independent research (Opus 4.6 Max, 4 Mar 2026).

---

## Two Dimensions of Safety

1. **Data privacy** — protecting children's personal data under Singapore law
2. **Pedagogical safety** — preventing AI dependency, answer leaking, and inappropriate content

Both are critical for a system used by minors (ages ~7–12).

---

## 1. Data Privacy: Singapore PDPA

### Applicable guidelines

Singapore's PDPC published **Advisory Guidelines on the PDPA for Children's Personal Data in the Digital Environment** on 28 March 2024. These explicitly apply to **educational technology (EdTech) products**. ([PDPC Advisory Guidelines, Mar 2024](https://www.pdpc.gov.sg/guidelines-and-consultation/2024/03/advisory-guidelines-on-the-pdpa-for-childrens-personal-data-in-the-digital-environment))

### Key requirements

| Requirement | What it means for this project |
|-------------|-------------------------------|
| **Consent age threshold** | Children aged 13+ can provide direct consent; **under 13 requires parental consent**. All three children (P2, P4, P6) are under 13, so the parent must control all accounts. ([PDPC, via Amica Law, 2024](https://www.amicalaw.com/singaporepdpcissuesnewguidelines050424)) |
| **Reasonable purposes only** | Process children's data only for clearly defined purposes (delivering age-appropriate learning content). No targeting, profiling for marketing, or sharing with third parties. |
| **Data minimization** | Collect and retain only the minimum necessary data. Don't store data you don't need for the learning purpose. |
| **Age-appropriate communication** | Use language and media (visual/audio aids) that children can understand when communicating about data use. No "wall of text" privacy policies. |
| **Age verification** | Implement age assurance throughout the user journey, not just at sign-up. |
| **Geolocation** | Disable by default or collect approximate location only. (Likely not needed for this app.) |
| **Enhanced security** | Appropriate security measures aligned with PDPC's Guide to Data Protection Practices for ICT Systems. |
| **Data Protection Impact Assessment (DPIA)** | Conduct a DPIA before launching the service. |

### Practical implications

- **Parent-controlled accounts.** The parent creates and manages all child accounts. Children cannot sign up independently.
- **Data minimization + encryption.** Store only what's needed; encrypt data at rest and in transit.
- **Ability to delete/export a child's data.** Must be able to fully remove a child's data on request.
- **"No external sharing" defaults.** No data leaves the system to third parties (except the LLM provider, which requires careful handling — see below).
- **DPIA recommended.** Even for a family-only tool, documenting what data is collected, why, and how it's protected is good practice.

### LLM provider data handling

When the system sends student data (question text, attempt context, mastery info) to a cloud LLM (e.g., Vertex AI Gemini), that data is being processed by a third party. Mitigations:

- **Send minimal context.** Only the top-k retrieved chunks + cropped question region — not the child's full history.
- **De-identify where possible.** Use child IDs rather than names in LLM prompts. The LLM doesn't need to know "Winston" — it just needs "Child A, P6."
- **Vertex AI data handling.** Google's Vertex AI platform has enterprise data handling commitments (data not used for model training by default), but this should be verified against current terms.
- **Consider local models for sensitive tasks.** If certain interactions involve particularly sensitive data, a local/on-premise model could handle those.

---

## 2. Pedagogical Safety: Answer-Gating Policies

### Per-child answer policies (from ChatGPT)

| Child | Grade | Policy |
|-------|-------|--------|
| **Abigail** | P2 | Never dump answers; always guided. Hints only, no reveals. |
| **Emma** | P4 | Allow answers only after she explains reasoning or uses 2–3 hints. |
| **Winston** | P6 | Allow answers for exam strategy, but require a full method + reflection for mastery updates. |

### Why this matters

This isn't just ethics — it's **effectiveness**. It prevents "AI dependency" and preserves retrieval practice (the effortful recall that actually builds memory). Research shows that easy access to answers undermines long-term learning.

### Implementation

The answer-gating policy should be enforced at the **system level**, not just in the LLM prompt:

1. **System-level enforcement:** The backend checks the child's policy before allowing the tutor agent to reveal an answer. The LLM's system prompt says "never reveal answers for this child," but the backend also blocks answer-containing responses as a second layer.

2. **Configurable by parent:** The parent can adjust policies over time (e.g., tighten Winston's policy as PSLE approaches, or relax Abigail's for specific topics where she needs more support).

3. **Audit trail:** Every time an answer is revealed or withheld, log the decision + the policy that triggered it.

---

## 3. Content Safety

### What the agent should never do

- Generate inappropriate, violent, or adult content
- Discuss topics outside the educational scope
- Make the child feel stupid or ashamed
- Compare siblings negatively
- Provide medical, psychological, or legal advice

### Implementation

- **System instruction constraints:** Clear boundaries in the agent's system prompt.
- **Output filtering:** A policy layer that scans responses before delivery. ADK Plugins can implement this.
- **Topic guardrails:** If the child asks something off-topic, redirect gently ("That's a great question! Let's ask your parents about that. Now, back to fractions…").

---

## 4. Parent-in-the-Loop

### Weekly summary (from ChatGPT)
- "What I noticed / what to do next week"
- Sent as an email-style report or visible on the parent dashboard

### Control knobs
- Set constraints: "Do not give final answers"; "Hints only"
- Set time budgets (weekday / weekend)
- Choose focus priorities

### Visibility into agent behavior
- Parent can review session transcripts (what the agent said, what the child said)
- Parent can see what tools the agent called (e.g., "revealed a hint at level 3")
- Parent can flag concerning interactions for review

---

> [!NOTE]
> **Opus 4.6 Max analysis** — additional safety considerations.

### Data retention policy

Consider a clear data retention policy:
- **Active data:** Current school year + 1 year back. Fully queryable.
- **Archived data:** Older data compressed and moved to cold storage. Available on request.
- **Deletion:** Parent can request full deletion of any child's data at any time. The system must be able to comply (PDPA requirement).

### Incident response

Even for a family-only tool, have a plan for:
- **What if the LLM generates something inappropriate?** Log it, suppress it, alert the parent.
- **What if a child's data is exposed?** (e.g., misconfigured cloud storage) Have a checklist for containment + notification.

### Open Questions

1. **Should session transcripts be stored permanently or auto-deleted after a period?** More data is better for analytics, but more data is also more risk.
2. **How to handle the LLM saying something pedagogically wrong?** (e.g., incorrect math) Should there be a "flag this response" button for the parent/child?
3. **Should the system have a "supervised mode"** where the parent must approve each session, vs. "autonomous mode" where the child can use it freely?
