# Speed to Insight — latency map + intervention plan (DRAFT, 2026-07-10)

> Research draft only. No code was changed for this document.
> #1 UX metric: **time from Ask to a trustworthy cited answer on screen.**
> Governing rule: anything that touches the answer engine must re-pass the golden gate
> (63/63 present + NF 9/9 + 0 rejected claims, per D-75/D-79 discipline) before it ships.

---

## 1. Where the time actually goes (mapped from code)

The default UI path is `/chat/stream` (`pipeline/routes_chat.py:104`, D-63), which calls
`answer_stream()` (`pipeline/answering.py:474`). Every stage below is **sequential** today.

| # | Stage | Code | Est. latency (M4 Pro 24GB, warm) | Notes |
|---|-------|------|------|-------|
| 1 | Route validation + thread persist (SQLite) | `routes_chat.py:109-115` | ~1-5 ms | Two catalog writes before any work starts. Negligible. |
| 2 | Small-talk gate | `answering.py:63` | ~0 | Pure string match; already skips retrieval for greetings (UX-1). |
| 3 | **Question embedding** (bge-m3 via Ollama `/api/embed`) | `retrieval.py:135` → `embed_store.py:55` | ~30-80 ms warm; **~1-3 s cold** | `embed_texts()` sends **no `keep_alive`**, so bge-m3 falls back to Ollama's 5m default and unloads while qwen3:14b stays warm 30m. Startup `preload_model()` (`api.py:127`) warms **only the chat model**. First question and every question after >5 min idle pays an embedder reload. |
| 4 | LanceDB dense search, matter-prefiltered, top-5 | `retrieval.py:135-139` | ~10-50 ms at current corpus scale | Matter allowlist is version-cached (`_MATTERS_CACHE`); D-66 fixed the full-store scan. Not a bottleneck. |
| 5 | Prompt assembly (~2.5k tokens: system + 5 chunks + question) | `answering.py:357` | <1 ms | |
| 6 | **LLM prefill → first token (TTFT)** | `answering.py:395` (`_stream_tokens`) | **~1.8-3.5 s median** (measured: median 3.09s June quiet / 3.45s July loaded; floor **0.28 s** on prefix-cache hits) | The dominant first-paint cost. Only the ~450-token system prompt is a stable, cacheable prefix; the ~2k chunk tokens differ per question and always re-prefill on the 14B. `eval/LATENCY.md` diagnosis stands: prefill-bound, not reasoning-bound (think=False). |
| 7 | **Decode (full answer)** | same stream | **~4-8 s** (full-answer mean 6.9s June / 8.6s July-loaded) | Streaming hides this: perceived wait = stages 3-6, tokens render live, `sources` event shows "reading" passages before token 1 (`answering.py:485`). |
| 8 | Mechanical span verification | `verifier.py:85` | ~1-10 ms | Pure-Python normalize + substring. Effectively free. Never a target. |
| 9 | **Refusal second pass (Move 1b)** | `answering.py:498-512` | **adds ~5-15 s** when triggered | Fully sequential after the complete first decode: re-embed + lazy FTS probe/index + 100-candidate hybrid + RRF (~0.3-1 s), then a **second full prefill (10 chunks, bigger prompt) + decode**. Worst-case questions land in the p90 ~12-19 s band (D-79 measurements). |
| 10 | Citation enrichment + persist | `routes_chat.py:158-163` | ~1-10 ms | SQLite lookups; fine. |

