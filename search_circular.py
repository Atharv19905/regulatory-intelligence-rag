import os



import re



import sqlite3



import time



from datetime import date



from pathlib import Path







import pymupdf



from google import genai

from groq import Groq

from dotenv import load_dotenv



from qdrant_client import QdrantClient



from qdrant_client.models import Filter, FieldCondition, MatchAny



from sentence_transformers import SentenceTransformer







BASE_DIR = Path(__file__).resolve().parent



DB_PATH = BASE_DIR / "data" / "regulatory.db"



QDRANT_PATH = BASE_DIR / "data" / "qdrant"



COLLECTION_NAME = "regulatory_chunks"



MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"



GEMINI_MODEL = "gemini-3.6-flash"

GROQ_MODEL = "openai/gpt-oss-20b"



# Load API keys from the project .env file.

load_dotenv(BASE_DIR / ".env")











def get_circular():



    """Load metadata for the sanctions-list circular entry shortcut."""



    with sqlite3.connect(DB_PATH) as connection:



        connection.row_factory = sqlite3.Row



        row = connection.execute(



            """



            SELECT d.document_id, d.title, d.regulator, d.source_url,



                   v.version_id, v.version_number, v.file_path,



                   v.publication_date, v.effective_date



            FROM documents AS d



            JOIN document_versions AS v ON d.document_id = v.document_id



            WHERE d.regulator = 'RBI'



              AND d.title LIKE '%Amendment of 03 Entries%'



            ORDER BY v.version_number DESC



            LIMIT 1



            """



        ).fetchone()







    if row is None:



        raise SystemExit("RBI sanctions-list circular not found in SQLite.")



    return dict(row)











def format_name(raw_name):



    """Convert numbered PDF name fields into a readable name."""



    parts = re.findall(r"\d+:\s*(.*?)(?=\s+\d+:\s*|$)", raw_name)



    if not parts:



        return raw_name.strip()



    parts = [part.strip() for part in parts if part.strip().lower() != "na"]



    return " ".join(parts)











def extract_entries(pdf_path):



    """Extract standalone sanctions-list entries and their PDF page numbers."""



    entries = []



    with pymupdf.open(pdf_path) as pdf:



        for page_number, page in enumerate(pdf, start=1):



            text = page.get_text("text")



            pattern = re.compile(



                r"(?m)^\s*((?:QDi|QDe)\.\d+)\s+Name:\s*(.+)$",



                re.IGNORECASE



            )



            for match in pattern.finditer(text):



                raw_name = match.group(2).strip()



                entries.append({



                    "identifier": match.group(1).strip(),



                    "name": format_name(raw_name),



                    "original_text": raw_name,



                    "page_number": page_number



                })



    return entries











def is_entry_question(question):



    """Return True for questions handled by the sanctions-entry shortcut."""



    question_lower = question.lower()



    return (



        "amended entr" in question_lower



        or "three entr" in question_lower



        or "entry identifiers" in question_lower



        or "entry names" in question_lower



    )











def answer_entry_question(question, circular, entries):



    """Answer questions asking for amended entry names or IDs."""



    if not is_entry_question(question):



        return False







    print("\nExtracted entries from the circular:\n")



    print(f"Document: {circular['title']}")



    print(f"Publication date: {circular['publication_date']}")



    print(f"Source: {circular['source_url']}\n")



    for entry in entries:



        print(f"Identifier: {entry['identifier']}")



        print(f"Name: {entry['name']}")



        print(f"Page: {entry['page_number']}")



        print(f"Version: {circular['version_number']}")



        print("-" * 50)



    print(f"\nFound {len(entries)} standalone entries in the extracted PDF.")



    return True











def keyword_score(text, question):



    """Score exact identifiers and meaningful question keywords."""



    text_lower = text.lower()



    question_lower = question.lower()



    score = 0







    identifiers = re.findall(



        r"\b(?:QDi|QDe)\.\d+\b", question, flags=re.IGNORECASE



    )



    for identifier in identifiers:



        if identifier.lower() in text_lower:



            score += 20







    ignored_words = {



        "which", "what", "when", "where", "this", "that", "with",



        "from", "listed", "circular", "about", "have", "does", "their",



        "there", "changed", "change", "changes", "tell", "explain",



        "show", "please", "were", "into", "under", "after", "before",



        "paragraph", "section"



    }



    keywords = [



        word for word in re.findall(r"\b[a-zA-Z]{4,}\b", question_lower)



        if word not in ignored_words



    ]



    for keyword in set(keywords):



        if keyword in text_lower:



            score += 1



    return score











