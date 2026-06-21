# Qwen ASR 句子级 Final 触发机制 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Qwen ASR `conversation.item.input_audio_transcription.text` 事件中检测到完整句子时提前触发 `final` 回调，避免等待 VAD 整段结束。

**Architecture:** 在 `_QwenASRSession` 内维护 `_emitted_text` 前缀追踪器。`.text` 事件到达时，从 `text` 中截取相对于 `_emitted_text` 的新增部分，按句尾标点拆分，每个完整句子立即调用 `_on_final_cb`。`.completed` 事件到达时，发射剩余文本并重置状态。

**Tech Stack:** Python 3.12+, re (standard library), pytest

---

### Task 1: 添加 `_SENTENCE_END_RE` 和 `_emitted_text` 状态

**Files:**
- Modify: `live_translator/services/qwen_asr.py`

- [ ] **Step 1: 在文件顶部添加 re 导入和编译的正则**

在 `live_translator/services/qwen_asr.py` 开头（现有 `import json, logging` 之后），添加：

```python
import re
```

在 `logger` 定义之后添加：

```python
# 匹配中英文句尾标点，用于句子级 final 检测
_SENTENCE_END_RE = re.compile(r'(?<=[。！？.!?\n])')
```

- [ ] **Step 2: 在 `__init__` 中添加 `_emitted_text` 状态**

在 `_QwenASRSession.__init__` 中 `self._connected = False` 之后添加：

```python
self._emitted_text: str = ""
```

- [ ] **Step 3: 提交**

```bash
git add live_translator/services/qwen_asr.py
git commit -m "feat: add sentence end regex and emitted text tracker for Qwen ASR"
```

---

### Task 2: 实现 `_handle_text_event` 方法

**Files:**
- Modify: `live_translator/services/qwen_asr.py`

- [ ] **Step 1: 添加 `_handle_text_event` 方法**

在 `_QwenASRSession` 中找到 `.text` 事件的当前处理代码（约 133-137 行），将其替换为独立方法。在现有 `_handle_messages` 方法之前添加：

```python
def _handle_text_event(self, data: dict) -> None:
    """Handle conversation.item.input_audio_transcription.text event.

    Emits partial (text+stash) for UI display, and extracts complete
    sentences from the confirmed ``text`` prefix to emit early ``final``
    callbacks without waiting for the VAD segment to end.
    """
    text = data.get("text", "")
    stash = data.get("stash", "")
    combined = f"{text}{stash}"

    # 1. Always emit partial for live display
    if combined and self._on_partial_cb:
        self._on_partial_cb(combined)

    # 2. Validate text state
    if not text:
        return
    if not text.startswith(self._emitted_text):
        # ASR rescored — text prefix regressed, skip this round
        logger.debug("Text prefix regression: emitted=%r text=%r", self._emitted_text, text)
        self._emitted_text = ""
        return
    if len(text) <= len(self._emitted_text):
        return  # No new confirmed content

    # 3. Extract delta (newly confirmed prefix beyond what was emitted)
    delta = text[len(self._emitted_text):]

    # 4. Split delta into sentence candidates
    parts = _SENTENCE_END_RE.split(delta)
    # parts = ["句子1。", "句子2？", "剩余尾巴"]  (split keeps delimiter attached to left)
    # last element may be incomplete (no sentence-ending punctuation yet)
    complete = parts[:-1]  # All except the last fragment are complete sentences
    last = parts[-1] if parts else ""

    if last and _SENTENCE_END_RE.search(last):
        # The last fragment itself ends with punctuation -> also complete
        complete = parts
        self._emitted_text = text
    elif complete:
        # Advance _emitted_text past the complete sentences
        emitted_len = 0
        for s in complete:
            emitted_len += len(s)
        self._emitted_text = text[:len(self._emitted_text) + emitted_len]
    else:
        return  # No complete sentence in this delta

    # 5. Emit final for each complete sentence
    for sentence in complete:
        stripped = sentence.strip()
        if stripped and self._on_final_cb:
            logger.debug(
                "Sentence-level final (%d chars): %s...",
                len(stripped), stripped[:60]
            )
            self._on_final_cb(stripped)
```

- [ ] **Step 2: 提交**

```bash
git add live_translator/services/qwen_asr.py
git commit -m "feat: implement _handle_text_event for sentence-level final triggers"
```

---

### Task 3: 实现 `_handle_completed_event` 方法

**Files:**
- Modify: `live_translator/services/qwen_asr.py`

- [ ] **Step 1: 添加 `_handle_completed_event` 方法**

在 `_handle_text_event` 方法之后添加：

