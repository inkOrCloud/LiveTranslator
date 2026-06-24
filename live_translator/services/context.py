"""Translation context manager for preserving conversation history.

Provides the 4-layer context structure for enhanced translation:

1. Prompt layer — system instructions (configured via system_prompt)
2. Background overview/compression layer — condensed summary of older conversation
3. Historical text layer — recent transcription → translation pairs
4. Current text layer — the text currently being translated

When the estimated token count exceeds ``max_context_tokens``, the background
and history layers are combined and compressed into a new background layer,
and the history layer is cleared.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class HistoryItem:
    """A single transcription-translation pair recorded in the session."""

    original: str
    translated: str
    timestamp: float = field(default_factory=time.time)


class TranslationContext:
    """Manages the 4-layer translation context structure.

    The context is built from:
    - **Background** — a compressed summary of older conversation history
    - **History** — a list of recent ``(original, translated)`` pairs
    - **Current text** — the text currently being translated

    When the total estimated token count exceeds ``max_context_tokens``,
    :meth:`needs_compression` returns ``True``. Callers should then invoke
    :meth:`build_compression_messages` to obtain messages for the LLM, store
    the compressed result via :attr:`background`, and call :meth:`clear_history`.

    Token estimation uses a simple heuristic (``ceil(len / 2)``) and does
    **not** require a model-specific tokenizer.
    """

    # Estimated token overhead per history item for labels and separators
    _LABEL_OVERHEAD_TOKENS = 7

    # General formatting overhead across all layers
    _FORMAT_OVERHEAD_TOKENS = 100

    def __init__(self, max_context_tokens: int = 4000) -> None:
        """Initialize an empty context.

        Args:
            max_context_tokens: Token threshold that triggers compression.
        """
        self._background: str = ""
        self._history: list[HistoryItem] = []
        self._max_context_tokens = max_context_tokens

    # ── Properties ──────────────────────────────────────────────

    @property
    def background(self) -> str:
        """Current compressed background summary (layer 2)."""
        return self._background

    @background.setter
    def background(self, value: str) -> None:
        self._background = value

    @property
    def history(self) -> list[HistoryItem]:
        """Read-only view of recent history items (layer 3)."""
        return list(self._history)

    @property
    def max_context_tokens(self) -> int:
        """Token threshold before compression is triggered."""
        return self._max_context_tokens

    @max_context_tokens.setter
    def max_context_tokens(self, value: int) -> None:
        self._max_context_tokens = value

    @property
    def item_count(self) -> int:
        """Number of history items currently stored."""
        return len(self._history)

    # ── Core operations ─────────────────────────────────────────

    def add_pair(self, original: str, translated: str) -> None:
        """Record a transcription-translation pair in the history layer.

        Args:
            original: Source text (transcription).
            translated: Translated text.
        """
        self._history.append(HistoryItem(original=original, translated=translated))
        logger.debug(
            "Context history appended: original=%s -> translated=%s",
            original[:60],
            translated[:60],
        )

    def clear_history(self) -> None:
        """Clear the history layer, typically after compression."""
        self._history.clear()
        logger.debug("Context history cleared")

    # ── Token estimation ────────────────────────────────────────

    @staticmethod
    def estimated_tokens(text: str) -> int:
        """Rough token estimate for mixed Chinese/English text.

        Uses ceiling division by 2: 1 token ≈ 2 characters. This is
        intentionally imprecise; exact tokenization would require a
        model-specific tokenizer. An empty string returns 0.

        Args:
            text: The text to estimate.

        Returns:
            Estimated token count (0 for empty input).
        """
        return (len(text) + 1) // 2

    def total_estimated_tokens(
        self,
        system_prompt: str = "",
        current_text: str = "",
    ) -> int:
        """Estimate total tokens across all layers plus formatting overhead.

        Args:
            system_prompt: The system prompt text (layer 1).
            current_text: The current text to translate (layer 4).

        Returns:
            Estimated total token count.
        """
        prompt_tokens = self.estimated_tokens(system_prompt)
        bg_tokens = self.estimated_tokens(self._background)

        history_tokens = sum(
            self.estimated_tokens(item.original)
            + self.estimated_tokens(item.translated)
            + self._LABEL_OVERHEAD_TOKENS
            for item in self._history
        )

        current_tokens = self.estimated_tokens(current_text)
        total = (
            prompt_tokens
            + bg_tokens
            + history_tokens
            + current_tokens
            + self._FORMAT_OVERHEAD_TOKENS
        )

        logger.debug(
            "Token estimate: prompt=%d, bg=%d, history=%d, current=%d, "
            "overhead=%d, total=%d/%d",
            prompt_tokens,
            bg_tokens,
            history_tokens,
            current_tokens,
            self._FORMAT_OVERHEAD_TOKENS,
            total,
            self._max_context_tokens,
        )
        return total

    def needs_compression(
        self,
        system_prompt: str = "",
        current_text: str = "",
    ) -> bool:
        """Check whether the context exceeds the token threshold.

        Args:
            system_prompt: The system prompt text (layer 1).
            current_text: The current text to translate (layer 4).

        Returns:
            ``True`` if compression should be performed.
        """
        return (
            self.total_estimated_tokens(system_prompt, current_text)
            > self._max_context_tokens
        )

    # ── Message building ────────────────────────────────────────

    def build_context_block(self, current_text: str) -> str:
        """Build the context block string (layers 2-4) for prompt injection.

        The returned string has three sections:
        - Background overview (if non-empty)
        - Recent conversation history (if any)
        - Current text to translate

        Args:
            current_text: The text currently being translated.

        Returns:
            A formatted multi-line string combining layers 2-4.
        """
        parts: list[str] = []

        if self._background:
            parts.append("[背景概述 / Conversation Background]")
            parts.append(self._background)
            parts.append("")

        if self._history:
            parts.append("[最近对话历史 / Recent Conversation History]")
            for item in self._history:
                parts.append(f"  原文: {item.original}")
                parts.append(f"  译文: {item.translated}")
                parts.append("  ---")
            parts.append("")

        parts.append("[当前待翻译文本 / Current Text to Translate]")
        parts.append(current_text)

        return "\n".join(parts).strip()

    def build_compression_messages(self) -> list[dict[str, str]]:
        """Build messages for the LLM compression step.

        These messages ask the model to produce a concise summary of the
        current background + history, preserving key topics, terminology,
        and conversational tone.

        Returns:
            A list of ``{"role": …, "content": …}`` dicts suitable for
            ``litellm.completion()``.
        """
        content_parts: list[str] = [
            "以下是一次实时翻译会话中已处理的历史记录，请将它们压缩为简洁的背景概述（中文）。",
            "",
            "要求：",
            "- 保留关键话题、术语、语气等上下文信息",
            "- 使后续翻译能结合已有上下文",
            "- 只输出压缩后的概述，不要额外说明",
            "- 概述应保持可读性和连贯性",
            "",
        ]

        if self._background:
            content_parts.append("=== 已有背景概述 ===")
            content_parts.append(self._background)
            content_parts.append("")

        if self._history:
            content_parts.append("=== 待压缩的历史翻译记录 ===")
            for item in self._history:
                content_parts.append(f"原文: {item.original}")
                content_parts.append(f"译文: {item.translated}")
                content_parts.append("---")

        return [
            {
                "role": "system",
                "content": (
                    "你是一个对话上下文压缩助手。请将实时翻译会话中的历史记录"
                    "压缩为简洁的背景概述，保留核心上下文信息。"
                ),
            },
            {
                "role": "user",
                "content": "\n".join(content_parts),
            },
        ]

    def reset(self) -> None:
        """Reset the entire context (background + history)."""
        self._background = ""
        self._history.clear()
        logger.debug("TranslationContext reset")
