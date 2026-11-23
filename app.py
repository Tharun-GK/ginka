from __future__ import annotations

import asyncio
import logging
from datetime import timezone

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import func, select

from src.database.db import SessionLocal, init_db
from src.database.models import EntityMapping, IngestionRun, Record
from src.integrations.export import CATEGORIES, csv_for, export_to_sheets
from src.pipeline.ingestion_pipeline import run_all, run_collector
from src.resolver.entity_resolver import EntityResolver

st.set_page_config(page_title="GRAPHONE | AI Intelligence", page_icon="◈", layout="wide")
st.markdown("""<style>
.stApp{background:#07111f;color:#e5f2ff}.block-container{padding-top:2rem}
[data-testid="stSidebar"]{background:#0b1a2b}
[data-testid="stMetric"]{background:#10243a;padding:16px;border:1px solid #163b58;border-radius:12px}
h1,h2,h3{color:#d9f3ff}
</style>""", unsafe_allow_html=True)
init_db()

PAGES = ["Overview", "Startups", "Products", "Research Papers", "AI Jobs", "AI News",
         "Entity Resolution", "Pipeline Monitor", "System Architecture", "Settings"]
with st.sidebar:
    st.markdown("# ◈ GRAPHONE")
    st.caption("Global AI Intelligence Platform")
    page = st.radio("Navigate", PAGES, label_visibility="collapsed")
    st.caption("Public sources · provenance preserved · no synthetic records")


def get_records(category: str | None = None) -> list[Record]:
    with SessionLocal() as session:
        query = select(Record).order_by(Record.published_at.desc(), Record.first_seen_at.desc())
        if category:
            query = query.where(Record.category == category)
        return list(session.scalars(query))


def record_frame(records: list[Record]) -> pd.DataFrame:
    return pd.DataFrame([{"Title": r.title, "Organization": r.organization, "Source": r.source_name,
                          "Published": r.published_at, "Summary": r.summary, "URL": r.record_url,
                          "Source URL": r.source_url} for r in records])


def run_action(name: str) -> None:
    with st.spinner("Collecting from public sources..."):
        result = asyncio.run(run_all() if name == "all" else run_collector(name))
    st.session_state["last_run"] = result
    st.success("Collector run finished. See results below.")


if page == "Overview":
    st.title("GRAPHONE")
    st.subheader("Global AI Intelligence Platform")
    st.caption("Live public-source intelligence · records are stored with traceable provenance.")
    counts = {}
    with SessionLocal() as session:
        for category in CATEGORIES:
            counts[category] = session.scalar(select(func.count(Record.id)).where(Record.category == category)) or 0
    columns = st.columns(5)
    for column, category, label in zip(columns, CATEGORIES,
                                        ["Startups", "Products", "Research Papers", "Fresh AI Jobs", "Fresh AI News"]):
        column.metric(label, counts[category])
    left, right = st.columns(2)
    with left:
        st.plotly_chart(px.bar(pd.DataFrame({"Category": list(counts), "Records": list(counts.values())}),
                               x="Category", y="Records", color="Category", title="Collected records by category"),
                        use_container_width=True)
    with right:
        all_records = get_records()
        dates = [r.first_seen_at.date().isoformat() for r in all_records]
        if dates:
            date_counts = pd.Series(dates).value_counts().sort_index()
            st.plotly_chart(px.line(x=date_counts.index, y=date_counts.values,
                                    labels={"x": "Date", "y": "Records"}, title="Ingestion over time"),
                            use_container_width=True)
        else:
            st.info("No source-backed records yet. Start an ingestion run to collect current public data.")
    if st.button("Run all collectors", type="primary"):
        run_action("all")