def get_relevant_change_events(question, as_of_date=None):



    """



    Retrieve relevant stored change events from SQLite.



    Changes are returned only on or after their effective date.



    """



    if not question.strip():



        return []







    ignored_words = {



        "what", "when", "where", "which", "does", "this", "that",



        "from", "with", "about", "have", "were", "into", "under",



        "tell", "explain", "show", "please", "changed", "change",



        "changes", "regulation", "regulations", "rule", "rules",



        "paragraph", "section", "before", "after", "effective",



        "date", "deleted", "deletion", "rbi", "repo", "rate", "mpc",

        "minutes", "monetary", "policy", "october", "current", "according",

        "scheduled", "next", "month"



    }



    question_words = {



        word.lower()



        for word in re.findall(r"\b[a-zA-Z]{3,}\b", question)



        if word.lower() not in ignored_words



    }



    explicit_paragraph_37 = bool(



        re.search(r"\b(?:paragraph|par&#x61;\.?)\s*37\b", question, re.IGNORECASE)



        or re.search(r"\b37\b", question)



    )





    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row



    try:

        rows = connection.execute(

            """

            SELECT

                rc.change_id,

                rc.target_title,

                rc.provision,

                rc.change_type,

                rc.effective_date,

                rc.old_text,

                rc.new_text,

                rc.historical_source_url,

                rc.amendment_source_url,

                rc.amendment_evidence,

                rc.provenance_status,

                dv.publication_date AS amendment_publication_date

            FROM regulatory_changes AS rc

            LEFT JOIN document_versions AS dv

                ON dv.version_id = rc.amendment_version_id

            ORDER BY rc.effective_date DESC, rc.change_id DESC

            """

        ).fetchall()

    except sqlite3.OperationalError:

        # Keep semantic search usable if required tables are absent.

        return []

    finally:

        connection.close()



    matches = []





    for row in rows:



        event = dict(row)





        effective_date = event.get("effective_date")

        amendment_publication_date = event.get("amendment_publication_date")



        # Exclude changes that were not yet effective by the requested date.

        if as_of_date and effective_date and effective_date > as_of_date:

            continue





        # Exclude amendments that cannot be verified as published by the cutoff.

        if as_of_date:

            if not amendment_publication_date:

                continue



            if amendment_publication_date > as_of_date:

                continue











        searchable_text = " ".join([



            event.get("target_title") or "",



            event.get("provision") or "",



            event.get("change_type") or "",



            event.get("old_text") or "",



            event.get("new_text") or "",



            event.get("amendment_evidence") or ""



        ]).lower()







        matched_words = [word for word in question_words if word in searchable_text]



        score = len(set(matched_words))



        if explicit_paragraph_37 and "paragraph 37" in (



            event.get("provision") or ""



        ).lower():



            score += 5







        if score > 0:



            event["relevance_score"] = score



            matches.append(event)







    matches.sort(key=lambda event: event["relevance_score"], reverse=True)



    relevant = [



        event for event in matches



        if event["relevance_score"] >= 2



        or (



            explicit_paragraph_37



            and "paragraph 37" in (event.get("provision") or "").lower()



        )



    ]



    return relevant[:5]









