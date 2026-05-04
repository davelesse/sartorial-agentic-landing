"""
═══════════════════════════════════════════════════════════
SARTORIAL AGENTIC — Agent Engine
Base class + LLM integration (Claude API).
═══════════════════════════════════════════════════════════
"""

import asyncio
import json
import re
import time
from abc import ABC, abstractmethod
from typing import Any

import structlog
from anthropic import AsyncAnthropic, RateLimitError, APIConnectionError, APITimeoutError, APIStatusError

from app.core.config import settings

logger = structlog.get_logger()


# Claude model selection — balance quality vs cost
CLAUDE_MODEL_POWERFUL = "claude-opus-4-5"            # Complex reasoning, multi-step workflows
CLAUDE_MODEL_BALANCED = "claude-sonnet-4-6"          # Default — most agent tasks
CLAUDE_MODEL_FAST     = "claude-haiku-4-5-20251001"  # Simple tasks, high volume

# Pricing en millicents par million de tokens (input/output)
# Stocké en millicents pour éviter la perte de précision avec int()
MODEL_PRICING = {
    CLAUDE_MODEL_POWERFUL: {"input": 1_500_000, "output": 7_500_000},
    CLAUDE_MODEL_BALANCED: {"input":   300_000, "output": 1_500_000},
    CLAUDE_MODEL_FAST:     {"input":    80_000, "output":   400_000},
}

_RETRY_DELAYS = (1.0, 2.0, 4.0)  # backoff exponentiel en secondes


class AgentExecutionResult:
    """Standardized output from every agent execution."""

    def __init__(
        self,
        success: bool,
        output: dict[str, Any] | None = None,
        error: str | None = None,
        tokens_used: int = 0,
        cost_cents: int = 0,
        duration_ms: int = 0,
    ):
        self.success = success
        self.output = output or {}
        self.error = error
        self.tokens_used = tokens_used
        self.cost_cents = cost_cents
        self.duration_ms = duration_ms

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "tokens_used": self.tokens_used,
            "cost_cents": self.cost_cents,
            "duration_ms": self.duration_ms,
        }


class BaseAgent(ABC):
    """
    Abstract base class for all Sartorial Agentic agents.
    Subclasses must implement `run()`.
    """

    slug: str = "base"
    name: str = "Base Agent"
    default_model: str = CLAUDE_MODEL_BALANCED

    def __init__(self, tenant_id: str, config: dict | None = None):
        self.tenant_id = tenant_id
        self.config = config or {}
        self.client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self._total_tokens = 0
        self._total_cost_millicents = 0  # millicents pour éviter la perte de précision

    @property
    def _total_cost_cents(self) -> int:
        return self._total_cost_millicents // 1000

    async def execute(self, input_data: dict) -> AgentExecutionResult:
        """Main entry point — wraps run() with timing & error handling."""
        start = time.time()
        logger.info(
            "agent.execution.start",
            agent=self.slug,
            tenant=self.tenant_id,
            input_keys=list(input_data.keys()),
        )

        try:
            output = await self.run(input_data)
            duration_ms = int((time.time() - start) * 1000)

            logger.info(
                "agent.execution.success",
                agent=self.slug,
                duration_ms=duration_ms,
                tokens=self._total_tokens,
                cost_cents=self._total_cost_cents,
            )

            return AgentExecutionResult(
                success=True,
                output=output,
                tokens_used=self._total_tokens,
                cost_cents=self._total_cost_cents,
                duration_ms=duration_ms,
            )
        except Exception as e:
            duration_ms = int((time.time() - start) * 1000)
            logger.exception(
                "agent.execution.failed",
                agent=self.slug,
                error=str(e),
                duration_ms=duration_ms,
            )
            return AgentExecutionResult(
                success=False,
                error=str(e),
                tokens_used=self._total_tokens,
                cost_cents=self._total_cost_cents,
                duration_ms=duration_ms,
            )

    def _parse_json(self, text: str) -> dict:
        """
        Parse la réponse JSON de Claude en gérant les blocs markdown.
        Robuste face aux ```json ... ``` que Claude ajoute parfois.
        """
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text.strip())
        cleaned = re.sub(r"\n?```\s*$", "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error(
                "agent.json_parse_failed",
                agent=self.slug,
                error=str(exc),
                raw_preview=cleaned[:200],
            )
            raise ValueError(f"Réponse Claude invalide (JSON malformé): {exc}") from exc

    @abstractmethod
    async def run(self, input_data: dict) -> dict:
        """
        Agent-specific logic. Subclasses implement this.
        Should return a dict output on success, raise on failure.
        """
        ...

    async def call_claude(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """
        Helper to call Claude API avec retry automatique et cost tracking.
        Retente jusqu'à 3 fois sur RateLimitError/APIConnectionError/APITimeoutError.
        """
        model = model or self.default_model

        messages = [{"role": "user", "content": prompt}]
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        last_exc: Exception | None = None
        for attempt, delay in enumerate(_RETRY_DELAYS):
            try:
                response = await self.client.messages.create(**kwargs)
                break
            except RateLimitError as exc:
                last_exc = exc
                logger.warning(
                    "claude.rate_limit",
                    agent=self.slug,
                    attempt=attempt + 1,
                    retry_in=delay,
                )
                await asyncio.sleep(delay)
            except (APIConnectionError, APITimeoutError) as exc:
                last_exc = exc
                logger.warning(
                    "claude.connection_error",
                    agent=self.slug,
                    attempt=attempt + 1,
                    error=str(exc),
                )
                await asyncio.sleep(delay)
            except APIStatusError as exc:
                # Erreurs 5xx → retry ; erreurs 4xx (sauf 429) → non-retryable
                if exc.status_code >= 500:
                    last_exc = exc
                    logger.warning("claude.server_error", status=exc.status_code, attempt=attempt + 1)
                    await asyncio.sleep(delay)
                else:
                    raise
        else:
            raise last_exc  # type: ignore[misc]

        # Track tokens & cost en millicents pour précision maximale
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        self._total_tokens += input_tokens + output_tokens

        pricing = MODEL_PRICING.get(model, MODEL_PRICING[CLAUDE_MODEL_BALANCED])
        cost_millicents = (
            input_tokens * pricing["input"] + output_tokens * pricing["output"]
        ) // 1_000_000
        self._total_cost_millicents += cost_millicents

        text_parts = [block.text for block in response.content if hasattr(block, "text")]
        return "".join(text_parts)
