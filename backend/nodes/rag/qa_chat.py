from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeResult,
    Port,
    PortType,
)
from backend.settings import settings


class QAChatNode(BaseNode):
    type = "qa-chat"
    name = "QA Chat"
    category = "rag"
    icon = "\U0001f4ac"
    color = "#a855f7"
    description = "Ask a question over the indexed document library and get an answer with retrieved evidence"
    version = "1.0.0"

    inputs = [
        Port(
            name="question",
            type=PortType.TEXT,
            label="Question",
            description="Question text from an upstream node (optional; falls back to config)",
            required=False,
        ),
        Port(
            name="context",
            type=PortType.JSON,
            label="Context",
            description="Optional upstream output (e.g. Vector Store results) — used to ensure ordering",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="answer",
            type=PortType.TEXT,
            label="Answer",
            description="Generated answer from retrieved document chunks",
        ),
        Port(
            name="retrieved_chunks",
            type=PortType.JSON,
            label="Retrieved Chunks",
            description="Top-k chunks with similarity scores and source filenames",
        ),
    ]

    config_fields = [
        ConfigField(
            key="question",
            label="Question",
            type="text",
            required=False,
            default="",
            description="The question to answer over the indexed documents.",
        ),
        ConfigField(
            key="file_ids",
            label="File IDs (comma-separated)",
            type="text",
            required=False,
            default="",
            description="Optional: index these documents first (if the library is not yet indexed).",
        ),
        ConfigField(
            key="top_k",
            label="Top K",
            type="number",
            required=False,
            default=5,
            description="Number of most relevant chunks to retrieve",
        ),
        ConfigField(
            key="with_validation",
            label="With Validation",
            type="boolean",
            required=False,
            default=False,
            description="Run the Critic Agent to validate the answer against evidence (slower)",
        ),
    ]

    @staticmethod
    def _list_library_file_ids() -> list[str]:
        upload_dir = Path(settings.upload_dir)
        index_path = upload_dir / ".documents-index.json"
        if not index_path.exists():
            return []
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return [fid for fid, rec in data.items() if isinstance(rec, dict)]
        except (OSError, json.JSONDecodeError):
            pass
        return []

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            question = ctx.get_input("question", "") or str(config.get("question", ""))
            top_k = int(config.get("top_k", 5))
            with_validation = bool(config.get("with_validation", False))

            if not question.strip():
                result.fail("No question provided via input port or 'question' config field")
                return result

            from backend.services.llm import LLMService
            from backend.services.qa_index import QAIndexService

            svc = QAIndexService()

            # Auto-index if the library is empty: use explicit file_ids if
            # provided, otherwise index the whole document library.
            if svc.get_stats()["chunks"] == 0:
                raw_file_ids = str(config.get("file_ids", "")).strip()
                if raw_file_ids:
                    file_ids = [fid.strip() for fid in raw_file_ids.split(",") if fid.strip()]
                else:
                    file_ids = self._list_library_file_ids()
                if file_ids:
                    await svc.index_documents(file_ids)

            chunks = await svc.query(question, top_k)

            if not chunks:
                result.fail(
                    "No documents indexed. Index documents first via POST /api/qa/index "
                    "(or the qa_chat.py client)."
                )
                return result

            excerpts = "\n\n".join(
                f"[{i + 1}] {c['chunk_text']}" for i, c in enumerate(chunks)
            )
            prompt = (
                f"Answer the question based ONLY on the following document excerpts.\n\n"
                f"Question: {question}\n\n"
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

            outputs: dict[str, Any] = {
                "answer": answer_text.strip(),
                "retrieved_chunks": [
                    {"chunk_text": c["chunk_text"], "filename": c["filename"], "score": c["score"]}
                    for c in chunks
                ],
            }

            if with_validation:
                try:
                    from backend.services.critic import CriticAgentService

                    critic = CriticAgentService()
                    review = await critic.review(
                        generated_response=answer_text,
                        evidence=chunks,
                        question=question,
                        verification_mode="llm_only",
                        language="en",
                    )
                    outputs["verdict"] = review.get("verdict", {})
                except Exception as e:
                    outputs["verdict"] = {"error": str(e)}

            result.succeed(outputs)

        except Exception as e:
            result.fail(f"QA Chat failed: {e}")

        return result