def check_answer_grounding(question, answer, evidence):

    """

    Check whether an answer's factual claims are supported by supplied evidence.



    Returns SUPPORTED, UNSUPPORTED, or UNCERTAIN.

    Returns UNCERTAIN if the check cannot be completed.

    """

    if not answer or not evidence:

        return "UNCERTAIN"



    audit_prompt = f"""

You are a strict evidence-verification system for banking regulations.



Compare the proposed answer with the supplied evidence.



Rules:

- Check factual claims, dates, numbers, regulatory requirements, and conclusions.

- A citation existing does not automatically make a claim supported.

- Treat stored change events as recorded claims, not automatically verified facts.

- Do not use outside knowledge.

- If any material factual claim is contradicted or unsupported, return UNSUPPORTED.

- If the evidence is ambiguous or insufficient, return UNCERTAIN.

- Return SUPPORTED only when all material factual claims are supported.



Question:

{question}



Evidence:

{evidence}



Proposed answer:

{answer}



Return exactly one word:

SUPPORTED

UNSUPPORTED

or

UNCERTAIN

"""



    groq_key = os.getenv("GROQ_API_KEY")

    if groq_key:

        try:

            client = Groq(api_key=groq_key)

            response = client.chat.completions.create(

                model=GROQ_MODEL,

                messages=[

                    {

                        "role": "system",

                        "content": (

                            "Verify claims strictly against supplied evidence. "

                            "Return exactly one verdict word."

                        ),

                    },

                    {"role": "user", "content": audit_prompt},

                ],

                temperature=0,

                max_completion_tokens=20,

            )



            verdict = (

                response.choices[0].message.content or ""

            ).strip().upper()



            if verdict in {"SUPPORTED", "UNSUPPORTED", "UNCERTAIN"}:

                return verdict



        except Exception as error:

            print(f"Groq grounding check failed: {error}")



        gemini_key = os.getenv("GEMINI_API_KEY")



    if gemini_key:

        client = genai.Client()



        # Retry transient service failures, but keep the retry limit small.

        for attempt in range(3):

            try:

                response = client.models.generate_content(

                    model=GEMINI_MODEL,

                    contents=audit_prompt,

                )



                verdict = (response.text or "").strip().upper()



                if verdict in {"SUPPORTED", "UNSUPPORTED", "UNCERTAIN"}:

                    return verdict



                print("Gemini returned an invalid grounding verdict.")

                return "UNCERTAIN"



            except Exception as error:

                print(

                    f"Gemini grounding check failed "

                    f"(attempt {attempt + 1}/3): {error}"

                )



                if attempt < 2:

                    time.sleep(2 ** attempt)



    return "UNCERTAIN"









def display_answer_if_supported(

    question, answer, evidence, provider, show_debug=False

):

    """Display only grounded answers; optionally show verification diagnostics."""

    verdict = check_answer_grounding(question, answer, evidence)



    print(f"\nAnswer grounding verdict: {verdict}")



    if verdict != "SUPPORTED":

        print(

            "The answer was blocked because its claims could not "

            "all be verified against the supplied evidence."

        )

        if show_debug:

            print("\nUNVERIFIED DRAFT (for debugging only; do not rely on it):")

            print(answer)

        return False



    print("\n" + "=" * 60)

    print(f"GENERATED ANSWER ({provider}; grounding checked)")

    print("=" * 60)

    print(answer)



    if show_debug:

        print("\n[Debug] Grounding evidence was supplied to the verifier.")

        print("[Debug] Full evidence is available in the retrieval diagnostics.")



    return True









