# Sorena — Multi-Agent Extension (Phase 7+)

Turns Sorena from a single agent loop into a small agent team that runs your day.
This is also the highest-value interview material: "I built a multi-agent system
with an orchestrator, specialized agents, and shared memory" is exactly what
AI-engineer job posts mean by "agentic systems."

---

## 1. Architecture: Orchestrator + Specialists

Keep it simple and honest — one **Orchestrator** (router) and a handful of
**Specialist agents**, each with its own system prompt, tool subset, and memory
scope. No framework needed at first; it's your existing ReAct loop instantiated
N times with different configs.

```
                    ┌─────────────┐
   voice/text ───►  │ Orchestrator │  (intent classify + delegate + merge)
                    └──────┬──────┘
        ┌────────────┬─────┴──────┬─────────────┬─────────────┬────────────┐
        ▼            ▼            ▼             ▼             ▼            ▼
   DayPlanner    Researcher    Coach       Interviewer    Scribe      JobScout
   (calendar,    (web search,  (learning   (mock          (notes to   (daily job
   tasks,        summarize,    plans,      interviews,    Obsidian,   search, match
   reminders)    RAG on your   quizzes,    scoring,       session     scoring, gap
                 vault)        spaced      feedback)      log)        analysis)
                               repetition)
```

Design rules (these become your ADRs):
- **Orchestrator never does work itself** — it classifies intent, picks agent(s), merges replies.
- **Each specialist gets only the tools it needs** (least privilege — great interview talking point).
- **Shared memory bus**: one SQLite DB; agents write "events" (task done, quiz score, interview feedback), Orchestrator reads them for context. This is how agents "know about each other" without direct chatter.
- Start **sequential** (one agent at a time). Parallel agents only if a real need appears — resist over-engineering.

---

## 2. The five agents and your daily routine

### DayPlanner
- Morning briefing on wake word: today's calendar, top 3 tasks, weather
- "Plan my day" → time-blocks your free hours, protecting a daily AI-learning block
- Evening: asks what got done, rolls over the rest
- Tools: calendar (CalDAV/Google free tier), a tasks table in SQLite, weather API (free)

### Researcher
- "What's new in agent frameworks this week?" → searches, summarizes to 5 bullets, saves to vault
- Feeds the Coach: finds articles/papers matching your current learning topic
- Tools: Tavily free tier, web fetch, RAG over your Obsidian vault

### Coach (your AI-learning tutor)
- Holds your learning roadmap (the 6 phases) as state
- Daily: one micro-lesson + 3 quiz questions on your current phase topic
- Spaced repetition: wrong answers come back in 2 days (simple SQLite scheduler)
- Weekly: "explain X back to me" sessions — teaching-back is the fastest way to interview-readiness
- Tools: memory DB, Researcher (delegated), your vault

### Interviewer (the job-prep killer feature — see §3)

### JobScout (daily job search matched to your profile)
The agent that closes the loop: finding the jobs your learning is aimed at.

**Your profile as data, not prose** — `profile.yaml` in the repo (or private
config), the single source of truth every agent reads:
```yaml
target_roles: [AI-Native Developer, Tech Lead, AI Engineer]
skills:
  strong: [Python, FastAPI, React, n8n, MCP development, agent systems]
  learning: [LangGraph, RAG, LLM evals]   # Coach updates this automatically
location: {base: Italy, remote: preferred, hybrid: acceptable}
languages: [English, Italian]
dealbreakers: [full onsite outside Italy]
salary_floor: ...
```

**Daily pipeline (cron, ~06:30):**
1. Pull postings from free sources: Remotive + RemoteOK APIs, HN "Who is
   Hiring" (monthly), Adzuna free API (has Italy coverage), Tavily searches
   for "<role> remote Italy" — avoid scraping LinkedIn (ToS risk on a public
   project; mention that in the ADR, it reads well).
2. Dedupe against SQLite (hash of company+title+location).
3. **Match scoring** against profile.yaml — you already built multi-dimensional
   job scoring in your job-search assistant; port that logic, don't rewrite it.
4. Top 3–5 matches land in the DayPlanner's morning briefing:
   "2 new strong matches today — want the summary?"

