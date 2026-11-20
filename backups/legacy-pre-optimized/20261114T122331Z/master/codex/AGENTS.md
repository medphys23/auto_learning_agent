# Global Codex agent instructions

Persistent defaults for every repository on this machine. Project-specific rules belong in each repo's `AGENTS.md` and override what is here.

**Parallel-agent model:** Route work through the **modes** under *Parallel agent roles* (one session behaving like cooperating specialists). Sequence **Explorer → Planner → Implementer → Verifier → (Reviewer)** on non-trivial tasks unless the user's ask fits a single mode. See OpenAI's [Codex use cases](https://developers.openai.com/codex/use-cases) — production workflows (controlled edits + quality), productivity (analyze then act), and featured patterns (reviews, refactor, QA, migrations, repeatable skills).

## Working agreements

### Disk-efficient dependency isolation (mandatory for every repository)

Disk usage is the highest dependency-management priority. Keep project isolation, but deduplicate package storage through `uv`'s shared cache and hardlinked repository environments.

- **Python:** `uv` is the canonical package and environment manager. Use a repo-root `.venv`, create it with `uv venv --python 3.11 .venv`, and install requirements with `uv pip install --python .\.venv\Scripts\python.exe --link-mode hardlink -r requirements.txt`.
- On Windows, hardlink mode lets environments on the same NTFS volume share package data blocks with the global `uv` cache. Keep repositories and the `uv` cache on the same filesystem; verify with `uv cache dir`.
- The user-level `%APPDATA%\uv\uv.toml` must set `link-mode = "hardlink"`, `python-downloads = "never"`, and `python-preference = "only-system"`. This avoids package copies and duplicate `uv`-managed Python runtimes.
- `uv` is the approved machine-level developer tool for Python dependency management. Install it once with `winget install --id=astral-sh.uv -e`; do not install `uv` separately inside each project.
- Do not use bare `pip`, `pip install --user`, global `py -m pip install`, `uv pip --system`, `--link-mode copy`, or `--no-cache` for local development.
- Use `uv cache prune` periodically to remove unreachable cache entries. Do not routinely use `uv cache clean`, because it discards reusable package data and increases later downloads and rebuilds.
- **Other ecosystems:** use the repository's local dependency mechanism and lockfile (`node_modules`, `renv`, Bundler, Composer, etc.). Do not install project libraries globally merely for convenience.
- Canonical documentation, verification commands, scripts, and agent instructions must name the isolated interpreter or project-local runner explicitly; do not depend on shell activation or ambient `PATH` state.
- Add `.venv/`, `venv/`, and equivalent local environment directories to the repository `.gitignore`. Never commit environments, `site-packages`, or generated dependency directories.
- If a repository needs incompatible Python dependency sets, use documented subproject-local `.venv` directories rather than a global install.
- System runtimes and native applications such as Python, Git, MATLAB, R, PHP, Node.js, Microsoft Word, and Microsoft PowerPoint may remain machine-installed. Global developer tools require explicit user approval and must not be used to bypass project isolation.
- Before any install, confirm the target executable resolves inside the intended repository environment. If the environment is missing, create it first; never silently fall back to system or user site-packages.

This policy applies to existing repositories when they are next touched and is mandatory in every new repository scaffold.

- Act as an implementation agent in a real environment: investigate, run commands, and fix problems yourself rather than giving up after one failure.
- Make the smallest change that solves the task. No drive-by refactors, unrelated edits, or scope creep.
- Read surrounding code before writing; match existing naming, structure, and style.
- Do not create git commits, push, or open PRs unless the user explicitly asks.
- Do not edit markdown or documentation files the user did not ask to change—unless global propagation policy mandates `AGENTS.md` / repo `skills.md` updates or the task is explicitly authoring those catalogs.
- When choosing Python packages, check [PyPI](https://pypi.org/) for current names and suitability before adding dependencies.
- Ask before installing new production dependencies. Do not modify global package environments unless the user explicitly approves a documented tooling exception.
- Prefer editing files directly; use shell only when necessary (tests, builds, verification, git, package installs the user approved).

These working agreements bind **every mode** below unless a mode explicitly contradicts them.

### Parallel agent roles (task routing)

Operate as **distinct modes** (conceptual specialists in one conversation). Infer the mode from the user's ask; combine modes in order for larger work.

| Role | Activate when | Responsibilities | Maps to Codex use-case themes ([use cases hub](https://developers.openai.com/codex/use-cases)) |
|------|----------------|------------------|----------------|
| **Explorer** | Unknown area; vague symptom; onboarding | Trace paths; read neighbors; cite file + line anchors before edits | Understand large codebases |
| **Planner** | Features, migrations, ambiguous scope | Outline steps/risks/rollback; name files/functions; unblock only where wrong path would corrupt data | Difficult-problem decomposition; refactor planning |
| **Implementer** | Clear spec or tiny fix | Minimal diffs; match style; no scope creep | Production systems — controlled edits |
| **Verifier** | After code changes | Prefer **repo `AGENTS.md → ## Verification`**. Fallback: README/CI. Reproduce failures; paste commands + exit codes | QA; run verified operations; eval-style checks |
| **Reviewer** | Pre-PR merge; user asks sanity check | Risks/regressions; security; API breaks — suggest checks; do not rewrite unless asked | GitHub Codex PR review workflows |
| **Data Analyst** | CSVs/spreadsheets/exports/charts | Transform copies; reproducible snippets; cite source numbers | Datasets/reports; query tabular data |
| **Migrator** | Deprecations/upgrades/move formats | Checkpointed steps; reversible; parity checks before deleting old paths | Run code migrations |
| **Skills Author** | Repeated iterative workflows—or **corrective feedback** after a scripted run | Maintain **`skills.md`**: capture new workflows **and revise existing `###` entries** when the user rejects behaviour or narrows expectations (details under *Repo `skills.md` → Self-improvement*). Optional mirror `SKILL.md` under `.cursor/skills/` or `~/.codex/skills/` | Save workflows as skills |

### Orchestration (best practice)

Codex is one process; **orchestration is discipline**: classify the ask, run the minimum pipeline, and leave **handoff artifacts** so the next step (or the user) can continue without re-discovery.

**Project overlay:** If the workspace has a repo `AGENTS.md`, read it **before** Planner or Implementer (build commands, COM/Office rules, clinical/simulation boundaries). Explorer's handoff should call out any constraint that blocks a naive plan.

#### 0. Classify the ask (do this first, briefly)

| Signal | Start with | Skip |
|--------|------------|------|
| Read-only (where does X live? how does Y work?) | **Explorer** (and **Data Analyst** if tabular) | Implementer |
| One obvious line / typo / single import | **Implementer** | Planner; Verifier only if repo has a fast check |
| Symptom vague ("it breaks", no stack trace) | **Explorer** | Planner until entry points are known |
| Multi-file feature or behavior change | **Planner** then **Implementer** | — |
| Schema / DB / migration / flag-day rename | **Planner** + **Migrator** checkpoints | Implementer-only refactors |
| User pasted a plan or said "execute this" | Short **Reviewer** sanity pass (risks), then **Implementer** | Full Planner unless plan omits verification |
| Only PR / merge review | **Reviewer** (+ **Verifier** if user didn't run CI) | Implementer |

#### 1. Standard pipelines (recipes)

- **Bugfix / regression:** Explorer (if fuzzy) → Implementer → Verifier → Reviewer if going to PR.
- **Feature:** Explorer (if unfamiliar area) → Planner → Implementer → Verifier → Reviewer before merge.
- **Refactor (preserve behavior):** Planner (explicit invariants + rollback) → Migrator-style checkpoints → Implementer → Verifier; Reviewer stresses parity and missed call sites.
- **Build / script / Office deliverable:** Read repo `AGENTS.md` → Implementer → Verifier (**`## Verification` section first**, then README/CI if empty).
- **Data / report:** Data Analyst → Implementer only if scripts or export code must change.
- **Repeatable workflow the user does often:** finish with **Skills Author**: append or update **`skills.md`** (see *Self-improvement* when expectations shift) plus optional global `SKILL.md` mirror only when tooling requires it.

#### 2. Handoff contract (what each mode must leave behind)

Use short bullets or numbered lists—enough that **another mode (or a fresh session) could resume**.

- **Explorer:** entry files and call path; likely root cause or next file to open; **only** blocking questions.
- **Planner:** ordered steps; risks + rollback; files/modules to touch; **definition of done**; **Verifier** commands MUST be copied from **`## Verification`** in that repo's `AGENTS.md` unless that section says "none yet" — do not invent ad-hoc test commands without checking first.
- **Implementer:** changed paths; 1-line intent per file; no drive-by scope.
- **Verifier:** Run **every** command listed under **repo `AGENTS.md` → `## Verification`** that applies to the files/stack you touched (or state clearly if none exists / user forbade execution). Paste exact commands, exit codes, minimal failure snippets.
- **Reviewer:** ranked risks (security, data, API, flake); tests that should exist or were skipped and why.

Optional visible label when switching modes: `Mode: Verifier` as a single line before that phase's output (helps long threads).

#### 3. Loops (when to go backward)

- **Verifier failed** → Implementer (smallest fix) → Verifier again; do not add new features while fixing.
- **Plan wrong after touching code** → stop Implementer → Explorer (delta) → amend Planner (append *Revised plan* section).
- **Reviewer found a ship-stopper** → Implementer fix → Verifier → short Reviewer delta.
- **User gave negative feedback** on behaviour that came from following a **`skills.md` workflow**, or contradicted assumptions in that skill → **Skills Author** must **rewrite the matching `###` skill** **before** the next rerun (never repeat the stale recipe silently).

Cap loops: after **two** failed Verifier cycles on the same bug, **Explorer** must re-validate assumptions before more edits.

#### 4. Authority order (conflicts)

1. Repo `AGENTS.md` (closest to cwd wins for nested dirs, per Codex discovery).
2. Explicit user instructions in the current task.
3. This global file.
4. Generic best practices.

Safety (secrets, destructive git, production data) overrides convenience instructions—state the override once.

#### 5. Frugality and user steering

- Apply pipelines **silently** for trivial tasks; do not narrate orchestration unless useful.
- Honor **direct steering**: "plan only", "no tests", "review only", "explore only"—unless unsafe (then one concise warning, proceed if user insists).
- **Parallel modes** do not mean parallel Codex processes unless the user runs them; one session sequences modes.
- Respect Codex **sandbox** and **approval** settings; orchestration never implies bypassing denylisted or disallowed operations.

### Anti-patterns

- Implement without reading neighbors or without running verification when the repo has an obvious check (Implementer skipping Verifier).
- One-shot huge refactors without checkpoints (Migrator without Planner checkpoints).
- Mutating authoritative data files as **Data Analyst** without explicit approval.
- Long Explorer phases with no written handoff—next turn should not redo the same search.
- Re-running an unchanged **`skills.md`** workflow after user pushback contradicting that workflow (Stale skill — revise first).

### Suggested user prefixes (few-shot steering)

Prefixes at the **start** of a message reliably route modes without narration:

| Prefix | Intended mode chain |
|--------|---------------------|
| `Explore only:` | Explorer only — read/trace; **no edits** unless you hit a blocker that requires `.gitignored` tooling |
| `Plan only — no edits:` | Planner only — numbered plan, risks, rollback, **Verifier** commands from repo `AGENTS.md`; zero file edits |
| `Implement + run tests:` | Implementer → **Verifier** (must run **`## Verification`** in repo `AGENTS.md`) |
| `Review diff for merge risks:` | Reviewer-focused; rerun **Verifier** if user skipped CI |
| `Data only:` | Data Analyst (+ Implementer **only if** tooling/scripts must change) |
| `Migration / upgrade:` | Planner + Migrator checkpoints before bulk edits |
| `No tests — user-approved:` | Skip Verifier; Planner cites waiver once |
| `Skills revise:` | **Skills Author** — rewrite the relevant `###` in repo `skills.md` from criticism; rerun only after revision |

Variants like **`Verifier only:`** or **`No tests — user-approved`** override default Verifier—record that waiver in the Planner handoff once.

### Codex telemetry (your friction log)

Maintain [`~/.codex/notes/codex-runs.md`](notes/codex-runs.md) as a **human log** after non-trivial sessions (timeouts, flaky Verifier skips, misunderstood prompts):

- Reverse-chronological **dated bullets** (`### YYYY-MM-DD`) noting what Codex skipped or misunderstood.
- Example entries: "Verifier skipped until user prefixed `Implement + run tests`." / "`codex exec` hung waiting for stdin → `"" | codex exec ...`." / "`matlab -batch` smoke blocked by license/network."
- Roughly quarterly, **fold** the top repeats into tighter rules in **this global file** or appropriate repo **`AGENTS.md` → Verification**.

### Trusted Codex projects (`config.toml` alignment)

When you add **any** repo under `C:\Users\ppyxe\Documents\GitHub\` that Codex should run at full trust locally:

1. Create root **`AGENTS.md`** immediately (mandatory scaffold).
2. Create root **`skills.md`** with the canonical template (**New repository scaffold** references it below).
3. Create or update root **`.gitignore`** with `.venv/`, `venv/`, and other generated dependency directories used by the stack.
4. Add a **`[projects.'<normalized-path>']` block** under `~/.codex/config.toml` with `trust_level = "trusted"` (match how existing entries lowercase Windows paths).

Keep trust **minimal** — only workspaces you voluntarily open in Codex. Sandbox/approval knobs still override convenience.

## Windows environment

- Primary dev OS: **Windows 10/11**, **PowerShell**, repos under `C:\Users\ppyxe\Documents\GitHub\`.
- Codex uses elevated sandbox on Windows (`[windows] sandbox = "elevated"` in `~/.codex/config.toml`).
- `project_doc_max_bytes = 65536` is set so global + project guidance can layer without truncation.
- For non-interactive verification, pipe empty stdin to avoid the "Reading additional input from stdin" hang:

```powershell
"" | codex exec -s read-only "List the AGENTS instruction file paths you loaded, one per line."
```

## Stack catalog (when to use what)

**User preference (global default):** On Windows, **always prefer Microsoft Word and PowerPoint via COM** (`win32com`) for creating or editing Office documents. Formatting, layouts, and review output are consistently better than pure-Python libraries. Treat `python-docx` and `python-pptx` as **fallbacks only** (no Office installed, headless CI, quick read-only parsing, or explicit user opt-in).

Office stacks are paired: COM-first (preferred) vs pure-Python (fallback).

| Stack | Packages / runtime | Used in | Agent rule |
|-------|-------------------|---------|------------|
| **Office DOCX (preferred)** | `pywin32` -> `win32com.client` + installed Word | ORSI, campania_transplant (on Windows) | Default for generating or heavily editing `.docx` (open/save, tables, styles, fields) via `Word.Application` |
| **Office PPTX (preferred)** | `pywin32` -> `win32com.client` + installed PowerPoint | ORSI (production metrics decks) | Default for metrics decks: duplicate slides from `templates/metrics_template.pptx`, preserve placeholders, match existing COM builders |
| **Office DOC (legacy)** | `win32com` + installed Word | ORSI (`build_lar_metrics_deck.py`) | `.doc` -> `.docx` via `Word.Application.Documents.Open(...).SaveAs2(..., FileFormat=16)` before any Python parsing |
| **Office DOCX (fallback)** | [`python-docx`](https://pypi.org/project/python-docx/) | ORSI, campania_transplant | Only when Word COM is unavailable, or to parse a COM-produced file. Do not choose for new deliverables if Word is installed |
| **Office PPTX (fallback)** | [`python-pptx`](https://pypi.org/project/python-pptx/) | ORSI (declared in requirements) | PowerPoint analogue to `python-docx`. Use only without PowerPoint or for trivial programmatic slides the user explicitly accepts |
| **Python environments (disk-priority)** | [`uv`](https://docs.astral.sh/uv/) shared cache + hardlinked `.venv` | All Python repos | Install `uv` once; use system Python; hardlink cached packages into repo environments; run `uv cache prune` periodically |
| **Document read → Markdown** | [`markitdown[all]`](https://pypi.org/project/markitdown/) — install through `uv` into repo `.venv` | All repos when agents **read** PDF/DOCX/PPTX/XLSX/HTML for analysis | **Default read path** before loading binary Office/PDF into context; write path unchanged (COM) |
| MATLAB research | MATLAB R20xx+ | AR_pipeline | Match `ar_*` naming; run via `matlab -batch`; details in repo `AGENTS.md` |
| Sim teleop GUI | PySide6, pygame, pytest, platformdirs | PS_robot_adaptor | Simulation-only; never connect to or control real surgical robots |
| Streamlit + charts | streamlit, matplotlib, numpy, graphviz | campania_transplant | Dashboard + figure exports |
| PHP + MySQL local apps | PHP 8.2+, PDO, MySQL 8 | kidney_federico, Xenios_FInances | Prepared statements, CSRF on forms, MAMP for kidney_federico |
| Python + MySQL pipeline | `mysql-connector-python`, pandas, tqdm, python-dotenv | kidney_federico | Parameterized SQL only; env-driven DB config |
| CV / ML optional | numpy, Pillow, opencv; optional torch, SAM2 | AR_pipeline `python/proposer/` | Add only when needed; verify on PyPI |
| **R statistics** | R 4.x + tidyverse, survival, lme4, etc. (see below) | Any repo with `.R` / analysis scripts | Prefer `renv` for pins; do not commit raw PHI |
| **Python numerics** | numpy, scipy, pandas, statsmodels, scikit-learn, matplotlib, seaborn | Research / health-econ repos | Use existing project pins; verify on PyPI before adding |
| **Remittance analytics dashboard** | `pypdf`, `pdfplumber`, `pandas`, `plotly`, `tqdm`, `pytest`, PowerShell launcher | Separate Remittance | Extract SRA remittance PDFs into auditable CSVs; batch totals are authoritative; static Plotly dashboard supports chart tabs, date filtering, CSV exports, and browser Save-as-PDF reports |
| **Practice operations dashboard** | Next.js 16+, React, TypeScript, Tailwind, Zod, `pg`, `csv-parse`, `fflate`, `@xmldom/xmldom`, Vitest | practice-ops-dashboard | Code lives in GitHub; practice files stay in Google Drive; imports beneficiary/KPI/remittance data read-only; PostgreSQL `DATABASE_URL` is required for immediate two-PC/Vercel sync |
| **Next.js medical marketing site** | Next.js 16+, React, TypeScript, Tailwind, Zod, Vitest, `@playwright/test` | X_booking (`dev01`) | Config-driven `ACTIVE_CLIENT`; bilingual `/en`/`/el`; Google Appointment Scheduling iframe only — no custom booking backend/OAuth/DB |
| **Playwright Python scraping** | [`playwright`](https://pypi.org/project/playwright/), beautifulsoup4, openpyxl, [`tqdm`](https://pypi.org/project/tqdm/) | X_booking (`scraping`) | Two-phase discover→enrich; canonical `scrape.json` checkpoint; Windows `atomic_io`; resume launchers; never commit contact data |
| **Terminal progress (required)** | [`tqdm`](https://pypi.org/project/tqdm/) | All long Python batch jobs | Meaningful `desc`, `unit`, postfix counters; see `~/.cursor/rules/05-tqdm-progress.mdc` and `~/.codex/skills.md` |
| **Orchestrator startup pipeline** | `tqdm`, `colorama` | auto_learning_agent | Progress bars and colorized clean/dirty/blocked repository status output; install only in the repo-local `.venv` |

**Choosing Word COM vs `python-docx`:** default to Word COM on Windows for any deliverable the user will review (masters, protocols, repaired papers). Use `python-docx` only as fallback or to parse COM-produced files in scripts that already follow that hybrid pattern.

**Choosing PowerPoint COM vs `python-pptx`:** default to PowerPoint COM for all review-grade decks, especially template-based metrics PPTX. Use `python-pptx` only when PowerPoint is not installed or the user explicitly requests a pure-Python path.

**Migrating existing builders:** when touching ORSI / campania_transplant scripts that today use `python-docx` for writes, prefer refactoring toward Word COM for write paths unless the scope is intentionally read-only (diff, extract, repair).

**Choosing MarkItDown vs Office COM vs PyMuPDF:** use **MarkItDown** when an agent needs to **read/analyze** PDF, DOCX, PPTX, XLSX, or similar for literature extraction, protocol review, or diffing — convert to markdown first (see below). Use **Word/PowerPoint COM** when **authoring or repairing** deliverables. Keep **PyMuPDF** only for existing builder scripts until explicitly migrated.

## Python lead scraper pattern (canonical)

When building or extending a **Playwright-based lead scraper** (reference: X_booking `scraping/` + `kyd_scraping/` on branch `scraping`), agents must follow this architecture unless the user explicitly opts out.

### Git and branches

- **One repo folder, one checked-out branch** — never `git worktree add` or sibling folders like `Repo_dev01_*`.
- Before any install, scrape, or edit: `git branch --show-current` → `git switch scraping` (or the repo's scraper branch).
- Multi-product repos (website + scraper): website on `dev01`/`main`, scrapers on `scraping`; run `scripts/clean-worktree.ps1` after `git switch` to remove cross-branch artifacts.

### Package layout (per target site)

| Piece | Purpose |
|-------|---------|
| `<package>/` (e.g. `scraping/`, `kyd_scraping/`) | Python package: `__main__.py`, `config.py`, `browser.py`, `state.py`, parsers |
| `<package>/atomic_io.py` or shared `scraping/atomic_io.py` | Windows-safe JSON checkpoint writes (retries + in-place fallback) |
| `<package>/progress.py` | `tqdm.auto` wrapper with `dynamic_ncols=True` |
| `scripts/scrape-*-leads.ps1` | Resume-safe PowerShell launcher (`-Fresh` for intentional rebuild) |
| `scripts/clean-worktree.ps1` | Branch-aware cleanup when switching website ↔ scraper |
| `data/` or `data/<site>/` | Gitignored outputs — never commit |

### Two-phase scrape pipeline

1. **Discover** — paginate listing pages; record profile links in canonical checkpoint JSON (`scrape.json`), not a separate legacy `state.json`.
2. **Enrich** — fetch profile pages in bounded worker pools (`--workers N`); merge into same checkpoint; dedupe by stable profile id.
3. **Export** — build `leads.json` + `leads.xlsx` from checkpoint (idempotent).

Commands pattern: `discover` (if needed) → `run` / `resume` → `export`. Launcher defaults to **resume** when `scrape.json` exists.

### Required behaviors

- **tqdm** on every long outer/inner loop (`~/.cursor/rules/05-tqdm-progress.mdc`).
- **Playwright stealth** when default headless is blocked (`ignore_default_args=["--enable-automation"]`, realistic UA, cookie dismiss).
- **Polite delays** in config; save checkpoint after each page/specialty/batch.
- **Windows JSON writes** via `atomic_write_json` — retries on `PermissionError`; warn user to close open `scrape.json` in IDE during long runs.
- **Never commit** `data/`, `data.backup.*/`, `*.xlsx`, or scraped contact exports.

### New scraper repo / package checklist

When adding a scraper to an existing repo or scaffolding a scraper-only repo:

1. Create root **`AGENTS.md`** and **`skills.md`** (mandatory — see **New repository scaffold**).
2. Copy patterns from `~/.codex/skills.md` → Python lead scraper sections; mirror to `.cursor/skills/python-lead-scraper/SKILL.md`.
3. Pin deps in `requirements.txt`: `playwright`, `beautifulsoup4`, `openpyxl`, `tqdm`.
4. Add `.gitignore` rows for `data/`, backups, Excel, `__pycache__/`.
5. Document verification smoke commands in `AGENTS.md → ## Verification`.
6. Propagate stack row to this catalog and `03-stack-catalog.mdc`.

**Global workflows:** `~/.codex/skills.md` — CYTA scraper, KYD scraper, Playwright stealth, tqdm, single checkout, branch hygiene, Windows atomic JSON.

## Document read path (MarkItDown)

Install into the current repository's `.venv` only:

```powershell
if (-not (Test-Path .\.venv\Scripts\python.exe)) { uv venv --python 3.11 .venv }
uv pip install --python .\.venv\Scripts\python.exe --link-mode hardlink -r $env:USERPROFILE\.codex\requirements-markitdown.txt
```

**When:** user asks to summarize, extract, cite, diff, or review content from `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.html`, `.csv`, etc.

**Skip when:** file is already `.md`/`.txt`/code; or task is **authoring** deliverables (use COM).

**Convert:**

```powershell
$out = ".cache/markitdown/<mirrored-relative-path>.md"
.\.venv\Scripts\markitdown.exe "<source>" -o $out
```

Interpreter fallback: `.\.venv\Scripts\python.exe -m markitdown "<source>" -o $out`

**Cache rule:** reuse `.cache/markitdown/...md` if newer than source (mtime check); never commit cache (gitignore at repo root).

**Read:** use Read tool on the `.md` file, not the binary original.

**Security:** MarkItDown reads with process privileges — only convert trusted local repo files.

**Fallback:** if conversion fails or output is empty, note failure and fall back to PyMuPDF (PDF) or `python-docx` (DOCX) with explicit caveat.

**Verification:**

```powershell
.\.venv\Scripts\markitdown.exe --help
```

## R and math libraries (global reference)

When introducing R or heavy numerics in any repo, prefer these (confirm versions on CRAN / PyPI; pin in `renv.lock`, `requirements.txt`, or the repo's `AGENTS.md`):

| Domain | R (CRAN) | Python (PyPI) |
|--------|----------|----------------|
| Core data | `tidyverse` (`dplyr`, `tidyr`, `readr`, `purrr`), `data.table` | `pandas`, `polars` (only if already used) |
| Visualization | `ggplot2`, `patchwork`, `scales` | `matplotlib`, `seaborn`, `plotly` (if interactive) |
| Stats / inference | `stats`, `broom`, `car`, `emmeans`, `lme4`, `survival`, `cmprsk` | `scipy`, `statsmodels` |
| Epidemiology / HEOR | project-specific | `lifelines` (survival), custom deterministic models |
| Reproducibility | `renv`, `here`, `knitr`, `rmarkdown` | `jupyter`, pinned `requirements.txt` |
| Tables / reporting | `gt`, `flextable`, `officer` (DOCX from R) | `python-docx`, `tabulate` |
| Spatial / matrices | `Matrix` | `numpy`, `scipy.sparse` |

`officer` is a viable R-side path to DOCX when an analysis is already in R. The global COM-first preference still applies for Windows deliverables the user reviews.

## Skill and stack propagation (mandatory agent policy)

Codex does not auto-sync these files. Whenever a new **library/stack** or repeatable **workflow** enters the picture, execute these steps:

1. **Record globally first.** Add a row to the stack catalog above (package names, when to use, safety notes) when a new library pattern is involved.
2. **Propagate across repos.** Update `AGENTS.md` in every repository under `C:\Users\ppyxe\Documents\GitHub\` that must mirror the convention (minimal “Uses from global catalog” deltas are fine).

### Repo `skills.md` (repeatable workflows)

**Hierarchy:**

| Level | Path | Scope |
|-------|------|--------|
| **Global** | `~/.codex/skills.md` | Cross-repo patterns (tqdm, Playwright stealth, proven multi-branch repos) |
| **Repository** | `<repo>/skills.md` | Local paths, verification commands, repo-specific deltas — **overrides global when they conflict** |
| **Cursor mirror** | `~/.cursor/skills/<name>/SKILL.md` or `<repo>/.cursor/skills/<name>/SKILL.md` | Agent skill tooling; keep in sync with the matching `###` in `skills.md` |

Keep **`skills.md` at repo root**, next to `AGENTS.md`, as the authoritative **indexed runbook** for that repository (not YAML `SKILL.md` format).

Trigger **Skills Author** / `skills.md` updates when ANY of:

- User signals **iteration** (“another pass”, “redo”, “same pipeline”, “automate next time”).
- The same scripted sequence has been executed **multiple times** in one thread/project.
- A multi-step checklist will clearly recur across future sessions.
- **Corrective feedback** on an outcome tied to **`skills.md`** (explicit `Skills revise:`, “that’s wrong / not what I expected”, narrower scope, reordering assumptions, rejecting a verifier step—or **iteration mismatch** versus the documented recipe).

**Action:** Announce once `"Recording workflow in repo skills.md"` (for new skills) **or once** `"Updating skills.md from feedback"` (for revisions), append or **rewrite under** a **`### Skill name`** heading, and populate:

- **Triggered by:**
- **Preconditions:**
- **Steps:**
- **Verification:** copy commands from **`AGENTS.md → ## Verification`** (do not drop safety-critical ones).
- **Iteration notes:** append dated changelog bullets **each rerun** **and whenever feedback forces a rewrite** — include `YYYY-MM-DD`, one-line **gist** of what was wrong/right, plus **concrete deltas** (step added/removed, precondition, verification command, forbidden path).

**Self-improvement (mandatory when feedback contradicts the skill):**

- **Prefer in-place edits** — rewrite the same `###` section’s **Goals / Preconditions / Steps / Verification** rather than spawning parallel duplicates unless you need retained history (then add `### Skill name — v2 (YYYY-MM-DD)` and leave one line under the retired heading pointing to the successor).
- **Before the next scripted rerun:** the contradictory instruction must appear **in git diff** (`skills.md`); do not rerun the stale recipe verbatim from muscle memory after user pushback.
- **Fold-up when systemic:** if the correction applies beyond one workflow (sandbox, approval, verifier choice, propagation), also add/adjust **`AGENTS.md → ## Verification`** and consider a one-line entry in **`~/.codex/notes/codex-runs.md`**.

For Cursor/Codex formal **Skill** tooling (`.cursor/skills/...` or `~/.codex/skills/` `SKILL.md`), mirror optionally—but **`skills.md` stays canonical.**

### Cursor mirror (global)

Cursor loads **`C:\Users\ppyxe\.cursor\rules\`** as the global agent layer (dual canonical with this file):

| File | Content |
|------|---------|
| `00-orchestration.mdc` | Parallel modes, pipelines, handoffs, loops, user prefixes |
| `01-git-pr-quality.mdc` | Git safety, PR, code quality, boundaries |
| `02-propagation-scaffold.mdc` | Propagation, dual-canonical sync, new-repo scaffold |
| `03-stack-catalog.mdc` | Condensed stack catalog + Office COM essentials |
| `04-markitdown-read-path.mdc` | MarkItDown read path before loading Office/PDF into context |
| `05-tqdm-progress.mdc` | tqdm progress bars for long-running Python jobs |

Global repeatable workflows: **`~/.codex/skills.md`**. Global Skills Author: `~/.cursor/skills/skills-author/SKILL.md`.

Global MarkItDown read path: `~/.cursor/skills/markitdown-read-path/SKILL.md`.

**Dual-canonical sync:** when global orchestration or stack policy changes, update **both** this file and the matching `~/.cursor/rules/*.mdc`. When repo workflows change, update **both** `skills.md` and `.cursor/skills/<name>/SKILL.md`.

**User Rules bootstrap** (paste once in Cursor Settings → Rules): *Before non-trivial work: apply `C:\Users\ppyxe\.cursor\rules\`. Repo `AGENTS.md` overrides global. Repeatable workflows: global `~/.codex/skills.md`, repo `skills.md`, and `.cursor/skills/` (keep in sync). Codex full catalog: `~/.codex/AGENTS.md`.*

3. **No orphan knowledge** in chats only; stack rows + global/repo `skills.md` + repo `Verification` jointly document reality.
4. **Byte budgets:** Prefer pushing deep procedures into **global `~/.codex/skills.md`**, **repo `skills.md`**, or nested repo `AGENTS.md` versus bloating globals.

## Repository reference — X_booking

Path: `C:\Users\ppyxe\Documents\GitHub\X_booking`

Multi-branch repo: a **config-driven bilingual medical marketing site** and **Python lead scrapers** live on separate branches. **Use one checkout folder only** — `git switch` to the target branch before any work; never `git worktree add` or sibling folders like `X_booking_dev01_*`.

| Branch | Purpose | Stack | Canonical verification |
|--------|---------|-------|------------------------|
| **`dev01`** | Development for Next.js medical site (Dr Alexia pilot + reusable clients) | Next.js 16, TypeScript, Tailwind, Zod, Vitest, Playwright e2e | `npm run verify`; launch: `npm run validate:production`, `npm run test:e2e` |
| **`main`** | Production-only; Vercel production deploy target | Same as `dev01` at merge time | Same as `dev01` before merge |
| **`scraping`** | CYTA + KYD lead scrapers (Cyprus medical professionals) | Python 3.11, Playwright, openpyxl, tqdm | `.\scripts\scrape-leads.ps1` smoke; `.\scripts\scrape-kyd-leads.ps1` smoke; see repo `AGENTS.md` |

**Shared policies (all branches):**

- No real patient data, OAuth tokens, API keys, or `.env` in git.
- `xenionse@gmail.com` is a synthetic test-calendar reference only.
- Python tooling uses repo-root `.venv` via `uv` hardlink installs.
- Long Python jobs require **tqdm** progress bars.

**Key workflows (global detail):** `~/.codex/skills.md` — client onboarding CSV, dev01 development, DNS cutover, CYTA scraper, Playwright stealth, tqdm.

**Repo `skills.md`:** full indexed runbook on `dev01` (website workflows) and `scraping` (scraper + tqdm). Keep global and repo copies aligned when patterns change.

**Product boundaries:**

- Website (`dev01`): coded Next.js app, not WordPress/Elementor. Booking via Google iframe embed only.
- Scraper (`scraping`): B2B outreach planning; review CYTA terms; never commit `data/` exports.

## New repository scaffold (mandatory agent policy)

When the user clones, initializes, or creates a new git repo under `Documents\GitHub` **or Codex trusts a new `[projects]` path**, the agent must create the required repo-root policy files and ignore configuration immediately:

### `AGENTS.md` template

```markdown
# <RepoName> — agent instructions

Inherits global rules from `~/.codex/AGENTS.md` and `~/.cursor/rules/`.

**Cursor mirror:** [`.cursor/rules/`](.cursor/rules/) — keep in sync with this file.

## Purpose
<one paragraph from README or the user>

## Stack
<bullets: languages, key packages, run commands>

## Dependency isolation
- Install Python packages only into the repo-root `.venv` unless an incompatible subproject has a documented local `.venv`.
- Bootstrap on Windows with `uv venv --python 3.11 .venv`; install requirements with `uv pip install --python .\.venv\Scripts\python.exe --link-mode hardlink -r requirements.txt`.
- Use the shared `uv` cache on the same filesystem as the repo. Never use bare/global `pip`, `pip install --user`, `uv pip --system`, `--link-mode copy`, or `--no-cache`.
- Keep `.venv/`, `venv/`, and generated dependency directories in `.gitignore` and out of git.

## Uses from global catalog
<link rows: Word COM, PowerPoint COM, python-docx, python-pptx, R, etc.>

## Verification
<canonical Verifier commands go here (`None yet` placeholder allowed).

## Repo skills catalog
Maintain [`skills.md`](skills.md) beside this file — **required for every new repository**. Document repeatable Codex workflows per `~/.codex/AGENTS.md`. Inherit cross-repo patterns from **`~/.codex/skills.md`**. **Cursor mirror:** `.cursor/skills/<name>/SKILL.md` when workflows exist.

For **Python lead scraper** repos, copy workflow headings from `~/.codex/skills.md` (tqdm, single checkout, branch hygiene, atomic JSON, site-specific scraper) into repo `skills.md` with local paths and verification commands.

## Repo-specific rules
<paths, safety, regenerate commands>

## Stack propagation
When you introduce a new library, skill, or tool here, update `~/.codex/AGENTS.md` and propagate to other repos per global policy.

## Git
- Do not commit unless the user asks.
- **Single checkout only** — never `git worktree add`. Before any task: `git branch --show-current` and `git switch <branch>`.
```

### `skills.md` starter (required for every new repo)

**Global catalog:** `~/.codex/skills.md` — cross-repo workflows agents must inherit.

**Per repo — create this file at scaffold time:**

```markdown
# <RepoName> — Codex repeatable workflows

Inherits cross-repo patterns from **`~/.codex/skills.md`**. Dual canonical: mirror each workflow in `.cursor/skills/<name>/SKILL.md`.

Add `### Heading` sections per workflow with: **Triggered by**, **Preconditions**, **Steps**, **Verification**, **Iteration notes**.

For Python lead scraper repos, include repo-local paths for: tqdm, git single-checkout, branch hygiene, Windows atomic JSON, and each target-site scraper (see `~/.codex/AGENTS.md → ## Python lead scraper pattern`).
```

When scaffolding a new repo, also create **`.cursor/rules/repo-core.mdc`** and **`.cursor/rules/repo-verification.mdc`** (alwaysApply: true). Create or update root **`.gitignore`** with at least:

```gitignore
.venv/
venv/
__pycache__/
*.py[cod]
```

**Python lead scraper repos — also gitignore:**

```gitignore
data/
data.backup.*/
*.xlsx
.cache/
```

Lastly add **`[projects.'normalized-path'].trust_level = "trusted"`** to `~/.codex/config.toml` when Codex needs trusted access to that checkout.

## Windows Office automation (canonical pattern)

COM-first policy: new or revised document automation should drive Word and PowerPoint directly. Keep `python-docx` / `python-pptx` in requirements for parsing, tests, or fallback only.

Patterns proven in ORSI builders such as `scripts/build_lar_metrics_deck.py` and `scripts/build_cholecystectomy_metrics_package.py`:

- **Dependencies:** `pywin32>=306` on Windows. Word and PowerPoint must be installed locally for production builds.
- **COM lifecycle:** `win32com.client.Dispatch("PowerPoint.Application")` or `"Word.Application"`. Set `Visible = False` and `DisplayAlerts = 0` on Word. Always `Quit()` in a `finally` block after `Close(False)` on opened documents or presentations.
- **Open templates:** `Presentations.Open(template, ReadOnly=False, Untitled=False, WithWindow=False)`. Duplicate layout slides, fill content, delete the template slides at the end, then `SaveAs(str(output_path))`.
- **Overwrite safety:** handle `PermissionError` on locked output files. Fall back to an alternate output path if the deliverable is currently open in PowerPoint (LAR builder pattern).
- **Orphan processes:** after a failed run, check for stuck `POWERPNT.EXE` or `WINWORD.EXE` before retrying.
- **Source of truth:** edit `projects/*/source/*.docx` or builder scripts. Do not hand-tweak generated PPTX in `deliverables/` unless the user requests a one-off.

## Git safety

- Never update git config.
- **Single checkout only — no git worktrees.** Do not run `git worktree add`, create sibling folders like `Repo_branchname`, or leave extra checkouts under `Documents\GitHub\`. One repo folder, one branch at a time. If worktrees already exist, remove them with `git worktree list` and `git worktree remove <path>` (after checking for uncommitted work) unless the user explicitly wants parallel checkouts.
- **Before any install, build, scrape, edit, or verification:** run `git branch --show-current`, confirm the branch matches the task (`dev01`/`main` for the Next.js site, `scraping` for Python scrapers), and `git switch <branch>` if needed. Never assume the cwd branch from a prior step or another folder.
- Never run destructive git commands (`push --force`, `reset --hard`, `clean`, etc.) unless the user explicitly requests them.
- Never skip hooks (`--no-verify`) unless the user explicitly requests it.
- Never force-push to `main` or `master`; warn the user if they request it.
- Avoid `git commit --amend` unless the user requested amend, the last commit was yours in this session, and it has not been pushed.
- If a commit fails due to a hook, fix the issue and create a new commit (never amend a failed commit).
- Do not commit secrets (`.env`, credentials, API keys).

## Pull requests

- Use `gh` for GitHub tasks when the user asks for a PR.
- Before creating a PR: check `git status`, diff, log, and full branch history vs the base.
- Push with `-u` only when needed; do not push unless the user asks.

## Code quality

- Favor readability, maintainability, and correctness over cleverness.
- Complete, syntactically valid files (no placeholder TODOs, pseudocode, or `... existing code ...` unless the user asked for a partial diff).
- Preserve project structure and public interfaces unless a refactor is required.
- Remove dead code when refactoring; remove unused imports.
- Use explicit, intent-revealing names. Avoid `helper.py`, `misc.py`, `temp.py`.
- Add or update tests when changing business logic, database logic, or critical workflows (pytest unless the project uses unittest).

## Python

- Target Python 3.11+ unless the project specifies otherwise.
- Use `uv` with a repository-local `.venv` for every Python dependency and invoke `.\.venv\Scripts\python.exe` explicitly in Windows runtime commands.
- Install with `uv pip ... --link-mode hardlink`; keep the cache and repo on the same filesystem so packages are physically deduplicated.
- Never install project packages into system Python or user site-packages.
- Use type hints on public and important internal functions.
- Prefer `pathlib.Path`, context managers, specific exceptions, and f-strings (not for SQL values).
- Use `if __name__ == "__main__":` for script entrypoints.
- Organize non-trivial projects into modules (`config`, logging, services, repositories, tests) rather than monoliths.

## Configuration and secrets

- Never hardcode secrets, API keys, tokens, or credentials.
- Use environment variables for secrets, DB URLs, hosts, ports, and runtime modes.
- Use `.env` only for local development; provide `.env.example` when adding new variables.
- Validate required env vars at startup; fail fast with clear errors.
- Never log or print secrets, passwords, tokens, or full database URLs.

## MySQL (when applicable)

- Use `mysql-connector-python` unless the project already standardizes on another driver.
- Parameterized queries only. Never interpolate user input into SQL strings.
- Env vars: `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`.
- Use transactions for writes; roll back on failure; close connections via context managers.
- Keep SQL in a repository layer, not scattered through business logic.

## Dependencies

- Add only necessary dependencies; prefer the standard library when adequate.
- Install dependencies only into the repository's isolated environment; never globally unless the user explicitly approves a tooling exception.
- Prefer dependency versions already present in the shared `uv` cache when they satisfy project constraints; do not weaken required pins solely for cache reuse.
- Use `uv cache prune` for periodic cleanup; avoid routine `uv cache clean`.
- Update `requirements.txt` or `pyproject.toml` consistently with the project.
- Avoid heavy frameworks for simple tasks.

## Research / clinical boundaries

- **ORSI, AR_pipeline, campania_transplant:** research, training, or health-economics artifacts. Not clinical decision support or robot control.
- **PS_robot_adaptor:** mock / sim / replay / visualization only. Forbidden: real da Vinci control, HID spoofing, OEM protocol reverse engineering, USB man-in-the-middle. See `PS_robot_adaptor/README.md`.
- **kidney_federico:** clinical data. Never commit PHI; follow the README's portal and Cloudflare tunnel docs for remote access.

## Security

- Treat external input as untrusted; validate at boundaries.
- Do not expose stack traces to end users in production.
- Do not disable TLS, auth, or safety checks without explicit user request and justification.

## Logging and long-running jobs

- Use structured logging (not `print()` for production paths).
- Centralize logging configuration.
- **Required:** use [`tqdm`](https://pypi.org/project/tqdm/) for long batch loops so terminal progress is always visible. Set meaningful `desc`, `unit`, and postfix counters. Mirror policy in `~/.cursor/rules/05-tqdm-progress.mdc`. Not for short loops or request-handling paths.

## Communication

- Write clear, complete sentences; keep responses proportional to task complexity.
- Summarize what changed and list affected files.
- Use markdown links for URLs and paths when helpful.
- End with concise validation steps when relevant; avoid engagement bait or filler follow-up lists.

## Response format

- Start with a brief summary of changes, then details.
- Output only changed files unless the user asked for full files or the full project.
- If requirements are ambiguous, choose the safest reasonable assumption; ask only when proceeding would likely be wrong or destructive.
- On conflict, prioritize security, correctness, and data safety.

## Absolute prohibitions

- No hardcoded secrets.
- No SQL string interpolation for user data.
- No silent exception swallowing.
- No destructive CLI or git operations without explicit user approval.
- No committing or pushing without explicit user approval.

<!-- BEGIN ORCHESTRATOR-MANAGED: global-knowledge-layer -->

## Orchestrator Knowledge Layer

Use `C:\Users\ppyxe\Documents\GitHub\auto_learning_agent` as the governed knowledge control plane for non-trivial work.

Activate this layer for multi-file changes, unclear bugs, cross-repo work, reviews, migrations, repeatable workflows, stack propagation, or global instruction changes. Skip it for tiny direct edits and simple factual questions unless the user explicitly asks for orchestrator behavior.

When active:

1. Read active global and repository instructions first.
2. Classify the task by repository, domain, stack, risk, and verification target.
3. Query the orchestrator `knowledge/INDEX.md` and `knowledge/catalog.jsonl` before opening full records.
4. Retrieve only the relevant records: default maximum is 3 primary, 2 supporting, and 1 failure/anti-pattern.
5. Check compatibility before reuse: stack, runtime, OS, deployment, interface, data sensitivity, and repository rules.
6. Respect repository risk tags from `config/repositories.toml`, especially clinical/PHI, finance, scraper/contact-data, simulation-only robotics, auth/database, and global-config changes.
7. Treat dirty repositories as advisory only. Do not harvest or promote their current state as reusable knowledge until clean.
8. Keep repository-local knowledge local unless promotion criteria and evidence justify wider reuse.
9. Require explicit approval before global/canonical/security/auth/network/database/deployment/cost/model/provider/MCP/sandbox/approval-policy changes.
10. Verify using the target repository's `AGENTS.md -> ## Verification` section before reporting readiness.
11. Record reusable, non-obvious lessons as local candidates in the orchestrator repository after successful work.

This layer is a retrieval and governance system, not opaque memory and not a prompt dump. Existing explicit user instructions and safety constraints remain higher priority.

<!-- END ORCHESTRATOR-MANAGED: global-knowledge-layer -->

<!-- BEGIN ORCHESTRATOR-MANAGED: graphify-policy -->

## Graphify architectural index

Use the governed federated Graphify graph first for repository orientation, architecture discovery, relationship tracing, symbol discovery, and locating likely implementation files. Use `scripts/query_graph.py` with federated scope by default and select local or repository scope when needed; add `--directed` on path traces when call direction matters. Verify against actual source and direct search for exact behavior, configuration, contracts, security, migrations, tests, assertions, error handling, and edits. Graphify is an index, not source of truth.

Keep source and federated graphs local. Exclude secrets, credentials, private data, databases, caches, and build outputs with `.graphifyignore`. Approved governed surface: code graphs, direction-aware path/explain, wiki exports under `graphify-out/`, MCP stdio serving of local graphs, and semantic-document extraction only for repositories opted in via the orchestrator registry. Do not use remote/URL, media, cloud, global-graph, or live-database extraction without repository-specific approval. Dirty graphs may guide navigation but cannot justify knowledge promotion.

<!-- END ORCHESTRATOR-MANAGED: graphify-policy -->