def generate_answer(question, candidates, change_events=None, as_of_date=None):

    """Generate an evidence-grounded answer with Groq first and Gemini fallback."""

    change_events = change_events or []

    if not candidates and not change_events:

        print("\nNo eligible, relevant regulatory evidence was retrieved for this cutoff.")

        return



    evidence_parts = []

    for index, item in enumerate(candidates[:4], start=1):

        payload = item["payload"]

        evidence_parts.append(

            f"[Retrieved passage {index}]\n"

            f"Document: {payload.get('title', 'Unknown')}\n"

            f"Regulator: {payload.get('regulator', 'Unknown')}\n"

            f"Publication date: {payload.get('publication_date', 'Unknown')}\n"

            f"Version: {payload.get('version_number', 'Unknown')}\n"

            f"Page: {payload.get('page_number', 'Unknown')}\n"

            f"Source URL: {payload.get('source_url', 'Unavailable')}\n"

            f"Passage:\n{payload.get('text', '')}"

        )



    for event in change_events:

        evidence_parts.append(

            f"[Stored regulatory change event {event['change_id']}]\n"

            f"Regulation: {event['target_title']}\n"

            f"Provision: {event['provision']}\n"

            f"Change type: {event['change_type']}\n"

            f"Recorded effective/temporal date: {event['effective_date']}\n"

            f"Previous wording recorded: {event['old_text']}\n"

            f"New state recorded: {event['new_text']}\n"

            f"Amendment evidence: {event['amendment_evidence']}\n"

            f"Amendment source URL: {event['amendment_source_url']}\n"

            f"Historical text source URL: {event['historical_source_url']}\n"

            f"Historical source status: {event['provenance_status']}"

        )



    evidence = "\n\n".join(evidence_parts)

    cutoff_note = (

        f"The user's requested publication cutoff date is {as_of_date}."

        if as_of_date else "The user did not specify a historical cutoff date."

    )

    prompt = f"""You are a banking and financial regulatory intelligence assistant.

Answer using ONLY the evidence below.



Rules:

1. Do not invent regulatory requirements, dates, or historical wording.

2. Distinguish retrieved passages from stored change events.

3. A stored event is a recorded claim, not independent proof that every part of its historical wording is authentic.

4. If historical wording has secondary-source provenance, disclose that limitation when discussing the old wording.

5. Respect the requested historical cutoff. Do not use evidence published after it.

6. Cite document page numbers when available and provide source URLs.

7. If evidence is insufficient or conflicting, state the limitation.

8. Do not claim to have checked external sources.



TEMPORAL CONTEXT:

{cutoff_note}



USER QUESTION:

{question}



EVIDENCE:

{evidence}



Write a concise answer followed by a Sources section."""



    # Prefer Groq. If it is unavailable or rate-limited, try Gemini if configured.

    groq_key = os.getenv("GROQ_API_KEY")

    if groq_key:

        try:

            client = Groq(api_key=groq_key)

            response = client.chat.completions.create(

                model=GROQ_MODEL,

                messages=[

                    {"role": "system", "content": "Answer strictly from supplied evidence; never fabricate citations."},

                    {"role": "user", "content": prompt},

                ],

                temperature=0.1,

                max_completion_tokens=1200,

            )

            answer = response.choices[0].message.content

            if answer:

                display_answer_if_supported(

                    question, answer, evidence, "Groq"

                )

                return

            print("Groq returned an empty answer; trying Gemini if configured.")

        except Exception as error:

            print(f"\nGroq answer generation failed: {error}")

            print("Trying Gemini if configured...")

    else:

        print("GROQ_API_KEY is not set; trying Gemini if configured.")



    if os.getenv("GEMINI_API_KEY"):

        try:

            client = genai.Client()

            response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)

            answer = response.text

            if answer:

                display_answer_if_supported(

                    question, answer, evidence, "Gemini fallback"

                )

                return

            print("Gemini returned an empty answer.")

        except Exception as error:

            print(f"Gemini answer generation failed: {error}")

    else:

        print("GEMINI_API_KEY is not set; Gemini fallback skipped.")



    # Deterministic fallback: show actual retrieved evidence, never invent a summary.

    print("\nNo LLM provider is currently available. Showing retrieved evidence instead.")

    for index, item in enumerate(candidates[:4], start=1):

        payload = item["payload"]

        print(f"\nEvidence {index}: {payload.get('title', 'Unknown')} â€” page {payload.get('page_number', 'Unknown')}")

        print(f"Publication date: {payload.get('publication_date', 'Unknown')}")

        print(f"Source: {payload.get('source_url', 'Unavailable')}")

        print(payload.get("text", ""))

    for event in change_events:

        print(f"\nStored change event {event.get('change_id')}: {event.get('provision')}")

        print(f"Change type: {event.get('change_type')}; recorded date: {event.get('effective_date')}")

        print(f"Old text recorded: {event.get('old_text')}")

        print(f"New state recorded: {event.get('new_text')}")

        print(f"Source: {event.get('amendment_source_url')}")

        print(f"Provenance: {event.get('provenance_status')}")





def get_eligible_document_ids(as_of_date):

    """Return document IDs with at least one version published by cutoff."""

    connection = sqlite3.connect(DB_PATH)

    try:

        rows = connection.execute(

            """

            SELECT DISTINCT document_id

            FROM document_versions

            WHERE publication_date IS NOT NULL

              AND publication_date <= ?

            """,

            (as_of_date,),

        ).fetchall()



        return [row[0] for row in rows]

    finally:

        connection.close()







