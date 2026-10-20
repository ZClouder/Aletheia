from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from .config import AppConfig
from .evaluators import JudgeOutput


class OllamaJudge:
    def __init__(self, config: AppConfig):
        self.config = config
        self.client = AsyncOpenAI(
            base_url=config.llm.base_url,
            api_key=config.llm.api_key,
            timeout=config.llm.timeout,
        )

    async def __call__(self, prompt: str) -> JudgeOutput:
        response = await self.client.chat.completions.create(
            model=self.config.judge.model,
            messages=[
                {
                    "role": "system",
                    "content": "你是严格的 AI 应用评测员，只遵循输出协议。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=self.config.judge.temperature,
            logprobs=True,
            top_logprobs=self.config.judge.top_logprobs,
        )
        choice = response.choices[0]
        text = choice.message.content or ""
        probabilities: dict[str, float] = {}
        raw_logprobs: Any = choice.logprobs
        content = getattr(raw_logprobs, "content", None) if raw_logprobs else None
        if content:
            for token_info in content:
                for item in getattr(token_info, "top_logprobs", []) or []:
                    token = str(getattr(item, "token", ""))
                    logprob = float(getattr(item, "logprob", float("-inf")))
                    probabilities[token] = max(probabilities.get(token, float("-inf")), logprob)
        return JudgeOutput(text, probabilities)

    async def close(self) -> None:
        await self.client.close()
