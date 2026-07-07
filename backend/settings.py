from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Sympact Workflow Engine"
    app_version: str = "0.1.0"
    debug: bool = True

    upload_dir: str = "data/uploads"
    storage_dir: str = "data/storage"

    llm_api_key: str = ""
    llm_default_model: str = "gpt-4o"

    vector_db_url: str = ""
    vector_db_collection: str = "sympact"

    ocr_tesseract_path: str = ""
    ocr_languages: str = "eng+fra"

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_prefix": "SYMPACT_", "env_file": ".env"}


settings = Settings()
