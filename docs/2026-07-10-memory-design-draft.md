# Memory for a Fully-Local Legal RAG — Design Draft

> **Status: DRAFT — for review. No code changes accompany this document.**
> Date: 2026-07-10. Scope: docuchat (legal-document-chat), matter-scoped local RAG on a
> 24GB unified-memory Mac (qwen3:14b chat, bge-m3 embeddings, LanceDB store, SQLCipher
> catalog, mechanical span verifier, 63/63 golden gate).

---

## 1. One-page recommendation

### The governing principle

Every fashionable memory system (Mem0, Zep/Graphiti, Letta) ultimately does one of two
things: it **steers retrieval** (picks better context) or it **injects text into the
prompt** (asserts content). For a tool whose whole promise is "every claim traces to a
verified span," the second is a trust hole: memory-injected text is exactly the kind of
uncited assertion the verifier exists to reject. So the design rule for this system is:

> **Memory may steer retrieval. Memory may never assert content — unless the memory
> entry itself carries a mechanically re-verifiable span pointer (doc, page,
> char_start, char_end, verbatim span).**

Under this rule, memory is not a new trust surface. It plugs into the existing pipeline
*upstream* of `retrieve()` (better queries, better candidate routing) or as
*provenance-carrying facts* that pass through the existing D-19 verifier unchanged. The
answer path (`answering.answer()` → `verifier.verify_answer()`) does not grow a bypass.

### What we found in the code (why memory, and which memory)

- **`answer()` is fully stateless.** Threads persist in the catalog
  (`catalog.threads/messages`) but history is never fed back — a follow-up like "and
  what's the late fee on that one?" retrieves on the bare fragment and fails or
  misfires. This is the single largest, cheapest quality gap.
- **Global/aggregate questions are structurally unanswerable.** "List every deadline in
  this matter" cannot be answered from top-5 chunk retrieval, no matter how good the
  embeddings are. The information exists but is scattered across documents.
- **`memory_notes` (routes_profile) is teachable-not-learned and fenced out of the
  answer path** (test_memory_fencing). That fence is correct and we keep it; we extend
  the same philosophy, not replace it.
- **The verifier + golden gate are the asset.** Any memory layer that produces
  span-pointered facts gets citation verification for free.

### What to build, in order

| # | Layer | What it is | Why this order |
|---|-------|-----------|----------------|
| **M-1** | **Conversation memory = query rewriting** | Condense thread history + new question into a standalone query; same retrieve→answer→verify path | Fixes a broken UX today; zero new storage; smallest diff; measurable in a week |
| **M-2** | **Matter digest: span-pointered fact extraction at ingest** | Background LLM pass per document extracts parties, dates/events, amounts, defined terms — every fact mechanically span-verified at write time, stored per matter in the catalog | Biggest answer-quality + speed-to-insight win: instant verified timeline on opening a matter, and a router that makes aggregate questions answerable |
| **M-3** | **Teachable retrieval hints (extend memory_notes)** | Per-matter user-written aliases ("the Feb agreement" = `nimbus_msa_v2.pdf`) that feed query rewriting and the FTS anchor arm only | Extends the existing teachable surface; steers retrieval, never asserts content |
| **M-4** | **Exact-match answer cache with citation re-verification** | Cache keyed on (matter, normalized question, store version); spans re-verified against current chunks before display | Latency only; safe because exact-match + re-verify makes staleness and false hits impossible |
| **M-5** | **Consolidation as a boring batch job** | Idempotent background refresh of the matter digest when documents change; dedupe facts | Do last; it's maintenance of M-2, not a new capability |

### Why this wins

- **Speed-to-insight:** M-2's timeline/parties/amounts view renders the moment a matter
  opens, from pre-extracted verified facts — zero LLM calls at read time. That is the
  "wow" a solo attorney feels in the first 10 seconds, and every row click-throughs to
  the exact source span.
- **Answer quality:** M-1 makes multi-turn conversations work at all; M-2's fact router
  makes entity/date questions and aggregates hit the right documents. Both are additive
  layers over an unchanged base path, so the 63/63 gate stays meaningful.
