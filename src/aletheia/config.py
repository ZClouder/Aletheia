from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, model_validator

from .models import StrictModel


class LLMConfig(StrictModel):
    base_url: str
    api_key: str = "ollama"
    model: str
    timeout: float = Field(default=120, gt=0)


class JudgeConfig(StrictModel):
    model: str
    temperature: float = Field(default=0, ge=0, le=2)
    top_logprobs: int = Field(default=5, ge=2, le=20)


class DataConfig(StrictModel):
    traces: Path
    evaluation_set: Path


class OutputConfig(StrictModel):
    directory: Path


class ThresholdConfig(StrictModel):
    pass_score: float = Field(default=0.7, ge=0, le=1)


class RuntimeConfig(StrictModel):
    max_concurrency: int = Field(default=4, ge=1, le=32)


class ObservabilityConfig(StrictModel):
    enabled: bool = False
    color: Literal["auto", "always", "never"] = "auto"
    verbose: bool = False


class AppConfig(StrictModel):
    llm: LLMConfig
    judge: JudgeConfig
    data: DataConfig
    output: OutputConfig
    thresholds: ThresholdConfig
    runtime: RuntimeConfig = RuntimeConfig()
    observability: ObservabilityConfig = ObservabilityConfig()

    @classmethod
    def from_yaml(cls, path: Path) -> AppConfig:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"configuration must be a mapping: {path}")
        return cls.model_validate(raw)

    @model_validator(mode="after")
    def models_are_present(self) -> AppConfig:
        if not self.llm.model.strip() or not self.judge.model.strip():
            raise ValueError("llm and judge model names must not be blank")
        return self
