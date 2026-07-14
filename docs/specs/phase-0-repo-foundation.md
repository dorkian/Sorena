# Phase 0 — Repo Foundation

**Status:** Complete (v0.0.1)
**Depends on:** Nothing (first phase)
**Target duration:** ½ week
**Release tag:** v0.0.1

## Goal
Set up the repo the way a senior engineer would before writing any feature code: modern packaging, CI, linting, and a spec-first docs structure. This phase produces no user-facing feature — it produces the scaffolding every later phase builds on.

## Skill learned
Professional open-source project setup. Asked about in nearly every senior/lead interview ("how do you structure a new project?") and it's the first thing a recruiter sees when they open the repo.

## Deliverables
- `pyproject.toml` using `uv` (or `poetry`) for dependency management
- `ruff` configured for lint + format, wired as a pre-commit hook
- `pytest` configured with a `tests/` folder and one passing smoke test
- `pre-commit` config running ruff + pytest (or at minimum lint) on commit
- GitHub Actions workflow: lint + test on every push/PR
- `README.md` with: project description, architecture diagram (Mermaid), quickstart commands, demo GIF placeholder
- `docs/spec/` folder established as the spec-first home (this `docs/specs/` folder already fulfills this)
- `docs/adr/` folder for Architecture Decision Records, with one seed ADR (e.g. "why uv over poetry/pip")
- `LICENSE` (MIT), `CONTRIBUTING.md`, issue templates (`.github/ISSUE_TEMPLATE/`)
- `.gitignore` appropriate for Python + local model artifacts

## Definition of Done
- [ ] `uv sync` (or `poetry install`) installs a clean environment from scratch
- [ ] `ruff check .` and `ruff format --check .` both pass
- [ ] `pytest` runs and passes with ≥1 real test
- [ ] Pushing a branch triggers CI; CI fails on a deliberately broken lint/test to prove it's wired correctly, then passes once fixed
- [ ] `git commit` triggers pre-commit hooks locally
- [ ] README renders correctly on GitHub, including the Mermaid diagram
- [ ] Repo tagged `v0.0.1`

## Efficient Learning Path
This phase is mostly configuration, not new concepts — don't over-study it, just build it once correctly and reuse the template for future projects.
- `uv` official docs "Getting Started" + "Projects" pages — the only two pages you need
- Skim one real-world `pyproject.toml` from a popular Python repo (e.g. a well-known FastAPI or CLI project) instead of reading the full packaging spec
- `ruff` docs "Configuration" page for the rule sets to enable — start with defaults, don't hand-pick 40 rules
- Copy a GitHub Actions Python CI workflow from an existing repo you trust and trim it, rather than writing one from scratch

**Methodology:** this phase rewards templating, not deep study. Build it once, save it as a personal cookiecutter/template for the next project, and move on to Phase 1 quickly — the interview value here is "I have this dialed in," not depth of packaging-tool knowledge.

## Interview line
*"I set up CI, linting, and spec-first docs before writing feature code."*
