from __future__ import annotations

import json as json_lib
import logging
import re
from typing import Any

import numpy as np

from backend.services.embedding import EmbeddingService
from backend.services.llm import LLMService

logger = logging.getLogger(__name__)

DEFAULT_SIMILARITY_THRESHOLD = 0.75

CRITIC_SYSTEM_PROMPT = """You are an expert fact-checking and verification agent (ORCA-inspired). Your job is to critically review AI-generated responses against provided source evidence.

ORCA OPEN-SOURCE RESEARCH COAGENT PRINCIPLES:
1. CROSS-REFERENCE: Verify EVERY factual claim in the response against the source documents.
2. FLAG ISSUES: Identify unsupported statements, hallucinations, contradictions, omissions, or misrepresentations.
3. CORRECT WHERE POSSIBLE: If a claim can be corrected using the source evidence, provide the correction.
4. BE HONEST: If you cannot verify something, mark it as unverifiable rather than assuming it's wrong.
5. SCORE DIMENSIONS: Evaluate along factual accuracy, source alignment, completeness, and consistency.

CRITICAL RULES:
1. Return ONLY valid JSON — no explanation, no markdown, no code blocks.
2. Each issue must include: severity (high, medium, low), the claim being checked, a description of the problem, and a suggestion.
3. Each correction must include: the original text, the corrected text, and the reason for correction.
4. Confidence score should reflect how well the response is supported by evidence (0.0 = no support, 1.0 = fully supported).
5. is_supported should be true ONLY if the overall confidence is >= 0.7 and no high-severity issues exist.
6. Return the JSON object directly, no wrapping.

SEVERITY GUIDELINES:
- high: Hallucination (invented fact not in evidence), critical contradiction, or major omission
- medium: Minor inaccuracy, partial contradiction, unclear attribution
- low: Stylistic issue, minor imprecision, excessive verbosity not affecting factual content"""

FLAGGED_CLAIM_SYSTEM_PROMPT = """You are an expert fact-checker. Your task is SIMPLE and FOCUSED:

Verify ONLY the specific claim below against the provided evidence. Determine if this claim is supported by the evidence or not.

RULES:
1. Return ONLY valid JSON — no explanation, no markdown, no code blocks.
2. Be decisive: is the claim supported, contradicted, or unverifiable?
3. If contradicted, provide the correct information from the evidence.
4. Keep it brief — one issue at most per claim.
5. Return the JSON object directly, no wrapping."""


