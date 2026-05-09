"""
YandexGPT LLM Provider (Yandex Cloud).
Uses lazy imports for the yandex SDK.
"""

import logging
import time

from config import Config
from services.llm import (
    BaseLLMProvider,
    LLMResponse,
)

logger = logging.getLogger(__name__)


class YandexGPTProvider(BaseLLMProvider):
    """YandexGPT API provider via Yandex Cloud."""

    def __init__(self, config: Config):
        super().__init__(config)
        self._session = None

    def _get_session(self):
        """Lazy import of httpx for YandexGPT API calls."""
        import httpx
        if self._session is None:
            self._session = httpx.AsyncClient(timeout=60.0)
        return self._session

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> LLMResponse:
        client = self._get_session()
        model = self.config.yandex_model
        folder_id = self.config.yandex_folder_id
        api_key = self.config.yandex_api_key

        # YandexGPT uses a specific message format
        # Extract system message if present
        system_prompt = "Ты полезный AI-ассистент."
        yandex_messages = []
        for m in messages:
            if m["role"] == "system":
                system_prompt = m["content"]
            else:
                role = "assistant" if m["role"] == "assistant" else "user"
                yandex_messages.append({"role": role, "text": m["content"]})

        request_body = {
            "modelUri": f"gpt://{folder_id}/{model}",
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": max_tokens,
            },
            "messages": yandex_messages,
        }

        # If json mode, add instruction
        if json_mode:
            request_body["completionOptions"]["temperature"] = 0.3
            system_prompt += "\nОтвечай строго в формате JSON."

        # Yandex doesn't have system message in the same sense;
        # we prepend system to the first user message or use instructionText
        if yandex_messages and yandex_messages[0]["role"] == "user":
            yandex_messages[0]["text"] = f"{system_prompt}\n\n{yandex_messages[0]['text']}"

        start = time.monotonic()
        try:
            response = await client.post(
                "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
                headers={
                    "Authorization": f"Api-Key {api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
            latency = (time.monotonic() - start) * 1000

            if response.status_code != 200:
                logger.error(
                    f"YandexGPT API error {response.status_code}: {response.text}"
                )
                return LLMResponse(
                    content=f"Извините, ошибка YandexGPT: HTTP {response.status_code}",
                    model=model,
                    provider="yandex",
                    latency_ms=round(latency, 1),
                    cost_usd=0,
                )

            data = response.json()
            result = data.get("result", {})
            alternatives = result.get("alternatives", [])
            if alternatives:
                content = alternatives[0].get("message", {}).get("text", "")
            else:
                content = ""

            # Yandex doesn't return token counts in the standard API
            return LLMResponse(
                content=content,
                model=model,
                provider="yandex",
                latency_ms=round(latency, 1),
                cost_usd=0.001,
                input_tokens=0,
                output_tokens=0,
            )
        except Exception as e:
            latency = (time.monotonic() - start) * 1000
            logger.error("YandexGPT API error after %.0fms: %s", latency, e)
            return LLMResponse(
                content=f"Извините, ошибка YandexGPT: {str(e)}",
                model=model,
                provider="yandex",
                latency_ms=round(latency, 1),
                cost_usd=0,
            )
