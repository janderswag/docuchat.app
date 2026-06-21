"""M2-8a targeted re-run — re-pose ONLY the facts the verifier-normalization fix
affects (F-014, F-016 escaped-quote false-rejects; F-042 alternate-page) through the
M2 pipeline with the fixed verifier, and append the raw results. This is the RUN
mechanism (a loop), NOT a pass/fail scorer; grading stays manual (TEST_PLAN §5). The
remaining facts stand from the M2-8 run (run-2026-06-20-m2.jsonl) — not re-run."""
import sys, json, time, os
sys.path.insert(0, '.')
from answering import answer

REPO = ".."
TARGETS = ["F-014", "F-016", "F-042"]

manifest = {}
with open(f"{REPO}/eval/golden_manifest.jsonl") as f:
    for line in f:
        if line.strip():
            r = json.loads(line); manifest[r["fact_id"]] = r
questions = {json.loads(l)["fact_id"]: json.loads(l)
             for l in open(f"{REPO}/eval/golden_questions.jsonl") if l.strip()}

out_path = f"{REPO}/eval/results/run-2026-06-20-m2-rerun.jsonl"
print("PID", os.getpid(), "appending", out_path, flush=True)
with open(out_path, "a") as out:
    for fid in TARGETS:
        rec = manifest[fid]
        matter = rec["matter_or_client"]  # all three are present facts -> scoped
        t0 = time.time()
        res = answer(questions[fid]["question"], matter=matter)
        dt = round(time.time() - t0, 2)
        out.write(json.dumps({
            "fact_id": fid, "question": questions[fid]["question"], "matter": matter,
            "answer_text": res["answer_text"], "citations": res["citations"],
            "grounding_chunks": res["grounding_chunks"],
            "rejected_claims": res["rejected_claims"], "latency_s": dt,
        }) + "\n")
        out.flush()
        print(fid, dt, "s", "verified=" + str(len(res["citations"])),
              "rejected=" + str(len(res["rejected_claims"])), flush=True)
print("DONE", flush=True)
