"""Tests for TranslationContext."""

from __future__ import annotations

from live_translator.services.context import HistoryItem, TranslationContext


def test_default_state() -> None:
    """A new context should have empty background and history."""
    ctx = TranslationContext()
    assert ctx.background == ""
    assert ctx.history == []
    assert ctx.item_count == 0
    assert ctx.max_context_tokens == 4000


def test_add_pair() -> None:
    """add_pair() should append a HistoryItem."""
    ctx = TranslationContext()
    ctx.add_pair("Hello", "你好")
    assert ctx.item_count == 1
    item = ctx.history[0]
    assert item.original == "Hello"
    assert item.translated == "你好"
    assert isinstance(item.timestamp, float)


def test_history_is_read_only() -> None:
    """The history property should return a copy."""
    ctx = TranslationContext()
    ctx.add_pair("Hello", "你好")
    hist = ctx.history
    hist.append(HistoryItem("x", "y"))
    # Original should be unaffected
    assert ctx.item_count == 1


def test_clear_history() -> None:
    """clear_history() should remove all history items."""
    ctx = TranslationContext()
    ctx.add_pair("Hello", "你好")
    ctx.add_pair("World", "世界")
    assert ctx.item_count == 2
    ctx.clear_history()
    assert ctx.item_count == 0


def test_background_property() -> None:
    """Setting and getting background."""
    ctx = TranslationContext()
    assert ctx.background == ""
    ctx.background = "A discussion about programming"
    assert ctx.background == "A discussion about programming"


def test_estimated_tokens() -> None:
    """estimated_tokens uses ceiling division by 2."""
    ctx = TranslationContext()
    assert ctx.estimated_tokens("") == 0
    assert ctx.estimated_tokens("a") == 1          # (1+1)//2 = 1
    assert ctx.estimated_tokens("Hello") == 3       # (5+1)//2 = 3
    assert ctx.estimated_tokens("你好世界") == 2    # (4+1)//2 = 2


def test_total_estimated_tokens_empty() -> None:
    """Total tokens for an empty context should be just the overhead (100)."""
    ctx = TranslationContext()
    total = ctx.total_estimated_tokens()
    assert total == 100  # FORMAT_OVERHEAD_TOKENS


def test_total_estimated_tokens_with_content() -> None:
    """Total tokens should include all layers."""
    ctx = TranslationContext()
    ctx.add_pair("Hello", "你好")
    total = ctx.total_estimated_tokens(
        system_prompt="Translate",
        current_text="World",
    )
    # prompt: (9+1)//2 = 5
    # bg: 0
    # history: (5+1)//2 + (2+1)//2 + 7 = 3+1+7 = 11
    # current: (5+1)//2 = 3
    # overhead: 100
    # total: 5 + 0 + 11 + 3 + 100 = 119
    assert total == 119


def test_needs_compression_false_when_empty() -> None:
    """needs_compression should be False for an empty context."""
    ctx = TranslationContext(max_context_tokens=100)
    # empty: 0+0+0+0+100 = 100, 100 > 100 = False
    assert ctx.needs_compression() is False


def test_needs_compression_true_when_exceeded() -> None:
    """needs_compression should be True when token estimate exceeds max."""
    ctx = TranslationContext(max_context_tokens=50)
    ctx.add_pair("A" * 200, "B" * 200)
    # history: 100+100+7 = 207, total = 0+0+207+0+100 = 307
    assert ctx.needs_compression() is True


def test_needs_compression_with_current_text() -> None:
    """needs_compression should account for current text."""
    ctx = TranslationContext(max_context_tokens=110)
    # Without current_text: 0+0+0+0+100 = 100 → False (100 <= 110)
    assert ctx.needs_compression() is False
    # With 21-char text: (21+1)//2 = 11 → total = 111 → True
    assert ctx.needs_compression(current_text="A" * 21) is True


def test_build_context_block_empty() -> None:
    """With no background or history, block should contain only the current text."""
    ctx = TranslationContext()
    block = ctx.build_context_block("Hello")
    assert "[当前待翻译文本 / Current Text to Translate]" in block
    assert "Hello" in block
    assert "[背景概述" not in block
    assert "[最近对话历史" not in block


def test_build_context_block_with_background() -> None:
    """With background set, block should include background section."""
    ctx = TranslationContext()
    ctx.background = "Previous topics"
    block = ctx.build_context_block("Hello")
    assert "[背景概述 / Conversation Background]" in block
    assert "Previous topics" in block
    assert "[当前待翻译文本" in block


def test_build_context_block_with_history() -> None:
    """With history, block should include history section."""
    ctx = TranslationContext()
    ctx.add_pair("Good morning", "早上好")
    block = ctx.build_context_block("How are you")
    assert "[最近对话历史 / Recent Conversation History]" in block
    assert "Good morning" in block
    assert "早上好" in block
    assert "[当前待翻译文本" in block
    assert "How are you" in block


def test_build_context_block_all_layers() -> None:
    """Block should include all layers when background and history are present."""
    ctx = TranslationContext()
    ctx.background = "Discussion about weather"
    ctx.add_pair("It's cold", "天气冷")
    block = ctx.build_context_block("Is it going to snow?")
    assert "[背景概述" in block
    assert "[最近对话历史" in block
    assert "[当前待翻译文本" in block
    assert "Discussion about weather" in block
    assert "It's cold" in block
    assert "天气冷" in block
    assert "Is it going to snow?" in block


def test_build_compression_messages_structure() -> None:
    """Compression messages should have system and user roles."""
    ctx = TranslationContext()
    ctx.add_pair("Hello", "你好")
    messages = ctx.build_compression_messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "压缩" in messages[1]["content"] or "压缩" in messages[0]["content"]


def test_build_compression_messages_with_background() -> None:
    """Compression messages should include existing background."""
    ctx = TranslationContext()
    ctx.background = "Previous context"
    ctx.add_pair("Hello", "你好")
    messages = ctx.build_compression_messages()
    assert "Previous context" in messages[1]["content"]
    assert "Hello" in messages[1]["content"]


def test_reset() -> None:
    """reset() should clear both background and history."""
    ctx = TranslationContext()
    ctx.background = "Some background"
    ctx.add_pair("Hello", "你好")
    ctx.reset()
    assert ctx.background == ""
    assert ctx.item_count == 0


def test_max_context_tokens_setter() -> None:
    """max_context_tokens should be settable."""
    ctx = TranslationContext(max_context_tokens=2000)
    assert ctx.max_context_tokens == 2000
    ctx.max_context_tokens = 5000
    assert ctx.max_context_tokens == 5000
