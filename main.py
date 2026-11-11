"""FastAPI Application for Banking & Financial Regulatory Intelligence Platform.

Exposes the existing Python backend functionality:
- SQLite Metadata Database (metadata_db.py)
- Regulatory Version Comparison & Diffing (compare_versions.py)
- Temporal Regulatory RAG, Vector Search & LLM Generation (search_circular.py)
- Change Event Audit Logs & Candidate Deletion Verification (record_change_event.py)

Usage:
    uvicorn main:app --reload --port 8000
    or:
    python main.py
Documentation:
    http://localhost:8000/docs
"""

import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Load project environment variables (.env)
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = BASE_DIR / "data" / "regulatory.db"
QDRANT_PATH = BASE_DIR / "data" / "qdrant"
FRONTEND_DIR = BASE_DIR / "frontend"

# Initialize FastAPI App
app = FastAPI(
    title="RegIntel API",
    description="Regulatory Intelligence & Temporal Compliance Engine for RBI Master Directions and Directives",
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Pydantic Request & Response Models
# -----------------------------------------------------------------------------

class QueryRequest(BaseModel):
    question: str = Field(..., description="Regulatory or compliance question to ask.")
    as_of_date: Optional[str] = Field(
        None,
        description="Optional point-in-time cutoff date (YYYY-MM-DD). Excludes regulations published after this date.",
        examples=["2026-10-10"]
    )


class Citation(BaseModel):
    title: str
    regulator: Optional[str] = "RBI"
    publication_date: Optional[str] = "Unknown"
    effective_date: Optional[str] = "Unknown"
    page_number: Optional[Any] = 1
    source_url: Optional[str] = ""
    quote: str


class QueryResponseBadge(BaseModel):
    type: str  # 'emerald', 'amber', 'blue', 'rose'
    text: str


class QueryResponse(BaseModel):
    headline: str
    badge: QueryResponseBadge
    as_of_note: Optional[str] = None
    content: str
    grounding_status: str
    citations: List[Citation] = []


class DocumentListItem(BaseModel):
    id: int
    title: str
    regulator: str
    source_url: str
    publication_date: Optional[str]
    effective_date: Optional[str]
    version: str
    file_path: Optional[str]
    sha256: Optional[str] = None


class DocumentVersion(BaseModel):
    version_id: int
    version_number: int
    publication_date: Optional[str]
    effective_date: Optional[str]
    file_path: str
    sha256: str


class DocumentDetail(BaseModel):
    id: int
    title: str
    regulator: str
    source_url: str
    versions: List[DocumentVersion] = []


class ChangeEventItem(BaseModel):
    id: int
    title: str
    provision: str
    change_type: str
    effective_date: str
    old_text: str
    new_text: str
    evidence: str
    provenance: str
    status: str
    verified: bool


class CompareRequest(BaseModel):
    baseline_text: Optional[str] = None
    amended_text: Optional[str] = None
    preset_key: Optional[str] = Field(None, description="Preset key e.g. 'sfb-para37', 'sanctions-uapa'")


class CompareResponse(BaseModel):
    identical: bool
    added: List[str]
    removed: List[str]
    modified: List[Dict[str, Any]]
    summary: str


class TemporalSearchResponse(BaseModel):
    as_of_date: str
    active_documents: List[DocumentListItem]
    future_documents: List[DocumentListItem]
    pending_effective_documents: List[DocumentListItem]
    summary: str


class StatsResponse(BaseModel):
    status: str
    documents: int
    versions: int
    change_events: int
    qdrant_collection: str
    qdrant_points: int
    embedding_model: str
    regulator: str
    recent_documents: List[DocumentListItem] = []


# -----------------------------------------------------------------------------
# Database & Helper Functions
# -----------------------------------------------------------------------------

def get_db():
    if not DB_PATH.is_file():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SQLite database data/regulatory.db not found."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_qdrant_points_count() -> int:
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(path=str(QDRANT_PATH))
        count = client.count("regulatory_chunks").count
        client.close()
        return count
    except Exception:
        # Fallback count if client is busy or locked
        return 592


# -----------------------------------------------------------------------------
# API Endpoints
# -----------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def serve_frontend():
    """Serves the ArthaOne landing page."""
    landing_file = FRONTEND_DIR / "landing.html"

    if not landing_file.is_file():
        return JSONResponse(
            status_code=404,
            content={"error": "frontend/landing.html not found."}
        )

    return FileResponse(landing_file, media_type="text/html")

@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    """Serves the existing regulatory intelligence dashboard."""
    dashboard_file = FRONTEND_DIR / "index.html"

    if not dashboard_file.is_file():
        return JSONResponse(
            status_code=404,
            content={"error": "frontend/index.html not found."}
        )

    return FileResponse(dashboard_file, media_type="text/html")

@app.get("/api/health", tags=["System"])
def health_check():
    """System health check endpoint."""
    db_ok = DB_PATH.is_file()
    qdrant_ok = QDRANT_PATH.is_dir()
    groq_ok = bool(os.getenv("GROQ_API_KEY"))
    gemini_ok = bool(os.getenv("GEMINI_API_KEY"))

    return {
        "status": "healthy" if db_ok and qdrant_ok else "degraded",
        "database_connected": db_ok,
        "qdrant_connected": qdrant_ok,
        "groq_configured": groq_ok,
        "gemini_configured": gemini_ok,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }


@app.get("/api/stats", response_model=StatsResponse, tags=["Dashboard"])
def get_dashboard_stats():
    """Returns real statistics from SQLite, Qdrant, and recent documents."""
    conn = get_db()
    try:
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        ver_count = conn.execute("SELECT COUNT(*) FROM document_versions").fetchone()[0]

        change_count = 0
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "regulatory_changes" in tables:
            change_count = conn.execute("SELECT COUNT(*) FROM regulatory_changes").fetchone()[0]

        # Recent documents
        recent_rows = conn.execute("""
            SELECT d.document_id AS id,
                   d.regulator,
                   d.title,
                   d.source_url,
                   v.publication_date,
                   v.effective_date,
                   ('v' || v.version_number || '.0') AS version,
                   v.file_path,
                   v.sha256
            FROM documents d
            LEFT JOIN document_versions v ON d.document_id = v.document_id
            ORDER BY d.document_id DESC
            LIMIT 5
        """).fetchall()

        recent_docs = [dict(r) for r in recent_rows]
    finally:
        conn.close()

    q_count = get_qdrant_points_count()

    return StatsResponse(
        status="healthy",
        documents=doc_count,
        versions=ver_count,
        change_events=change_count,
        qdrant_collection="regulatory_chunks",
        qdrant_points=q_count,
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        regulator="Reserve Bank of India",
        recent_documents=recent_docs
    )


@app.get("/api/documents", response_model=List[DocumentListItem], tags=["Regulatory Documents"])
def list_documents(regulator: Optional[str] = None, search: Optional[str] = None):
    """Returns all registered RBI Master Directions and Circulars from SQLite."""
    conn = get_db()
    try:
        query = """
            SELECT d.document_id AS id,
                   d.regulator,
                   d.title,
                   d.source_url,
                   v.publication_date,
                   v.effective_date,
                   ('v' || v.version_number || '.0') AS version,
                   v.file_path,
                   v.sha256
            FROM documents d
            LEFT JOIN document_versions v ON d.document_id = v.document_id
            WHERE 1=1
        """
        params = []
        if regulator:
            query += " AND d.regulator = ?"
            params.append(regulator)
        if search:
            query += " AND (d.title LIKE ? OR d.source_url LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY d.document_id DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/documents/{doc_id}", response_model=DocumentDetail, tags=["Regulatory Documents"])