- **No new trust surface:** nothing in M-1..M-5 can put an unverifiable sentence in
  front of the user. Every layer is inspectable (plain SQLite rows), deletable per
  matter (all tables keyed by `matter_slug`), and fenced (explicit matter param on
  every read, same D-18 discipline).
- **It's the Karpathy version:** flat verified rows in SQLite + a query rewriter,
  instead of a temporal knowledge graph and an agentic memory OS. The state of the art
  (see §5) shows the graph/agent machinery pays off mainly on open-domain temporal
  benchmarks, at extreme token/complexity cost, and the corrected evaluations show
  modest or negative gains for exactly our query mix.

---

## 2. Mechanism designs

### M-1 — Conversation memory: query rewriting (no new storage)

**Problem.** `routes_chat.chat()` persists messages but `answer()` sees only the latest
question. Follow-ups with pronouns/ellipsis ("what about the other invoice?", "and the
late fee?") retrieve on a fragment.

**Design.** The standard, well-evidenced fix for stateless conversational RAG is to
rewrite the latest turn into a standalone question using recent history, then run the
unchanged pipeline (ChatQA, arXiv:2401.10225; question-rewriting line of work,
arXiv:2004.14652; decontextualization, arXiv:2507.04884). Concretely:

1. In `routes_chat`, when `thread_id` has prior messages, load the last N=6 messages
   (user + assistant text only, citations stripped).
2. **Gate before rewriting.** Blind rewriting of every query adds noise (a documented
   failure mode). Rewrite only when the question is plausibly context-dependent:
   short (< ~60 chars) OR contains anaphora/deixis markers (`it, that, this, those,
   the same, also, and what about, he, she, they, the other, ...`). Self-contained
   questions pass through byte-identical — the existing 63/63 questions are all
   self-contained, so the base path is provably unchanged for them.
3. One qwen3:14b call, temperature 0, tight prompt: "Rewrite the final user question to
   be fully standalone using only the conversation. Do not answer it. Do not add facts.
   If it is already standalone, return it unchanged."
4. Feed the rewritten question to `answer()`. The rewrite is only a retrieval/prompt
   input; the verifier still checks every span against retrieved chunks, so a bad
   rewrite can cause a refusal but never a fabricated citation.

**Inspectability.** The UI shows "Interpreted as: <rewritten question>" above the
answer whenever a rewrite fired (mirrors the second-pass marker pattern). The rewrite
is stored on the message row (`rewritten_question` column on `messages`) so history is
auditable.

**Schema change (catalog.py, idempotent ALTER like `doc_type`):**

```sql
ALTER TABLE messages ADD COLUMN rewritten_question TEXT;  -- NULL = no rewrite fired
```

**Cost.** One extra short LLM call on context-dependent turns only (~1–2s warm). No new
store, no consolidation, nothing to delete beyond what thread deletion already deletes.

### M-2 — Matter digest: span-pointered fact extraction at ingest

**Problem.** Aggregate and entity questions ("all deadlines", "who are the parties",
"every payment obligation") need information scattered across many chunks; top-k
similarity cannot assemble it. Attorneys also want a chronology the moment a matter
opens — commercial litigation tools treat evidence-linked chronologies as the core
deliverable (each event linked to page/line references; see Opus 2, LexChronos
arXiv line of work).

**Design.** At ingest (in the existing background `ingest_worker`, which already yields
to interactive chat via `activity.mark_chat`), run one extraction pass per chunk-group
(~2–4 pages of clean text) with qwen3:14b, temperature 0, JSON schema output:

- `party` — name, role (provider/client/plaintiff/...), organization form
- `date_event` — ISO date (or explicit partial date), event label
- `amount` — value, currency, what it is for
- `defined_term` — term, definition location
- `key_ref` — identifiers (invoice numbers, claim numbers, section cites)

Every extracted item MUST include the verbatim source span. **The write gate is
mechanical, not trusted:** before a row is inserted, the span is checked as a
normalized substring of the page slice (reuse the exact verifier normalization
contract), and offsets are located mechanically. Anything that fails the check is
dropped and counted. This mirrors the D-19 stance: the LLM proposes, the mechanical
check disposes. Structured-output hallucination is real and looks authoritative
(plausible value, valid JSON — see the Structured Output Benchmark, arXiv:2604.25359),
which is precisely why nothing enters the table on the model's word alone. On the
plus side, 13–14B-class models are demonstrably adequate extractors when the output is
verified (Phi-4 14B beat GPT-5 on value accuracy in that benchmark; a Qwen-14B
pipeline hit ~95% accuracy on medical entity extraction, PMC11015372) — and our
mechanical gate converts residual extraction errors into recall loss, never precision
loss.

**Schema (catalog.py):**

```sql
CREATE TABLE IF NOT EXISTS matter_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_slug TEXT NOT NULL,          -- the fence: every read requires it
    doc_id INTEGER NOT NULL,            -- FK documents(id); delete doc -> delete facts
    fact_type TEXT NOT NULL,            -- 'party'|'date_event'|'amount'|'defined_term'|'key_ref'
    value_json TEXT NOT NULL,           -- typed payload, e.g. {"date":"2026-03-01","label":"termination notice deadline"}
    page INTEGER NOT NULL,
    char_start INTEGER NOT NULL,        -- offsets into the clean page text (same space as chunks)
    char_end INTEGER NOT NULL,
    span TEXT NOT NULL,                 -- verbatim; mechanically verified at write time
    extractor_version TEXT NOT NULL,    -- prompt+model version; re-extract on bump
    created TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_matter_facts ON matter_facts (matter_slug, fact_type);
```

**Three consumers, in order of trust simplicity:**

1. **Timeline / matter overview UI (no LLM at read time).** Deterministic render of
   `date_event` + `party` + `amount` rows, sorted, each with a click-through to the
   PDF page + highlighted span (the pdf_view path already does this for citations).
   This is pure display of mechanically verified data — the safest possible surface
   and the fastest insight in the product.
2. **Fact router for retrieval.** For questions matching extracted entities/dates/refs
   (cheap string/anchor match against `matter_facts`, same spirit as
   `extract_anchors`), fetch the chunks containing those facts' offsets and merge them
   into the candidate pool (like the second-pass hybrid arm). The answer path and
   verifier are untouched — facts only *pick* real chunks.
3. **Aggregate answers (later, optional).** For "list all X" questions, assemble the
   answer deterministically from fact rows with standard citation tags. Because every
   span is real and offsets are real, these citations pass the existing verifier
   mechanically. This mode ships only after 1 and 2 prove out.

**Deletion & fencing.** Facts die with their document (`delete_document` cascade) and
with their matter (disposition path). Every accessor takes `matter_slug` explicitly;
a `test_memory_fencing`-style test asserts no code path reads `matter_facts` without
it, and that `answering.py` has no import path to the digest module (the router feeds
`retrieve()`'s candidate set from routes-level code, keeping the answering module pure).

**Cost.** One extraction call per ~2–4 pages at ingest, background priority. For a
50-page document: ~15–25 warm calls, minutes of background time, zero read-time cost.

**Related but separate: contextual chunk headers.** Anthropic's contextual retrieval
(prepending a 50–100 token document-context line to each chunk before embedding) cuts
retrieval failures 35–67% in their benchmarks and is the same "distill at ingest"
motion. It changes the embedded text, i.e. it is an **engine change requiring its own
full 63/63 gate cycle**, so it is noted as a candidate follow-on (M-2b), not bundled
here.

### M-3 — Teachable retrieval hints (extension of memory_notes)

**Problem.** Attorneys use shorthand the corpus doesn't contain: "the Feb agreement",
"my client", "the deposition". Today those queries embed poorly and anchor to nothing.

**Design.** Keep the existing global `memory_notes` exactly as is (greeting/suggestion
layer only, fenced). Add a **per-matter, user-written alias table** whose entries are
used in exactly two places, both upstream of retrieval:

- appended to the M-1 rewriter's context ("In this matter, 'the Feb agreement' refers
  to nimbus_msa_v2.pdf; the client is Pemberton Logistics"), and
- expanded into the FTS anchor arm (alias → expansion terms) on the second pass.

Hints steer retrieval; they are never quoted as facts and never appear in the grounded
context block, so a wrong hint can only cause a refusal or an irrelevant retrieval that
the verifier already guards. This is the ChatGPT-memory lesson applied narrowly:
user-visible, user-edited, source-attributed memory is the part of that design users
trust; silent learned inference is the part that generates the criticism
(OpenAI memory controls; arXiv:2602.01450). We ship only the trusted half —
consistent with the project's existing teachable-not-learned decision.

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS matter_hints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_slug TEXT NOT NULL,
    alias TEXT NOT NULL,        -- what the user says   (<= 80 chars)
    expansion TEXT NOT NULL,    -- what it means        (<= 200 chars)
    created TEXT NOT NULL,
    UNIQUE (matter_slug, alias)
);
```

UI: a "This matter's memory" panel — list, add, delete. Nothing is auto-learned. (A
low-risk assist: after a session, *offer* candidate hints derived from rewrites the
user accepted — but each becomes a hint only on explicit save. Optional, later.)

### M-4 — Answer cache with citation re-verification

**Problem/opportunity.** Warm answers take ~5–15s; attorneys re-ask the same questions
across sessions ("what's the indemnification cap?").

**Design constraint from the literature:** semantic (embedding-similarity) caches have
catastrophic false-positive modes — production reports of ~99% FP rates under
misconfigured thresholds, and a banking case study where "ATM locations" served loan
instructions at 0.809 confidence (InfoQ; respan.ai). For a legal tool, one confidently
wrong cached answer is disqualifying. So:

- **Exact-match only** on the normalized question (lowercase, whitespace/punct
  collapsed — the small-talk normalizer already exists). No similarity threshold to
  tune, no FP class to monitor.
- **Keyed on the store version.** LanceDB bumps `table.version` on every write (the
  matter-allowlist cache already exploits this); any ingest/delete invalidates.
- **Re-verify before display.** On a hit, re-run the mechanical span check of the
  cached citations against the *current* chunk texts (fetch by offsets). Cheap
  (milliseconds, no LLM) and makes serving a stale span impossible even if
  versioning ever missed a case. This is the local analogue of the standard advice to
  hash retrieved chunk IDs into the cache key.
- **Labeled in the UI:** "Answered previously (cached) — sources re-verified."

**Schema:**

```sql
CREATE TABLE IF NOT EXISTS answer_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    matter_slug TEXT NOT NULL,
    question_norm TEXT NOT NULL,
    store_version INTEGER NOT NULL,     -- LanceDB table version at answer time
    result_json TEXT NOT NULL,          -- full answer() result incl. citations + grounding
    created TEXT NOT NULL,
    UNIQUE (matter_slug, question_norm, store_version)
);
```

Deletable per matter; a Settings toggle disables it entirely. Expected hit rate is
modest (exact match), which is fine — this layer is a latency bonus, not a quality
layer, which is why it is fourth.

### M-5 — Consolidation: a boring batch job, not an agent

When documents are added/re-ingested/deleted, a background task (same worker/priority
machinery as ingest) refreshes the affected `matter_facts`: delete rows for the doc,
re-extract, dedupe exact-duplicate facts across documents (same normalized span +
value), and record counts in the audit log. Letta's "sleep-time compute" is the
fashionable framing of the same idea — background reorganization of memory while the
user is idle (letta.com/blog/sleep-time-compute) — but the dual-agent machinery is
unnecessary here: our memory is a table with provenance, so consolidation is an
idempotent SQL-plus-extraction job with a version stamp (`extractor_version`), not an
agent with judgment. Re-extraction on prompt/model version bump gives clean upgrade
semantics.

---

## 3. Measurement: how each layer must prove itself

**Standing rule:** the existing 63/63 golden gate stays the hard gate for the base
path. All memory layers are additive and flag-guarded; a layer that costs even one
existing golden question does not ship. New capabilities get **new golden classes**,
run by the same `run_golden.py`/`score_golden.py` machinery (extended to accept a
`turns` script per question) so scoring stays mechanical and grade-identical.

### G-MT — multi-turn class (gates M-1)

~12 scripted 2–3 turn conversations over the existing synthetic corpus, e.g.
`["What is the monthly service fee in the Nimbus-Pemberton MSA?", "And the late charge on it?"]`.
Manifest carries gold filename/page/span for the final turn. PASS criteria identical to
the existing scorer (right doc+page or same-doc same-fact, zero rejected claims, no
refusal). Also include 3 **anti-rewrite** cases: a self-contained second turn on a
*different* topic must retrieve on its own content (rewriter must not drag in stale
context) — this measures the rewrite gate's precision. Baseline first: run G-MT on
today's stateless pipeline (expected mostly FAIL), then require M-1 to take it to
target (≥ 10/12) with zero change on the 63.

### G-DIG — extraction quality (gates M-2, no LLM judging needed)

The golden manifest already contains verbatim spans for dates, amounts, parties —
reuse it as extraction ground truth, plus a hand-labeled fact inventory for 3–4 corpus
documents (one long MSA, one pleading, one correspondence set):

- **Precision:** by construction ~100% at the span level (mechanical write gate);
  measured instead as *value correctness* — does `value_json` faithfully represent its
  verified span (spot-graded once per extractor_version, then frozen as expected rows).
- **Recall:** fraction of inventoried facts extracted. Target ≥ 85% on dates/amounts
  (the timeline's bread and butter); parties ≥ 90%.
- **Report the drop count** (spans that failed mechanical verification) per run — a
  rising drop rate is the early-warning signal for extractor regressions.

### G-AGG — aggregate/timeline class (gates M-2 consumers 2–3)

~8 questions of the form "List all payment deadlines in <matter>" / "Who are the
parties across this matter's documents?" with manifest gold = the set of fact rows.
PASS = every gold fact present and cited at its true doc+page, zero fabricated items
(any listed item without a verifying citation = FAIL). Baseline on today's pipeline
(expected near-0), then measure with fact-router on.

### G-NF stays adversarial

Add 3 not-found questions phrased to *tempt* each memory layer: a follow-up whose
antecedent is absent from the corpus (M-1), an aggregate over a fact type the corpus
lacks (M-2), a question using a user hint that points at a nonexistent document (M-3).
All must produce the exact refusal with zero citations.

### Latency + hygiene budgets

- M-1 rewrite: ≤ 2.5s added on rewritten turns only; 0 on self-contained turns.
- M-2: read-time 0ms budget (all work at ingest); ingest throughput regression ≤ 25%.
- M-4: cache hit end-to-end ≤ 500ms including re-verification.
- Fencing tests per table (no read without `matter_slug`; `answering.py` imports none
  of the memory modules). Deletion tests: matter disposition leaves zero rows in
  `matter_facts` / `matter_hints` / `answer_cache`.

---

## 4. Non-goals: fashionable ideas rejected, and why

1. **Knowledge graph memory (GraphRAG / LightRAG / HippoRAG / Zep-Graphiti).**
   The corrected evidence is unkind: a systematic evaluation (arXiv:2502.11371) found
   vanilla RAG wins single-hop/detail questions while GraphRAG wins only multi-hop and
   global sensemaking; bias-controlled re-evaluation flipped LightRAG's reported 72%
   win rate over naive RAG to a slight loss. Zep's temporal graph leads LongMemEval
   but at ~600k tokens of graph construction per conversation and delayed availability
   of new facts — a nonstarter on a 24GB local machine and for "answers about the doc
   you just ingested." Our multi-hop/global need is narrow and known in advance
   (parties, dates, amounts, terms), so a typed, span-pointered fact table covers it
   with SQL, full inspectability, and trivial per-matter deletion — three properties
   graphs are bad at for a lay user. If a future eval class shows genuine multi-hop
   failures the fact router can't fix, HippoRAG-style entity linking over the fact
   table is the escalation path, not a rebuild.
2. **Learned/automatic conversation memory (Mem0-style silent fact harvesting).**
   Violates the project's teachable-not-learned decision, and the transparency
   research on ChatGPT's memory shows silent inference is exactly where user trust and
   privacy expectations break (arXiv:2602.01450). For attorney work product, a memory
   the user didn't write and can't source is a liability. We ship the inspectable half
   only (M-3), and memory that IS learned automatically (M-2) is learned from
   *documents with provenance*, never from the user.
3. **Semantic (similarity-threshold) answer caching.** Documented FP catastrophe class
   (up to 99% FP under misconfiguration; wrong-answer-at-high-confidence case studies).
   Exact-match + store-version key + mechanical re-verification gives the safe subset
   of the win with zero threshold tuning.
4. **Letta/MemGPT-style agentic memory OS (self-paging, memory tools).** Adds an
   agentic loop, latency, and non-determinism; independent comparisons note the paging
   metaphor "doesn't always pay off" on benchmarks. Our answer path is deliberately a
   pure function ending in a mechanical verifier; giving the model memory tools would
   reintroduce the autonomy this product explicitly forswears.
5. **RAPTOR-style recursive summary trees as the memory substrate.** The insight
   (retrieve at multiple abstraction levels; +20% on QuALITY) is real, but summaries
   are *paraphrases* — they cannot carry verbatim span citations, so anything answered
   from a summary node is unverifiable by our gate. The matter digest keeps the
   "distill at ingest" benefit while storing only verbatim, offset-anchored spans.
6. **Fine-tuning or preference-training the local model on user data.** Not
   inspectable, not deletable per matter, gate-hostile (every answer changes), and
   unnecessary for the observed failure modes.
7. **Cross-matter memory of any kind.** Even "harmless" global patterns ("this user
   always asks about indemnification") stay out of the answer path; the only global
   memory remains the existing profile/suggestion layer. Matter isolation (D-18) is a
   product invariant, not an optimization target.

---

## 5. Sources

**Memory systems & benchmarks**
- Agent memory frameworks compared (Mem0/Zep/Letta, LOCOMO + LongMemEval numbers): https://vectorize.io/articles/best-ai-agent-memory-systems ; https://www.agenticwire.news/article/mem0-zep-letta-agent-memory ; https://particula.tech/blog/agent-memory-frameworks-tested-mem0-zep-letta-cognee-2026 ; https://www.graphlit.com/blog/survey-of-ai-agent-memory-frameworks ; https://rohitraj.tech/en/notes/open-source-ai-agent-memory-mem0-vs-zep-letta-2026
- Letta sleep-time compute & agent memory: https://www.letta.com/blog/sleep-time-compute/ ; https://www.letta.com/blog/agent-memory/
- Curated memory research index: https://github.com/TeleAI-UAGI/Awesome-Agent-Memory

**Graphs vs vectors**
- RAG vs GraphRAG systematic evaluation: https://arxiv.org/abs/2502.11371
- Bias-corrected GraphRAG meta-analysis / architecture tradeoffs: https://tianpan.co/blog/2026-04-17-graphrag-vs-vector-rag-knowledge-graphs ; https://tianpan.co/blog/2026-04-19-graphrag-vs-vector-rag-architecture-decision
- HippoRAG (OpenIE graph + personalized PageRank): https://arxiv.org/abs/2405.14831

**Conversational RAG / query rewriting**
- ChatQA (conversational QA + retrieval): https://arxiv.org/abs/2401.10225
- Question rewriting for conversational QA: https://arxiv.org/abs/2004.14652
- Decontextualizing user questions: https://arxiv.org/abs/2507.04884

**Ingest-time distillation & extraction**
- Anthropic contextual retrieval (35–67% retrieval-failure reduction): https://www.anthropic.com/news/contextual-retrieval
- LLM-generated metadata for enterprise RAG: https://arxiv.org/abs/2512.05411
- Structured Output Benchmark (14B ≈ frontier on value accuracy): https://arxiv.org/html/2604.25359v1
- PARSE (schema optimization for reliable entity extraction): https://arxiv.org/html/2510.08623v1
- Qwen-14B medical entity extraction pipeline (~95% accuracy): https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11015372/
- LexChronos (legal event timeline extraction): https://arxiv.org/pdf/2603.01651
- Evidence-linked litigation chronologies (practice standard): https://www.opus2.com/litigation-timeline-software/

**Caching**
- Semantic-cache false positives, banking case study: https://www.infoq.com/articles/reducing-false-positives-retrieval-augmented-generation/
- When to ship/skip semantic cache; chunk-ID keying: https://www.respan.ai/articles/semantic-cache-llm ; https://myengineeringpath.dev/genai-engineer/llm-caching/

**User-controllable memory**
- OpenAI memory & controls: https://openai.com/index/memory-and-new-controls-for-chatgpt/
- Deconstructing ChatGPT memory (transparency gaps): https://arxiv.org/pdf/2602.01450

**Summary trees**
- RAPTOR (ICLR 2024): https://arxiv.org/abs/2401.18059
