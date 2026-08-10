import logging
from backend.services.llm import LLMService

logger = logging.getLogger(__name__)

class SummarizerService:
    def __init__(self, model: str = ""):
        self.llm = LLMService(model=model)

    async def summarize(self, text: str, style: str = "short") -> str:
        """
        Generate a summary for the given text using the specified style.
        """
        if not text.strip():
            return ""

        style = style.lower().strip()
        
        system_prompt = (
            "You are an expert document summarizer. "
            "Analyze the provided text and create an accurate, clear summary based on the requested style. "
            "Do not add information that is not present in the text."
        )

        if style == "short":
            prompt = f"Please provide a concise, one-paragraph summary of the following text:\n\n{text}"
        elif style == "long":
            prompt = f"Please provide a detailed, multi-paragraph summary of the following text, capturing all key points and nuance:\n\n{text}"
        elif style == "bullet_points":
            prompt = f"Please provide a summary of the following text as a list of clear bullet points:\n\n{text}"
        elif style == "executive":
            prompt = f"Please provide a high-level executive summary of the following text, focusing on main conclusions, recommendations, and critical insights:\n\n{text}"
        else:
            # Fallback
            prompt = f"Please summarize the following text:\n\n{text}"

        try:
            summary = await self.llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=2048,
            )
            return summary.strip()
        except Exception as e:
            logger.error(f"SummarizerService failed to generate summary: {e}")
            raise
