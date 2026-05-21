"""
FastAPI web API for the AI Business Chatbot.
Provides REST endpoints for chat, health check, and admin operations.
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import Config
from crm import CRMFactory
from models.base import Database
from services.classifier import QueryClassifier
from services.llm import LLMFactory
from services.rag import RAGEngine

logger = logging.getLogger(__name__)


# ── Request/Response Schemas ────────────────────────────────────────────


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4096, description="User message")
    user_id: str = Field(..., description="Unique user identifier")
    user_name: str | None = Field(None, max_length=128)
    history: list[dict[str, str]] | None = Field(
        None, description="Previous messages as [{'role': 'user'|'assistant', 'content': '...'}]"
    )


class ChatResponse(BaseModel):
    reply: str = Field(..., description="AI response")
    classification: dict[str, Any] | None = Field(None)
    sources: list[dict[str, Any]] | None = Field(None)


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    mock_mode: bool = False
    services: dict[str, str] = {}


class LeadResponse(BaseModel):
    id: int
    name: str | None
    phone: str | None
    service: str | None
    status: str
    created_at: str


class StatsResponse(BaseModel):
    users: int
    leads: int
    dialog_messages: int


# ── API Application ─────────────────────────────────────────────────────


class WebAPI:
    """FastAPI web application."""

    def __init__(self, config: Config, db: Database):
        self.config = config
        self.db = db

        # Services (lazy)
        self._llm = None
        self._crm = None
        self._classifier = None
        self._rag = None

        self.app = FastAPI(
            title=f"{config.business_name} AI Chatbot API",
            version="1.0.0",
            lifespan=self._lifespan,
        )
        if not config.api_key:
            logger.warning(
                "API_KEY is not set — web API endpoints are UNPROTECTED. "
                "Set API_KEY env var to secure /chat, /leads, /stats, /reindex."
            )
        self._setup_middleware()
        self._register_routes()

    @property
    def llm(self):
        if self._llm is None:
            self._llm = LLMFactory.get_provider(self.config)
        return self._llm

    @property
    def crm(self):
        if self._crm is None:
            self._crm = CRMFactory.get_crm(self.config)
        return self._crm

    @property
    def classifier(self):
        if self._classifier is None:
            self._classifier = QueryClassifier(self.config)
        return self._classifier

    @property
    def rag(self):
        if self._rag is None:
            self._rag = RAGEngine(self.config)
        return self._rag

    @asynccontextmanager
    async def _lifespan(self, app: FastAPI):
        """Application lifespan: init RAG and DB on startup."""
        logger.info("WebAPI starting up...")
        await self.db.create_tables()
        try:
            await self.rag.initialize()
        except Exception as e:
            logger.warning("RAG init failed (non-fatal): %s", e)
        yield
        logger.info("WebAPI shutting down...")

    def _setup_middleware(self):
        """Setup CORS and other middleware."""
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _register_routes(self):
        """Register all API routes."""

        _api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

        async def _require_api_key(
            api_key: str | None = Security(_api_key_header),
        ):
            if self.config.api_key and api_key != self.config.api_key:
                raise HTTPException(status_code=401, detail="Invalid or missing API key")

        @self.app.get("/health", response_model=HealthResponse)
        async def health():
            """Health check endpoint."""
            # Real database check
            db_status = "ok"
            try:
                from sqlalchemy import text
                async with self.db.session_factory() as session:
                    await session.execute(text("SELECT 1"))
            except Exception as e:
                db_status = f"error: {e}"

            services_status = {
                "database": db_status,
                "llm": "mock" if self.config.mock_mode else self.config.llm_provider,
                "crm": "mock" if self.config.mock_mode else self.config.crm_provider,
                "rag": (
                    "initialized"
                    if hasattr(self.rag, "_initialized") and self.rag._initialized
                    else "pending"
                ),
            }
            return HealthResponse(
                status="ok" if db_status == "ok" else "degraded",
                version="1.0.0",
                mock_mode=self.config.mock_mode,
                services=services_status,
            )

        @self.app.post("/chat", response_model=ChatResponse)
        async def chat(request: ChatRequest, _key: str | None = Depends(_require_api_key)):
            """Process a chat message and return AI response."""
            try:
                # Classify query
                classification = await self.classifier.classify(
                    request.message, request.history
                )

                # Build system prompt
                system_prompt = (
                    f"Ты AI-ассистент компании «{self.config.business_name}». "
                    f"Тон: {self.config.business_tonality}. "
                    f"Отвечай на русском языке, будь полезным и вежливым."
                )
                if request.user_name:
                    system_prompt += f"\nКлиент: {request.user_name}"

                # Get response with RAG
                try:
                    reply = await self.rag.answer_with_context(
                        query=request.message,
                        llm_provider=self.llm,
                        system_prompt=system_prompt,
                    )
                except Exception:
                    response = await self.llm.chat_with_history(
                        system_prompt=system_prompt,
                        user_message=request.message,
                        history=request.history,
                    )
                    reply = response.content

                # Get RAG sources if available
                sources = None
                try:
                    rag_results = await self.rag.retrieve_context(request.message)
                    if rag_results:
                        sources = [
                            {
                                "text": chunk.text[:200],
                                "source": chunk.source,
                                "page": chunk.page,
                                "score": round(float(score), 3),
                            }
                            for chunk, score in rag_results[:3]
                        ]
                except Exception:
                    pass

                # Handle sales qualification via web
                if classification.is_sales() and classification.extracted_data.get("phone"):
                    phone = classification.extracted_data["phone"]
                    try:
                        crm_result = await self.crm.create_deal(
                            name=request.user_name or "Веб-клиент",
                            phone=phone,
                            service=classification.extracted_data.get("service"),
                            budget=classification.extracted_data.get("budget"),
                        )
                        if crm_result.success:
                            logger.info("CRM deal created via web: %s", crm_result.deal_id)
                    except Exception as e:
                        logger.warning("CRM creation failed (web): %s", e)

                return ChatResponse(
                    reply=reply,
                    classification=classification.to_dict(),
                    sources=sources,
                )

            except Exception as e:
                logger.error("Chat API error: %s", e, exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Internal server error: {str(e)}",
                ) from e

        @self.app.get("/stats", response_model=StatsResponse)
        async def stats(_key: str | None = Depends(_require_api_key)):
            """Get basic statistics."""
            try:
                s = await self.db.get_stats()
                return StatsResponse(**s)
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.app.get("/leads", response_model=list[LeadResponse])
        async def leads(
            _key: str | None = Depends(_require_api_key),
            limit: int = Query(10, ge=1, le=100),
            status: str | None = Query(None),
        ):
            """Get recent leads."""
            try:
                if status:
                    lead_list = await self.db.get_leads_by_status(status, limit)
                else:
                    lead_list = await self.db.get_all_leads(limit)

                return [
                    LeadResponse(
                        id=lead.id,
                        name=lead.name,
                        phone=lead.phone,
                        service=lead.service,
                        status=lead.status,
                        created_at=lead.created_at.isoformat() if lead.created_at else "",
                    )
                    for lead in lead_list
                ]
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e)) from e

        @self.app.post("/reindex")
        async def reindex(_key: str | None = Depends(_require_api_key)):
            """Force re-index RAG documents."""
            try:
                await self.rag.initialize(force_reload=True)
                return {"status": "ok", "message": "RAG index rebuilt"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e)) from e