def get_eligible_version_ids(as_of_date):

    """Return version IDs published on or before the requested date."""

    connection = sqlite3.connect(DB_PATH)

    try:

        rows = connection.execute(

            """

            SELECT version_id

            FROM document_versions

            WHERE publication_date IS NOT NULL

              AND publication_date <= ?

            """,

            (as_of_date,),

        ).fetchall()

        return [row[0] for row in rows]

    finally:

        connection.close()







def normalize_pdf_text(text):

    """Normalize PDF text for comparison despite line breaks and spacing."""

    text = str(text or "").replace("\u00ad", "")

    text = re.sub(r"-\s*\n\s*", "", text)

    text = re.sub(r"\s+", " ", text)

    return text.strip().casefold()





def passage_exists_on_page(passage, page_text):

    """Return True only when the normalized passage appears on the page."""

    normalized_passage = normalize_pdf_text(passage)

    normalized_page = normalize_pdf_text(page_text)



    if not normalized_passage:

        return False



    return normalized_passage in normalized_page





def validate_candidate_citations(candidates, as_of_date=None):

    """

    Validate retrieved passage metadata against SQLite.



    Rejects passages with missing or mismatched document/version metadata,

    invalid page numbers, missing source URLs, or publication dates after

    the requested cutoff.

    """

    if not candidates:

        return []



    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row



    validated = []



    try:

        for item in candidates:

            payload = item.get("payload", {})



            document_id = payload.get("document_id")

            version_number = payload.get("version_number")

            page_number = payload.get("page_number")



            if document_id is None or version_number is None:

                print("Rejected citation: missing document ID or version.")

                continue



            try:

                page_number = int(page_number)

                version_number = int(version_number)

                document_id = int(document_id)

            except (TypeError, ValueError):

                print("Rejected citation: invalid ID, version, or page number.")

                continue



            if page_number < 1:

                print("Rejected citation: page number must be positive.")

                continue



            row = connection.execute(

                """

                SELECT

                    d.document_id,

                    d.title,

                    d.source_url,

                    v.version_number,

                    v.publication_date,

                    v.file_path

                FROM documents AS d

                JOIN document_versions AS v

                    ON d.document_id = v.document_id

                WHERE d.document_id = ?

                  AND v.version_number = ?

                """,

                (document_id, version_number),

            ).fetchone()



            if row is None:

                print("Rejected citation: document/version not found in SQLite.")

                continue



            publication_date = row["publication_date"]



            if not publication_date:

                print("Rejected citation: publication date is missing.")

                continue



            try:

                date.fromisoformat(publication_date)

            except (TypeError, ValueError):

                print("Rejected citation: invalid publication date in SQLite.")

                continue



            if as_of_date and publication_date > as_of_date:

                print("Rejected citation: published after the requested cutoff.")

                continue



            source_url = row["source_url"]

            if not source_url or not source_url.startswith(("https://", "http://")):

                print("Rejected citation: missing or invalid source URL.")

                continue



            pdf_path = Path(row["file_path"])

            if not pdf_path.is_absolute():

                pdf_path = BASE_DIR / pdf_path



            if not pdf_path.is_file():

                print("Rejected citation: source PDF file is missing.")

                continue





            try:

                with pymupdf.open(pdf_path) as pdf:

                    if page_number > len(pdf):

                        print("Rejected citation: page exceeds PDF page count.")

                        continue



                    page_text = pdf[page_number - 1].get_text("text")

                    passage_text = payload.get("text", "")



                    if not passage_exists_on_page(passage_text, page_text):

                        print(

                            "Rejected citation: retrieved passage does not match "

                            "the cited PDF page."

                        )

                        continue



            except Exception as error:

                print(f"Rejected citation: source PDF verification failed: {error}")

                continue





            # Replace citation metadata with values verified from SQLite.

            item = dict(item)

            item["payload"] = dict(payload)

            item["payload"].update({

                "document_id": row["document_id"],

                "title": row["title"],

                "version_number": row["version_number"],

                "publication_date": publication_date,

                "source_url": source_url,

                "page_number": page_number,

            })



            validated.append(item)



    finally:

        connection.close()



    return validated









