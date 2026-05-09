"""
LLM Service — multi-provider gateway.
Supports OpenAI-compatible, GigaChat, and YandexGPT.
Uses lazy imports for heavy SDKs to avoid import errors in tests.
"""

import logging
import time
from typing import Any

from config import Config

logger = logging.getLogger(__name__)


# ── Pydantic-style schema for structured output ────────────────────────


class LLMResponse:
    """Typed LLM response with content and optional metadata."""

    def __init__(
        self,
        content: str,
        model: str,
        provider: str,
        latency_ms: float,
        cost_usd: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        raw: dict[str, Any] | None = None,
    ):
        self.content = content
        self.model = model
        self.provider = provider
        self.latency_ms = latency_ms
        self.cost_usd = cost_usd
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.raw = raw or {}

    def __str__(self) -> str:
        return self.content

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "model": self.model,
            "provider": self.provider,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }


# ── Cost estimation ────────────────────────────────────────────────────

MODEL_COST_PER_1K_INPUT = {
    "gpt-4o-mini": 0.00015,
    "gpt-4o": 0.0025,
    "gpt-3.5-turbo": 0.0005,
    "GigaChat-20-1.5-h2o": 0.001,
    "yandexgpt-lite": 0.0008,
    "yandexgpt": 0.0012,
}

MODEL_COST_PER_1K_OUTPUT = {
    "gpt-4o-mini": 0.0006,
    "gpt-4o": 0.01,
    "gpt-3.5-turbo": 0.0015,
    "GigaChat-20-1.5-h2o": 0.002,
    "yandexgpt-lite": 0.001,
    "yandexgpt": 0.0016,
}


def estimate_cost(
    model: str, input_tokens: int, output_tokens: int
) -> float:
    """Estimate cost in USD."""
    input_cost = MODEL_COST_PER_1K_INPUT.get(model, 0.001) * input_tokens / 1000
    output_cost = MODEL_COST_PER_1K_OUTPUT.get(model, 0.002) * output_tokens / 1000
    return round(input_cost + output_cost, 6)


# ── Base provider ───────────────────────────────────────────────────────


class BaseLLMProvider:
    """Abstract base for LLM providers."""

    def __init__(self, config: Config):
        self.config = config

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResponse:
        raise NotImplementedError

    async def chat_with_history(
        self,
        system_prompt: str,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResponse:
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})
        return await self.chat(messages, temperature, max_tokens, json_mode)


# ── OpenAI Provider ─────────────────────────────────────────────────────


class OpenAIProvider(BaseLLMProvider):
    """OpenAI-compatible API provider (works with any OpenAI-compatible endpoint)."""

    def _get_client(self):
        """Lazy import of openai to avoid import errors in tests without the SDK."""
        import openai

        kwargs: dict[str, Any] = {"api_key": self.config.openai_api_key}
        if self.config.openai_base_url:
            kwargs["base_url"] = self.config.openai_base_url
        return openai.AsyncOpenAI(**kwargs)

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResponse:
        client = self._get_client()
        model = self.config.openai_model

        extra_kwargs: dict[str, Any] = {}
        if json_mode:
            extra_kwargs["response_format"] = {"type": "json_object"}

        start = time.monotonic()
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **extra_kwargs,
            )
            latency = (time.monotonic() - start) * 1000

            choice = response.choices[0]
            content = choice.message.content or ""

            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0
            cost = estimate_cost(model, input_tokens, output_tokens)

            return LLMResponse(
                content=content,
                model=model,
                provider="openai",
                latency_ms=round(latency, 1),
                cost_usd=cost,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                raw=response.model_dump() if hasattr(response, "model_dump") else {},
            )
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error("OpenAI API error after %.0fms: %s", latency, e)
            return LLMResponse(
                content=f"Извините, произошла ошибка при обращении к AI: {str(e)}",
                model=model,
                provider="openai",
                latency_ms=round(latency, 1),
                cost_usd=0,
            )


# ── Mock Provider (dev mode) ────────────────────────────────────────────


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM provider for development and testing."""

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResponse:
        # Extract the last user message for a context-aware mock response
        last_user_msg = ""
        for m in reversed(messages):
            if m["role"] == "user":
                last_user_msg = m["content"]
                break

        # Simulate delay
        await __import__("asyncio").sleep(0.3)

        content = (
            f"🤖 <b>Mock ответ</b>\\n\\n"
            f"Вы написали: «{last_user_msg[:100]}»\\n\\n"
            f"Это тестовый ответ от AI-ассистента. "
            f"В production режиме здесь будет ответ от {self.config.llm_provider}.\\n\\n"
            f"Чем я могу ещё помочь?"
        )

        return LLMResponse(
            content=content,
            model="mock",
            provider="mock",
            latency_ms=300,
            cost_usd=0.0,
            input_tokens=0,
            output_tokens=0,
        )


# ── Factory ─────────────────────────────────────────────────────────────


class LLMFactory:
    """Factory to create appropriate LLM provider based on config."""

    @staticmethod
    def get_provider(config: Config) -> BaseLLMProvider:
        if config.mock_mode:
            logger.info("Using MockLLMProvider (MOCK_MODE=true)")
            return MockLLMProvider(config)

        provider = config.llm_provider.lower()
        if provider == "openai":
            logger.info("Using OpenAI provider (model: %s)", config.openai_model)
            return OpenAIProvider(config)
        elif provider == "gigachat":
            logger.info("Using GigaChat provider (model: %s)", config.gigachat_model)
            # Lazy import for GigaChat
            try:
                from services.llm_gigachat import GigaChatProvider

                return GigaChatProvider(config)
            except ImportError:
                logger.warning("GigaChat SDK not installed, falling back to mock")
                return MockLLMProvider(config)
        elif provider == "yandex":
            logger.info("Using YandexGPT provider (model: %s)", config.yandex_model)
            try:
                from services.llm_yandex import YandexGPTProvider

                return YandexGPTProvider(config)
            except ImportError:
                logger.warning("YandexGPT SDK not installed, falling back to mock")
                return MockLLMProvider(config)
        else:
            logger.warning("Unknown LLM provider '%s', using mock", provider)
            return MockLLMProvider(config)