**Already done (don't re-spend effort here):** streaming default (B6/D-63), `keep_alive=30m`
+ `num_ctx=8192` on chat (P0.2), startup chat-model preload (cold cliff closed: 5.5s → 0.14s
`load_duration`), `OLLAMA_FLASH_ATTENTION=1` in the managed launcher, think=False, small-talk
gate, interactive priority pausing ingest (`activity.mark_chat`). Reranker is **off** on the
answer path (`rerank=False`), so it contributes zero today.

**Sequential steps that could overlap:**
- The second pass waits for the full first decode even though the refusal sentence is an
  exact, known prefix; wide retrieval (and even second-pass prefill) could start the moment
  the streamed prefix matches `REFUSAL`.
- Hybrid's dense and FTS arms run back-to-back (`retrieval.py:122-132`); independent queries.
- FTS index is built lazily on first hybrid use (`_ensure_fts_index`), charging index build
  to a user's unlucky first second-pass instead of ingest.
- Embedder warm-up could ride the existing startup preload thread instead of the first question.

**Speed-to-insight budget, typical warm question:** ~0.1s retrieval + ~2-3.5s TTFT +
~4-8s decode + ~0ms verify ≈ **6-12 s to verified citations**, with first visible feedback
(sources card) at ~0.1-0.3 s and first token at ~2-3.5 s. Refusal-path questions: ~2x.

---

## 2. Ranked interventions

Legend: win = expected latency effect; risk = answer-quality risk (gate = must re-run the
63/63 golden gate + NF 9/9 + 0 rejected claims); size = XS/S/M/L implementation.

| Rank | Intervention | Expected win | Quality risk | Size |
|------|--------------|--------------|--------------|------|
| 1 | **Warm + pin the embedder** — preload bge-m3 in the startup thread alongside `preload_model()`, and send `keep_alive: "30m"` in `embed_texts()` | Kills the 1-3 s post-idle cold cliff on stage 3; makes retrieval reliably <100 ms | None (no engine semantics change; identical vectors). Gate optional, cheap to run anyway | XS |
| 2 | **System-prompt KV warm on startup/matter-open** — replace/augment the empty-messages preload with a 1-token generation over the real `SYSTEM_PROMPT`, so Ollama's prefix cache holds its ~450-token KV before question 1. Ollama's 2026 cache upgrade reuses cache across conversations and snapshots at prompt positions, so a shared system prompt is exactly the case it serves | ~0.3-0.7 s off TTFT of the first question per session; sustains the measured 0.28 s TTFT floor more often | None (prompt bytes unchanged; cache-hit output is identical) | XS-S |
| 3 | **Overlap the refusal second pass** — in `answer_stream`, when the streamed prefix matches the exact `REFUSAL` sentence, kick off `_retrieve_wide()` on a thread while the first decode finishes; optionally stop consuming the first stream once the refusal + reminder sentence are complete | ~0.5-1.5 s off every second-pass answer (retrieval + FTS overlap); early-abort saves a further ~1-2 s of pointless decode | Low — same verifier, same adoption rule (span-verified non-refusal only). Touches `answering.py` → **gate required** | S |
| 4 | **Build the FTS index at ingest + parallelize hybrid arms** — move `_ensure_fts_index` into the KB ingest path; run dense + FTS searches concurrently in `retrieve(hybrid=True)` | ~0.2-0.5 s off second-pass retrieval; removes a one-time multi-second index build from a user's first refusal retry | None for index-at-ingest; parallel arms feed the same RRF → **gate required** (touches retrieval) | S |
| 5 | **Staged-status streaming UI** — sequence the existing events into visible stages: "Searching \<matter\>..." on send → per-source "Reading contract.pdf p.4" chips from the `sources` event → live tokens → citation chips flip to "verified" on `done`. Add a skeleton for source cards | Zero engine ms, but streaming + staged status is repeatedly measured to make identical waits feel 30-60% faster, and it *shows* the verification story (trust = the product) | None (UI only) | S |
| 6 | **KV cache quantization `q8_0`** (`OLLAMA_KV_CACHE_TYPE=q8_0` in the managed launcher; requires flash attention, already on) | Halves KV memory → headroom to keep qwen3:14b + bge-m3 + (future) reranker co-resident on 24GB without unload thrash; indirect but real on this hardware tier | Near-zero measured quality delta (perplexity +0.002-0.05), but it changes generation numerics → **gate required** | XS |
| 7 | **Prefill diet: trim grounded context** — options in increasing aggressiveness: tighter chunk `max_chars` at ingest; top_k 5→4; per-chunk head/tail trim. TTFT is ~linear in prompt tokens; caching static prompt parts + shorter prompts is the standard 40-60% TTFT lever | ~15-25% context-token cut ≈ ~0.4-0.8 s TTFT | **High** — directly moves retrieval recall and span availability. Full gate + a re-ingest; only attempt with the extended benchmark (§4) in place | M |
| 8 | **Query-embedding LRU cache** (normalized question → vector) | ~50-80 ms on repeats/rephrases; near-free | None | XS |
| 9 | **Precomputed per-document summaries at ingest** — generate once, store in catalog; UI shows an instant matter overview while the first live answer streams; summary-type questions can be answered from a doc-level layer | Large *perceived* win on matter open; converts dead wait into insight | Medium — summaries are generated content; must be labeled as unverified overview or pass the same citation discipline. Never present as a cited answer | M-L |
| 10 | **Speculative decoding** — parked. Ollama's speculative support today is MTP-based (models with MTP heads, e.g. Gemma 4: ~90% faster decode, auto-tuned); **qwen3:14b has no MTP head**, and classic draft-model speculation isn't exposed in Ollama (open issues #5800/#9216). Multiple 2026 Metal benchmarks show classic draft speculation is a net **loss** on Apple Silicon (draft overhead > gain), though one M-series GGUF suite reports 3.2x with a well-matched tiny draft — hardware/model dependent | 0 now; potentially 1.5-3x decode later | Output-identical by construction *if* available; swapping runtimes (llama.cpp server / LM Studio) to get it is a large infra + gate change | L (park) |
| 11 | **Smaller/faster chat model** — **already measured and rejected** (D-79): qwen3.5:9b scored 46/63 with 25 rejected claims (abbreviates "verbatim" spans) and was speed-neutral-to-worse (p90 19.2s vs 11.9s). Keep as a documented dead end; any future candidate must beat the same gate first | — | Proven high | done/rejected |
| 12 | **TurboRAG-style precomputed chunk KV caches** — precompute per-chunk KV at ingest, stitch at query time (research: eliminates online prefill, up to ~9x TTFT) | Would attack the *actual* bottleneck (chunk prefill) | Not implementable on stock Ollama today; requires custom llama.cpp integration and re-validating attention over stitched caches. Watch the space | L (watch) |

---

## 3. Top 3 SAFE quick wins for this cycle

1. **Warm + pin the embedder (rank 1).** Add bge-m3 to the startup preload thread and pass
   `keep_alive: "30m"` in `embed_store.embed_texts()`. Symmetric with the P0.2 chat-model fix;
   removes the last cold cliff on the ask path. Two-line-ish change, no engine semantics.
2. **System-prompt KV warm (rank 2).** Preload with the real system prompt (+`num_predict: 1`)
   instead of empty messages, at startup and optionally on matter open. Rides Ollama's prefix
   cache; first-question TTFT drops toward the measured 0.28 s floor's behavior for its first
   ~450 tokens. No prompt bytes change at answer time.
3. **Staged-status streaming UI (rank 5).** Pure front-end: staged progress copy driven by the
   events the backend already emits (`sources`, `token`, `second_pass`, `done`), skeleton
   source cards, and a visible "verifying citations" beat before chips flip to verified.
   Biggest perceived-speed win per line of code, zero gate exposure.

Ranks 3-4 (second-pass overlap, FTS-at-ingest + parallel arms) are the best *engine* wins for
the following cycle: real seconds saved on the worst-latency answers, small diffs, but each
requires a full golden-gate run before merge.

---

## 4. How to benchmark (extend the existing recipe)

`pipeline/run_latency.py` (G-LAT) already measures TTFT + total at production parity over the
63 present-fact golden questions. Extend, don't replace:

1. **Measure the metric that matters: time-to-verified-citations (TTVC).** Today's harness
   stops at model total. Add an end-to-end mode that drives `POST /chat/stream` and stamps:
   `t_sources` (first `sources` event), `t_first_token`, `t_done` (verified citations
   rendered-ready). TTVC = speed to insight; report mean/median/p95 alongside TTFT.
2. **Stage decomposition.** Log per-question `embed_s`, `search_s`, `ttft_s` (≈ prefill),
   `decode_s`, `verify_s`, `second_pass` (bool) + second-pass sub-timings. Refusal-path
   questions must be reported as their own cohort, not averaged away.
3. **Cold/warm scenarios.** Scripted: (a) force-unload bge-m3 (`keep_alive: 0`) then ask —
   the embedder-cliff regression test for quick win 1; (b) fresh app start then first
   question — the preload test; (c) back-to-back same-matter questions — the prefix-cache
   test (expect the 0.28 s-floor cohort to grow after quick win 2).
4. **Record machine conditions.** The 2026-07-07 run was ~20% slower purely from load
   average ~7 (`eval/LATENCY.md` caveat). Stamp `os.getloadavg()` + timestamp into each
   JSONL row so runs are comparable; prefer quiet-machine runs for gate decisions.
5. **Pair every engine-touching change with the golden gate.** Same discipline as D-63/D-79:
   `run_golden.py` 63/63 present + NF 9/9 + 0 rejected claims, run under the exact knobs
   being shipped, results in `eval/results/` (git-ignored) + a dated `eval/LATENCY.md` entry.
6. **Acceptance targets to propose:** TTFT median <3 s on a quiet machine (existing CE_PLAN
   target, currently 3.09-3.45 s); `t_sources` <500 ms; TTVC median <10 s; refusal-path
   TTVC p90 cut ≥20% after ranks 3-4.

---

## Sources

**Ollama caching / keep-alive / preload**
- Ollama API docs — `keep_alive` (default 5m, per-request incl. `/api/embed`), empty-messages preload/unload: https://github.com/ollama/ollama/blob/main/docs/api.md
- Ollama cache upgrade (cross-conversation reuse, prompt-position snapshots): https://x.com/ollama/status/2038835455777763762
- Prefix caching mechanics (longest-common-prefix KV reuse): https://bentoml.com/llm/inference-optimization/prefix-caching
- Ollama KV cache & scheduling internals: https://jonathanding.github.io/llm-learning/en/articles/ollama-kv-cache-scheduling/

**TTFT / streaming / perceived latency**
- TTFT levers, prompt-length linearity, system-prompt caching 40-60%: https://www.boundev.ai/blog/llm-inference-latency-time-to-first-token
- Streaming latency strategies: https://latitude.so/blog/real-time-llms-optimizing-latency-streaming
- Streaming perceived 40-60% faster; skeleton ~30% faster than spinner; staged status text: https://thefrontkit.com/blogs/what-is-streaming-ui-in-ai-applications and https://thefrontkit.com/blogs/ai-chat-ui-best-practices
- Streaming UX pattern reference: https://aiuxplayground.com/pattern/streaming/
- Think-time UX (designing the wait): https://www.uxtigers.com/post/think-time-ux
- TTFT perception analysis: https://tianpan.co/blog/2026-04-16-streaming-ttft-latency-perception

**Speculative decoding on local/Apple Silicon**
- llama.cpp speculative decoding docs: https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md
- Metal draft-speculation net-loss measurements: https://modelfit.io/blog/speculative-decoding-mac-llm/
- Contrasting M-series GGUF suite (3.2x with matched tiny draft): https://hiesch.eu/blog/llamacpp-benchmarks-speculative-decoding/
- Ollama feature requests (classic draft models): https://github.com/ollama/ollama/issues/5800 and https://github.com/ollama/ollama/issues/9216
- Qwen MoE + speculation: no net speedup found (19 configs): https://github.com/thc1006/qwen3.6-speculative-decoding-rtx3090
- LM Studio speculative decoding (alternative runtime): https://lmstudio.ai/blog/lmstudio-v0.3.10

**Quantization / KV cache on Apple Silicon**
- Q4_K_M vs Q8_0 quality/size tradeoffs: https://www.kunalganglani.com/blog/llm-quantization-levels-q4-q8-fp16 and https://bmdpat.com/blog/gguf-quantization-q4-q5-q8-explained-2026
- `OLLAMA_KV_CACHE_TYPE=q8_0` (requires flash attention; ~half KV memory, negligible perplexity): https://modelpiper.com/blog/ollama-kv-cache-quantization
- KV-quantization measurements on Apple Silicon: https://contracollective.com/blog/kv-cache-quantization-q8-vs-q4-m5-max-mlx-2026
- Inference internals on Apple Silicon (KV cache, flash attention): https://vijay.eu/co-authored/llm-inference-internals-apple-silicon/

**Reranker latency budgets** (relevant only if rerank ever enters the answer path)
- bge-reranker-v2-m3 CPU ~130 ms/16-pair batch; keep candidates 10-30: https://localaimaster.com/blog/reranking-cross-encoders-guide and https://agentset.ai/rerankers/baaibge-reranker-v2-m3
- Cross-encoder rerank implementation costs: https://markaicode.com/bge-reranker-cross-encoder-reranking-rag/

**RAG caching / prefetch / precomputation research**
- TurboRAG (precomputed chunk KV caches, prefill elimination): https://arxiv.org/pdf/2410.07590
- RAGCache (hierarchical KV caching for RAG): https://www.emergentmind.com/topics/ragcache
- Predictive prefetching for RAG: https://arxiv.org/html/2605.17989v1
- PCR prefetch-enhanced cache reuse: https://arxiv.org/pdf/2603.23049
- Approximate caching for faster RAG: https://arxiv.org/html/2503.05530v3
