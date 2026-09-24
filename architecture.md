# Succession Radar — Architecture & Build Plan

## 1. What we're building

An agent that takes `sector + region + size` and returns a ranked list of French SMEs showing signs of an imminent ownership/succession change, each with a transparent score breakdown and cited evidence — not a black-box number.

Buyer persona: independent sponsors / search funds, business brokers, PE roll-up teams, corporate-dev groups — people who currently do this by cold-calling thousands of owners.

Demo market: France, because `recherche-entreprises.api.gouv.fr` and Pappers expose exactly the signal we need (director age, tenure, group structure) legally and for free, and there's a real, well-documented policy problem behind it (*transmission d'entreprise* — hundreds of thousands of SME owners nearing retirement with no identified successor).

**Demo slice (lock this on day 1 morning, do not widen it):**
- Sector: 1-3 NAF codes in manufacturing or professional services (e.g. `25.xx` metalwork, or a services equivalent)
- Region: one region with a strong industrial SME base
- Size: 10–49 employees
- A hand-curated list of ~20–30 real SIREN numbers the finance-background teammate has sanity-checked, used as the reliable demo set

## 2. Control-flow decision

**Your own code controls the flow, not the LLM.** 

!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
!!!!!!!!!!!!!!!!!!!!THIS IS GOING TO CHANGE !!!!!!!!!!!!!!!!!!!!!!!!!!!
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

For every candidate company, the orchestrator *always* calls all three signal-gathering agents, *always* in parallel. The LLM is used only for the two steps that genuinely need judgment:

1. Extracting "exploring strategic alternatives"-type language out of messy press text (Press Agent).
2. Writing the human-readable rationale in the Scoring Agent, grounded strictly in the structured facts already computed.

This is still multi-step, tool-using, and reasoning over real data — it counts as agentic — but it's debuggable by a mixed-skill team under time pressure, which an autonomous tool-picking agent framework is not. **Do not reach for LangGraph for the MVP.** Plain `asyncio` is simpler to build, simpler to debug live during a demo, and easier for four of five teammates to read. If time remains on day 3, the person with LangGraph experience can wrap the existing, working orchestrator in a graph purely for the "agentic" visual/pitch value — never build the graph first and the logic second.

## 3. Data sources (verified)

| Signal | Source | Auth | Notes |
|---|---|---|---|
| Discovery (search by NAF/region/size) | `recherche-entreprises.api.gouv.fr` | **None — free, keyless** | Also returns `dirigeants[]` with name + `date_naissance` per company in the same call. Confirm exact `tranche_effectif_salarie` bracket codes for 10-49 against a live response on day 1 — don't hardcode from memory. |
| Leadership (director age, tenure) | Same gov API, or Pappers `/entreprise/{siren}` for cleaner `date_nomination` | Gov API: none. Pappers: API key | Age = today − birth year. Tenure = today − nomination/appointment date. Verify the appointment-date field name against a live Pappers response; field naming has changed across their API versions. |
| Ownership (holding structure, group) | Pappers `/entreprise/{siren}` (`personnes_morales`, `representants`, group/`SIREN` of parent) | API key (free tier: 100 credits on signup with a professional email) | **Sign up for this on hour 1**, in parallel with everything else — it's the one dependency with signup latency. If it's not approved fast enough, fall back to inferring group structure from the gov API (same address + same dirigeant across multiple SIRENs is a usable weak proxy). |
| Press (M&A-adjacent language) | GDELT DOC 2.0 API (free, keyless, multilingual) primary; Google News RSS by company name as a zero-setup fallback | None | **Expect this to return nothing for most companies.** A 30-person manufacturing SME rarely makes the news. Design the agent and the scorecard to treat "no coverage" as a neutral, not negative, signal — never let a missing Press result block or zero out a score. |

None of these are pre-scraped or cached ahead of time — every agent is a live API call at request time, per company, per run. (We do add a *result cache* for demo reliability — see §7 — but that's a cache of our own pipeline's output, not a copy of the registry.)

## 4. Data model

```python
# models.py
from dataclasses import dataclass, field
from datetime import date

@dataclass
class Director:
    name: str
    birth_year: int | None
    appointment_date: date | None
    role: str  # "gérant", "président", etc.

@dataclass
class LeadershipSignal:
    directors: list[Director]
    oldest_director_age: int | None
    sole_director: bool
    tenure_years_of_oldest: float | None
    source: str  # "recherche-entreprises.api.gouv.fr" or "pappers"

@dataclass
class OwnershipSignal:
    has_holding_company: bool
    holding_company_created_year: int | None
    number_of_legal_entities_in_group: int
    source: str

@dataclass
class Evidence:
    text: str          # e.g. "exploring strategic options for the business"
    url: str
    published_date: date | None
    article_title: str

@dataclass
class PressSignal:
    articles_found: int
    extracted_signals: list[Evidence]  # empty list is a valid, common result
    source: str

@dataclass
class ScoreBreakdown:
    total_score: float  # 0-100
    contributions: dict[str, float]   # {"director_age": 32, "sole_director": 15, ...}
    rationale: str                    # LLM-written, grounded only in the fields above

@dataclass
class CompanyResult:
    siren: str
    name: str
    naf_code: str
    region: str
    employee_band: str
    leadership: LeadershipSignal
    ownership: OwnershipSignal
    press: PressSignal
    score: ScoreBreakdown
```