def topic_relevant(question, payload):

    """Reject obviously off-topic passages for common narrow query types."""

    question_lower = question.lower()

    title = str(payload.get("title", "")).lower()

    text = str(payload.get("text", "")).lower()

    combined = f"{title} {text}"



    # Monetary-policy questions should not be answered from sanctions or

    # derivative-contract passages merely because embeddings score them highly.

    monetary_terms = ("repo rate", "repo", "monetary policy", "mpc", "policy rate")

    if any(term in question_lower for term in monetary_terms):

        return any(term in combined for term in (

            "repo rate", "policy repo rate", "monetary policy committee",

            "monetary policy", "mpc minutes", "policy rate"

        ))

    return True





def find_future_topic_documents(question, as_of_date):

    """Find later-published documents whose titles match a narrow query topic."""

    if not as_of_date:

        return []

    question_lower = question.lower()

    if not any(term in question_lower for term in ("repo rate", "repo", "mpc", "monetary policy")):

        return []



    with sqlite3.connect(DB_PATH) as connection:

        connection.row_factory = sqlite3.Row

        rows = connection.execute(

            """

            SELECT d.title, d.source_url, v.publication_date

            FROM documents d

            JOIN document_versions v ON d.document_id = v.document_id

            WHERE v.publication_date > ?

            ORDER BY v.publication_date ASC

            """,

            (as_of_date,),

        ).fetchall()



    terms = ("mpc", "monetary policy", "repo rate")

    return [dict(row) for row in rows if any(

        term in str(row["title"]).lower() for term in terms

    )]





