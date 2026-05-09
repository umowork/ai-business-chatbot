"""
Tests for LLM service — providers, factory, cost estimation.
"""

import pytest

from services.llm import (
    LLMFactory,
    LLMResponse,
    MockLLMProvider,
    OpenAIProvider,
    estimate_cost,
)


class TestLLMResponse:
    """Test LLMResponse data class."""

    def test_llm_response_creation(self):
        resp = LLMResponse(
            content="Hello",
            model="gpt-4o-mini",
            provider="openai",
            latency_ms=150.0,
            cost_usd=0.001,
            input_tokens=50,
            output_tokens=100,
        )
        assert resp.content == "Hello"
        assert resp.model == "gpt-4o-mini"
        assert resp.latency_ms == 150.0
        assert resp.cost_usd == 0.001

    def test_llm_response_str(self):
        resp = LLMResponse(
            content="Test response",
            model="mock",
            provider="mock",
            latency_ms=0,
        )
        assert str(resp) == "Test response"

    def test_llm_response_to_dict(self):
        resp = LLMResponse(
            content="Dict test",
            model="test-model",
            provider="test",
            latency_ms=50,
        )
        d = resp.to_dict()
        assert d["content"] == "Dict test"
        assert d["model"] == "test-model"
        assert d["latency_ms"] == 50


class TestCostEstimation:
    """Test LLM cost estimation."""

    def test_estimate_cost_gpt4o_mini(self):
        cost = estimate_cost("gpt-4o-mini", input_tokens=1000, output_tokens=500)
        # 1000 * 0.00015 / 1000 + 500 * 0.0006 / 1000
        expected = 0.00015 + 0.0003
        assert cost == pytest.approx(expected, rel=1e-3)

    def test_estimate_cost_unknown_model(self):
        cost = estimate_cost("unknown-model", input_tokens=1000, output_tokens=1000)
        # Falls back to default costs: 0.001 input, 0.002 output
        expected = 0.001 + 0.002
        assert cost == pytest.approx(expected, rel=1e-3)

    def test_estimate_cost_zero_tokens(self):
        cost = estimate_cost("gpt-4o-mini", input_tokens=0, output_tokens=0)
        assert cost == 0.0


class TestMockLLMProvider:
    """Test MockLLMProvider."""

    @pytest.mark.asyncio
    async def test_mock_provider_chat(self, test_config):
        provider = MockLLMProvider(test_config)
        response = await provider.chat([
            {"role": "user", "content": "Привет"}
        ])
        assert response.content is not None
        assert "Mock" in response.content or "тестовый" in response.content
        assert response.provider == "mock"
        assert response.latency_ms > 0

    @pytest.mark.asyncio
    async def test_mock_provider_chat_with_history(self, test_config):
        provider = MockLLMProvider(test_config)
        response = await provider.chat_with_history(
            system_prompt="Тест",
            user_message="Как дела?",
            history=[{"role": "assistant", "content": "Всё отлично!"}],
        )
        assert response.content is not None
        assert response.provider == "mock"


class TestLLMFactory:
    """Test LLM Factory."""

    def test_factory_mock_mode(self, test_config):
        # When MOCK_MODE is true, factory should return MockLLMProvider
        provider = LLMFactory.get_provider(test_config)
        assert isinstance(provider, MockLLMProvider)

    def test_factory_unknown_provider_fallback(self, test_config):
        # Temporarily set an unknown provider
        import os
        os.environ["LLM_PROVIDER"] = "nonexistent"
        os.environ["MOCK_MODE"] = "false"

        fresh_config = test_config.__class__.from_env()
        # Force MOCK_MODE false for this test
        object.__setattr__(fresh_config, "mock_mode", False)
        object.__setattr__(fresh_config, "llm_provider", "nonexistent")

        provider = LLMFactory.get_provider(fresh_config)
        assert isinstance(provider, MockLLMProvider)

    def test_factory_openai_provider(self, test_config):
        """OpenAI provider should be instantiated (not connected)."""
        import os
        os.environ["MOCK_MODE"] = "false"
        os.environ["LLM_PROVIDER"] = "openai"

        fresh_config = test_config.__class__.from_env()
        object.__setattr__(fresh_config, "mock_mode", False)
        object.__setattr__(fresh_config, "llm_provider", "openai")

        provider = LLMFactory.get_provider(fresh_config)
        assert isinstance(provider, OpenAIProvider)