```python
def _handle_completed_event(self, data: dict) -> None:
    """Handle conversation.item.input_audio_transcription.completed event.

    Emits any remaining text that was not yet dispatched via sentence-level
    finals, then resets ``_emitted_text`` for the next VAD segment.
    """
    transcript = data.get("transcript", "")
    if not transcript:
        self._emitted_text = ""
        return

    # Extract remaining text beyond what was already emitted as sentence finals
    if transcript.startswith(self._emitted_text) and len(transcript) > len(self._emitted_text):
        remaining = transcript[len(self._emitted_text):]
    elif transcript == self._emitted_text:
        remaining = ""  # All text already emitted via sentence-level finals
    else:
        # transcript doesn't match _emitted_text — fallback to full transcript
        logger.debug(
            "Transcript mismatch in completed event: emitted=%r transcript=%r",
            self._emitted_text, transcript,
        )
        remaining = transcript

    if remaining.strip() and self._on_final_cb:
        logger.debug(
            "Completed-event final (%d chars): %s...",
            len(remaining), remaining[:60]
        )
        self._on_final_cb(remaining.strip())

    self._emitted_text = ""
```

- [ ] **Step 2: 提交**

```bash
git add live_translator/services/qwen_asr.py
git commit -m "feat: implement _handle_completed_event for remaining text emission"
```

---

### Task 4: 将新方法接入 `_handle_messages`

**Files:**
- Modify: `live_translator/services/qwen_asr.py`

- [ ] **Step 1: 修改 `_handle_messages` 中的事件路由**

将 `_handle_messages` 中现有的 `if` 分支替换为对新方法的调用：

```python
def _handle_messages(self) -> None:
    """Non-blocking read of incoming WebSocket messages."""
    if not self._ws or not self._connected:
        return
    try:
        message = self._ws.recv(timeout=0.001)
        data = json.loads(message)
        msg_type = data.get("type", "")

        if msg_type == "conversation.item.input_audio_transcription.completed":
            self._handle_completed_event(data)

        elif msg_type == "conversation.item.input_audio_transcription.text":
            self._handle_text_event(data)

        elif msg_type == "error":
            error_msg = data.get("error", {}).get("message", "Unknown error")
            logger.error("Qwen ASR server error: %s", error_msg)
            if self._on_error_cb:
                self._on_error_cb(RuntimeError(error_msg))

        elif msg_type in ("session.created", "session.updated"):
            logger.info(
                "Qwen ASR session %s: %s",
                msg_type, data.get("session", {}).get("id", ""),
            )

        elif msg_type in (
            "input_audio_buffer.speech_started",
            "input_audio_buffer.speech_stopped",
        ):
            # Reset emitted text on new VAD segment for safety
            if msg_type == "input_audio_buffer.speech_started":
                self._emitted_text = ""
            logger.debug("Qwen ASR speech boundary: %s", msg_type)

        elif msg_type == "session.finished":
            self._connected = False
            logger.info("Qwen ASR session finished")

    except TimeoutError:
        pass
    except ConnectionClosedError:
        logger.warning("Qwen ASR connection closed")
        self._connected = False
        self._ws = None
    except Exception as exc:
        logger.exception("Qwen ASR poll error")
        if self._on_error_cb:
            self._on_error_cb(exc)
```

- [ ] **Step 2: 提交**

```bash
git add live_translator/services/qwen_asr.py
git commit -m "feat: route completed/text events through new handlers in _handle_messages"
```

---

### Task 5: 编写句子级 final 测试

**Files:**
- Modify: `tests/test_services/test_qwen_asr.py`

- [ ] **Step 1: 添加 `_handle_text_event` 单个完整句子的测试**

```python
def test_qwen_asr_text_event_single_sentence() -> None:
    """Single complete sentence in text event should trigger one on_final."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    final_results: list[str] = []
    partial_results: list[str] = []
    session.on_final(final_results.append)
    session.on_partial(partial_results.append)

    session._handle_text_event({
        "type": "conversation.item.input_audio_transcription.text",
        "text": "今天天气真好。",
        "stash": "",
    })

    assert partial_results == ["今天天气真好。"]
    assert final_results == ["今天天气真好。"]
    assert session._emitted_text == "今天天气真好。"


def test_qwen_asr_text_event_multiple_sentences() -> None:
    """Multiple complete sentences in text event should trigger one on_final per sentence."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    final_results: list[str] = []
    session.on_final(final_results.append)
    session.on_partial(lambda _: None)

    session._handle_text_event({
        "type": "conversation.item.input_audio_transcription.text",
        "text": "今天天气真好。你吃饭了吗？",
        "stash": "",
    })

    assert final_results == ["今天天气真好。", "你吃饭了吗？"]
    assert session._emitted_text == "今天天气真好。你吃饭了吗？"


def test_qwen_asr_text_event_no_sentence_boundary() -> None:
    """Text without sentence-ending punctuation should not trigger on_final."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    final_results: list[str] = []
    session.on_final(final_results.append)
    session.on_partial(lambda _: None)

    session._handle_text_event({
        "type": "conversation.item.input_audio_transcription.text",
        "text": "今天天气",
        "stash": "真好",
    })

    # partial should include stash, but no final since no sentence boundary
    assert final_results == []
    assert session._emitted_text == ""


def test_qwen_asr_text_event_incremental_sentences() -> None:
    """Incremental text updates should only emit newly completed sentences."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    final_results: list[str] = []
    session.on_final(final_results.append)
    session.on_partial(lambda _: None)

    # First update: one sentence confirmed
    session._handle_text_event({
        "type": "conversation.item.input_audio_transcription.text",
        "text": "今天天气真好。",
        "stash": "",
    })
    assert final_results == ["今天天气真好。"]
    assert session._emitted_text == "今天天气真好。"

    # Second update: second sentence confirmed
    session._handle_text_event({
        "type": "conversation.item.input_audio_transcription.text",
        "text": "今天天气真好。你吃饭了吗？",
        "stash": "还剩",
    })
    assert final_results == ["今天天气真好。", "你吃饭了吗？"]
    assert session._emitted_text == "今天天气真好。你吃饭了吗？"


def test_qwen_asr_text_event_regression() -> None:
    """Text regression (prefix changed) should skip emission and reset state."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    session._emitted_text = "今天天气真好。"

    final_results: list[str] = []
    session.on_final(final_results.append)
    session.on_partial(lambda _: None)

    # New text regressed (different prefix)
    session._handle_text_event({
        "type": "conversation.item.input_audio_transcription.text",
        "text": "昨天天气不错。",
        "stash": "",
    })

    assert final_results == []  # No emission on regression
    assert session._emitted_text == ""  # Reset


def test_qwen_asr_text_event_duplicate() -> None:
    """Identical text repeated should not emit duplicate finals."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    session._emitted_text = "今天天气真好。"

    final_results: list[str] = []
    session.on_final(final_results.append)
    session.on_partial(lambda _: None)

    session._handle_text_event({
        "type": "conversation.item.input_audio_transcription.text",
        "text": "今天天气真好。",
        "stash": "你",
    })

    assert final_results == []  # No new text to emit
    assert session._emitted_text == "今天天气真好。"  # Unchanged
```

