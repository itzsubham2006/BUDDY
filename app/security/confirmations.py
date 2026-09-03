"""
Confirmation flow for sensitive tool calls.

The orchestrator uses this to pause execution, describe what it is about
to do in plain language, and wait for an explicit "yes" from the user
before a HIGH or CRITICAL tool actually runs.

This module is intentionally transport-agnostic: it doesn't know whether
confirmation comes from speech, a typed reply, or a UI button. The caller
supplies an `ask_fn` callback that returns the user's raw response text.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

logger = logging.getLogger("jarvis.security.confirmations")

# Multi-word phrases are matched as substrings; single tokens are matched
# as whole words only (via _WORD_PATTERN) to avoid false positives like
# the letter "y" matching inside "maybe".
AFFIRMATIVE_PHRASES = {"do it", "go ahead"}
AFFIRMATIVE_WORDS = {"yes", "y", "yeah", "yep", "yup", "sure", "confirm", "confirmed", "affirmative"}
NEGATIVE_PHRASES = {"do not"}
NEGATIVE_WORDS = {"no", "n", "nope", "cancel", "stop", "don't", "negative"}


@dataclass
class ConfirmationRequest:
    tool_name: str
    summary: str
    arguments: dict


@dataclass
class ConfirmationResult:
    confirmed: bool
    raw_response: Optional[str] = None


AskFn = Callable[[str], Awaitable[str]]


class ConfirmationManager:
    """Handles asking the user to confirm a sensitive action."""

    def __init__(self, ask_fn: AskFn) -> None:
        """
        Parameters
        ----------
        ask_fn:
            Async callable that takes a prompt string, presents it to the
            user (via TTS + STT, or text UI), and returns their raw
            response text.
        """
        self._ask_fn = ask_fn

    async def request_confirmation(self, request: ConfirmationRequest) -> ConfirmationResult:
        prompt = f"{request.summary} Should I proceed?"
        logger.info("Requesting confirmation for tool=%s", request.tool_name)
        response = await self._ask_fn(prompt)
        confirmed = self._interpret(response)
        logger.info(
            "Confirmation for tool=%s -> %s", request.tool_name, "YES" if confirmed else "NO"
        )
        return ConfirmationResult(confirmed=confirmed, raw_response=response)

    @staticmethod
    def _interpret(response: str) -> bool:
        normalized = (response or "").strip().lower()
        if not normalized:
            return False

        words = set(re.findall(r"[a-z']+", normalized))

        if any(phrase in normalized for phrase in NEGATIVE_PHRASES):
            return False
        if words & NEGATIVE_WORDS:
            return False
        if any(phrase in normalized for phrase in AFFIRMATIVE_PHRASES):
            return True
        if words & AFFIRMATIVE_WORDS:
            return True
        # Default to NOT confirmed on ambiguous input — safety first.
        return False
