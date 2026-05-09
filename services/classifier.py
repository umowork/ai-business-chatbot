"""
Query Classifier Service.
Classifies incoming messages into Sales / Support / Other categories
using LLM-based classification with structured output.
"""

import json
import logging
from enum import Enum
from typing import Any

from config import Config
from services.llm import LLMFactory, LLMResponse

logger = logging.getLogger(__name__)


class QueryCategory(str, Enum):
    SALES = "sales"
    SUPPORT = "support"
    OTHER = "other"


class ClassificationResult:
    """Result of query classification."""

    def __init__(
        self,
        category: QueryCategory,
        confidence: float = 0.0,
        explanation: str = "",
        extracted_data: dict[str, Any] | None = None,
    ):
        self.category = category
        self.confidence = confidence
        self.explanation = explanation
        self.extracted_data = extracted_data or {}

    def is_sales(self) -> bool:
        return self.category == QueryCategory.SALES

    def is_support(self) -> bool:
        return self.category == QueryCategory.SUPPORT

    def is_other(self) -> bool:
        return self.category == QueryCategory.OTHER

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "confidence": self.confidence,
            "explanation": self.explanation,
            "extracted_data": self.extracted_data,
        }


# ── Keywords and patterns for rule-based fallback ───────────────────────

SALES_KEYWORDS = [
    "купить", "заказать", "цена", "стоимость", "сколько стоит",
    "хочу", "приобрести", "услуга", "услуги", "запись",
    "записаться", "консультация", "прайс", "скидка", "акция",
    "предложение", "коммерческое", "расчет", "рассчитать",
    "оставить заявку", "свяжитесь", "перезвоните",
]

SUPPORT_KEYWORDS = [
    "проблема", "не работает", "ошибка", "сломалось", "помогите",
    "не могу", "не получается", "поддержка", "техподдержка",
    "жалоба", "претензия", "вернуть", "возврат", "брак",
    "гарантия", "ремонт", "неисправность", "сбой",
]


def keyword_classify(text: str) -> QueryCategory | None:
    """Fast keyword-based classification as fallback."""
    text_lower = text.lower().strip()

    sales_score = sum(1 for kw in SALES_KEYWORDS if kw in text_lower)
    support_score = sum(1 for kw in SUPPORT_KEYWORDS if kw in text_lower)

    if sales_score > support_score and sales_score >= 1:
        return QueryCategory.SALES
    if support_score > sales_score and support_score >= 1:
        return QueryCategory.SUPPORT
    if sales_score == support_score >= 1:
        return QueryCategory.SUPPORT
    return None


# ── LLM-based Classifier ────────────────────────────────────────────────

CLASSIFIER_SYSTEM_PROMPT = """Ты — классификатор запросов для бизнес-чат-бота.
Определи категорию сообщения клиента и извлеки ключевые данные.

Категории:
- **sales** — клиент хочет купить услугу, записаться, получить консультацию, узнать цены
- **support** — клиент сообщает о проблеме, ошибке, неисправности, нужна техподдержка
- **other** — общее общение, приветствие, вопрос не по делу

Ответь строго в JSON формате:
{
    "category": "sales|support|other",
    "confidence": от 0.0 до 1.0,
    "explanation": "Краткое пояснение решения",
    "extracted_data": {
        "service": null или строка,
        "urgency": null или "low"|"medium"|"high",
        "budget": null или строка,
        "phone": null или строка
    }
}"""


class QueryClassifier:
    """Classifies user queries using LLM with rule-based fallback."""

    def __init__(self, config: Config):
        self.config = config
        self._llm = None

    @property
    def llm(self):
        """Lazy LLM provider initialization."""
        if self._llm is None:
            self._llm = LLMFactory.get_provider(self.config)
        return self._llm

    async def classify(
        self, text: str, chat_history: list[dict[str, str]] | None = None
    ) -> ClassificationResult:
        """
        Classify a user query.
        Uses LLM first, falls back to keyword matching.
        """
        if not text.strip():
            return ClassificationResult(
                category=QueryCategory.OTHER,
                confidence=0.5,
                explanation="Empty message",
            )

        # Fast keyword-based classification for simple cases
        keyword_result = keyword_classify(text)
        if keyword_result and len(text) < 50:
            # For short messages with clear intent, use keyword classification
            return ClassificationResult(
                category=keyword_result,
                confidence=0.7,
                explanation=f"Keyword-based classification: {keyword_result.value}",
            )

        # LLM-based classification
        try:
            response = await self.llm.chat_with_history(
                system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                user_message=text,
                history=chat_history,
                temperature=0.1,
                max_tokens=256,
                json_mode=True,
            )
            return self._parse_llm_response(response, text)
        except Exception as e:
            logger.error("LLM classification error: %s", e)
            # Fallback to keyword
            keyword_cat = keyword_classify(text)
            return ClassificationResult(
                category=keyword_cat or QueryCategory.OTHER,
                confidence=0.5,
                explanation=f"Fallback after LLM error: {str(e)}",
            )

    def _parse_llm_response(
        self, response: LLMResponse, original_text: str
    ) -> ClassificationResult:
        """Parse LLM JSON response into ClassificationResult."""
        try:
            data = json.loads(response.content)
            category_str = data.get("category", "other").lower()
            category = QueryCategory(category_str)
            confidence = float(data.get("confidence", 0.5))
            explanation = data.get("explanation", "")
            extracted_data = data.get("extracted_data", {})

            return ClassificationResult(
                category=category,
                confidence=min(max(confidence, 0.0), 1.0),
                explanation=explanation,
                extracted_data=extracted_data or {},
            )
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            logger.warning("Failed to parse LLM classification: %s", e)
            # Fallback to keyword
            keyword_cat = keyword_classify(original_text)
            return ClassificationResult(
                category=keyword_cat or QueryCategory.OTHER,
                confidence=0.4,
                explanation=f"Parse error: {str(e)}",
            )

    async def is_sales_query(
        self, text: str, chat_history: list[dict[str, str]] | None = None
    ) -> bool:
        """Quick check if query is sales-related."""
        result = await self.classify(text, chat_history)
        return result.is_sales()
