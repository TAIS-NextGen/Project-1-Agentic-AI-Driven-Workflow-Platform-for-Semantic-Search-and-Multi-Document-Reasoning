from __future__ import annotations

from typing import Any

from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeResult,
    Port,
    PortType,
)

BUILTIN_TEMPLATES: dict[str, str] = {
    "qa_with_sources": (
        "Answer the question based ONLY on these documents. "
        "Cite which document each fact comes from. "
        "If the documents do not contain the answer, say so.\n\n"
        "DOCUMENTS:\n{chunks}\n\n"
        "Question: {question}\n\n"
        "Answer:"
    ),
    "qa_concise": (
        "Provide a concise answer based on the context below.\n\n"
        "Context:\n{chunks}\n\n"
        "Question: {question}\n\n"
        "Answer:"
    ),
    "summary": (
        "Summarize the following documents.\n\n"
        "Documents:\n{chunks}\n\n"
        "Summary:"
    ),
    "analysis": (
        "Analyze the following documents and extract key findings.\n\n"
        "Documents:\n{chunks}\n\n"
        "Analysis focus: {question}\n\n"
        "Analysis:"
    ),
}


class PromptBuilderNode(BaseNode):
    type = "prompt-builder"
    name = "Prompt Builder"
    category = "rag"
    icon = "\U0001f4dd"
    color = "#10b981"
    description = "Construire le prompt final pour le LLM a partir des chunks, du contexte et de la question"
    version = "1.0.0"

    inputs = [
        Port(
            name="chunks",
            type=PortType.JSON,
            label="Chunks",
            description="Pre-ranked document chunks from VectorStore (array of {text, source, ...})",
        ),
        Port(
            name="context",
            type=PortType.JSON,
            label="Context",
            description="Additional metadata or context to inject into the prompt",
            required=False,
        ),
        Port(
            name="question",
            type=PortType.TEXT,
            label="Question",
            description="User query or analysis instruction",
        ),
    ]

    outputs = [
        Port(
            name="prompt",
            type=PortType.TEXT,
            label="Structured Prompt",
            description="Final assembled prompt ready for the LLM",
        ),
    ]

    config_fields = [
        ConfigField(
            key="prompt_template",
            label="Prompt Template",
            type="select",
            required=False,
            default="qa_with_sources",
            options=["qa_with_sources", "qa_concise", "summary", "analysis", "custom"],
            description="Built-in template or custom",
        ),
        ConfigField(
            key="custom_template",
            label="Custom Template",
            type="text",
            required=False,
            default="",
            description="Custom template with {chunks}, {context}, {question} placeholders. Used when template is 'custom'.",
        ),
        ConfigField(
            key="system_prompt",
            label="System Prompt",
            type="text",
            required=False,
            default="",
            description="Optional system instruction prepended to the final prompt",
        ),
        ConfigField(
            key="language",
            label="Language",
            type="select",
            required=False,
            default="fr",
            options=["fr", "en", "ar"],
            description="Template language hint",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            template_name = config.get("prompt_template", "qa_with_sources")
            system_prompt = config.get("system_prompt", "")

            chunks = ctx.get_input("chunks", [])
            context = ctx.get_input("context", {})
            question = ctx.get_input("question", "")

            if not question:
                result.fail("'question' input is required")
                return result

            formatted_chunks = self._format_chunks(chunks)

            if template_name == "custom":
                template = config.get("custom_template", "")
                if not template:
                    result.fail("'custom_template' must be provided when using 'custom' template")
                    return result
            else:
                template = BUILTIN_TEMPLATES.get(template_name, BUILTIN_TEMPLATES["qa_with_sources"])

            prompt = template.replace("{chunks}", formatted_chunks)
            prompt = prompt.replace("{context}", str(context))
            prompt = prompt.replace("{question}", question)

            if system_prompt:
                prompt = f"[SYSTEM]\n{system_prompt}\n\n[USER]\n{prompt}"

            result.succeed({"prompt": prompt})

        except Exception as e:
            result.fail(str(e))

        return result

    @staticmethod
    def _format_chunks(chunks: list[Any]) -> str:
        if not chunks:
            return "[No relevant documents found]"

        parts: list[str] = []
        for i, chunk in enumerate(chunks, start=1):
            if isinstance(chunk, dict):
                text = chunk.get("text", str(chunk))
                source = chunk.get("source", "")
                src = f" (source: {source})" if source else ""
                parts.append(f"[{i}] {text}{src}")
            else:
                parts.append(f"[{i}] {str(chunk)}")

        return "\n\n".join(parts)
