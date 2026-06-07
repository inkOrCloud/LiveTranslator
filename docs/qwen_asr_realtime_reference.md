# Qwen-ASR-Realtime API 参考手册

> 整理自阿里云百炼官方文档，聚焦 WebSocket 直连方式（低级别API）的交互方法。
> 
> 模型：`qwen3-asr-flash-realtime`（及其他 ASR 模型）
> 
> 官方文档：
> - [交互流程](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-interaction-process)
> - [客户端事件](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-client-events)
> - [服务端事件](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-server-events)
> - [Python SDK](https://help.aliyun.com/zh/model-studio/qwen-asr-realtime-python-sdk)

---

## 目录

1. [服务端点和请求头](#1-服务端点和请求头)
2. [交互模式](#2-交互模式)
3. [客户端事件（Client Events）](#3-客户端事件client-events)
4. [服务端事件（Server Events）](#4-服务端事件server-events)
5. [WebSocket 直连交互流程](#5-websocket-直连交互流程)
6. [Python SDK 使用](#6-python-sdk-使用)
7. [关键要点与注意事项](#7-关键要点与注意事项)

---

## 1. 服务端点和请求头

### WebSocket URL

**华北2（北京）**
```
wss://dashscope.aliyuncs.com/api-ws/v1/realtime?model=<model_name>
```

**新加坡**
```
wss://{WorkspaceId}.ap-southeast-1.maas.aliyuncs.com/api-ws/v1/realtime?model=<model_name>
```

> ⚠️ **重要**：
> - URL 必须使用 `wss://` 协议
> - 模型通过 URL 查询参数 `model` 指定（如 `qwen3-asr-flash-realtime`）
> - 新加坡旧版域名 `wss://dashscope-intl.aliyuncs.com` 即将下线
> - Authorization 在**请求头**中设置（WebSocket 握手阶段验证）

### 请求头

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `Authorization` | string | **是** | 格式为 `Bearer <your_api_key>` |
| `user-agent` | string | 否 | 客户端标识 |
| `X-DashScope-WorkSpace` | string | 否 | 百炼业务空间ID |
| `X-DashScope-DataInspection` | string | 否 | 数据合规检测，默认不传或 `enable`，非必要勿启用 |

> ⚠️ 如果 API Key 无效或缺失，握手失败返回 HTTP 401/403。

---

## 2. 交互模式

支持 **VAD 模式**（默认）和 **Manual 模式**。

### VAD 模式（默认）

- **服务端自动**检测语音起点和终点（断句）
- 开发者只需持续发送音频流
- 服务端检测到一句话结束时自动返回最终结果
- 适用于：实时对话、会议记录
- **启用方式**：`session.update` 事件中的 `session.turn_detection` 设为有效配置（非 null）

### Manual 模式

- **客户端控制**断句
- 发送完整一句话的音频后，发 `input_audio_buffer.commit` 通知服务端
- 适用于：聊天软件发送语音、客户端能明确判断语句边界的场景
- **启用方式**：`session.update` 事件中的 `session.turn_detection` 设为 `null`

---

## 3. 客户端事件（Client Events）

客户端通过 WebSocket 发送 JSON 消息到服务端。

### 3.1 `session.update`

更新会话配置，建议连接建立后**首先发送**。若不发送则使用默认配置。

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 固定为 `"session.update"` |
| `event_id` | string | 是 | 事件ID |
| `session` | object | 是 | 会话配置对象 |
| `session.input_audio_format` | string | 否 | 音频格式：`pcm`（默认）或 `opus` |
| `session.sample_rate` | int | 否 | 采样率：`16000`（默认）或 `8000` |
| `session.input_audio_transcription` | object | 否 | 语音识别配置 |
| `session.input_audio_transcription.language` | string | 否 | 音频语言（见下方语言列表） |
| `session.turn_detection` | object | 否 | VAD 配置。设为 `null` 则启用 Manual 模式 |
| `session.turn_detection.type` | string | 依赖 | 固定为 `"server_vad"` |
| `session.turn_detection.threshold` | float | 否 | VAD检测阈值，推荐 `0.0`，默认 `0.2`，范围 [-1, 1] |
| `session.turn_detection.silence_duration_ms` | int | 否 | VAD断句阈值(ms)，推荐 `400`，默认 `800`，范围 [200, 6000] |

**支持的语言**：`zh`（中文/普通话/四川话/闽南语/吴语）、`yue`（粤语）、`en`、`ja`、`de`、`ko`、`ru`、`fr`、`pt`、`ar`、`it`、`es`、`hi`、`id`、`th`、`tr`、`uk`、`vi`、`cs`、`da`、`fil`、`fi`、`is`、`ms`、`no`、`pl`、`sv`

**VAD 阈值说明**：
- 较低的 threshold（如接近 -1）→ 灵敏度高，可能误判背景噪音为语音
- 较高的 threshold（如接近 1）→ 灵敏度低，嘈杂环境减少误触发
- 较低的 silence_duration_ms（如 300ms）→ 响应更快，但可能在自然停顿处不合理断句
- 较高的 silence_duration_ms（如 1200ms）→ 更好处理长句停顿，但增加延迟

**示例**：
```json
{
  "event_id": "event_123",
  "type": "session.update",
  "session": {
    "input_audio_format": "pcm",
    "sample_rate": 16000,
    "input_audio_transcription": {
      "language": "zh"
    },
    "turn_detection": {
      "type": "server_vad",
      "threshold": 0.0,
      "silence_duration_ms": 400
    }
  }
}
```

### 3.2 `input_audio_buffer.append`

将音频数据块追加到服务端的输入缓冲区。**核心事件**。

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 固定为 `"input_audio_buffer.append"` |
| `event_id` | string | 是 | 事件ID |
| `audio` | string | 是 | **Base64编码**的音频数据 |

> ⚠️ **服务端不会对此事件发送任何确认响应**（无 acknowledge）
>
> VAD 模式：服务端自动决定何时提交
> Manual 模式：单事件 audio 最大 15 MiB，建议小块流式发送

**示例**：
```json
{
  "event_id": "event_2728",
  "type": "input_audio_buffer.append",
  "audio": "<audio_base64>"
}
```

### 3.3 `input_audio_buffer.commit`

Manual 模式下，通知服务端已发送完一段完整语音，触发识别。

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 固定为 `"input_audio_buffer.commit"` |
| `event_id` | string | 是 | 事件ID |

> ⚠️ VAD 模式下**禁用**此事件

**示例**：
```json
{
  "event_id": "event_789",
  "type": "input_audio_buffer.commit"
}
```

### 3.4 `session.finish`

结束当前会话。客户端发送后，服务端完成最后识别并返回 `session.finished`。

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `type` | string | 是 | 固定为 `"session.finish"` |
| `event_id` | string | 是 | 事件ID |

**服务端响应流程**：
- **已检测到语音**：完成最后识别 → 发送 `conversation.item.input_audio_transcription.completed` → 发送 `session.finished`
- **未检测到语音**：直接发送 `session.finished`

> 客户端监听到 `session.finished` 后，**需主动断开连接**

**示例**：
```json
{
  "event_id": "event_341",
  "type": "session.finish"
}
```

---

## 4. 服务端事件（Server Events）

服务端通过 WebSocket 发送 JSON 消息到客户端。

### 4.1 `error`

| 参数 | 说明 |
|------|------|
| `type` | `"error"` |
| `error.type` | 错误类型，如 `"invalid_request_error"` |
| `error.code` | 错误代码，如 `"invalid_value"` |
| `error.message` | 具体报错信息 |
| `error.param` | 相关参数 |
| `error.event_id` | 关联的客户端事件ID |

**示例**：
```json
{
  "event_id": "event_B2uoU7VOt1AAITsPRPH9n",
  "type": "error",
  "error": {
    "type": "invalid_request_error",
    "code": "invalid_value",
    "message": "Invalid value: 'whisper-1xx'. Supported values are: 'whisper-1'.",
    "param": "session.input_audio_transcription.model",
    "event_id": "event_123"
  }
}
```

### 4.2 `session.created`

连接成功后的**第一个事件**，包含默认配置信息。

| 参数 | 说明 |
|------|------|
| `session.id` | WebSocket 会话ID |
| `session.model` | 当前模型名称 |
| `session.modalities` | 输出模态，固定 `["text"]` |
| `session.input_audio_format` | 输入音频格式 |
| `session.input_audio_transcription` | 语音识别配置 |
| `session.turn_detection` | VAD 配置 |

**示例**：
```json
{
  "event_id": "event_1234",
  "type": "session.created",
  "session": {
    "id": "sess_001",
    "object": "realtime.session",
    "model": "qwen3-asr-flash-realtime",
    "modalities": ["text"],
    "input_audio_format": "pcm16",
    "input_audio_transcription": null,
    "turn_detection": {
      "type": "server_vad",
      "threshold": 0.5,
      "silence_duration_ms": 200
    }
  }
}
```

### 4.3 `session.updated`

`session.update` 成功后服务端返回的确认。

### 4.4 `input_audio_buffer.speech_started`

**仅 VAD 模式**。检测到语音开始时发送。

| 参数 | 说明 |
|------|------|
| `audio_start_ms` | 从会话开始到检测到语音的毫秒数 |
| `item_id` | 将创建的用户消息项ID |

> ⚠️ 若客户端未收到此事件就直接发送 `session.finish`，服务端会直接返回 `session.finished`，不会有识别结果。

**示例**：
```json
{
  "event_id": "event_B1lV7FPbgTv9qGxPI1tH4",
  "type": "input_audio_buffer.speech_started",
  "audio_start_ms": 64,
  "item_id": "item_B1lV7jWLscp4mMV8hSs8c"
}
```

### 4.5 `input_audio_buffer.speech_stopped`

**仅 VAD 模式**。检测到语音结束时发送。
触发后，服务端将紧接着发送 `conversation.item.created`。

| 参数 | 说明 |
|------|------|
| `audio_end_ms` | 从会话开始到语音停止的毫秒数 |
| `item_id` | 语音停止时将创建的用户消息项ID |

**示例**：
```json
{
  "event_id": "event_B3GGEYh2orwNIdhUagZPz",
  "type": "input_audio_buffer.speech_stopped",
  "audio_end_ms": 28128,
  "item_id": "item_B3GGE8ry4yqbqJGzrVhEM"
}
```

### 4.6 `input_audio_buffer.committed`

VAD 模式：客户端完成音频发送后触发
Manual 模式：客户端发送 `input_audio_buffer.commit` 后触发

| 参数 | 说明 |
|------|------|
| `previous_item_id` | 前一个对话项ID |
| `item_id` | 将创建的用户对话项ID |

### 4.7 `conversation.item.created`

对话项（item）创建时发送。包含完整消息元信息。

### 4.8 `conversation.item.input_audio_transcription.text` ⭐

**高频发送**，用于展示**实时识别结果**。这是实时显示的核心事件。

| 参数 | 说明 |
|------|------|
| `item_id` | 关联的对话项ID |
| `language` | 被识别音频的语种 |
| `emotion` | 情感：`surprised`/`neutral`/`happy`/`sad`/`disgusted`/`angry`/`fearful` |
| `text` | ✅ **已确认的文本前缀**（不会再变更的部分） |
| `stash` | 🔄 **预识别的文本后缀**（临时草稿，可能被修正） |

> **关键理解**：实时预览 = `text` + `stash`
> - `text`：模型已确认不再变更的部分
> - `stash`：仍在处理、可能被修正的临时结果

**示例**（假设用户说"今天天气不错，阳光明媚"）：

| 时间 | 用户说话 | text | stash | UI显示(text+stash) |
|------|---------|------|-------|-------------------|
| T1 | "今天……" | "" | "今天" | 今天 |
| T2 | "……天气……" | "" | "今天天气" | 今天天气 |
| T3 | "……不错" | "今天" | "天气不错" | 今天天气不错 |
| T4 | (短暂停顿) | "今天天气不错，" | "" | 今天天气不错， |
| T5 | "……阳光……" | "今天天气不错，" | "阳光" | 今天天气不错，阳光 |
| T6 | "……明媚。" | "今天天气不错，" | "阳光明媚。" | 今天天气不错，阳光明媚 |
| T7 | 结束 | → 用 `completed` 的 `transcript` 作为最终结果 | | |

**示例 JSON**：
```json
{
  "event_id": "event_R7Pfu8QVBfP5HmpcbEFSd",
  "type": "conversation.item.input_audio_transcription.text",
  "item_id": "item_MpJQPNQzqVRc9aC9zMwSj",
  "content_index": 0,
  "language": "zh",
  "emotion": "neutral",
  "text": "",
  "stash": "北京的"
}
```

### 4.9 `conversation.item.input_audio_transcription.completed` ⭐

**最终识别结果**。标志一个对话项（item）的结束。

| 参数 | 说明 |
|------|------|
| `item_id` | 关联的对话项ID |
| `language` | 语种 |
| `emotion` | 情感 |
| `transcript` | ✅ **完整识别结果** |

**示例**：
```json
{
  "event_id": "event_B3GGEjPT2sLzjBM74W6kB",
  "type": "conversation.item.input_audio_transcription.completed",
  "item_id": "item_B3GGC53jGOuIFcjZkmEQ9",
  "content_index": 0,
  "language": "zh",
  "emotion": "neutral",
  "transcript": "今天天气怎么样"
}
```

### 4.10 `conversation.item.input_audio_transcription.failed`

输入了音频但识别失败时发送。与 `error` 事件分开，便于客户端关联具体项目。

### 4.11 `session.finished`

会话结束事件。只有客户端发送 `session.finish` 后才会发送。
客户端收到后可**主动断开连接**。

**示例**：
```json
{
  "event_id": "event_2239",
  "type": "session.finished"
}
```

---

## 5. WebSocket 直连交互流程

### VAD 模式（默认）

```
客户端 (Client)                         服务端 (Server)
  │                                          │
  │  1. WebSocket connect (wss://...)        │
  │  Headers: Authorization: Bearer <key>    │
  │────────────────────────────────────────>│
  │                                          │
  │                                          │  2. session.created
  │<────────────────────────────────────────│
  │                                          │
  │  3. session.update                       │
  │  (配置语言、VAD参数等)                     │
  │────────────────────────────────────────>│
  │                                          │
  │                                          │  4. session.updated
  │<────────────────────────────────────────│
  │                                          │
  │  5. input_audio_buffer.append (持续)     │
  │  (Base64音频块，流式发送)                  │
  │────────────────────────────────────────>│
  │                                          │
  │            [服务端检测到语音开始]          │
  │                                          │  6. input_audio_buffer.speech_started
  │<────────────────────────────────────────│
  │                                          │
  │  7. input_audio_buffer.append (继续)     │
  │────────────────────────────────────────>│
  │                                          │
  │            [服务端检测到语音结束]          │
  │                                          │  8. input_audio_buffer.speech_stopped
  │<────────────────────────────────────────│
  │                                          │  9. input_audio_buffer.committed
  │<────────────────────────────────────────│
  │                                          │  10. conversation.item.created
  │<────────────────────────────────────────│
  │                                          │  11. conversation.item.input_audio_transcription.text
  │<────────────────────────────────────────│  (高频发送，text + stash 实时结果)
  │                                          │  12. conversation.item.input_audio_transcription.completed
  │<────────────────────────────────────────│  (最终结果)
  │                                          │
  │  13. session.finish                      │
  │────────────────────────────────────────>│
  │                                          │
  │                                          │  14. session.finished
  │<────────────────────────────────────────│
  │                                          │
  │  15. 客户端主动断开连接                    │
  │────────────────────────────────────────>│
```

### Manual 模式

```
客户端 (Client)                         服务端 (Server)
  │                                          │
  │  1. WebSocket connect                    │
  │────────────────────────────────────────>│
  │                                          │  2. session.created
  │<────────────────────────────────────────│
  │                                          │
  │  3. session.update                       │
  │  (turn_detection: null)                  │
  │────────────────────────────────────────>│
  │                                          │  4. session.updated
  │<────────────────────────────────────────│
  │                                          │
  │  5. input_audio_buffer.append (完整语句) │
  │────────────────────────────────────────>│
  │                                          │
  │  6. input_audio_buffer.commit            │
  │────────────────────────────────────────>│
  │                                          │  7. input_audio_buffer.committed
  │<────────────────────────────────────────│
  │                                          │  8. conversation.item.input_audio_transcription.text
  │<────────────────────────────────────────│
  │                                          │  9. conversation.item.input_audio_transcription.completed
  │<────────────────────────────────────────│
  │                                          │
  │  10. session.finish                      │
  │────────────────────────────────────────>│
  │                                          │  11. session.finished
  │<────────────────────────────────────────│
```

---

## 6. Python SDK 使用

使用 DashScope SDK（版本 >= 1.25.6），封装了底层 WebSocket 细节，通过回调模式处理事件。

### 安装
```bash
pip install dashscope>=1.25.6
```

### 核心类

| 类 | 导入路径 |
|----|---------|
| `OmniRealtimeConversation` | `from dashscope.audio.qwen_omni import OmniRealtimeConversation` |
| `OmniRealtimeCallback` | `from dashscope.audio.qwen_omni import OmniRealtimeCallback` |
| `TranscriptionParams` | `from dashscope.audio.qwen_omni import TranscriptionParams` |
| `MultiModality` | `from dashscope.audio.qwen_omni import MultiModality` |
| `AudioFormat` | `from dashscope.audio.qwen_omni import AudioFormat` |

### SDK 构造参数

**`OmniRealtimeConversation(...)` 构造参数**：

| 参数 | 类型 | 必须 | 说明 |
|------|------|------|------|
| `model` | str | **是** | 模型名称，如 `"qwen3-asr-flash-realtime"` |
| `callback` | OmniRealtimeCallback | **是** | 事件回调实例 |
| `url` | str | **是** | 服务地址（含地域） |

### `update_session()` 方法

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `output_modalities` | List[MultiModality] | - | 固定 `[MultiModality.TEXT]` |
| `enable_turn_detection` | bool | `True` | VAD 开关；`False` = Manual 模式 |
| `turn_detection_type` | str | `"server_vad"` | 固定值 |
| `turn_detection_threshold` | float | `0.2` | VAD 阈值，推荐 `0.0` |
| `turn_detection_silence_duration_ms` | int | `800` | 断句阈值(ms)，推荐 `400` |
| `transcription_params` | TranscriptionParams | - | 识别配置（语言、采样率等） |
| `enable_input_audio_transcription` | bool | `True` | 是否启用语音识别 |

### `TranscriptionParams` 参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `language` | str | - | 语言代码，如 `"zh"` |
| `sample_rate` | int | `16000` | 采样率，支持 `16000` 或 `8000` |
| `input_audio_format` | str | `"pcm"` | 音频格式，`"pcm"` 或 `"opus"` |

### SDK 关键方法

| 方法 | 对应服务端事件 | 说明 |
|------|---------------|------|
| `connect()` | `session.created` / `session.updated` | 建立 WebSocket 连接 |
| `update_session(...)` | `session.updated` | 更新会话配置（连接后先调用） |
| `append_audio(audio_b64)` | 无 | 发送 Base64 音频数据 |
| `commit()` | `input_audio_buffer.committed` | Manual 模式：提交音频 |
| `end_session(timeout=20)` | `session.finished` | 结束会话（VAD：发送完音频后；Manual：commit后） |
| `close()` | 无 | 终止任务并关闭连接 |
| `get_session_id()` | - | 获取当前 session_id |
| `get_last_response_id()` | - | 获取最近 response_id |

### 回调接口（OmniRealtimeCallback）

| 方法 | 参数 | 说明 |
|------|------|------|
| `on_open()` | 无 | WebSocket 连接成功建立时触发 |
| `on_event(message)` | message: dict | 收到服务端事件时触发（核心回调） |
| `on_close(code, msg)` | code, msg | 连接关闭时触发 |

### 完整示例

```python
from dashscope.audio.qwen_omni import (
    OmniRealtimeConversation,
    OmniRealtimeCallback,
    TranscriptionParams,
    MultiModality,
)

class MyCallback(OmniRealtimeCallback):
    def __init__(self, conversation):
        self.conversation = conversation
        self.handlers = {
            'session.created': self._handle_session_created,
            'conversation.item.input_audio_transcription.completed': self._handle_final_text,
            'conversation.item.input_audio_transcription.text': self._handle_stash_text,
            'input_audio_buffer.speech_started': lambda r: print('======Speech Start======'),
            'input_audio_buffer.speech_stopped': lambda r: print('======Speech Stop======'),
        }

    def on_open(self):
        print('Connection opened')

    def on_close(self, code, msg):
        print(f'Connection closed, code: {code}, msg: {msg}')

    def on_event(self, response):
        try:
            handler = self.handlers.get(response['type'])
            if handler:
                handler(response)
        except Exception as e:
            print(f'[Error] {e}')

    def _handle_session_created(self, response):
        print(f"Start session: {response['session']['id']}")

    def _handle_final_text(self, response):
        print(f"Final: {response['transcript']}")

    def _handle_stash_text(self, response):
        text = response.get('text', '')
        stash = response.get('stash', '')
        print(f"实时: {text}{stash}")

conversation = OmniRealtimeConversation(
    model='qwen3-asr-flash-realtime',
    url='wss://dashscope.aliyuncs.com/api-ws/v1/realtime',
    callback=MyCallback(conversation=None)  # 暂时传None
)
conversation.callback.conversation = conversation

# 配置会话
transcription_params = TranscriptionParams(
    language='zh',
    sample_rate=16000,
    input_audio_format='pcm'
)
conversation.update_session(
    output_modalities=[MultiModality.TEXT],
    enable_turn_detection=True,
    turn_detection_type='server_vad',
    turn_detection_threshold=0.0,
    turn_detection_silence_duration_ms=400,
    enable_input_audio_transcription=True,
    transcription_params=transcription_params
)

# 发送音频
import base64
with open('audio.pcm', 'rb') as f:
    audio_data = f.read()
    audio_b64 = base64.b64encode(audio_data).decode('utf-8')
    conversation.append_audio(audio_b64)

# 结束会话
conversation.end_session()
```

---

## 7. 关键要点与注意事项

### 协议要点
1. **wss:// 必须**：不支持 ws://
2. **Authorization 在握手阶段验证**，不是消息体里
3. **模型名在 URL 参数中指定**，如 `?model=qwen3-asr-flash-realtime`
4. **音频数据必须 Base64 编码**后发送

### 事件生命周期
- `input_audio_buffer.append` -> **无确认响应**，只管发送
- `input_audio_buffer.speech_started` -> 若未收到就发 `session.finish`，直接结束无结果
- `conversation.item.input_audio_transcription.text` -> **高频**，实时显示用 `text + stash`
- `conversation.item.input_audio_transcription.completed` -> **最终结果**，用 `transcript` 字段
- `session.finished` -> 客户端收到后**必须主动断开连接**

### VAD vs Manual 选择
| 场景 | 推荐模式 |
|------|---------|
| 实时对话、会议记录 | VAD（默认） |
| 用户按住说话、聊天语音 | Manual |
| 需要精确控制断句 | Manual |
| 不想处理 VAD 调参 | VAD |

### VAD 参数推荐
| 场景 | threshold | silence_duration_ms |
|------|-----------|---------------------|
| 通用推荐 | 0.0 | 400 |
| 快速响应（短句） | 0.0 | 300 |
| 长句/停顿多 | 0.0 | 1200 |
| 嘈杂环境 | 0.5 | 800 |

### 音频格式
- **PCM**：16-bit, 16kHz (或 8kHz)，单声道，小端序
- **OPUS**：也支持
- `input_audio_buffer.append` 单次最大 **15 MiB**（Manual 模式）

### 情感识别
服务端返回的 `emotion` 字段支持：`surprised`、`neutral`、`happy`、`sad`、`disgusted`、`angry`、`fearful`
