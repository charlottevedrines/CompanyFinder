# Succession Radar — Session Context

Recap of planning done before build started. Read this + `architecture.md` first thing when resuming — `architecture.md` is the technical spec/build plan; this file is the "how we got here" and the open items.

## The hackathon

Agentic AI hackathon, 3-day build, team of 5:
- **Teammate A** — CS + Math background, currently doing an LLM/graph master's, LangGraph-certified. Natural orchestration lead.
- **Teammate B, C** — AI & Data Science for business, both doing the Hugging Face agentic AI course during the event. Best fit for the signal-gathering agents and the scoring logic.
- **Teammate D** — Finance background, no CS, not doing the HF course. Owns the scoring rubric (M&A judgment on which signals matter), hand-curates the real demo companies, sanity-checks output, owns the pitch/business narrative.
- **Teammate E** — Finance background with some CS, notably experienced with Claude Code. Pairs with Teammate A on infra/glue code, natural owner of the frontend.

No Anthropic API access for this project — **OpenAI is the actual LLM provider**, via hackathon sponsor credits (not a fallback, the primary choice).

## Sponsor resources on offer

- **OpenAI** — Codex + API access. → In use as the core LLM provider (see architecture.md §8). Confirm exact model names/tiers the credits actually grant once obtained.
- **Pipelex** — declarative DSL for deterministic, typed AI workflows. → Optional, timeboxed spike only (architecture.md §13), not adopted by default. Fits the project's philosophy well (code controls the flow) but is an unfamiliar tool under time pressure.
- **Dust** — no-code agent-orchestration platform, connector-based (Slack/Notion/Drive/etc). → Poor fit for the core pipeline (our agents are thin REST wrappers, not connector-based). Only plausible use: a fully optional "chat with your shortlist" bonus feature on day 3 afternoon, after the core demo is locked. Fully expendable.
- **Gradium** — TTS/STT. → Not core; at most a demo-flair stretch (voice-read the top rationale). Not planned for by default.
- **Jinko** — travel research agents. → Does not fit this project at all. Ruled out.

## The idea, in one paragraph

An agent that takes sector + region + size and returns a ranked list of French SMEs showing signs of an imminent succession/ownership change, each with a transparent score breakdown and cited evidence (not a black-box number). Buyer persona: independent sponsors/search funds, business brokers, PE roll-up teams, corporate-dev groups — people who currently do this by cold-calling owners. Demo market is France because French company registries expose director age/tenure/group-structure data legally and for free, and there's a real, well-documented policy problem behind it (*transmission d'entreprise* — SME owners nearing retirement with no identified successor).

## Key architectural decisions already made (and why)

1. **Code controls the flow; the LLM only does two judgment steps.** For every candidate, the orchestrator always calls all three signal-gathering agents (Leadership, Ownership, Press), always in parallel, in plain code. The LLM is used only to (a) extract succession-language signals from messy press text, and (b) write the human-readable rationale from already-computed structured facts. This is simpler to build and debug under time pressure than an autonomous tool-picking agent, and still counts as agentic for judging.
2. **Plain Python `asyncio` for the MVP orchestrator, not LangGraph, Pipelex, or Dust by default.** Teammate A's LangGraph experience and the sponsor tools are optional day-2/day-3 upgrades attempted only after the safe version already works — never build the graph/DSL first and the logic second.
3. **Weighted, transparent scorecard — not a trained/hand-labeled ML model.** Faster to build, fully explainable, matches the "not a black box" pitch. The score is pure deterministic arithmetic (architecture.md §6); the LLM is only invoked afterward to narrate a decision the code already made, never to compute the score itself.
4. **Demo scope must be locked to one narrow slice on day 1 morning**: 1-3 NAF codes, one region, 10-49 employees, ~20-30 hand-curated real SIREN numbers. "Works for any French SME" is explicitly not the goal for the live demo.
5. **Press Agent will likely return nothing for most companies, and that's fine.** Small SMEs rarely make the news. Treat "no coverage" as neutral, not negative, in the scorecard, and say so openly in the pitch rather than let it surface as an unexplained gap.
6. **Cache every agent's raw response locally per SIREN**, not to pre-scrape the registry, but so day-3 demo reliability doesn't depend on live APIs/rate limits during judging.

## Data sources (verified via research this session)

- `recherche-entreprises.api.gouv.fr` — **free, no signup, no API key.** Covers Discovery (search by NAF/postal/region/size) and Leadership (returns `dirigeants[]` with `date_naissance`) in one call. This is the fastest path to real data on day 1. Exact `tranche_effectif_salarie` bracket codes for 10-49 employees were not confirmed with full certainty — verify against a live response before hardcoding.
- **Pappers API** — needs account signup with a professional email (100 free credits). Used for Ownership (group/holding structure) and cleaner director appointment dates. **Start signup on hour 1** — it's the one dependency with approval latency. Fallback if it's slow: infer group structure from the gov API (same address/same dirigeant across multiple SIRENs as a weak proxy).
- **GDELT DOC 2.0** (free, keyless) primary for Press; Google News RSS by company name as a zero-setup fallback. Expect sparse results for small SMEs — by design, not a bug.

## Deliverables produced this session

- `architecture.md` — full technical spec: data model, orchestrator code, each agent's data source and code sketch, scoring formula, exactly where/how the two LLM calls fit, caching strategy, repo structure, setup checklist, day-by-day plan with task ownership, sponsor tool add-on analysis, and a pitch-ready limitations section.
- `succession-radar-diagram.png` — the original pipeline diagram (Discovery → 3 parallel agents → Scoring → Shortlist) that shaped the architecture.

## Open items / not yet decided

- Exact NAF codes, region, and employee-band bracket codes for the demo slice — needs the team together to pick, plus a live API call to confirm bracket codes.
- Which OpenAI model tiers the sponsor credits actually grant.
- Whether Pappers signup approval is fast enough in practice — untested.
- Whether the Pipelex/Dust spikes get attempted at all — explicitly optional, decide in the moment based on how day 1-2 go.
- No repo/code has been written yet — this session was architecture and planning only.
