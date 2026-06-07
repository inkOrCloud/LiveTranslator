# Qwen ASR 句子级 Final 触发机制设计

## 概述

当前 Qwen ASR Realtime 服务仅在收到服务端 `conversation.item.input_audio_transcription.completed` 事件时触发 `final` 回调。但该事件在 VAD 判定一个完整语音片段结束后才触发——若说话人句间停顿较短（小于 `silence_duration_ms` 阈值，当前为 400ms），一段 VAD 片段可能包含多句话，导致用户需等待整段说完才能看到逐句翻译。

本设计利用 Qwen ASR `conversation.item.input_audio_transcription.text` 事件中的 **`text` 字段已确认前缀语义**，在 `text` 每出现一个完整的句子时即提前触发 `final`，实现更低的翻译延迟。

## 改动范围

- **仅修改** `live_translator/services/qwen_asr.py` 中的 `_QwenASRSession` 类
- 不涉及 `asr.py` 协议层、`PipelineScheduler`、OpenAI Realtime 服务或其他模块
- 对外接口不变：`on_final` 回调签名和行为语义保持不变（只是触发时机更早、粒度更细）

## 设计

### 新增状态

`_QwenASRSession` 增加一个实例变量：

```python
self._emitted_text: str = ""
```

记录当前 VAD 片段中已通过 `final` 回调发射的文本前缀。每轮 VAD 开始时为空，处理后逐步推进。

### 句尾标点模式

```python
_SENTENCE_END_RE = re.compile(r'(?<=[。！？.!?\n])')
```

支持中英文句尾标点，`\n` 覆盖换行分隔的语音片段。

### _process_text_event

每次收到 `conversation.item.input_audio_transcription.text` 时执行以下步骤：

1. 拼接 `text + stash` 并照常调用 `_on_partial_cb`（UI 实时显示不变）
2. 截取 `text` 中超出 `_emitted_text` 的新增部分 `delta`
3. 用 `_SENTENCE_END_RE.split(delta)` 将 `delta` 按句尾标点分割
4. 遍历分割结果，对每个以句尾标点结尾的片段调用 `_on_final_cb(sentence)`
5. 将 `_emitted_text` 推进到最后一个已发射的完整句子结尾位置

伪代码：

```python
def _handle_text_event(self, data: dict) -> None:
    text = data.get("text", "")
    stash = data.get("stash", "")
    combined = f"{text}{stash}"

    # 1. Partial 回调（照常）
    if combined and self._on_partial_cb:
        self._on_partial_cb(combined)

    # 2. 计算新增部分
    if not text:
        return
    if not text.startswith(self._emitted_text):
        # text 回退了——不安全的中间状态，跳过本轮，重置
        self._emitted_text = ""
        return
    if len(text) <= len(self._emitted_text):
        return  # 无新内容

    delta = text[len(self._emitted_text):]  # 新增部分

    # 3. 拆完整句子
    parts = _SENTENCE_END_RE.split(delta)
    complete = parts[:-1]  # 最后一个片段可能不完整
    last = parts[-1] if parts else ""

    # 如果最后一个片段本身以句尾标点结尾，也是完整句子
    if last and _SENTENCE_END_RE.search(last):
        complete = parts  # 全部是完整句子
        self._emitted_text = text
    elif complete:
        # 推进到最后一个完整句子之后
        emitted_len = 0
        for s in complete:
            emitted_len += len(s)
        self._emitted_text = text[:len(self._emitted_text) + emitted_len]
    else:
        return  # 没有完整句子

    # 4. 发射 final
    for sentence in complete:
        stripped = sentence.strip()
        if stripped and self._on_final_cb:
            self._on_final_cb(stripped)
```

### _process_completed_event

收到 `conversation.item.input_audio_transcription.completed` 时：

1. 取 `transcript` 中超出 `_emitted_text` 的剩余文本
2. 如有剩余，调用 `_on_final_cb(remaining)`
3. 重置 `_emitted_text = ""`（下一轮 VAD 重新开始）

伪代码：

```python
def _handle_completed_event(self, data: dict) -> None:
    transcript = data.get("transcript", "")
    if not transcript:
        self._emitted_text = ""
        return

    # 取已发射文本后的剩余部分
    if transcript.startswith(self._emitted_text) and len(transcript) > len(self._emitted_text):
        remaining = transcript[len(self._emitted_text):]
    elif transcript == self._emitted_text:
        remaining = ""  # 已全部通过 text 事件发射，无剩余
    else:
        # transcript 与 _emitted_text 不匹配——异常情况，回退到发射完整文本
        remaining = transcript

    if remaining.strip() and self._on_final_cb:
        self._on_final_cb(remaining.strip())

    self._emitted_text = ""
```

### 修改后的 _handle_messages

```python
def _handle_messages(self) -> None:
    ...
    if msg_type == "conversation.item.input_audio_transcription.completed":
        self._handle_completed_event(data)

    elif msg_type == "conversation.item.input_audio_transcription.text":
        self._handle_text_event(data)

    elif msg_type == "input_audio_buffer.speech_started":
        # 新 VAD 片段开始，重置历史（安全兜底，completed 也会重置）
        self._emitted_text = ""
        ...
```

## 边界情况

| 场景 | 行为 |
|---|---|
| `text` 不以 `_emitted_text` 为前缀（ASR 重评分导致回退） | 跳过本轮，重置 `_emitted_text = ""` |
| `.text` 连续多次收到完全相同的内容 | `delta` 为空，直接返回，无操作 |
| `.text` 的 `text` 为空 | 跳过，不发射任何内容 |
| `transcript` 与 `_emitted_text` 不匹配 | `_handle_completed_event` 回退到发射完整 `transcript` |
| 单句话很长且不含句尾标点（如念一个 URL） | 不会触发句子级 final，等到 `.completed` 才发射 |
| stash 中包含完成句子 | stash 不参与句子分割，静待下一轮 `.text` 中 `text` 推进后处理 |

## 测试

在已有的 `tests/test_services/test_qwen_asr.py` 中添加：

- `.text` 事件单个完整句子 → 触发一次 `final`
- `.text` 事件多个完整句子 → 对每个句子分别触发 `final`
- `.text` 事件部分句子（不含句尾标点） → 不触发 `final`
- `.text` 事件之后 `.completed` 触发 → 发射剩余文本，重置 `_emitted_text`
- `text` 前缀回退 → 跳过本轮，不发射非法内容
- 空 `text` 或空 `transcript` → 无操作
- `.speech_started` 后重新开始的 VAD 片段 → `_emitted_text` 正确重置