class CriticAgentService:
    def __init__(self, model: str = ""):
        self._llm: LLMService | None = None
        self._model = model
        self._embedding: EmbeddingService | None = None

    def _get_llm(self) -> LLMService:
        if self._llm is None:
            self._llm = LLMService(model=self._model) if self._model else LLMService()
        return self._llm

    def _get_embedding(self) -> EmbeddingService:
        if self._embedding is None:
            self._embedding = EmbeddingService()
        return self._embedding

    @staticmethod
    def _extract_json(text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            blocks = text.split("```")
            for i in range(1, len(blocks), 2):
                candidate = blocks[i].strip()
                if candidate.startswith("json"):
                    candidate = candidate[4:].strip()
                return candidate
        brace_start = text.find("{")
        if brace_start >= 0:
            return text[brace_start:]
        return text

    @staticmethod
    def _split_claims(text: str) -> list[str]:
        raw = re.split(r"(?<=[.!?])\s+|\n+", text)
        claims = []
        for c in raw:
            c = c.strip()
            if c and len(c) > 5:
                claims.append(c)
        return claims if claims else [text]

    def _format_evidence_texts(self, evidence: Any) -> list[str]:
        if isinstance(evidence, list):
            texts = []
            for chunk in evidence:
                if isinstance(chunk, dict):
                    texts.append(chunk.get("text", str(chunk)))
                else:
                    texts.append(str(chunk))
            return texts
        if isinstance(evidence, str):
            return [evidence]
        return [json_lib.dumps(evidence, indent=2, ensure_ascii=False)]

    @staticmethod
    def _format_evidence(evidence: Any) -> str:
        if isinstance(evidence, list):
            parts: list[str] = []
            for i, chunk in enumerate(evidence, start=1):
                if isinstance(chunk, dict):
                    text = chunk.get("text", str(chunk))
                    source = chunk.get("source", "")
                    src = f" [source: {source}]" if source else ""
                    parts.append(f"[DOC {i}]{src}\n{text}")
                else:
                    parts.append(f"[DOC {i}]\n{str(chunk)}")
            return "\n\n---\n\n".join(parts)
        if isinstance(evidence, str):
            return evidence
        return json_lib.dumps(evidence, indent=2, ensure_ascii=False)

    @staticmethod
    def _compute_similarity(vec1: list[float], vec2: list[float]) -> float:
        return float(np.dot(vec1, vec2))

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        svc = self._get_embedding()
        result = await svc.embed(texts)
        return [e["vector"] for e in result["embeddings"]]

    async def review(
        self,
        generated_response: str,
        evidence: Any,
        question: str = "",
        strictness: str = "moderate",
        language: str = "fr",
        max_issues: int = 5,
        verification_criteria: list[dict[str, Any]] | None = None,
        verification_mode: str = "hybrid",
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> dict[str, Any]:
        if not generated_response or not generated_response.strip():
            raise ValueError("No generated response provided for verification")
        if not evidence:
            raise ValueError("No evidence provided for verification")

        if verification_mode == "llm_only":
            return await self._review_llm_only(
                generated_response=generated_response,
                evidence=evidence,
                question=question,
                strictness=strictness,
                language=language,
                max_issues=max_issues,
                verification_criteria=verification_criteria,
            )

        if verification_mode == "embedding_only":
            return await self._review_embedding_only(
                generated_response=generated_response,
                evidence=evidence,
                similarity_threshold=similarity_threshold,
            )

        return await self._review_hybrid(
            generated_response=generated_response,
            evidence=evidence,
            question=question,
            strictness=strictness,
            language=language,
            max_issues=max_issues,
            verification_criteria=verification_criteria,
            similarity_threshold=similarity_threshold,
        )

    async def _review_hybrid(
        self,
        generated_response: str,
        evidence: Any,
        question: str = "",
        strictness: str = "moderate",
        language: str = "fr",
        max_issues: int = 5,
        verification_criteria: list[dict[str, Any]] | None = None,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> dict[str, Any]:
        claims = self._split_claims(generated_response)
        evidence_texts = self._format_evidence_texts(evidence)

        all_texts = claims + evidence_texts
        all_vectors = await self._embed_batch(all_texts)

        claim_vectors = all_vectors[: len(claims)]
        evidence_vectors = all_vectors[len(claims) :]

        passed_claims: list[dict[str, Any]] = []
        flagged_claims: list[dict[str, Any]] = []

        for i, claim_vec in enumerate(claim_vectors):
            similarities = [self._compute_similarity(claim_vec, ev) for ev in evidence_vectors]
            max_sim = max(similarities) if similarities else 0.0
            best_ev_idx = similarities.index(max_sim) if similarities else -1

            claim_info = {
                "claim": claims[i],
                "max_similarity": round(max_sim, 4),
                "best_evidence": evidence_texts[best_ev_idx] if best_ev_idx >= 0 else "",
                "best_evidence_idx": best_ev_idx,
            }

            if max_sim >= similarity_threshold:
                passed_claims.append(claim_info)
            else:
                flagged_claims.append(claim_info)

        all_issues: list[dict[str, Any]] = []
        all_corrections: list[dict[str, Any]] = []

        all_similarities = [c["max_similarity"] for c in passed_claims + flagged_claims]
        avg_sim = sum(all_similarities) / len(all_similarities) if all_similarities else 0.0
        source_alignment = avg_sim
        factual_accuracy = avg_sim

        if flagged_claims:
            flagged_with_evidence = []
            for fc in flagged_claims:
                relevant = fc["best_evidence"] if fc["best_evidence"] else evidence_texts[0] if evidence_texts else ""
                flagged_with_evidence.append({
                    "claim": fc["claim"],
                    "evidence": relevant,
                    "similarity": fc["max_similarity"],
                })

            llm_result = await self._verify_flagged_claims(
                flagged_claims=flagged_with_evidence,
                question=question,
                language=language,
                max_issues=max_issues,
            )

            llm_issues = llm_result.get("issues", [])
            llm_corrections = llm_result.get("corrections", [])
            llm_supported_count = llm_result.get("supported_count", 0)

            all_issues.extend(llm_issues)
            all_corrections.extend(llm_corrections)

            total_claims = len(claims)
            flagged_count = len(flagged_claims)
            passed_count = len(passed_claims)

            unsupported_count = flagged_count - llm_supported_count
            supported_count = passed_count + llm_supported_count

            if total_claims > 0:
                factual_accuracy = supported_count / total_claims

            all_issues.sort(key=lambda x: {
                "high": 0, "medium": 1, "low": 2,
            }.get(x.get("severity", "low"), 2))
        else:
            if len(claims) > 0:
                factual_accuracy = 1.0

        corrected_response = generated_response
        if all_corrections:
            for corr in all_corrections:
                original = corr.get("original", "")
                corrected = corr.get("corrected", "")
                if original and corrected and original in corrected_response:
                    corrected_response = corrected_response.replace(original, corrected, 1)

        has_high_severity = any(i.get("severity") == "high" for i in all_issues)
        has_critical_gap = factual_accuracy < similarity_threshold

        confidence_score = factual_accuracy if not has_high_severity else max(0.0, factual_accuracy - 0.3)

        is_supported = (
            confidence_score >= 0.7
            and not has_high_severity
            and not has_critical_gap
        )

        flagged_similarities = [c["max_similarity"] for c in flagged_claims]
        flagged_avg = sum(flagged_similarities) / len(flagged_similarities) if flagged_similarities else 0.0
        consistency = 1.0 - flagged_avg if flagged_similarities else 1.0

        return {
            "verdict": {
                "confidence_score": round(confidence_score, 4),
                "is_supported": is_supported,
                "issues": all_issues[:max_issues],
                "corrections": all_corrections,
            },
            "corrected_response": corrected_response,
            "score": {
                "overall_score": round(confidence_score, 4),
                "factual_accuracy": round(factual_accuracy, 4),
                "source_alignment": round(source_alignment, 4),
                "completeness": round(float(len(passed_claims) + len(flagged_claims)) / len(claims), 4) if claims else 0.0,
                "consistency": round(consistency, 4),
            },
            "_debug": {
                "mode": "hybrid",
                "total_claims": len(claims),
                "passed_claims": len(passed_claims),
                "flagged_claims": len(flagged_claims),
                "similarity_threshold": similarity_threshold,
                "avg_similarity": round(avg_sim, 4),
            },
        }

    async def _review_embedding_only(
        self,
        generated_response: str,
        evidence: Any,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    ) -> dict[str, Any]:
        claims = self._split_claims(generated_response)
        evidence_texts = self._format_evidence_texts(evidence)

        all_texts = claims + evidence_texts
        all_vectors = await self._embed_batch(all_texts)

        claim_vectors = all_vectors[: len(claims)]
        evidence_vectors = all_vectors[len(claims) :]

        issues: list[dict[str, Any]] = []
        passed = 0
        flagged = 0

        for i, claim_vec in enumerate(claim_vectors):
            similarities = [self._compute_similarity(claim_vec, ev) for ev in evidence_vectors]
            max_sim = max(similarities) if similarities else 0.0

            if max_sim >= similarity_threshold:
                passed += 1
            else:
                flagged += 1
                severity = "high" if max_sim < 0.2 else "medium" if max_sim < similarity_threshold * 0.7 else "low"
                issues.append({
                    "severity": severity,
                    "claim": claims[i],
                    "description": f"Claim similarity to evidence is {max_sim:.2f} (below threshold {similarity_threshold})",
                    "suggestion": "This claim could not be verified against the source documents. Review manually or provide additional evidence.",
                })

        total = len(claims)
        factual_accuracy = passed / total if total > 0 else 0.0
        has_high = any(i.get("severity") == "high" for i in issues)

        confidence_score = factual_accuracy if not has_high else max(0.0, factual_accuracy - 0.3)
        is_supported = confidence_score >= 0.7 and not has_high

        return {
            "verdict": {
                "confidence_score": round(confidence_score, 4),
                "is_supported": is_supported,
                "issues": issues,
                "corrections": [],
            },
            "corrected_response": generated_response,
            "score": {
                "overall_score": round(confidence_score, 4),
                "factual_accuracy": round(factual_accuracy, 4),
                "source_alignment": round(float(passed) / total, 4) if total > 0 else 0.0,
                "completeness": 1.0,
                "consistency": round(1.0 - float(flagged) / total, 4) if total > 0 else 1.0,
            },
            "_debug": {
                "mode": "embedding_only",
                "total_claims": total,
                "passed_claims": passed,
                "flagged_claims": flagged,
                "similarity_threshold": similarity_threshold,
            },
        }

    async def _verify_flagged_claims(
        self,
        flagged_claims: list[dict[str, Any]],
        question: str = "",
        language: str = "fr",
        max_issues: int = 5,
    ) -> dict[str, Any]:
        claims_text = ""
        for i, fc in enumerate(flagged_claims, 1):
            claims_text += f"[CLAIM {i}] (similarity to evidence: {fc['similarity']})\n{fc['claim']}\n"
            claims_text += f"Evidence: {fc['evidence']}\n\n"

        question_hint = ""
        if question and question.strip():
            question_hint = f"\nOriginal question: {question}\n"

        prompt = f"""Verify these specific claims against the provided evidence.{question_hint}
Language: {language}

For EACH claim, determine if it is: supported, contradicted, or unverifiable.

Return ONLY this JSON structure:

{{
  "supported_count": number of claims that ARE supported by evidence,
  "issues": [
    {{
      "severity": "high" or "medium" or "low",
      "claim": "The claim text",
      "description": "Why this claim is problematic",
      "suggestion": "How to fix"
    }}
  ],
  "corrections": [
    {{
      "original": "Original claim",
      "corrected": "Corrected version from evidence",
      "reason": "Why corrected"
    }}
  ]
}}

CLAIMS TO VERIFY:
{claims_text}"""

        llm = self._get_llm()
        response_text = await llm.generate(
            prompt=prompt,
            system_prompt=FLAGGED_CLAIM_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=2048,
            disable_thinking=True,
        )

        json_str = self._extract_json(response_text)

        try:
            parsed = json_lib.loads(json_str)
        except json_lib.JSONDecodeError:
            logger.warning(f"Failed to parse flagged claims LLM JSON response. Response was: {response_text[:500]}")
            parsed = {}

        return {
            "supported_count": parsed.get("supported_count", 0),
            "issues": parsed.get("issues", []),
            "corrections": parsed.get("corrections", []),
        }

    async def _review_llm_only(
        self,
        generated_response: str,
        evidence: Any,
        question: str = "",
        strictness: str = "moderate",
        language: str = "fr",
        max_issues: int = 5,
        verification_criteria: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        formatted_evidence = self._format_evidence(evidence)

        strictness_map = {
            "lenient": "Be lenient — only flag clear hallucinations and major errors. Give benefit of doubt.",
            "moderate": "Be balanced — flag unsupported claims and moderate inaccuracies. Standard verification.",
            "strict": "Be strict — flag even minor inconsistencies, ambiguous attributions, and imprecise language.",
        }
        strictness_instruction = strictness_map.get(strictness, strictness_map["moderate"])

        language_map = {"fr": "French", "en": "English", "ar": "Arabic"}
        lang_name = language_map.get(language, language)

        criteria_section = ""
        if verification_criteria and len(verification_criteria) > 0:
            criteria_lines = []
            for c in verification_criteria:
                criteria_lines.append(
                    f"- {c.get('label', c.get('key', ''))}: {c.get('description', '')}"
                )
            if criteria_lines:
                criteria_section = (
                    "\nADDITIONAL VERIFICATION CRITERIA:\n" + "\n".join(criteria_lines)
                )

        question_hint = ""
        if question and question.strip():
            question_hint = f"\n\nOriginal question: {question}"

        prompt = f"""Verify the following AI-generated response against the provided source documents.
{question_hint}

Language of response: {lang_name}
Strictness level: {strictness}
{strictness_instruction}
{criteria_section}
Limit issues to maximum {max_issues} most important ones.

Return EXACTLY this JSON structure:

{{
  "verdict": {{
    "confidence_score": number between 0.0 and 1.0,
    "is_supported": true or false,
    "issues": [
      {{
        "severity": "high" or "medium" or "low",
        "claim": "The claim being checked",
        "description": "Detailed explanation of the issue",
        "suggestion": "How to fix or improve this"
      }}
    ],
    "corrections": [
      {{
        "original": "Original text from the response",
        "corrected": "Corrected version based on evidence",
        "reason": "Why this correction was made"
      }}
    ]
  }},
  "corrected_response": "Full corrected version of the response incorporating all corrections",
  "score": {{
    "overall_score": number between 0.0 and 1.0,
    "factual_accuracy": number between 0.0 and 1.0,
    "source_alignment": number between 0.0 and 1.0,
    "completeness": number between 0.0 and 1.0,
    "consistency": number between 0.0 and 1.0
  }}
}}

SOURCE DOCUMENTS (EVIDENCE):
{formatted_evidence}

AI-GENERATED RESPONSE TO VERIFY:
{generated_response[:2000]}"""

        llm = self._get_llm()
        response_text = await llm.generate(
            prompt=prompt,
            system_prompt=CRITIC_SYSTEM_PROMPT,
            temperature=0.0,
            max_tokens=1024,
            disable_thinking=True,
        )

        json_str = self._extract_json(response_text)

        try:
            parsed = json_lib.loads(json_str)
        except json_lib.JSONDecodeError:
            logger.warning(
                f"Failed to parse critic LLM JSON response. Response was: {response_text[:500]}"
            )
            parsed = {}

        verdict = parsed.get("verdict") or {}
        score = parsed.get("score") or {}

        return {
            "verdict": {
                "confidence_score": verdict.get("confidence_score", 0.0),
                "is_supported": verdict.get("is_supported", False),
                "issues": verdict.get("issues", []),
                "corrections": verdict.get("corrections", []),
            },
            "corrected_response": parsed.get("corrected_response", generated_response),
            "score": {
                "overall_score": score.get("overall_score", 0.0),
                "factual_accuracy": score.get("factual_accuracy", 0.0),
                "source_alignment": score.get("source_alignment", 0.0),
                "completeness": score.get("completeness", 0.0),
                "consistency": score.get("consistency", 0.0),
            },
            "_debug": {
                "mode": "llm_only",
            },
        }
