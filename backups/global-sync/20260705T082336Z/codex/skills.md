# Global Codex repeatable workflows

Cross-repo runbook for patterns proven on this machine. **Repo `skills.md` overrides or extends** these with local paths and verification commands.

**Dual canonical (Cursor):** mirror each `###` section in `~/.cursor/skills/<name>/SKILL.md` when the workflow recurs outside one repository.

**Primary source repo:** [X_booking](C:\Users\ppyxe\Documents\GitHub\X_booking) — branch map in `~/.codex/AGENTS.md → ## Repository reference — X_booking`.

---

### tqdm progress bars (required)

**Triggered by:** Any long-running Python script, scraper, batch job, migration, or data pipeline; or when the user asks to **see progress always**.

**Preconditions:**

- Add [`tqdm`](https://pypi.org/project/tqdm/) to project `requirements.txt` / `pyproject.toml`.
- Prefer a small helper (e.g. `progress.py`) wrapping `tqdm.auto` with `dynamic_ncols=True`.

**Steps:**

1. Identify outer loops (specialties, files, epochs) and inner loops (pages, rows, profiles) that run longer than ~30 seconds.
2. Wrap each with `tqdm(..., desc="...", unit="...")`.
3. Update postfix with live counters (`unique`, `indexed`, `page`, truncated current label).
4. Nested bars: inner `leave=False`; keep the outer bar visible.
5. Do not rely on sparse `print()` alone for multi-minute jobs.

**Verification:** Run the job; confirm bars advance for the full duration.

**Global policy:** `~/.cursor/rules/05-tqdm-progress.mdc`, `~/.codex/AGENTS.md → ## Logging and long-running jobs`.

**Cursor mirror:** [`~/.cursor/skills/tqdm-progress/SKILL.md`](~/.cursor/skills/tqdm-progress/SKILL.md)

**Iteration notes:**

- 2026-06-20 — User requirement; wired into X_booking CYTA scraper and global Cursor rule.

---

### Separate Remittance dashboard

**Triggered by:** Viewing, refreshing, extending, or troubleshooting the Separate Remittance SRA PDF revenue dashboard.

**Preconditions:**

- Project path: `G:\My Drive\Alexia_Eleftheriadou_Practise_documents\Separate Remittance`.
- Use the repo `.venv` via `uv`; do not use global Python packages.
- Source PDFs live in `20??` year folders and SRA remittance PDFs are the canonical trend source.
- The FY2025 supplier statement and formal audit memo are supporting documents, not all-year trend inputs.

**Architecture:**

- `pypdf` extracts payment date, cheque number, supplier number, and authoritative batch total.
- `pdfplumber` extracts invoice rows from word positions instead of `extract_tables()`.
- `pandas` writes auditable processed CSVs under `data/processed/`.
- `plotly` builds `dashboard/remittance_dashboard.html` with chart tabs, date filtering, CSV exports, and print-ready PDF report generation.
- `tqdm` is available for long batch loops; `pytest` verifies parsing, normalization, and dashboard output.
- `scripts/start-dashboard.ps1` scans year folders, auto-normalizes filenames, extracts, rebuilds, serves locally, and opens the latest dashboard.

**Steps:**

1. Work from the repo root.
2. Prefer one-command viewing:

```powershell
.\scripts\start-dashboard.ps1
```

3. Use the non-interactive path for verification or Codex runs:

```powershell
.\scripts\start-dashboard.ps1 -NoOpen
```

4. Manual rebuild path when inspecting intermediate outputs:

```powershell
.\.venv\Scripts\python.exe -m remittance_dashboard normalize --dry-run
.\.venv\Scripts\python.exe -m remittance_dashboard normalize --apply
.\.venv\Scripts\python.exe -m remittance_dashboard extract --check
.\.venv\Scripts\python.exe -m remittance_dashboard build-dashboard
```

**Verification:**

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m remittance_dashboard normalize --dry-run
.\.venv\Scripts\python.exe -m remittance_dashboard extract --check
.\.venv\Scripts\python.exe -m remittance_dashboard build-dashboard
.\scripts\start-dashboard.ps1 -NoOpen
```

**Iteration notes:**

- 2026-07-02 - Productionized Separate Remittance with PDF extraction, auditable CSVs, branded static Plotly dashboard, date filters, CSV exports, print-ready PDF reports, and startup launcher.

---

### Practice operations dashboard

**Triggered by:** Viewing, refreshing, extending, or troubleshooting the Vercel-ready practice operations dashboard for beneficiaries, KPI reports, and remittance revenue.

**Preconditions:**

- Code repo: `C:\Users\ppyxe\Documents\GitHub\practice-ops-dashboard`.
- Practice data root: `G:\My Drive\Alexia_Eleftheriadou_Practise_documents`.
- Keep Google Drive source folders read-only and out of Git.
- Set `DATABASE_URL` for immediate two-PC/Vercel synchronization. Local snapshot mode is development-only.

**Architecture:**

- Next.js App Router, TypeScript, React, Tailwind, Zod, and npm, matching X_booking `dev01`.
- `csv-parse` reads the latest beneficiary CSV and remittance processed CSVs.
- `fflate` + `@xmldom/xmldom` read KPI `.xlsx` workbooks without the vulnerable `xlsx` package.
- `pg` writes synchronized task state to hosted PostgreSQL when `DATABASE_URL` is configured.
- Single-password v1 login uses `PRACTICE_DASHBOARD_PASSWORD` and `SESSION_SECRET`; replace with managed auth before broader production use.

**Steps:**

1. Work from the repo root.
2. Import read-only Google Drive data:

```powershell
npm run import:data
```

3. Start local development:

```powershell
npm run dev
```

4. Visit `/`, `/kpi`, `/remittance`, and `/sources`.

**Verification:**

```powershell
npm run lint
npm run typecheck
npm run test
npm run build
```

**Iteration notes:**

- 2026-07-02 - Replaced Google Drive Python/SQLite prototype with GitHub Next.js code repo, read-only Drive imports, single-password login, and PostgreSQL-ready synchronized state.

---

### Config-driven bilingual Next.js medical site (X_booking)

**Triggered by:** Building or extending a reusable doctor/practice marketing site with EN/EL locales and iframe booking.

**Preconditions:**

- Branch: **`dev01`** (not `scraping`, not direct commits to `main` for ordinary work).
- Node.js `>=20.19.0`, npm, committed `package-lock.json`.
- `ACTIVE_CLIENT` env var selects the client bundle (`dr-alexia`, `sample-gp`, etc.).

**Architecture (proven on `dev01`):**

- Next.js 16 App Router, TypeScript, Tailwind, Zod-validated client configs.
- Locale routes `/en` and `/el`; `/` redirects to default locale.
- **Booking:** Google Appointment Scheduling iframe only (`booking.scheduleEmbedUrl` in client config). Google owns availability; no custom OAuth, DB, or email backend in this version.
- **Theme:** `gesyProfessionalTheme` (GESY/gov.cy-inspired) in `src/lib/config/theme-presets.ts`; per-client colour overrides via `theme.colors`.
- **Reuse:** one codebase, many clients via config + content files — not WordPress/Elementor.

**Verification:**

```powershell
npm run verify
```

Expands to lint, typecheck, test, validate:config, build, and onboarding dry-run.

**Iteration notes:**

- 2026-06-19 — Dr Alexia pilot: bilingual static site, GESY branding, embedded map, service cards, legal pages.
- 2026-06-20 — `dev01` development branch; `main` reserved for production launch.

**Repo mirror:** `X_booking/skills.md` on `dev01`; Cursor: `.cursor/skills/client-onboarding/SKILL.md`.

---

### Client onboarding via intake CSV (X_booking)

**Triggered by:** Onboarding a new doctor/client from Google Form facts into a validated config bundle.

**Preconditions:**

- On **`dev01`** with Node tooling installed.
- Form columns match `templates/onboarding/intake-template.csv` (see `docs/client-onboarding-intake.md`).
- CSV exports stay out of git (template is committed; other `*.csv` ignored).

**Steps:**

1. Collect facts via Google Form built from `docs/client-onboarding-intake.md`.
2. Review the Sheet row; export to CSV locally.
3. Preview, then generate:

   ```powershell
   npm run import:client -- --csv <file> --row <n> --dry-run
   npm run import:client -- --csv <file> --row <n>
   ```

4. Script writes `src/clients/<id>/{client.config.ts,content.en.ts,content.el.ts}`, patches `src/lib/config/registry.ts`, runs `validate:config`.
5. Review generated Greek and policy copy. Keep `compliance.legalReviewed: false` until real client/legal review.
6. Before public launch:

   ```powershell
   $env:ACTIVE_CLIENT="<id>"; npm run validate:production
   npm run test:e2e
   ```

7. Deploy Vercel project with `ACTIVE_CLIENT=<id>` and domain matching `site.productionUrl`.

**Implementation anchors:** `src/lib/onboarding/intake-schema.ts`, `content-templates.ts`, `scripts/import-client.ts`.

**Verification:** `npm run verify`; launch gate: `validate:production` + `test:e2e`.

**Cursor mirror:** `X_booking/.cursor/skills/client-onboarding/SKILL.md` (on `dev01`).

**Iteration notes:**

- 2026-06-19 — Production launch gate, schedule URL validation, Playwright smoke tests added.
- 2026-06-20 — Policy copy no longer uses "sample" wording; legal review flag still manual.

---

### Development on dev01 (X_booking)

**Triggered by:** Ordinary code, content, styling, or docs changes before public production launch.

**Preconditions:**

- Work on **`dev01`**, not `main`.
- Do not change DNS for `www.dralexia.com` during development.

**Steps:**

1. `git branch --show-current` — switch to `dev01` if needed.
2. Make changes.
3. Run applicable verification from repo `AGENTS.md`.
4. Commit/push only when the user asks.

**Verification:** `npm run lint`, `npm run typecheck`, `npm run validate:config`, `npm run build`, onboarding dry-run, `npm run test:e2e` when UI/routing changed.

**Cursor mirror:** `X_booking/.cursor/skills/development-on-dev01/SKILL.md` (on `dev01`).

**Iteration notes:**

- 2026-06-20 — `dev01` = development; `main` = production; Vercel previews from `dev01`.

---

### Production launch and DNS cutover (X_booking)

**Triggered by:** Explicit final launch approval for a client domain (e.g. `www.dralexia.com`).

**Preconditions:**

- `dev01` reviewed and ready; legal pages reviewed → then set `compliance.legalReviewed: true`.
- Vercel project has correct `ACTIVE_CLIENT`.
- Elementor rollback DNS records documented before cutover.

**Steps:**

1. Verify `dev01` (`npm run verify`, `validate:production`, `test:e2e`).
2. Merge reviewed `dev01` → `main`; push `main`.
3. Confirm Vercel production deploys from `main`.
4. Add domains in Vercel; replace Elementor website DNS with Vercel records.
5. **Keep mail records unchanged** (MX, SPF, DKIM, DMARC).
6. Smoke test `/el`, `/en`, `/book`, `/contact`, legal pages, `sitemap.xml`.

**Verification:** Full verify suite + DNS inspection + browser smoke after SSL.

**Cursor mirror:** `X_booking/.cursor/skills/production-launch-dns-cutover/SKILL.md` (on `dev01`).

**Iteration notes:**

- 2026-06-20 — DNS still on Elementor until explicit launch step.

---

### CYTA lead scraper — resumable Playwright scrape (X_booking)

**Triggered by:** Collecting Cyprus medical professional leads from [cytayellowpages.com.cy](https://www.cytayellowpages.com.cy/) for B2B outreach planning.

**Preconditions:**

- Branch: **`scraping`** (Next.js app is on `dev01`, not this branch).
- Python 3.11 + repo `.venv` via `uv`; Playwright Chromium installed.
- Never commit `data/`, `*.xlsx`, or scraped contact exports.

**Setup:**

```powershell
uv venv --python 3.11 .venv
uv pip install --python .\.venv\Scripts\python.exe --link-mode hardlink -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

**Architecture (two-phase):**

1. **Discover** — `python -m scraping discover` → `data/specialties.json`.
2. **Run / resume** — paginate listing pages into canonical **`data/scrape.json`**; enrich profiles with `--workers N` (default 8).
3. **Export** — `python -m scraping export` → `data/leads.json`, `data/leads.xlsx`.

**Resume-safe launcher (preferred):**

```powershell
.\scripts\scrape-leads.ps1              # resumes when data/scrape.json exists
.\scripts\scrape-leads.ps1 -Fresh       # intentional rebuild (backs up data/)
```

**CLI (direct):**

```powershell
.\.venv\Scripts\python.exe -m scraping discover
.\.venv\Scripts\python.exe -m scraping run         # fresh scrape (backs up data/ first)
.\.venv\Scripts\python.exe -m scraping resume        # continue interrupted run
.\.venv\Scripts\python.exe -m scraping export
```

**Flags:** `--headed`, `--no-enrich`, `--workers N`, `--max-specialties N`, `--max-pages N` (smoke).

**Outputs (gitignored `data/`):**

| File | Purpose |
|------|---------|
| `specialties.json` | Discovered specialty terms and search URLs |
| `scrape.json` | Canonical resumable checkpoint (discovery + enrichment) |
| `leads.json` | Deduped leads by `profileId` |
| `leads.xlsx` | Excel export for marketing review |

**Site quirks:**

- Cyprus-wide search: location `Κύπρος` / `ALL`, query `d=Cyprus`.
- ASP.NET WebForms pagination via **Επόμενη** — requires Playwright stealth headless (`scraping/browser.py`).
- Polite delays in `scraping/config.py`; close open `scrape.json` in IDE on Windows before long runs.

**Verification (smoke):**

```powershell
.\.venv\Scripts\python.exe -m scraping run --max-specialties 1 --max-pages 1 --no-enrich
.\.venv\Scripts\python.exe -m scraping export
```

**Compliance:** Review CYTA terms before contacting leads; legitimate B2B planning only.

**Cursor mirror:** `~/.cursor/skills/python-lead-scraper/SKILL.md`; repo `X_booking/skills.md` on `scraping`.

**Iteration notes:**

- 2026-06-20 — Scraper-only branch; tqdm; browser cleanup hardened.
- 2026-06-20 — Two-phase discover→enrich; canonical checkpoint is `scrape.json` (not `state.json`); resume launchers.

---

### KYD lead scraper — Know Your Doctor (X_booking)

**Triggered by:** Collecting doctor and dentist leads from [knowyourdoctor.com.cy](https://www.knowyourdoctor.com.cy/).

**Preconditions:**

- Branch: **`scraping`**; independent package `kyd_scraping/` (not CYTA `scraping/`).
- **Installed Google Chrome** via Playwright `channel="chrome"` — bundled/headless Chromium blocked by KYD.
- Never commit `data/kyd/` or Excel exports.

**Architecture (same two-phase pattern):**

1. **Run** — discover Doctor + Dentist categories/subspecialties, paginate listings → **`data/kyd/scrape.json`**.
2. **Resume** — continue checkpoint; enrich with `--workers N` (default 4).
3. **Export** — `python -m kyd_scraping export` → `data/kyd/leads.json`, `data/kyd/leads.xlsx`.

**Resume-safe launcher (preferred):**

```powershell
.\scripts\scrape-kyd-leads.ps1          # resumes when data/kyd/scrape.json exists
.\scripts\scrape-kyd-leads.ps1 -Fresh   # intentional rebuild
```

**Verification (smoke):**

```powershell
.\.venv\Scripts\python.exe -m kyd_scraping run --max-categories 1 --max-specialties 1 --max-pages 1 --no-enrich
.\.venv\Scripts\python.exe -m kyd_scraping export
```

**Cursor mirror:** `~/.cursor/skills/python-lead-scraper/SKILL.md`; repo `X_booking/skills.md` on `scraping`.

**Iteration notes:**

- 2026-06-20 — Added KYD scraper; Chrome channel required; shared `atomic_io` with CYTA.

---

### Git single checkout — no worktrees

**Triggered by:** Any git work in a multi-branch repo (website + scraper, or multiple product lines in one folder).

**Preconditions:** One repo folder only — never `git worktree add` or sibling folders like `Repo_dev01_*`.

**Steps:**

1. `git branch --show-current` — confirm branch matches the task.
2. `git switch <branch>` before installs, scrapes, or edits.
3. After switching scraper ↔ website branches, run branch cleanup (next workflow).

**Verification:** `git worktree list` shows only the main worktree.

**Cursor mirror:** `~/.cursor/skills/git-single-checkout/SKILL.md`

**Iteration notes:**

- 2026-06-20 — Worktrees caused cross-branch pollution; banned globally in `01-git-pr-quality.mdc`.

---

### Multi-branch repo hygiene (clean worktree)

**Triggered by:** After `git switch` between branches with different artifacts (Next.js on `dev01`, scrapers on `scraping`).

**Steps:**

1. `git switch <target-branch>`.
2. Run branch-aware cleanup (X_booking: `.\scripts\clean-worktree.ps1`).
3. Confirm only branch-appropriate files remain.

**Verification:** `git status` clean or only expected untracked paths.

**Cursor mirror:** `~/.cursor/skills/branch-hygiene/SKILL.md`

**Iteration notes:**

- 2026-06-20 — X_booking scraping ↔ dev01; pattern reusable elsewhere.

---

### Windows atomic JSON checkpoints (scrapers)

**Triggered by:** Scraper checkpoint writes on Windows; `PermissionError` on `.tmp` → final JSON rename.

**Steps:**

1. Use `atomic_write_json` (`scraping/atomic_io.py` or copy into new package).
2. Retries on `PermissionError`; fallback in-place write if replace still fails.
3. Warn user to close open `scrape.json` / Excel in IDE before long runs.

**Verification:** Long scrape completes; resume reads valid JSON.

**Cursor mirror:** `~/.cursor/skills/windows-atomic-json/SKILL.md`

**Iteration notes:**

- 2026-06-20 — Fixed CYTA/KYD failures when IDE held files open.

---

### Python lead scraper — new repo scaffold

**Triggered by:** Creating a new lead scraper or adding a scraper package to an existing repo.

**Steps:**

1. Create **`AGENTS.md`** + **`skills.md`** (mandatory — `~/.codex/AGENTS.md → New repository scaffold`).
2. Copy workflows from this file: tqdm, single checkout, branch hygiene, atomic JSON, Playwright stealth, site-specific scraper.
3. Package layout: `__main__.py`, `config.py`, `browser.py`, `state.py`, `progress.py`, `atomic_io.py`.
4. Add `scripts/scrape-*-leads.ps1` resume launcher; pin deps in `requirements.txt`.
5. Gitignore `data/`, `data.backup.*/`, `*.xlsx`.
6. Document smoke commands in `AGENTS.md → ## Verification`.
7. Mirror to `.cursor/skills/`; propagate stack row globally.

**Canonical reference:** `~/.codex/AGENTS.md → ## Python lead scraper pattern`.

**Cursor mirror:** `~/.cursor/skills/python-lead-scraper/SKILL.md`

**Iteration notes:**

- 2026-06-20 — Pattern from X_booking CYTA + KYD.

---

### Playwright stealth headless for protected sites

**Triggered by:** A target site returns "Page not found" or blocks default Playwright headless automation.

**Preconditions:**

- Playwright installed in repo `.venv`; Chromium browser binaries present.

**Steps:**

1. Launch with stealth args: `ignore_default_args=["--enable-automation"]`, realistic `user_agent`, normal viewport.
2. Dismiss cookie banners early (multi-selector fallback loop).
3. Prefer `async` context manager for browser lifecycle; catch `TargetClosedError` on cleanup so success is not masked.
4. Use Playwright for postback/JS pagination; use BeautifulSoup for HTML parsing after `page.content()`.
5. Add polite delays between page/profile requests.

**Verification:** Headless smoke run matches headed run for the same URL and item count.

**Proven in:** `X_booking/scraping/browser.py`, `discover.py`, `__main__.py`.

**Iteration notes:**

- 2026-06-20 — Required for CYTA yellow pages ASP.NET pagination.