**Cross-agent loops (this is the demo gold):**
- JobScout → **Coach**: aggregates skill requirements across this week's
  postings, diffs against profile.skills → "LangGraph appeared in 7 of 12
  matches, it's your top gap" → Coach schedules it into micro-lessons.
- JobScout → **Interviewer**: "interview me for the Milan AI Engineer posting
  from Tuesday" → Interviewer builds questions from that exact job ad.
- JobScout → **Scribe**: weekly market report to your vault (which skills are
  trending in your niche — also reusable as LinkedIn content for your brand).

### Scribe
- Every session ends with a structured note to your Obsidian vault (you already have this pattern with session-wrap — port it)
- Weekly digest: what you learned, quiz scores, interview performance trend

**A concrete day with Sorena:**
- 08:00 — wake word → DayPlanner briefing (2 min, voice)
- Learning block → Coach: micro-lesson + quiz on current phase topic
- Lunch — Researcher: "anything new on MCP today?" (voice, while cooking)
- Afternoon — build session on Sorena itself; Scribe logs it at the end
- 2–3× per week — Interviewer: 20-minute mock interview, scored
- 21:30 — DayPlanner evening review; Scribe writes the daily note

---

## 3. Interview Simulator (design)

Three sub-modes, all reusing your existing loop + one rubric:

**a) Technical screen** — Interviewer asks questions drawn from a question bank
seeded by the Researcher from real job posts (paste 3–5 job ads for your target
role; it extracts required skills and generates questions per skill).

**b) Behavioral (STAR)** — asks "tell me about a time…", listens (voice pipeline!),
then scores your answer on Situation/Task/Action/Result completeness and pushes
follow-ups on the weak part, like a real interviewer.

**c) System design lite** — "design an agent system that does X" — this is where
your Sorena build experience becomes your answer material.

Mechanics:
- **Persona prompt**: hiring manager for the exact role/company type you target; difficulty knob (friendly / neutral / stress)
- **Voice mode makes it real**: answering out loud is 10× closer to a real interview than typing
- **Scoring rubric** per answer (1–5 on correctness, depth, structure, communication) stored in SQLite → progress chart over weeks
- **Post-session report** by the Coach: 3 strengths, 3 gaps, and it schedules the gaps into upcoming micro-lessons (agents cooperating — demo gold)
- Sessions saved as transcripts → RAG lets you ask "what did I keep failing this month?"

You already have resume-* skills with question/scoring logic — port their rubrics
into the Interviewer's prompt instead of starting from zero.

---

## 4. What each piece teaches you (job-market mapping)

| Piece | Skill keyword in job posts |
|---|---|
| Orchestrator routing | "multi-agent systems", intent classification |
| Least-privilege tool scoping | AI safety/guardrails |
| Shared memory bus | agent state management |
| Coach + spaced repetition | applied product thinking with LLMs |
| Interviewer scoring rubric | LLM-as-judge, evals |
| Cross-agent handoffs (Interviewer→Coach) | agent orchestration/handoff patterns |
| JobScout pipeline | scheduled agents, data pipelines, structured extraction |
| Posting→skill-gap analysis | LLM structured output, entity extraction |

## 5. Build order (after Phase 6 of the main roadmap)
1. Orchestrator with hardcoded 2 agents (DayPlanner + Scribe) — prove routing works
2. Coach with quiz + spaced repetition (pure SQLite, no new infra)
3. Interviewer text-mode with rubric scoring
4. Interviewer voice-mode (reuses Phase 4 pipeline)
5. Researcher + cross-agent delegation (Coach asks Researcher for material)
6. JobScout: profile.yaml + one source (Remotive) + scoring, then add sources
7. JobScout→Coach gap analysis and JobScout→Interviewer "interview me for this posting"
8. Weekly digest + progress charts -- scope: Scribe's own §2 bullet only
   (what you learned, quiz scores, interview performance trend, plus
   job-match count/grade distribution since that data already exists from
   step 7). The JobScout→Scribe "weekly market report" cross-agent loop
   (§2, trending-skills-across-postings analysis) is explicitly NOT part
   of this step -- it's unscoped future work, not yet assigned a build
   step. (Resolved during the /build pass for step 8.)

Each step is a tagged release and a README GIF. By step 4 you have a demo that
almost no job applicant can show: "I practice interviews with an AI system I
built myself, end to end, by voice."
