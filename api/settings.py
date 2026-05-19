import json
import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


class VertexAISettings(BaseModel):
    model_name: str = Field()
    project: str = Field()


class AppSettings(BaseModel):
    vertex_ai: VertexAISettings = Field(default_factory=VertexAISettings)


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    candidates = [
        Path(__file__).resolve().parents[1] / "app_config.json",
        Path(__file__).resolve().with_name("app_config.json"),
    ]
    config_path = next((path for path in candidates if path.exists()), candidates[-1])
    payload: dict = {}

    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

    try:
        settings = AppSettings.model_validate(payload)
    except Exception as exc:
        raise RuntimeError(
            f"Missing or invalid app configuration in {config_path}. "
            "Define vertex_ai.model_name and vertex_ai.project in app_config.json or set VERTEX_MODEL_NAME and VERTEX_PROJECT."
        ) from exc

    env_model_name = os.getenv("VERTEX_MODEL_NAME")
    env_project = os.getenv("VERTEX_PROJECT")

    if env_model_name:
        settings.vertex_ai.model_name = env_model_name
    if env_project:
        settings.vertex_ai.project = env_project

    return settings