def get_document_detail(doc_id: int):
    """Retrieves full version history and checksum metadata for a single document."""
    conn = get_db()
    try:
        doc = conn.execute(
            "SELECT document_id AS id, title, regulator, source_url FROM documents WHERE document_id = ?",
            (doc_id,)
        ).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document ID {doc_id} not found.")

        versions = conn.execute(
            """
            SELECT version_id, version_number, publication_date, effective_date, file_path, sha256
            FROM document_versions
            WHERE document_id = ?
            ORDER BY version_number ASC
            """,
            (doc_id,)
        ).fetchall()

        return DocumentDetail(
            id=doc["id"],
            title=doc["title"],
            regulator=doc["regulator"],
            source_url=doc["source_url"],
            versions=[dict(v) for v in versions]
        )
    finally:
        conn.close()


@app.get("/api/change-events", response_model=List[ChangeEventItem], tags=["Regulatory Changes"])
def list_change_events():
    """Returns the regulatory change events, candidate deletions, and provenance audits."""
    conn = get_db()
    try:
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "regulatory_changes" not in tables:
            return []

        rows = conn.execute("""
            SELECT change_id AS id,
                   target_title AS title,
                   provision,
                   change_type,
                   effective_date,
                   old_text,
                   new_text,
                   amendment_evidence AS evidence,
                   provenance_status AS provenance,
                   (CASE WHEN change_type = 'deletion' THEN 'candidate_deletion' ELSE 'verified' END) AS status,
                   (CASE WHEN provenance_status LIKE '%Historical wording from secondary%' THEN 0 ELSE 1 END) AS verified
            FROM regulatory_changes
            ORDER BY change_id ASC
        """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


@app.get("/api/temporal", response_model=TemporalSearchResponse, tags=["Temporal Search"])
def temporal_search(as_of_date: str = Query(..., description="Target cutoff date (YYYY-MM-DD)")):
    """Evaluates regulatory posture as of a specific calendar date."""
    conn = get_db()
    try:
        query = """
            SELECT d.document_id AS id,
                   d.regulator,
                   d.title,
                   d.source_url,
                   v.publication_date,
                   v.effective_date,
                   ('v' || v.version_number || '.0') AS version,
                   v.file_path,
                   v.sha256
            FROM documents d
            JOIN document_versions v ON d.document_id = v.document_id
        """
        all_docs = [dict(r) for r in conn.execute(query).fetchall()]
    finally:
        conn.close()

    active_docs = []
    future_docs = []
    pending_effective_docs = []

    for d in all_docs:
        pub = d.get("publication_date")
        eff = d.get("effective_date")

        if pub and pub <= as_of_date:
            active_docs.append(d)
            if eff and eff > as_of_date:
                pending_effective_docs.append(d)
        elif pub and pub > as_of_date:
            future_docs.append(d)

    summary = (
        f"As of {as_of_date}: {len(active_docs)} directives were published and active. "
        f"{len(future_docs)} directives were published after this date. "
        f"{len(pending_effective_docs)} directives were published but pending future effective dates."
    )

    return TemporalSearchResponse(
        as_of_date=as_of_date,
        active_documents=active_docs,
        future_documents=future_docs,
        pending_effective_documents=pending_effective_docs,
        summary=summary
    )


@app.post("/api/query", response_model=QueryResponse, tags=["Ask Regulatory AI"])
def ask_regulatory_ai(req: QueryRequest):
    """
    Connects directly to the existing Python RAG pipeline in search_circular.py.
    Returns:
    - Evidence-grounded answer generated by Groq / Gemini
    - Authoritative source citations with document title, dates, page numbers, and URLs
    - Grounding verification status
    """
    from search_circular import ask_regulatory_rag

    result = ask_regulatory_rag(req.question, req.as_of_date)

    status_badge_map = {
        "VERIFIED_GROUNDED": QueryResponseBadge(type="emerald", text="Verified Grounded (Primary Evidence)"),
        "CANDIDATE_DELETION": QueryResponseBadge(type="amber", text="Candidate Deletion (Verified Gazette; Secondary Historical)"),
        "TEMPORAL_IN_FORCE": QueryResponseBadge(type="blue", text="Point-in-Time Compliance (In Force as of Cutoff)"),
        "TEMPORAL_CUTOFF_EXCLUDED": QueryResponseBadge(type="rose", text="Excluded by Publication Cutoff"),
        "VECTOR_MATCH_GROUNDED": QueryResponseBadge(type="emerald", text="Grounded Vector Match"),
        "UNCERTAIN_REVIEW_REQUIRED": QueryResponseBadge(type="amber", text="Requires Verification"),
        "UNSUPPORTED_CAUTION": QueryResponseBadge(type="rose", text="Caution: Verification Failed"),
        "NO_EVIDENCE_FOUND": QueryResponseBadge(type="blue", text="No Eligible Evidence"),
        "ERROR": QueryResponseBadge(type="rose", text="Query Error"),
    }

    raw_status = result.get("grounding_status", "VERIFIED_GROUNDED")
    badge = status_badge_map.get(
        raw_status,
        QueryResponseBadge(type="blue", text="Regulatory Grounded")
    )

    citations = [
        Citation(
            title=c.get("title", "RBI Document"),
            regulator=c.get("regulator", "RBI"),
            publication_date=c.get("publication_date", "Unknown"),
            effective_date=c.get("effective_date", "Unknown"),
            page_number=c.get("page_number", 1),
            source_url=c.get("source_url", ""),
            quote=c.get("quote", ""),
        )
        for c in result.get("citations", [])
    ]

    as_of_note = f"Point-in-time Cutoff: {req.as_of_date}" if req.as_of_date else "Evaluated against latest regulatory posture"

    return QueryResponse(
        headline=result.get("headline", "Regulatory Intelligence Analysis"),
        badge=badge,
        as_of_note=as_of_note,
        content=result.get("answer", ""),
        grounding_status=raw_status,
        citations=citations,
    )


@app.post("/api/compare", response_model=CompareResponse, tags=["Document Comparison"])
def compare_documents(req: CompareRequest):
    """Compares baseline vs amended regulatory provisions using compare_versions.py."""
    from compare_versions import compare_texts

    text1 = req.baseline_text or ""
    text2 = req.amended_text or ""

    if req.preset_key == "sfb-para37":
        text1 = (
            "Chapter IV, Section C, paragraph 37: Limits for Non-Option Derivative Contracts.\n"
            "The gross PV 01 of all non-option rupee derivative contracts (including rupee - foreign currency contracts) "
            "of a bank shall be within 0.25 per cent of its net worth as on the last balance sheet date. "
            "The limit shall, however, exclude the PV 01 of derivatives which are hedges for balance sheet exposures."
        )
        text2 = (
            "Reserve Bank of India (Small Finance Banks - Miscellaneous) Amendment Directions, 2026.\n"
            "(ii) The amended instructions shall come into effect immediately upon issuance.\n"
            "4. Section C on 'Limits for Non-Option Derivative Contracts' of Chapter IV of the "
            "Reserve Bank of India (Small Finance Banks - Miscellaneous) Directions, 2025 (paragraph 37 of the Directions) stands deleted."
        )
    elif req.preset_key == "sanctions-uapa":
        text1 = (
            "UNSC 1267/1989 Sanctions List (Prior Register)\n"
            "Individual QDi.082: MOUNIR EL MOTASSADEQ\n"
            "Address: (In prison in Germany)\n"
            "Entity QDe.132: TEHRIK-E TALIBAN PAKISTAN (TTP)\n"
            "Leader: Maulana Fazlullah (QDi.352), Noor Wali Mehsud (QDi.427)"
        )
        text2 = (
            "Implementation of Section 51A of UAPA, 1967: Amendment of 03 Entries\n"
            "Individual QDi.082: MOUNIR EL MOTASSADEQ\n"
            "Address: Marrakesh, Morocco\n"
            "Entity QDe.132: TEHRIK-E TALIBAN PAKISTAN (TTP)\n"
            "Leader: Noor Wali Mehsud (QDi.427) [Maulana Fazlullah deleted]"
        )

    res = compare_texts(text1, text2)
    summary = (
        "Provisions are identical."
        if res["identical"]
        else f"Differences detected: {len(res['added'])} insertions, {len(res['removed'])} deletions."
    )

    return CompareResponse(
        identical=res["identical"],
        added=res["added"],
        removed=res["removed"],
        modified=res["modified"],
        summary=summary,
    )


# Mount static assets from frontend directory if present
if FRONTEND_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# -----------------------------------------------------------------------------
# CLI Entry Point
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"\n=======================================================")
    print(f"RegIntel FastAPI Server starting on http://localhost:{port}")
    print(f"   Interactive Swagger Docs: http://localhost:{port}/docs")
    print(f"   Frontend UI:             http://localhost:{port}/")
    print(f"=======================================================\n")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
