"""
GigaChat LLM Provider (Sber).
Uses lazy imports for the gigachat SDK.
"""

import logging
import os
import time

from services.llm import (
    BaseLLMProvider,
    LLMResponse,
    estimate_cost,
)

logger = logging.getLogger(__name__)


class GigaChatProvider(BaseLLMProvider):
    """GigaChat API provider from Sber."""

    def _get_client(self):
        """Lazy import to avoid errors when SDK not installed."""
        from gigachat import GigaChat

        verify_ssl = os.getenv("GIGACHAT_VERIFY_SSL", "true").lower() in ("1", "true", "yes")
        return GigaChat(
            credentials=self.config.gigachat_credentials,
            model=self.config.gigachat_model,
            verify_ssl_certs=verify_ssl,
        )

    def _convert_messages(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Convert standard messages to GigaChat format."""
        result = []
        for m in messages:
            role = m["role"]
            if role == "system":
                role = "system"
            elif role == "assistant":
                role = "assistant"
            else:
                role = "user"
            result.append({"role": role, "content": m["content"]})
        return result

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResponse:
        client = self._get_client()
        model = self.config.gigachat_model
        giga_messages = self._convert_messages(messages)

        start = time.monotonic()
        try:
            response = await client.achat(
                messages=giga_messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            latency = (time.monotonic() - start) * 1000

            choice = response.choices[0] if response.choices else None
            content = choice.message.content if choice else ""

            # GigaChat may or may not return token counts
            input_tokens = getattr(response, "usage", None)
            input_tok = input_tokens.prompt_tokens if input_tokens else 0
            output_tok = input_tokens.completion_tokens if input_tokens else 0
            cost = estimate_cost(model, input_tok, output_tok)

            return LLMResponse(
                content=content,
                model=model,
                provider="gigachat",
                latency_ms=round(latency, 1),
                cost_usd=cost,
                input_tokens=input_tok,
                output_tokens=output_tok,
            )
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error("GigaChat API error after %.0fms: %s", latency, e)
            return LLMResponse(
                content=f"Извините, ошибка GigaChat: {str(e)}",
                model=model,
                provider="gigachat",
                latency_ms=round(latency, 1),
                cost_usd=0,
            )
