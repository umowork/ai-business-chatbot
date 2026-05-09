"""
Tests for Query Classifier service.
"""

import pytest

from services.classifier import (
    CLASSIFIER_SYSTEM_PROMPT,
    ClassificationResult,
    QueryCategory,
    QueryClassifier,
    keyword_classify,
)


class TestQueryCategory:
    """Test QueryCategory enum."""

    def test_category_values(self):
        assert QueryCategory.SALES.value == "sales"
        assert QueryCategory.SUPPORT.value == "support"
        assert QueryCategory.OTHER.value == "other"

    def test_category_is_methods(self):
        result = ClassificationResult(category=QueryCategory.SALES)
        assert result.is_sales() is True
        assert result.is_support() is False
        assert result.is_other() is False

        result2 = ClassificationResult(category=QueryCategory.SUPPORT)
        assert result2.is_sales() is False
        assert result2.is_support() is True

        result3 = ClassificationResult(category=QueryCategory.OTHER)
        assert result3.is_sales() is False
        assert result3.is_other() is True


class TestClassificationResult:
    """Test ClassificationResult data class."""

    def test_defaults(self):
        result = ClassificationResult(category=QueryCategory.OTHER)
        assert result.confidence == 0.0
        assert result.explanation == ""
        assert result.extracted_data == {}

    def test_with_data(self):
        result = ClassificationResult(
            category=QueryCategory.SALES,
            confidence=0.95,
            explanation="Клиент хочет купить",
            extracted_data={"service": "Консультация", "phone": "+7 999 123-45-67"},
        )
        assert result.confidence == 0.95
        assert result.extracted_data["service"] == "Консультация"
        assert result.is_sales() is True

    def test_to_dict(self):
        result = ClassificationResult(
            category=QueryCategory.SUPPORT,
            confidence=0.8,
            explanation="Проблема с продуктом",
        )
        d = result.to_dict()
        assert d["category"] == "support"
        assert d["confidence"] == 0.8


class TestKeywordClassification:
    """Test keyword-based classification fallback."""

    def test_sales_keywords(self):
        assert keyword_classify("Хочу купить услугу") == QueryCategory.SALES
        assert keyword_classify("Сколько стоит консультация") == QueryCategory.SALES
        assert keyword_classify("Записаться на прием") == QueryCategory.SALES

    def test_support_keywords(self):
        assert keyword_classify("У меня проблема с продуктом") == QueryCategory.SUPPORT
        assert keyword_classify("Не работает, помогите") == QueryCategory.SUPPORT
        assert keyword_classify("Хочу вернуть товар") == QueryCategory.SUPPORT

    def test_other_keywords(self):
        assert keyword_classify("Привет") is None
        assert keyword_classify("Как дела?") is None

    def test_mixed_keywords_sales_wins(self):
        """When both sales and support keywords present, sales should win with more matches."""
        # "купить" (sales) + "помогите" (support) + "стоимость" (sales) = sales wins
        result = keyword_classify("Хочу купить, помогите, какая стоимость?")
        assert result == QueryCategory.SALES

    def test_empty_text(self):
        assert keyword_classify("") is None

    def test_case_insensitive(self):
        assert keyword_classify("КУПИТЬ УСЛУГУ") == QueryCategory.SALES


class TestQueryClassifier:
    """Test QueryClassifier (mock mode uses keyword fallback)."""

    @pytest.mark.asyncio
    async def test_classify_empty(self, test_config):
        classifier = QueryClassifier(test_config)
        result = await classifier.classify("")
        assert result.category == QueryCategory.OTHER

    @pytest.mark.asyncio
    async def test_classify_sales_short(self, test_config):
        """Short sales messages should use keyword classification."""
        classifier = QueryClassifier(test_config)
        result = await classifier.classify("Хочу купить")
        assert result.is_sales() is True

    @pytest.mark.asyncio
    async def test_classify_support_short(self, test_config):
        classifier = QueryClassifier(test_config)
        result = await classifier.classify("Не работает, помогите")
        assert result.is_support() is True

    @pytest.mark.asyncio
    async def test_classify_other(self, test_config):
        classifier = QueryClassifier(test_config)
        result = await classifier.classify("Привет, как дела?")
        assert result.is_other() is True

    @pytest.mark.asyncio
    async def test_is_sales_query(self, test_config):
        classifier = QueryClassifier(test_config)
        assert await classifier.is_sales_query("Хочу купить услугу") is True
        assert await classifier.is_sales_query("Привет") is False

    def test_system_prompt_defined(self):
        """The classifier system prompt should be a non-empty string."""
        assert CLASSIFIER_SYSTEM_PROMPT is not None
        assert len(CLASSIFIER_SYSTEM_PROMPT) > 50
        assert "sales" in CLASSIFIER_SYSTEM_PROMPT
        assert "support" in CLASSIFIER_SYSTEM_PROMPT
