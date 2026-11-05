# RBI Master Directions pipeline

This adds a controlled workflow without changing the existing RAG search, SQLite schema, or Qdrant collection.

## 1. Discover (no database writes)

```powershell
python run_rbi_pipeline.py --discover
```

Review `data/versions/rbi_master_directions_discovered.json`. The manifest contains the RBI detail-page URL, direct PDF URL, title, and listing publication date.

## 2. Download and register only selected documents

Use numeric IDs from the `detail_url` query string. For example:

```powershell
python run_rbi_pipeline.py --download-ids 11060 12427
```

The script accepts only HTTPS direct PDFs hosted on an RBI domain and checks the PDF signature before writing/registering. It uses the stable detail-page URL as the logical document key, allowing subsequent PDFs for that Master Direction to become versions of the same SQLite document. Publication date is taken from the RBI listing; effective date is left blank unless independently established from authoritative evidence.

## 3. Compare the latest two registered versions

Find the `document_id` in `data/regulatory.db`, then run:

```powershell
python run_rbi_pipeline.py --compare DOCUMENT_ID
```

The report preserves page references. Added/removed/modified text is a candidate textual difference, not by itself proof of a legally operative amendment.

## Safety

- Discovery alone does not register or download documents.
- Downloads require explicit IDs chosen after manifest review.
- No existing PDF, database row, or Qdrant point is deleted.
- This pipeline does not automatically re-index Qdrant. Review and approve a document/version before using the existing indexing workflow.
- Existing `download_regulations.py` uses version-specific PDF URLs as logical document keys; use this new pipeline for RBI Master Directions version tracking.