## 5. Orchestration

```python
# orchestrator.py
import asyncio
from models import CompanyResult

async def process_company(siren: str, company_meta: dict) -> CompanyResult:
    # Always call all three, always in parallel — code decides this, not the LLM.
    leadership, ownership, press = await asyncio.gather(
        leadership_agent(siren),
        ownership_agent(siren),
        press_agent(company_meta["name"]),
        return_exceptions=True,   # one agent failing must not kill the run
    )
    leadership = leadership if not isinstance(leadership, Exception) else EMPTY_LEADERSHIP
    ownership = ownership if not isinstance(ownership, Exception) else EMPTY_OWNERSHIP
    press = press if not isinstance(press, Exception) else EMPTY_PRESS

    score = score_company(leadership, ownership, press)  # deterministic, see §6
    return CompanyResult(
        siren=siren, name=company_meta["name"], naf_code=company_meta["naf"],
        region=company_meta["region"], employee_band=company_meta["band"],
        leadership=leadership, ownership=ownership, press=press, score=score,
    )

async def run_search(naf_codes: list[str], region: str, size_band: str) -> list[CompanyResult]:
    candidates = await discovery_agent(naf_codes, region, size_band)
    results = await asyncio.gather(*(process_company(c["siren"], c) for c in candidates))
    return sorted(results, key=lambda r: r.score.total_score, reverse=True)
```

Design rule: **every agent function returns a typed, empty-but-valid object on failure or "no data," never raises past its own boundary.** That's what makes the "one agent failing shouldn't kill the run" behavior in the diagram actually true, and it's what lets the Press Agent's very common "zero articles" outcome be a normal code path instead of a special case someone forgets to handle at 2am on day 3.

## 6. Scoring — weighted scorecard, not a trained model

Skip hand-labeling a training set. Three days isn't enough to make a small logistic-regression model trustworthy, and a transparent weighted scorecard is both faster to build *and* a stronger demo moment ("flagged because: 71-year-old founder-CEO, no other directors listed, holding company registered 2019" is exactly the framing your spec wants).

```python
# scoring.py
WEIGHTS = {
    "director_age_70_plus": 35,
    "director_age_65_69": 20,
    "sole_director": 15,
    "long_tenure_15y_plus": 10,
    "recent_holding_company": 15,   # created in last ~3 years — common pre-sale restructuring
    "press_succession_language": 25,
}

def score_company(leadership, ownership, press) -> ScoreBreakdown:
    contributions = {}
    if leadership.oldest_director_age is not None:
        if leadership.oldest_director_age >= 70:
            contributions["director_age_70_plus"] = WEIGHTS["director_age_70_plus"]
        elif leadership.oldest_director_age >= 65:
            contributions["director_age_65_69"] = WEIGHTS["director_age_65_69"]
    if leadership.sole_director:
        contributions["sole_director"] = WEIGHTS["sole_director"]
    if leadership.tenure_years_of_oldest and leadership.tenure_years_of_oldest >= 15:
        contributions["long_tenure_15y_plus"] = WEIGHTS["long_tenure_15y_plus"]
    if ownership.has_holding_company and ownership.holding_company_created_year:
        contributions["recent_holding_company"] = WEIGHTS["recent_holding_company"]
    if press.extracted_signals:
        contributions["press_succession_language"] = WEIGHTS["press_succession_language"]

    total = min(sum(contributions.values()), 100)
    rationale = generate_rationale(leadership, ownership, press, contributions)  # LLM call, §8
    return ScoreBreakdown(total_score=total, contributions=contributions, rationale=rationale)
```

The score itself is pure arithmetic — fully deterministic, fully explainable, reproducible without calling the LLM at all. The LLM is only invoked afterward, to turn the `contributions` dict into one readable sentence. This ordering matters: if the LLM computed the score, you'd be back to a black box; instead it only narrates a decision your code already made.

## 7. Caching (for demo reliability, not for pre-scraping)

Cache every agent's *raw* response to a local JSON file keyed by SIREN + agent name, with a timestamp. This is not "owning a copy of the registry" — it's memoizing our own pipeline's live calls so that:
- reruns during development don't burn API credits or hit rate limits,
- the day-3 demo can run instantly against a pre-warmed cache of the ~20-30 curated companies, with a couple of companies re-run live on stage to prove it's real,
- a flaky network or an API outage 10 minutes before judging doesn't sink the demo.

