from __future__ import annotations

import json as json_lib
from typing import Any

from backend.sdk import (
    BaseNode,
    ConfigField,
    ExecutionContext,
    NodeResult,
    Port,
    PortType,
)
from backend.services.critic import CriticAgentService


class CriticAgentNode(BaseNode):
    type = "critic-agent"
    name = "Validation / Critic Agent"
    category = "validation"
    icon = "\u2705"
    color = "#22c55e"
    description = "Verifier la fiabilite d'une reponse generee en la croisant avec les documents sources (inspire ORCA)"
    version = "1.0.0"

    inputs = [
        Port(
            name="generated_response",
            type=PortType.TEXT,
            label="Generated Response",
            description="Reponse generee par le LLM a verifier",
            required=True,
        ),
        Port(
            name="evidence",
            type=PortType.JSON,
            label="Evidence",
            description="Documents sources ou chunks utilises pour generer la reponse (array of {text, source, ...})",
            required=True,
        ),
        Port(
            name="question",
            type=PortType.TEXT,
            label="Question",
            description="Question originale pour le contexte de verification",
            required=False,
        ),
    ]

    outputs = [
        Port(
            name="verdict",
            type=PortType.JSON,
            label="Verdict",
            description="Verdict de verification : score de confiance, supporte, problemes detectes, corrections",
        ),
        Port(
            name="corrected_response",
            type=PortType.TEXT,
            label="Corrected Response",
            description="Reponse corrigee integrant toutes les corrections basees sur l'evidence",
        ),
        Port(
            name="score",
            type=PortType.JSON,
            label="Score Details",
            description="Scores detailles : precision factuelle, alignement source, completude, coherence",
        ),
    ]

    config_fields = [
        ConfigField(
            key="verification_mode",
            label="Verification Mode",
            type="select",
            required=False,
            default="hybrid",
            options=["hybrid", "llm_only", "embedding_only"],
            description="Mode de verification : hybrid (embedding filter + LLM), llm_only (LLM only), embedding_only (similarity only, no LLM)",
        ),
        ConfigField(
            key="similarity_threshold",
            label="Similarity Threshold",
            type="number",
            required=False,
            default=0.75,
            description="Seuil de similarite cosinus pour le mode hybrid/embedding_only (0.0 - 1.0). Plus eleve = plus strict.",
        ),
        ConfigField(
            key="strictness",
            label="Strictness",
            type="select",
            required=False,
            default="moderate",
            options=["lenient", "moderate", "strict"],
            description="Niveau de rigueur : indulgent (erreurs majeures seulement), modere, strict (moindre imprecision) — utilise uniquement en mode llm_only",
        ),
        ConfigField(
            key="language",
            label="Language",
            type="select",
            required=False,
            default="fr",
            options=["fr", "en", "ar"],
            description="Langue de la reponse a verifier",
        ),
        ConfigField(
            key="max_issues",
            label="Max Issues",
            type="number",
            required=False,
            default=5,
            description="Nombre maximum de problemes a signaler",
        ),
        ConfigField(
            key="verification_criteria",
            label="Verification Criteria",
            type="json",
            required=False,
            default="[]",
            description="Criteres de verification personnalises au format JSON [{key, label, description}]",
        ),
        ConfigField(
            key="generated_response",
            label="Generated Response",
            type="text",
            required=False,
            default="",
            description="The AI-generated response to verify. Leave empty if provided via upstream LLM/RAG node.",
        ),
        ConfigField(
            key="evidence",
            label="Evidence (JSON)",
            type="json",
            required=False,
            default="{}",
            description="Source documents or chunks as JSON. Leave empty if provided via upstream VectorStore.",
        ),
        ConfigField(
            key="question",
            label="Question",
            type="text",
            required=False,
            default="",
            description="Original user question (optional, for context).",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            verification_mode = config.get("verification_mode", "hybrid")
            similarity_threshold = float(config.get("similarity_threshold", 0.5))
            strictness = config.get("strictness", "moderate")
            language = config.get("language", "fr")
            max_issues = int(config.get("max_issues", 5))

            generated_response = ctx.get_input("generated_response", "") or str(config.get("generated_response", ""))
            if not generated_response or not generated_response.strip():
                result.fail("No generated response provided. Connect a node providing text upstream (LLM, RAG, etc.), or type text in the config field.")
                return result

            evidence = ctx.get_input("evidence")
            if not evidence:
                raw_evidence = config.get("evidence", "{}")
                if isinstance(raw_evidence, str) and raw_evidence.strip():
                    try:
                        evidence = json_lib.loads(raw_evidence)
                    except (json_lib.JSONDecodeError, TypeError):
                        evidence = {}
                elif isinstance(raw_evidence, (dict, list)):
                    evidence = raw_evidence
            if not evidence:
                result.fail("No evidence provided. Connect a node providing source documents upstream (VectorStore, chunks, etc.), or provide JSON in the config field.")
                return result

            question = ctx.get_input("question", "") or str(config.get("question", ""))

            custom_criteria_raw = config.get("verification_criteria", "[]")
            if isinstance(custom_criteria_raw, str) and custom_criteria_raw.strip() and custom_criteria_raw.strip() != "[]":
                verification_criteria = json_lib.loads(custom_criteria_raw)
            elif isinstance(custom_criteria_raw, list):
                verification_criteria = custom_criteria_raw
            else:
                verification_criteria = None

            service = CriticAgentService()
            review_result = await service.review(
                generated_response=generated_response,
                evidence=evidence,
                question=question,
                strictness=strictness,
                language=language,
                max_issues=max_issues,
                verification_criteria=verification_criteria,
                verification_mode=verification_mode,
                similarity_threshold=similarity_threshold,
            )

            result.succeed({
                "verdict": review_result["verdict"],
                "corrected_response": review_result["corrected_response"],
                "score": review_result["score"],
            })

        except Exception as e:
            result.fail(str(e))

        return result
