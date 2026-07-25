from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class TranslationService:
    """Offline translation using Argos Translate — no API key required.
    Downloads and installs language packages on first use per language pair."""

    def __init__(self):
        self._installed_pairs: set[tuple[str, str]] = set()

    def _ensure_language_package(self, from_code: str, to_code: str) -> None:
        import argostranslate.package
        import argostranslate.translate

        pair = (from_code, to_code)
        if pair in self._installed_pairs:
            return

        installed_languages = argostranslate.translate.get_installed_languages()
        from_lang = next(
            (l for l in installed_languages if l.code == from_code), None
        )
        to_lang = next((l for l in installed_languages if l.code == to_code), None)

        if from_lang and to_lang and from_lang.get_translation(to_lang):
            self._installed_pairs.add(pair)
            return

        argostranslate.package.update_package_index()
        available_packages = argostranslate.package.get_available_packages()
        package = next(
            (
                p
                for p in available_packages
                if p.from_code == from_code and p.to_code == to_code
            ),
            None,
        )
        if package is None:
            raise ValueError(
                f"No Argos Translate package available for {from_code} -> {to_code}"
            )

        download_path = package.download()
        argostranslate.package.install_from_path(download_path)
        self._installed_pairs.add(pair)

    def translate(self, text: str, from_code: str, to_code: str) -> dict[str, Any]:
        import argostranslate.translate

        if from_code == to_code:
            return {
                "translated_text": text,
                "from_language": from_code,
                "to_language": to_code,
                "skipped": True,
            }

        self._ensure_language_package(from_code, to_code)
        translated = argostranslate.translate.translate(text, from_code, to_code)

        return {
            "translated_text": translated,
            "from_language": from_code,
            "to_language": to_code,
            "skipped": False,
        }