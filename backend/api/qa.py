from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.services.llm import LLMService
from backend.services.qa_index import QAIndexService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/qa", tags=["qa"])


class IndexRequest(BaseModel):
    file_ids: list[str]


class AskRequest(BaseModel):
    question: str
    top_k: int = 5
    with_validation: bool = False


class AskResponse(BaseModel):
    question: str
    answer: str
    retrieved_chunks: list
    index_stats: dict


@router.post("/index")
async def index_documents(req: IndexRequest):
    svc = QAIndexService()
    result = await svc.index_documents(req.file_ids)
    result["index_stats"] = svc.get_stats()
    return result


@router.post("/ask")
async def ask(req: AskRequest):
    svc = QAIndexService()

    chunks = await svc.query(req.question, req.top_k)
    if not chunks:
        return {
            "question": req.question,
            "answer": "No documents indexed. Index documents first via POST /api/qa/index.",
            "retrieved_chunks": [],
            "index_stats": svc.get_stats(),
        }

    excerpts = "\n\n".join(f"[{i+1}] {c['chunk_text']}" for i, c in enumerate(chunks))
    prompt = (
        f"Answer the question based ONLY on the following document excerpts.\n\n"
        f"Question: {req.question}\n\n"
        f"Document excerpts:\n{excerpts}\n\n"
        f"Answer (be specific and quote the exact value; answer in one short phrase):"
    )

    llm = LLMService()
    answer_text = await llm.generate(
        prompt=prompt,
        system_prompt="You are a document QA assistant. Answer only from the provided excerpts.",
        temperature=0.0,
        max_tokens=512,
        disable_thinking=True,
    )

    response = {
        "question": req.question,
        "answer": answer_text.strip(),
        "retrieved_chunks": [
            {"chunk_text": c["chunk_text"], "filename": c["filename"], "score": c["score"]}
            for c in chunks
        ],
        "index_stats": svc.get_stats(),
    }

    if req.with_validation:
        try:
            from backend.services.critic import CriticAgentService

            critic = CriticAgentService()
            review = await critic.review(
                generated_response=answer_text,
                evidence=chunks,
                question=req.question,
                verification_mode="llm_only",
                language="en",
            )
            response["verdict"] = review.get("verdict", {})
        except Exception as e:
            logger.error(f"Critic validation failed: {e}")
            response["verdict"] = {"error": str(e)}

    return response


@router.get("/stats")
async def stats():
    svc = QAIndexService()
    return svc.get_stats()
