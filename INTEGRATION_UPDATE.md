# Regulatory Intelligence Project — Integration Update

## What changed in this update

The main query workflow in `search_circular.py` now connects the existing SFB paragraph 37 comparison workflow to RAG retrieval:

1. For questions mentioning Small Finance Banks, paragraph 37, or non-option derivative contracts, it attempts to load the registered RBI amendment from SQLite.
2. It extracts the operative amendment evidence from the registered amendment PDF.
3. It compares that evidence with `data/raw/204MD.pdf` using the existing SFB comparison function.
4. If the comparison remains a `candidate_deletion`, it creates an in-memory candidate and passes it to `get_relevant_change_events()`.
5. The candidate is explicitly labelled unverified in the LLM evidence context. The historical paragraph wording is not represented as authenticated.
6. The candidate is never inserted into `regulatory_changes`; this integration does not write to SQLite or Qdrant.
7. The sanctions-list direct-entry shortcut is now optional. If its circular record is unavailable, the application continues to general regulatory retrieval instead of exiting before the question is asked.

## Required local files

Keep your existing local data and configuration. This source ZIP intentionally does not include them.

The SFB candidate workflow expects:
- `data/regulatory.db`
- `data/raw/204MD.pdf` (the consolidated SFB Directions PDF)
- The amendment PDF path registered in `document_versions` for the official amendment URL.

The normal RAG workflow also expects your existing Qdrant collection under `data/qdrant`, the embedding model, and configured API credentials.

## Run

From the project directory with your virtual environment activated:

```powershell
python -m unittest test_version_comparison -v
python -m unittest test_sfb_candidate_retrieval -v
python search_circular.py
```

Ask a question such as:

```text
What happened to paragraph 37 of the Small Finance Banks Directions?
```

The answer should distinguish the official amendment's deletion statement from the unverified historical wording. If the consolidated PDF or registered amendment is unavailable, the candidate loader reports the reason and does not create a database event.

## Safety and limitations

- No database migrations or event writes are performed by this update.
- No Qdrant indexing, deletion, or rebuild is performed.
- The historical wording remains unverified until checked against an original historical RBI source.
- The amendment's immediate-upon-issuance clause is preserved as evidence; the candidate is not assigned an independently verified effective-date field.
- RBI discovery/download scripts remain separate from the interactive query workflow. They should be run deliberately, not automatically on every question.
