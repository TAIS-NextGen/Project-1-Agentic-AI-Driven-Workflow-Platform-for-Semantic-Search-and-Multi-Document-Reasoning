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
from backend.services.gap_checker import GapCheckerService


class GapCheckerNode(BaseNode):
    type = "gap-checker"
    name = "Gap Checker"
    category = "checking"
    icon = "\U0001f50e"
    color = "#ef4444"
    description = "Verifier les champs manquants dans un document par rapport a une checklist de reference"
    version = "1.0.0"

    inputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Text",
            description="Texte extrait du document via OCR (provenant d'un noeud OCR en amont)",
            required=True,
        ),
    ]

    outputs = [
        Port(
            name="report",
            type=PortType.JSON,
            label="Gap Report",
            description="Analyse detaillee champ par champ avec statut de chaque champ",
        ),
        Port(
            name="score",
            type=PortType.JSON,
            label="Completeness Score",
            description="Score de completude (pourcentage, champs critiques manquants, seuil depasse)",
        ),
        Port(
            name="missing",
            type=PortType.JSON,
            label="Missing Fields",
            description="Liste des champs critiques manquants uniquement",
        ),
    ]

    config_fields = [
        ConfigField(
            key="template",
            label="Checklist Template",
            type="text",
            required=False,
            default="generic",
            description="Template name: generic, invoice_fr, claim_dossier",
        ),
        ConfigField(
            key="language",
            label="Language",
            type="select",
            required=False,
            default="fr",
            options=["fr", "en", "ar"],
            description="Document language for LLM evaluation and regex patterns",
        ),
        ConfigField(
            key="strictness_threshold",
            label="Strictness Threshold",
            type="number",
            required=False,
            default=0.85,
            description="Minimum completeness percentage to pass (0.0 - 1.0)",
        ),
        ConfigField(
            key="evaluation_mode",
            label="Evaluation Mode",
            type="select",
            required=False,
            default="both",
            options=["deterministic_only", "semantic", "both"],
            description="'deterministic_only': regex only, no LLM. 'semantic': LLM only. 'both': regex + LLM for unfound fields.",
        ),
        ConfigField(
            key="custom_checklist",
            label="Custom Checklist",
            type="json",
            required=False,
            default="[]",
            description="Inline JSON checklist array (used instead of template if non-empty)",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            template = config.get("template", "generic")
            language = config.get("language", "fr")
            threshold = float(config.get("strictness_threshold", 0.85))
            mode = config.get("evaluation_mode", "both")

            text = ctx.get_input("text", "")
            if not text or not text.strip():
                result.fail("No text provided. Connect an OCR node (OCR Node or Handwriting OCR) upstream.")
                return result

            service = GapCheckerService()

            custom_raw = config.get("custom_checklist", "[]")
            if isinstance(custom_raw, str) and custom_raw.strip() and custom_raw.strip() != "[]":
                checklist = service._parse_custom_checklist(custom_raw)
            else:
                checklist = service.load_checklist(template)

            gap_result = await service.check(
                text=text,
                checklist=checklist,
                mode=mode,
                threshold=threshold,
                language=language,
            )

            result.succeed({
                "report": {
                    "fields": gap_result["fields"],
                    "has_critical_gaps": gap_result["has_critical_gaps"],
                },
                "score": gap_result["score"],
                "missing": gap_result["missing"],
            })

        except Exception as e:
            result.fail(str(e))

        return result