```python
# cache.py
import json, hashlib
from pathlib import Path

CACHE_DIR = Path("cache")

def cache_key(siren: str, agent: str) -> Path:
    return CACHE_DIR / agent / f"{siren}.json"

async def cached_call(siren: str, agent: str, fn, *args, max_age_hours=24):
    path = cache_key(siren, agent)
    if path.exists():
        return json.loads(path.read_text())
    result = await fn(*args)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, default=str))
    return result
```

## 8. Where the LLM is actually used

**Provider: OpenAI** (hackathon-provided credits — no Anthropic access for this project, so OpenAI's API is the actual provider, not a backup). Confirm the exact model names the sponsor credits grant access to before hardcoding IDs; use the cheapest/fastest available tier for extraction (high call volume) and a stronger tier for rationale synthesis (one call per company, quality matters more than speed). Optionally use Codex for coding assistance alongside whatever the team already uses.

Two calls, both grounded and constrained — never let the model invent facts not present in its input.

**Press extraction** (cheap/fast tier, called once per article — could be many calls):
```python
EXTRACTION_PROMPT = """Read this news article snippet about {company_name}.
Does it contain language suggesting the company is exploring a sale, succession,
strategic alternatives, or leadership transition? Quote the exact sentence if so.
If not, respond with exactly: NO_SIGNAL

Article:
{article_text}
"""
# model: cheapest/fastest OpenAI tier available via the sponsor credits
```

**Rationale synthesis** (once per company — quality matters more than speed, still cheap at this volume):
```python
RATIONALE_PROMPT = """Write a 1-2 sentence rationale for why this company was flagged,
using ONLY the facts below. Do not add, infer, or embellish beyond them.

Facts: {contributions_dict}
Director details: {leadership_summary}
Ownership details: {ownership_summary}
Press evidence: {press_evidence_or_none}
"""
# model: stronger OpenAI tier — better prose, still cheap at ~1 call per company
```

## 9. Frontend

Streamlit, single page. Don't over-invest here.
- Top: filter inputs (sector, region, size) — can be hardcoded to the demo slice with the filters shown as read-only for the actual demo, to avoid live-typing risk on stage.
- Ranked table: score, company name, one-line rationale.
- Expandable row per company: full evidence — director list with ages, ownership structure, press quotes with source links.

## 10. Repo structure

```
succession-radar/
  agents/
    discovery.py
    leadership.py
    ownership.py
    press.py
  scoring.py
  orchestrator.py
  models.py
  cache.py
  llm.py            # thin wrapper around OpenAI API calls
  app.py             # Streamlit UI
  cache/              # gitignored, populated at runtime
  .env                # ANTHROPIC_API_KEY, PAPPERS_API_KEY — gitignored
  demo_companies.csv  # curated SIREN list for the reliable demo set
```

## 11. Setup checklist (do these in parallel, hour 1)

- [ ] OpenAI API key from the hackathon sponsor credits, and confirm which model names/tiers are actually granted
- [ ] Pappers account signup with a professional email (100 free credits) — start this immediately, it's the one external dependency with approval latency
- [ ] Confirm `recherche-entreprises.api.gouv.fr` needs no key (it shouldn't) and hit it once with a real query to see the actual JSON shape
- [ ] Lock NAF codes, region, and employee band for the demo slice
- [ ] Shared repo + `.env.example` + `requirements.txt` (`httpx`, `openai`, `streamlit`, `pandas`)

## 12. Day-by-day plan

**Day 1 — real data flowing end to end, even on a thin slice**
- Whole team (first hour): lock the demo slice, run setup checklist above
- *Orchestration lead (CS/Math):* scaffold repo, data models (§4), async orchestrator (§5) against **mocked** agents so the full shape works on dummy data by midday; then start wiring in real agents as teammates finish them
- *Claude-Code-experienced teammate:* build Discovery Agent + Leadership Agent against the free gov API — same endpoint serves both, so this is the fastest path to real data flowing
- *AI/DS teammate #1:* Pappers signup + Ownership Agent (holding structure, group entities)
- *AI/DS teammate #2:* Press Agent — GDELT/news wrapper + the extraction prompt (§8), with a handful of few-shot examples
- *Finance teammate:* define the scoring rubric from an M&A lens (which signals actually matter, rough weights — feed into §6); hand-curate the ~20-30 real SIREN demo list; start the pitch narrative
- **End of day 1:** Discovery + Leadership working on real data for the demo slice; Ownership and Press agents functional standalone even if not yet wired into the orchestrator

**Day 2 — wire it together, score it, get a UI up**
- *Orchestration lead:* replace mocks with real agents in the orchestrator; add the cache layer (§7); add per-agent error isolation so one failing agent degrades gracefully instead of killing the run
- *AI/DS teammates:* implement the scorecard (§6) and the rationale LLM call (§8); tune weights against the finance teammate's judgment
- *Claude-Code-experienced teammate:* build the Streamlit UI (§9)
- *Finance teammate:* sanity-check scores and rationales against real knowledge of the curated companies — does a 71-year-old sole director with a 2019 holding company actually look right? — feed corrections back into weights; keep building the pitch and the "who'd pay for this" + honest-limitations section (no LinkedIn scraping; augments an analyst, doesn't replace one; press coverage is sparse for small SMEs by nature, not by bug)
- **End of day 2:** full pipeline works end-to-end on real data for the curated list, with a working UI — a roughshod demo already exists
- *If ahead of schedule:* whoever has spare bandwidth runs the timeboxed Pipelex spike (§13) on the Press Agent or rationale step — 1-2 hours, hard stop, abandon if it's not clicking

**Day 3 — polish, freeze a reliable demo, rehearse**
- Morning: bug fixes, handle missing/partial data gracefully, tighten rationale prompt quality, UI polish
- Midday: run the full pipeline once against the final curated list, let it populate the cache — this is the reliable fallback dataset; plan to run 2-3 companies live on stage to prove it's real, with the rest served from cache
- Afternoon: finalize the pitch (problem framing — *transmission d'entreprise* crisis — demo walkthrough, this architecture diagram, honest limitations, business model), rehearse the live demo at least twice
- *Only if the core demo is fully locked and cached with time to spare:* attempt the Dust "chat with your shortlist" bonus (§13) — fully expendable, never let it threaten the rehearsed demo
- Keep real buffer time — something will break the morning of

## 13. Sponsor tool add-ons (optional, non-blocking)

The hackathon provides credits/access to several partner platforms. Two are relevant here beyond OpenAI (already the core LLM provider, §8); the others (Jinko — travel agents, Gradium — speech APIs) don't fit this project except Gradium as a pure demo-flair stretch (e.g. voice-reading the top rationale aloud), never core.

**Pipelex** — a declarative DSL for deterministic, typed AI workflows — fits this architecture's philosophy unusually well ("code controls the flow, LLM only for judgment steps" is close to exactly what it's for). Fit varies by piece:

| Piece | Fit |
|---|---|
| Discovery / Leadership / Ownership agents (REST call + parsing) | Low-to-reasonable value — mostly buys formality, not solving a hard problem |
| **Press Agent** (unstructured text → structured judgment) | **Best candidate** — self-contained, one clear input/output contract, textbook shape for Pipelex |
| **Scoring rationale step** (structured facts → one grounded sentence) | Good second candidate, same reasoning as Press |
| Orchestrator (parallel fan-out + merge) | Highest payoff (this is Pipelex's core sell) but also highest risk — it's the backbone; don't touch it until the smaller pieces have proven the tool out |
| Frontend | Not relevant |

Sequencing: build Press Agent + Scoring rationale in plain Python first (per §8), since that must work regardless. Once solid, give whoever has spare bandwidth a **strict 1-2 hour timeboxed spike** porting just those two steps to Pipelex. If it clicks cleanly, extend to the orchestrator on day 2 morning. If you're still fighting the DSL past the timebox, abandon it — no sunk-cost continuation — and stay on plain Python. This has not been hands-on tested against Pipelex's actual docs (only their public marketing pages), so validate "how do I wrap a custom REST call" early if pursuing this — that's the detail most likely to eat the timebox.

**Dust** — a no-code agent-orchestration platform with strengths in connectors (Slack/Notion/Drive/GitHub) and knowledge-base-grounded chat agents. Poor fit for the core pipeline (our agents are thin wrappers around arbitrary REST APIs, not the connector-based sources Dust is built for). The one plausible value-add is additive, not a replacement: a bonus "chat with your shortlist" agent layered on top of the already-computed ranked results (export the ranked CSV, let Dust index it, let a judge ask it questions live during the demo). Attempt this only on day 3 afternoon, only after the core demo is fully locked and cached, and only if someone has spare capacity — treat it as fully expendable.

## 14. Known limitations to state up front in the pitch (this is a strength, not a weakness, in front of judges)

- No LinkedIn scraping — against ToS, fragile to build against in a weekend; we lean on public registries, news search, and filings.
- Press coverage is structurally sparse for small SMEs — most 10-50 employee companies never appear in national news. The scorecard treats this as neutral, not negative, and the pitch should say so explicitly rather than let a judge discover it.
- This augments an analyst's judgment; it does not replace one. The scorecard is a lead-generation and prioritization tool, not a transaction-ready diligence report.
- Demo is scoped to one sector/region/size slice with real data; the architecture generalizes to other slices and, with a different registry, other markets — but that generalization is not what's being demonstrated live.
