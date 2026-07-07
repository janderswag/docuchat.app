"""Mechanical golden-run scorer — one set of criteria applied identically to any
run file, so two runs can be compared grade-to-grade (the [GATE] discipline's
"grade-identical" check without a human in the loop for the mechanical part).

Per present-fact question (manifest has the gold filename + page):
  PASS = displayed citations include (gold filename, gold page) — or the SAME
  document cited at another page with a span whose tokens substantially overlap
  the manifest's verbatim_span (the same fact genuinely recurs, e.g. a judge's
  name in both the caption and the signature block; the span was already
  mechanically verified to exist where cited) — AND no rejected claims AND the
  answer is not the refusal. A cite to a different document never passes.
Per NF question (expected_absent_topics non-empty):
  PASS = the answer refuses (REFUSAL constant) with no displayed citations.

This scores the same properties the manual TEST_PLAN grading checks mechanically
(citation-at-page + zero fabrications + refusal discipline); free-text answer
quality still deserves eyes, but a grade-identical mechanical score on identical
questions is the regression signal the gate needs.

Usage: .venv/bin/python score_golden.py <run.jsonl> [<run2.jsonl> ...]
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from answering import REFUSAL  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


def _tokens(s):
    return {t for t in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(t) > 1}


def _same_fact(cite_span, gold_span):
    """Cited-span tokens substantially overlap the gold span (>= 0.6)."""
    c, g = _tokens(cite_span), _tokens(gold_span)
    return bool(c) and len(c & g) / len(c) >= 0.6


def load_manifest():
    manifest = {}
    with open(REPO / "eval" / "golden_manifest.jsonl", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                manifest[r["fact_id"]] = r
    return manifest


def score(run_path, manifest=None):
    manifest = manifest or load_manifest()
    rows = [json.loads(l) for l in open(run_path, encoding="utf-8") if l.strip()]
    present = {"pass": [], "fail": []}
    nf = {"pass": [], "fail": []}
    rejected_total = 0
    for r in rows:
        m = manifest[r["fact_id"]]
        rejected_total += len(r.get("rejected_claims") or [])
        if m["expected_absent_topics"]:
            ok = r["answer_text"].strip().startswith(REFUSAL) and not r["citations"]
            (nf["pass"] if ok else nf["fail"]).append(r["fact_id"])
        else:
            cited = any(
                c["filename"] == m["filename"]
                and (c["page"] == m["page_number"]
                     or _same_fact(c.get("span"), m["verbatim_span"]))
                for c in r["citations"])
            ok = (cited and not r.get("rejected_claims")
                  and not r["answer_text"].strip().startswith(REFUSAL))
            (present["pass"] if ok else present["fail"]).append(r["fact_id"])
    return {
        "run": str(run_path),
        "present": f"{len(present['pass'])}/{len(present['pass']) + len(present['fail'])}",
        "nf_refusal": f"{len(nf['pass'])}/{len(nf['pass']) + len(nf['fail'])}",
        "rejected_claims_total": rejected_total,
        "present_fail_ids": present["fail"],
        "nf_fail_ids": nf["fail"],
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("usage: score_golden.py <run.jsonl> [...]")
    manifest = load_manifest()
    for p in sys.argv[1:]:
        print(json.dumps(score(p, manifest), indent=2))
