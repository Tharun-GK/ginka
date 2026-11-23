# GraphOne architecture and scale-out notes

## Prototype data flow

1. The dashboard starts a named collector or all five collectors.
2. Async HTTP clients fetch only public API/RSS responses with bounded
   concurrency and an identifying user agent.
3. RSS jobs and news must have a parseable publication time within the previous
   24 hours. Unknown dates are rejected rather than guessed.
4. SQLAlchemy stores source URL, record URL, raw payload, timestamps, and a
   stable SHA-256 fingerprint. A unique database constraint prevents duplicate
   inserts.
5. Entity aliases are normalized and matched exactly first. Fuzzy matching is
   deliberately strict; uncertain matches remain unresolved for review.
6. Streamlit reads the same SQLite database and offers filtered tables, run
   status, CSV downloads, and an explicitly triggered optional Sheets export.

## Vercel deployment mode

The static browser dashboard is served from `public/`; a FastAPI ASGI
application is exposed through `index.py` as a Python Function. The existing
Streamlit dashboard remains available for local development and is not the
Vercel frontend. Vercel's function filesystem is ephemeral, so its runtime
rejects SQLite and requires a persistent PostgreSQL `DATABASE_URL`. Collector
and Google Sheets POST actions require an eight-hour signed, HTTP-only,
SameSite=Strict admin cookie issued after password authentication. The password
and signing secret are Vercel environment variables, never frontend assets.
Local SQLite data can be copied to the configured PostgreSQL database with
`scripts/migrate_local_db.py`.

## LLM fallback

The optional extraction client attempts Gemini Flash, then Groq, then DeepSeek.
Pydantic validates structured results; HTTP 429 responses are retried with
exponential delay and jitter. Oversized responses (413) are surfaced rather
than silently truncated. HTML cleanup and chunking preserve all non-empty text
in bounded chunks. If credentials are absent or every provider fails, source
records remain persisted with extraction pending.

## Schema and provenance

SQLite schema version is 1.0. Records are categorized with a unique
`(category, fingerprint)` constraint; source name, source URL, original record
URL, publication timestamp, first/last-seen timestamps, raw data, and
extraction status are retained. SQLAlchemy supports PostgreSQL by configuring a
PostgreSQL `DATABASE_URL` and installing the corresponding driver.

## Compliance and limitations

Use public APIs and RSS sources, honor their terms and rate limits, and check
robots and licensing policies before adding any HTML source. Do not circumvent
CAPTCHAs, login requirements, or anti-bot protections. Configure authorized
feeds/APIs instead. The current startup and product collectors are discovery
proxies, not vetted directories; verify entities before business decisions.

## Scaling beyond the prototype

For 500,000+ records, benchmark workloads first, then evolve by replacing SQLite
with PostgreSQL, putting collector jobs on Redis plus Celery (or an equivalent
queue), and using multiple low-concurrency async workers with per-domain
rate-limit scheduling. Keep database uniqueness constraints and idempotent
fingerprints as the final duplicate guard across workers. Store large raw HTML
in object storage and retain checksums/URLs in PostgreSQL. Introduce a vector
database for semantic retrieval and a graph database for relationships only
when query needs justify their operational cost. Add centralized structured
logs, metrics, tracing, alerting, dead-letter queues, and backpressure. Batch
database writes and monitor API quotas, freshness lag, queue depth, retries,
provider failures, and provenance coverage. None of these distributed
components is included or claimed to be running in this local prototype.
