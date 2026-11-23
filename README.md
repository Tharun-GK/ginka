# GraphOne – FrontierAtlas Intelligence Graph

A local, source-attributed prototype for collecting public AI-related research,
open-source products, startup discoveries, fresh jobs, and fresh news. It uses
asynchronous source requests, a SQLite database, conservative entity resolution,
and an interactive Streamlit dashboard. It does not fabricate records or claim
production-scale throughput.

## Architecture

`src/collectors/` contains independently runnable collectors: arXiv Atom API,
GitHub's public repository search, Hacker News Show HN, and configurable RSS
feeds. Job and news records are accepted only when their publication time is
known and no more than 24 hours old. Every stored record keeps its source and
record URLs. `src/database/` persists de-duplicated records with SQLAlchemy and
a database uniqueness constraint. `src/resolver/` uses exact aliases and
conservative fuzzy matching. `app.py` provides live collector controls, tables,
pipeline status, CSV downloads, and optional Sheets export.

## Install and run

Python 3.11+ is recommended (the project is also tested with Python 3.12).

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-local.txt
Copy-Item .env.example .env
streamlit run app.py
```

In the sidebar, open **Pipeline Monitor** and run a collector, or run one
independently from PowerShell:

```powershell
python -m src.collectors.research_collector
python -m src.collectors.product_collector
python -m src.collectors.startup_collector
python -m src.collectors.job_collector
python -m src.collectors.news_collector
```

The JSON API can be started separately with `uvicorn index:app --reload` and
provides `/health`, `/collectors`, `/collectors/{name}/run`, `/records`, and
`/runs`.

The database is created on first launch at `data/graphone.db`. Collection needs
internet access. Respect each public source's usage policy and rate limits.
Job/news feed URLs can be overridden with comma-separated `JOB_RSS_FEEDS` and
`NEWS_RSS_FEEDS` environment variables. Only RSS items with a verifiable date
in the last 24 hours are accepted.

## Optional integrations

* **GitHub:** unauthenticated public requests work at low rates. Set
  `GITHUB_TOKEN` in `.env` for a higher API quota. Never commit tokens.
* **LLMs:** configure `GEMINI_API_KEY`, `GROQ_API_KEY`, and/or `DEEPSEEK_API_KEY`.
  Providers are attempted in that order. Without a configured provider, raw
  collected records remain saved and extraction stays pending.
* **Google Sheets:** configure `GOOGLE_CREDENTIALS_FILE` and `SPREADSHEET_ID`,
  enable Sheets/Drive APIs, and share the spreadsheet with the service account.
  Settings offers an explicit export action; without credentials, download CSVs.

## Vercel deployment

Vercel serves the static dashboard in `public/` and runs the FastAPI application
as a Python Function. The existing Streamlit interface remains for local use;
Vercel uses the browser dashboard instead. Unlike SQLite on a local machine,
Vercel's function filesystem is not persistent, so Vercel requires a PostgreSQL
`DATABASE_URL` (for example, from a Neon Marketplace integration).

1. Import this project into Vercel, or deploy with the Vercel CLI from the
   repository root. With the CLI, run `npx vercel login` followed by
   `npx vercel deploy`. Python 3.12 and the API-only `requirements.txt` are
   selected for the function.
2. Connect PostgreSQL and set `DATABASE_URL` in the Vercel project's
   environment. Use the provider's pooled connection string where available;
   the application rejects SQLite on Vercel.
3. Add `DASHBOARD_PASSWORD` and a long random `DASHBOARD_SESSION_SECRET`.
   The password must be at least 12 characters; the session secret must be at
   least 32 characters.
   Collector runs and Google Sheets exports require an authenticated admin
   session; public browsing and CSV downloads remain read-only.
4. Add optional LLM, GitHub, and Sheets variables only when those integrations
   are needed. Never commit production credentials.
5. To copy local records after PostgreSQL is configured, set the same
   `DATABASE_URL` in a local `.env`, then run:

   ```powershell
   python scripts/migrate_local_db.py
   ```

Vercel cannot host the existing long-running Streamlit process as-is; the
Vercel-compatible static frontend and FastAPI serverless backend are separate
entrypoints. Collector work is limited by Vercel function duration and should
move to a queue/scheduled worker if collection grows. Vercel account access and
a PostgreSQL service are required for a persistent interactive deployment.

## Tests

```powershell
python -m pip install -r requirements-local.txt
python -m pytest -q
```

Tests use isolated, synthetic fixtures only; fixtures are not real collected
intelligence. No demonstration records are inserted into the application
database.

Generate the short architecture handout with:

```powershell
python -m src.integrations.architecture_pdf
```

## Limitations

* Startup discovery uses public Hacker News Show HN submissions matching AI
  terms; this is not a comprehensive or verified startup directory.
* Products are AI-related repositories returned by GitHub's `ai-tools` topic,
  not a catalog of commercial products.
* Job collection quality depends on configured RSS feed coverage. Feeds without
  verifiable timestamps are deliberately skipped.
* The prototype stores extracted source summaries/RSS excerpts, not full
  copyrighted articles. It does not bypass authentication, robots rules, or
  anti-bot controls.
* LLM extraction and Google Sheets require user-provided credentials. LLM
  providers can change model availability or response formats.
* SQLite is suitable for local demonstration, not high-concurrency production.

## Production evolution

See [docs/architecture.md](docs/architecture.md) for a scale-out plan. The
prototype has not been load-tested for 500,000 records.
