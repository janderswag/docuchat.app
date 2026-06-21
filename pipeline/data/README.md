# pipeline/data — curated reference data (tracked)

Tracked, synthetic-free reference data used by the pipeline. **No document bodies or
secrets** live here (those stay git-ignored, D-28). This directory holds only authored
metadata.

## `clause_taxonomy.json` — Contract Review clause checklist (T-CLAUSE, M-ENRICH)

A curated set of 20 standard contract clauses a solo attorney checks on a commercial
agreement. Each entry is `{id, name, category, question, doc_types}`. The pipeline
(`clauses.extract_clauses`) poses each `question` to the existing grounded-answer path
(`answer()` + the mechanical span verifier) and classifies the result:

- **found** — the answer returned **at least one span-verified, chunk-derived citation**
  (D-19/D-38). Only then is a value + citation shown.
- **potentially_missing** — the answer was the exact D-30 refusal
  (`"I could not find this in the documents."`). Advisory, **non-citable** — surfaced as
  "not located in the documents", never as legal advice and never with a fabricated
  citation for an absence.
- **not_confirmed** — prose was returned but the verifier rejected every asserted span.
  Never shown as found (the never-false-accept invariant).

### Provenance (CUAD, CC BY 4.0)

The clause **categories** are informed by the **CUAD** (Contract Understanding Atticus
Dataset) 41-label taxonomy from **The Atticus Project**, reviewed at
`/tmp/Legal-AI_Project/server/data/questions*.txt`. CUAD is licensed **CC BY 4.0**
(https://www.atticusprojectai.org/cuad).

We did **not** copy CUAD's question text. CUAD phrases every label as *"Highlight the
parts (if any) of this contract related to \"X\" that should be reviewed by a lawyer.
Details: …"*. The natural-language questions in `clause_taxonomy.json` are **our own
authored phrasing**, written for an attorney locate-and-summarize workflow and aligned to
this project's product boundary. No CUAD answer spans, contracts, or annotations are
vendored — only the clause-category vocabulary informs ours, with attribution per CC BY.

### Product boundary

Every question asks **what the documents say** — none asks for advice, drafting, an
opinion, or a recommendation (CLAUDE.md "What this project is NOT"). `doc_types` is
advisory display metadata describing where a clause typically appears; the **full
checklist is always run** so that an absent standard clause surfaces honestly as
"potentially missing" rather than being silently skipped.