elif page in ["Startups", "Products", "Research Papers", "AI Jobs", "AI News"]:
    category = {"Startups": "startup", "Products": "product", "Research Papers": "research",
                "AI Jobs": "job", "AI News": "news"}[page]
    st.title(page)
    frame = record_frame(get_records(category))
    if not frame.empty:
        query = st.text_input("Search")
        if query:
            frame = frame[frame.astype(str).apply(lambda col: col.str.contains(query, case=False)).any(axis=1)]
        st.dataframe(frame, use_container_width=True, hide_index=True,
                     column_config={"URL": st.column_config.LinkColumn(), "Source URL": st.column_config.LinkColumn()})
    else:
        st.info("No records collected. Start this collector to fetch real source-backed data.")
    if st.button(f"Run {page} collector"):
        run_action(category)
    st.download_button("Download CSV", csv_for(category), file_name=f"{category}.csv", mime="text/csv")

elif page == "Entity Resolution":
    st.title(page)
    raw_name = st.text_input("Name to resolve")
    if raw_name:
        st.json(EntityResolver().resolve(raw_name))
    with SessionLocal() as session:
        mappings = list(session.scalars(select(EntityMapping).order_by(EntityMapping.created_at.desc())))
    st.dataframe(pd.DataFrame([{"Raw name": m.raw_name, "Canonical": m.canonical_name,
                                "Confidence": m.confidence, "Method": m.method, "Source": m.source_url}
                               for m in mappings]), use_container_width=True, hide_index=True)
    st.download_button("Download mapping CSV", csv_for("entity_mapping"), "entity_mapping.csv", "text/csv")

elif page == "Pipeline Monitor":
    st.title(page)
    selected = st.selectbox("Collector", ["All", *CATEGORIES])
    if st.button("Run selected collector", type="primary"):
        run_action("all" if selected == "All" else selected)
    if "last_run" in st.session_state:
        st.write(st.session_state["last_run"])
    with SessionLocal() as session:
        runs = list(session.scalars(select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(50)))
    st.dataframe(pd.DataFrame([{"Collector": r.collector, "Status": r.status, "Found": r.records_found,
                                "New": r.records_saved, "Started": r.started_at, "Error": r.error}
                               for r in runs]), use_container_width=True, hide_index=True)

elif page == "System Architecture":
    st.title(page)
    st.markdown("""**Collectors → asynchronous public APIs/RSS → freshness and provenance validation → duplicate-safe SQLite → entity resolution → dashboard/CSV/optional Sheets.**

Current deployment is a local prototype; it is not benchmarked or represented as handling 500,000 records.
For scale, move persistence to PostgreSQL, enqueue fingerprint-keyed tasks in Redis/Celery, store raw documents
in object storage, add vector and graph databases only for measured search/relationship needs, and monitor
centralized logs, retries, rate limits, and queue depth. Database uniqueness constraints keep distributed
workers from inserting the same source record twice.""")
    st.code("Public APIs/RSS → asyncio collectors → 24-hour filter → SQLAlchemy (SQLite) → Streamlit\n"
            "Gemini → Groq → DeepSeek (optional keys; raw records retained when not configured)", language="text")

else:
    st.title("Settings")
    st.caption("Secrets are read from the environment or an untracked .env file and are never displayed.")
    st.write("Database schema version: 1.0")
    st.write("LLM providers configured:", {
        "Gemini": bool(__import__("os").getenv("GEMINI_API_KEY")),
        "Groq": bool(__import__("os").getenv("GROQ_API_KEY")),
        "DeepSeek": bool(__import__("os").getenv("DEEPSEEK_API_KEY")),
    })
    if st.button("Export six worksheets to Google Sheets"):
        result = export_to_sheets()
        if result.uploaded:
            st.success(f"Uploaded: {', '.join(result.uploaded)}")
        if result.skipped:
            st.info(f"Not uploaded: {', '.join(result.skipped)}")
        if result.errors:
            st.error(result.errors)
    st.subheader("CSV exports")
    for category in [*CATEGORIES, "entity_mapping"]:
        filename = f"{category}.csv"
        st.download_button(f"Download {filename}", csv_for(category), filename, "text/csv", key=category)