- [ ] **Step 2: 添加 `_handle_completed_event` 的测试**

```python
def test_qwen_asr_completed_event_remaining_text() -> None:
    """Completed event should emit remaining text and reset state."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    session._emitted_text = "今天天气真好。"

    final_results: list[str] = []
    session.on_final(final_results.append)

    session._handle_completed_event({
        "type": "conversation.item.input_audio_transcription.completed",
        "transcript": "今天天气真好。你吃饭了吗？",
    })

    assert final_results == ["你吃饭了吗？"]
    assert session._emitted_text == ""  # Reset


def test_qwen_asr_completed_event_all_emitted() -> None:
    """Completed event when all text already emitted should not emit again."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    session._emitted_text = "今天天气真好。你吃饭了吗？"

    final_results: list[str] = []
    session.on_final(final_results.append)

    session._handle_completed_event({
        "type": "conversation.item.input_audio_transcription.completed",
        "transcript": "今天天气真好。你吃饭了吗？",
    })

    assert final_results == []  # No duplicate
    assert session._emitted_text == ""  # Reset


def test_qwen_asr_completed_event_empty_transcript() -> None:
    """Empty transcript should just reset state without emitting."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    session._emitted_text = "something"

    final_results: list[str] = []
    session.on_final(final_results.append)

    session._handle_completed_event({
        "type": "conversation.item.input_audio_transcription.completed",
        "transcript": "",
    })

    assert final_results == []
    assert session._emitted_text == ""


def test_qwen_asr_completed_event_mismatch() -> None:
    """Completed with mismatched transcript should fallback to full transcript."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    session._emitted_text = "今天天气真好。"  # Different from what server returns

    final_results: list[str] = []
    session.on_final(final_results.append)

    session._handle_completed_event({
        "type": "conversation.item.input_audio_transcription.completed",
        "transcript": "昨天的天气",
    })

    assert final_results == ["昨天的天气"]  # Fallback to full transcript
    assert session._emitted_text == ""  # Reset


def test_qwen_asr_completed_event_blank_remaining() -> None:
    """Completed with blank remaining (only whitespace) should not emit."""
    service = QwenASRService({
        "api_key": "test-key",
        "model": "qwen3-asr-flash-realtime",
    })
    session = service.create_session()
    session._emitted_text = "hello"

    final_results: list[str] = []
    session.on_final(final_results.append)

    session._handle_completed_event({
        "type": "conversation.item.input_audio_transcription.completed",
        "transcript": "hello   ",
    })

    assert final_results == []  # Only whitespace
    assert session._emitted_text == ""
```

- [ ] **Step 3: 运行所有测试验证通过**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest tests/test_services/test_qwen_asr.py -v`
Expected: 所有测试 PASS

- [ ] **Step 4: 提交**

```bash
git add tests/test_services/test_qwen_asr.py live_translator/services/qwen_asr.py
git commit -m "test: add sentence-level final trigger tests for Qwen ASR"
```

---

### Task 6: 运行完整测试套件

- [ ] **Step 1: 运行全部测试**

Run: `cd /home/ink/Desktop/develop/LiveTranslator && UV_CACHE_DIR=/tmp/uv-cache uv run pytest -v`
Expected: 全部测试 PASS，无回归

- [ ] **Step 2: 如有失败修复，如无则提交**

```bash
git add -A
git commit -m "chore: fix test regressions from sentence-level final changes"
```
