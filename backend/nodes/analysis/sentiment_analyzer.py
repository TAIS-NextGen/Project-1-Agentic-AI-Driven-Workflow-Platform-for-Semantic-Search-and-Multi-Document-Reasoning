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
from backend.services.sentiment import SentimentAnalyzerService


class SentimentAnalyzerNode(BaseNode):
    type = "sentiment-analyzer"
    name = "Sentiment / Tone Analyzer"
    category = "analysis"
    icon = "\U0001f3ad"
    color = "#f59e0b"
    description = "Analyser le ton et le sentiment du texte : polarite, tonalites, intensite et score de confiance"
    version = "1.0.0"

    inputs = [
        Port(
            name="text",
            type=PortType.TEXT,
            label="Text",
            description="Texte a analyser (provenant d'un noeud OCR, LLM, ou autre source en amont)",
            required=True,
        ),
    ]

    outputs = [
        Port(
            name="sentiment",
            type=PortType.JSON,
            label="Sentiment Score",
            description="Score de sentiment : polarite (positive/negative/neutral), score (-1 a 1), confiance",
        ),
        Port(
            name="tone",
            type=PortType.JSON,
            label="Tone Analysis",
            description="Analyse de la tonalite : tonalite principale, tonalites secondaires, intensite, confiance",
        ),
        Port(
            name="summary",
            type=PortType.TEXT,
            label="Summary",
            description="Resume en langage naturel du sentiment et de la tonalite",
        ),
    ]

    config_fields = [
        ConfigField(
            key="language",
            label="Language",
            type="select",
            required=False,
            default="fr",
            options=["fr", "en", "ar"],
            description="Langue du texte pour ameliorer la precision de l'analyse",
        ),
        ConfigField(
            key="analysis_type",
            label="Analysis Type",
            type="select",
            required=False,
            default="both",
            options=["sentiment_only", "tone_only", "both"],
            description="Type d'analyse : sentiment seulement, tonalite seulement, ou les deux",
        ),
        ConfigField(
            key="detail_level",
            label="Detail Level",
            type="select",
            required=False,
            default="detailed",
            options=["basic", "detailed"],
            description="Niveau de detail : basic (tonalites secondaires limitees) ou detailed (analyse complete)",
        ),
        ConfigField(
            key="text",
            label="Text",
            type="text",
            required=False,
            default="",
            description="Text to analyze. Leave empty if provided via upstream connection (OCR, LLM, etc.).",
        ),
    ]

    async def execute(self, ctx: ExecutionContext) -> NodeResult:
        result = NodeResult(node_id=self.node_id)
        result.start()

        try:
            config = self.get_resolved_config()
            language = config.get("language", "fr")
            analysis_type = config.get("analysis_type", "both")
            detail_level = config.get("detail_level", "detailed")

            text = ctx.get_input("text", "") or str(config.get("text", ""))
            if not text or not text.strip():
                result.fail("No text provided. Connect a node providing text upstream (OCR, LLM, etc.), or type text in the config field.")
                return result

            service = SentimentAnalyzerService()
            analysis_result = await service.analyze(
                text=text,
                language=language,
                analysis_type=analysis_type,
                detail_level=detail_level,
            )

            result.succeed({
                "sentiment": analysis_result["sentiment"],
                "tone": analysis_result["tone"],
                "summary": analysis_result["summary"],
            })

        except Exception as e:
            result.fail(str(e))

        return result