def semantic_search(question, circular, as_of_date=None):



    """Retrieve, rank, and deduplicate regulatory passages."""



    model = SentenceTransformer(MODEL_NAME)



    client = QdrantClient(path=str(QDRANT_PATH))







    try:



        query_vector = model.encode(



            question, normalize_embeddings=True



        ).tolist()









        eligible_version_ids = None

        if as_of_date:

            eligible_version_ids = get_eligible_version_ids(as_of_date)









        results = []



        if eligible_version_ids is None or eligible_version_ids:





            query_filter = None



            if eligible_version_ids is not None:

                query_filter = Filter(

                    must=[

                        FieldCondition(

                            key="version_id",

                            match=MatchAny(any=eligible_version_ids),

                        )

                    ]

                )





            results = client.query_points(



                collection_name=COLLECTION_NAME,



                query=query_vector,



                limit=30,



                with_payload=True,



                query_filter=query_filter



            ).points







        candidates = []



        for result in results:



            payload = result.payload or {}



            text = payload.get("text", "").strip()



            if not text:

                continue

            if not topic_relevant(question, payload):

                continue



            semantic_score = float(result.score)



            exact_score = keyword_score(text, question)



            candidates.append({



                "payload": payload,



                "semantic_score": semantic_score,



                "keyword_score": exact_score,



                "combined_score": semantic_score + 0.05 * exact_score



            })







        candidates.sort(



            key=lambda item: item["combined_score"], reverse=True



        )







        # Remove highly overlapping passages from the same document/page.



        unique_candidates = []



        for item in candidates:



            current_payload = item["payload"]



            current_text = current_payload.get("text", "")



            current_words = set(current_text.lower().split())



            current_page = current_payload.get("page_number")



            current_doc = current_payload.get("document_id")

            current_version = current_payload.get("version_id")

            is_duplicate = False







            for existing in unique_candidates:



                existing_payload = existing["payload"]





                if (

                    existing_payload.get("document_id") != current_doc

                    or existing_payload.get("version_id") != current_version

                    or existing_payload.get("page_number") != current_page

                ):

                    continue





                existing_words = set(



                    existing_payload.get("text", "").lower().split()



                )



                if not current_words or not existing_words:



                    continue



                overlap = len(current_words & existing_words) / min(



                    len(current_words), len(existing_words)



                )



                if overlap >= 0.85:



                    is_duplicate = True



                    break







            if not is_duplicate:



                unique_candidates.append(item)







        candidates = unique_candidates



        # Validate passage metadata against the authoritative SQLite records.



        candidates = validate_candidate_citations(

            candidates,

            as_of_date=as_of_date,

        )



        # Keep only passages relevant to the user's question.

        candidates = [

            item for item in candidates

            if topic_relevant(question, item.get("payload", {}))

        ]



        change_events = get_relevant_change_events(question, as_of_date)





        future_documents = find_future_topic_documents(question, as_of_date)

        if not candidates and future_documents:

            print("\nRelevant-topic documents exist, but they are after the requested cutoff:")

            for document in future_documents:

                print(f"- {document['title']} (published {document['publication_date']})")

                print(f"  Source: {document['source_url']}")

            print("These documents are excluded from the answer by the publication cutoff.")





        relevant_change_events = [

            event for event in change_events

            if topic_relevant(

                question,

                {

                    "title": event.get("target_title", ""),

                    "text": " ".join(

                        str(event.get(key, "") or "")

                        for key in (

                            "provision",

                            "change_type",

                            "old_text",

                            "new_text",

                            "amendment_evidence",

                        )

                    ),

                },

            )

        ]



        if not candidates and not relevant_change_events:

            print(

                "\nNO ANSWER: No eligible, relevant evidence was found "

                "for this question and publication cutoff."

            )

            return



        generate_answer(



            question,



            candidates,



            change_events=relevant_change_events,



            as_of_date=as_of_date



        )









        show_debug = False  # Set to True to inspect retrieval diagnostics



        if show_debug and change_events:

            print("\nRelevant stored regulatory changes:\n")



            for event in change_events:

                print(f"Change ID: {event['change_id']}")

                print(f"Regulation: {event['target_title']}")

                print(f"Provision: {event['provision']}")

                print(f"Change type: {event['change_type']}")

                print(f"Effective date: {event['effective_date']}")

                print(f"Amendment source: {event['amendment_source_url']}")

                print(f"Historical source status: {event['provenance_status']}")

                print("-" * 60)



        if show_debug:

            print("\nRelevant passages (hybrid ranking):\n")



            for index, item in enumerate(candidates[:7], start=1):

                payload = item["payload"]



                print(f"Result {index}")

                print(f"Score: {item['combined_score']:.4f}")

                print(f"Document: {payload.get('title', 'Unknown')}")

                print(f"Page: {payload.get('page_number', 'Unknown')}")

                print(f"Version: {payload.get('version_number', 'Unknown')}")

                print(f"Source: {payload.get('source_url', 'Unavailable')}")

                print("\nPassage:")

                print(payload.get("text", ""))

                print("-" * 60)







        if not candidates:



            print("No relevant semantic passages were retrieved.")



    finally:



        client.close()











def main():



    circular = get_circular()



    pdf_path = Path(circular["file_path"])



    if not pdf_path.is_absolute():



        pdf_path = BASE_DIR / pdf_path



    if not pdf_path.exists():



        raise SystemExit(f"PDF file not found: {pdf_path}")







    question = input(



        "Ask a question about the regulatory documents: "



    ).strip()



    if not question:



        raise SystemExit("Please enter a question.")







    date_input = input(



        "Optional publication cutoff date (YYYY-MM-DD, press Enter to skip): "



    ).strip()



    as_of_date = None



    if date_input:



        try:



            as_of_date = date.fromisoformat(date_input).isoformat()



        except ValueError:



            raise SystemExit(



                "Invalid date. Use YYYY-MM-DD, for example 2026-10-19."



            )







    entries = extract_entries(pdf_path)



    circular_publication_date = circular.get("publication_date")







    # Do not answer a direct-entry question using a circular published after



    # the requested cutoff. Continue to general search for other questions.



    if (



        as_of_date



        and circular_publication_date



        and circular_publication_date > as_of_date



    ):



        if is_entry_question(question):



            print(



                f"That circular was published on {circular_publication_date}, "



                f"after the requested cutoff date {as_of_date}. "



                "Its entries are not available as of that date."



            )



            return



    elif answer_entry_question(question, circular, entries):



        return







    semantic_search(question, circular, as_of_date)











if __name__ == "__main__":



    main()
