"""Chat router — matter-scoped cited answering over .lancedb_kb, with persisted threads.

POST /chat answers ONLY from the chosen matter's KB chunks (D-18 hard pre-filter inside
answer()/retrieve()); citations are chunk-derived (D-38) + span-verified (D-19). An
empty matter (no indexed chunks) returns the exact D-30 refusal — never a tool/web call
(D-2). Threads + messages persist for Chat History.
"""

import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import catalog
import routes_kb  # for the shared KB_DB path (monkeypatchable in tests)
from answering import answer, REFUSAL

router = APIRouter()


class ChatRequest(BaseModel):
    question: str
    matter: str
    thread_id: int | None = None


def _refusal_result():
    return {"answer_text": REFUSAL, "citations": [], "rejected_claims": [], "grounding_chunks": []}


@router.post("/chat")
def chat(body: ChatRequest):
    if not catalog.get_matter(body.matter):
        raise HTTPException(status_code=400, detail=f"unknown matter: {body.matter!r}")
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="empty question")

    thread_id = body.thread_id
    if not thread_id:
        thread_id = catalog.create_thread(body.matter, body.question.strip())["id"]
    catalog.add_message(thread_id, "user", body.question)

    try:
        res = answer(body.question, matter=body.matter, db_path=str(routes_kb.KB_DB))
    except ValueError:
        # matter has no indexed chunks yet (empty KB) -> D-30 refusal, no tool/web call
        res = _refusal_result()

    catalog.add_message(thread_id, "assistant", res["answer_text"],
                        json.dumps(res["citations"]))
    catalog.touch_thread(thread_id)
    return {"thread_id": thread_id, **res}


@router.get("/chat/threads")
def list_threads():
    return {"threads": catalog.list_threads()}


@router.get("/chat/threads/{thread_id}")
def thread_messages(thread_id: int):
    return {"messages": catalog.get_thread_messages(thread_id)}
