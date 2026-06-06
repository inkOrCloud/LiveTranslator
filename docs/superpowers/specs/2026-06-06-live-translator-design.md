# LiveTranslator 同声传译桌面应用 — 设计文档

> 创建日期: 2026-06-06
> 状态: 草稿

## 1. 概述

LiveTranslator 是一款 Linux 桌面同声传译应用。它监听系统扬声器输出，通过云端 AI 服务实时识别语音并翻译为目标语言，结果以悬浮字幕窗口或控制面板形式展示。

## 2. 总体架构（四层模型）

```
┌────────────────────────────────────────────┐
│                GUI 层                        │
│   ┌──────────────┐  ┌───────────────────┐  │
│   │ 悬浮字幕窗口   │  │  控制面板          │  │
│   │ (透明/置顶)   │  │  (配置/历史/日志)  │  │
│   └──────┬───────┘  └───────┬───────────┘  │
├──────────┼──────────────────┼──────────────┤
│    音频引擎层                │              │
│   ┌────────────────────┐   │              │
│   │ AudioCapture        │   │              │
│   │ (PulseAudio Monitor)│   │              │
│   │ → RingBuffer        │   │              │
│   │ → VAD 语音段分割    │   │              │
│   └────────┬───────────┘   │              │
├────────────┼────────────────┼──────────────┤
│      AI 引擎层              │              │
│   ┌────────────────┐  ┌───┴──────────┐   │
│   │ SpeechRecognizer│  │  Translator  │   │
│   │ (抽象接口)      │  │  (抽象接口)  │   │
│   │ [OpenAI Realtime│  │  [DeepL API] │   │
│   │  / Whisper API] │  │  [GPT API]   │   │
│   └────────┬───────┘  └───┬──────────┘   │
├────────────┼──────────────┼──────────────┤
│       Pipeline 调度器      │              │
│   ┌──────────────────────────────────┐   │
│   │  Audio → VAD → ASR → Translate  │   │
│   │  → emit("translation", result)  │   │
│   │  → 广播至所有窗口               │   │
│   └──────────────────────────────────┘   │
└──────────────────────────────────────────┘
```

### 设计原则

1. **依赖倒置**：AI 引擎通过抽象接口（Protocol）对接具体服务实现
2. **单一职责**：每层只做一件事，通过信号/事件通信
3. **可替换**：ASR 和翻译服务通过 JSON 配置动态装载，支持热切换
4. **可观测**：所有环节可日志、可监控、可调试

## 3. 服务接口抽象层 — 流式方案

### SpeechRecognizer（ASR 接口 — 流式）

```python
class ASRSession(Protocol):
    """一次流式语音识别会话。"""

    def send_audio(self, chunk: bytes) -> None:
        """持续送入音频流（PCM16, 16kHz, mono）。"""

    def on_partial(self, callback: Callable[[str], None]) -> None:
        """注册中间结果回调（进行中的内容，可能变化）。"""

    def on_final(self, callback: Callable[[str], None]) -> None:
        """注册最终结果回调（一句话确认完毕）。"""

    def on_error(self, callback: Callable[[Exception], None]) -> None:
        """注册错误回调。"""

    def close(self) -> None:
        """结束会话，释放连接。"""

    @property
    def is_alive(self) -> bool: ...


class SpeechRecognizer(Protocol):
    service_id: str
    display_name: str
    config: dict

    def create_session(self) -> ASRSession:
        """创建一个新的流式识别会话。"""

    @classmethod
    def config_schema(cls) -> dict: ...
```

### Translator（翻译接口）

```python
class Translator(Protocol):
    service_id: str
    display_name: str
    config: dict

    def translate(self, text: str, source_lang: str,
                  target_lang: str) -> str: ...
    def supported_languages(self) -> list[dict]: ...

    @classmethod
    def config_schema(cls) -> dict: ...

    # 可选：对 partial 结果做轻量翻译（如仅缓存避免重复请求）
    def translate_partial(self, text: str, source_lang: str,
                          target_lang: str) -> str | None: ...
```

### JSON Schema 驱动表单渲染

每个服务实现 `config_schema()` 返回 JSON Schema，GUI 据此自动生成配置表单：

| JSON Schema 字段 | 对应控件 |
|-----------------|---------|
| `type: string` + `format: password` | 密码输入框 |
| `type: string` + `enum: [...]` | 下拉选择框 |
| `type: number` | 数字输入框（带步进） |
| `type: integer` | 整数输入框 |
| `type: boolean` | 复选框 |
| `type: string` + `default:` | 普通文本输入框 |

### 初始实现的服务

| 类别 | 服务 | 说明 |
|------|------|------|
| ASR | `OpenAIRealtimeSession` | OpenAI Realtime API（WebSocket 流式，内置 VAD） |
| ASR | `OpenAIWhisperService` | OpenAI Whisper API（传统分批，备选） |
| Translator | `DeepLService` | DeepL API，高精度翻译 |
| Translator | `GPTTranslateService` | OpenAI GPT 翻译（备选） |

### 配置存储（JSON）

```json
{
  "services": {
    "asr": { "active": "openai_realtime", "providers": {...} },
    "translator": { "active": "deepl", "providers": {...} }
  },
  "audio": { "source": "monitor", "sample_rate": 16000 },
  "appearance": { "subtitle_size": 28, "opacity": 0.9 }
}
```

## 4. 音频采集层

### 核心组件

| 模块 | 职责 |
|------|------|
| `AudioSource` | 音频源抽象接口 |
| `SystemMonitor` | PulseAudio monitor source 实现（Linux） |
| `RingBuffer` | 线程安全环形缓冲区 |
| `VAD` | 语音活动检测（能量阈值法），分割语音段（仅分批方案需要） |
| `AudioProcessor` | 重采样 -> 16kHz mono PCM16 |

### 流式数据流

```
PulseAudio monitor callback
  -> 原始 PCM 数据写入 RingBuffer
  -> ASRSession.create_session()  [建立 WebSocket 连接]
  -> 持续推送裸音频流 send_audio(chunk)
  -> 远端 API 内置 VAD 自动断句，触发 on_final 回调
  -> 用户停止/切换语言时主动 close()
```

### 跨平台扩展

| 平台 | 实现 | 优先级 |
|------|------|--------|
| Linux | PulseAudio monitor source | P0 |
| Windows | WASAPI loopback | P2 |
| macOS | AudioUnit / BlackHole | P2 |

## 5. Pipeline 调度器

```
状态机: IDLE -> STREAMING -> (循环)
         ↓         ↓
       停止    ASR 流式会话中（远端 API 内置 VAD 和断句）
              on_partial -> UI 更新原文提示
              on_final   -> 触发翻译 -> 输出译文

- ASRSession 维持长连接语音识别
- partial 回调 -> 仅更新 UI 显示原文（"正在听..."），不翻译
- final 回调 -> 触发 Translator.translate() -> 输出确认译文到 UI
- 音频段按序处理，保证结果顺序
- 超时保护：单段超 N 秒则跳过 + 日志告警
- 支持暂停/恢复流水线
```

### 信号定义

```python
pipeline.partial_ready = Signal(str)      # 中间原文（UI 提示）
pipeline.translation_ready = Signal(str, str)  # 原文, 译文
pipeline.status_changed = Signal(PipelineStatus)
pipeline.error_occurred = Signal(str)
```

## 6. GUI 层

### 窗口体系

```
QApplication
├── SubtitleWindow (悬浮字幕)
│   - 无边框 | 置顶 | 鼠标穿透 | 全屏底部
│   - 半透明黑底 + 白字
│   - 原文/译文双行配对
│   - 显示最近 1-3 句，新内容推入
│   - partial 结果在原文行显示"..."后缀
│
├── MainWindow (控制面板)
│   - 启动/暂停/停止控制
│   - 模式切换（字幕/面板/双模式）
│   - 服务配置（动态表单渲染）
│   - 翻译历史列表（最近 200 条）
│   - 导出 .srt / .txt
│   - 日志查看器
│
└── QSystemTrayIcon
    - 后台最小化
    - 右键菜单：显示/隐藏/退出
```

### 悬浮窗口实现

```python
# PySide6 关键要点
window = QWidget()
window.setWindowFlags(
    Qt.FramelessWindowHint |
    Qt.WindowStaysOnTopHint |
    Qt.Tool  # 不在任务栏显示
)
window.setAttribute(Qt.WA_TransparentForMouseEvents)
window.setAttribute(Qt.WA_TranslucentBackground)

# 背景绘制：圆角半透明矩形
# 文字渲染：QPainter + 抗锯齿
```

## 7. 项目目录结构

```
live-translator/
├── main.py                      # 应用入口
├── pyproject.toml               # 项目配置 + Ruff/MyPy 配置
├── .gitignore
├── README.md
│
├── live_translator/
│   ├── __init__.py
│   │
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── app.py               # QApplication 初始化
│   │   ├── subtitle_window.py    # 悬浮字幕窗口
│   │   ├── main_window.py        # 控制面板窗口
│   │   ├── config_form.py        # JSON Schema -> 动态表单
│   │   └── tray_icon.py          # 系统托盘
│   │
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── source.py             # AudioSource 抽象接口
│   │   ├── system_monitor.py     # PulseAudio 系统音频采集
│   │   ├── ring_buffer.py        # 环形缓冲区
│   │   └── vad.py                # 语音活动检测
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── asr.py                # SpeechRecognizer / ASRSession 协议
│   │   ├── translator.py         # Translator 协议
│   │   ├── openai_realtime.py    # OpenAI Realtime API 流式实现
│   │   ├── openai_whisper.py     # OpenAI Whisper API 分批实现（备选）
│   │   ├── deepl_translate.py    # DeepL API 实现
│   │   └── registry.py           # 服务注册/发现
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── scheduler.py          # Pipeline 调度器
│   │   └── events.py             # 信号/事件定义
│   │
│   └── config/
│       ├── __init__.py
│       ├── manager.py            # JSON 配置读写
│       └── schema.py             # 配置结构定义
│
└── tests/
    ├── __init__.py
    ├── test_services/
    ├── test_audio/
    └── test_pipeline/
```

## 8. 技术栈

| 层 | 技术 | 版本 |
|----|------|------|
| 语言 | Python | >=3.12 |
| GUI | PySide6 | >=6.8 |
| 音频 | sounddevice + numpy | 最新 |
| VAD | webrtcvad 或 能量阈值 | -- |
| ASR | OpenAI Realtime API（WebSocket 流式） | -- |
| 翻译 | DeepL API / OpenAI GPT API | -- |
| 配置 | JSON (标准库) | -- |
| 格式 | Ruff (lint+format) + MyPy strict | -- |

## 9. 非功能性需求

- **延迟**：从语音结束到译文显示，目标 < 2s（API 网络延迟为主要因素）
- **资源占用**：空闲时内存 < 100MB，运行时 < 200MB
- **容错**：网络超时自动重试（最多 3 次），API 失败不影响后续音频段
- **隐私**：音频数据仅缓存用于分段，处理完即丢弃；不上传用户本地文件
- **国际化和本地化**：配置界面支持中/英文

## 10. 后续扩展方向（非 P0）

- 本地 Whisper 模型（ggml/llama.cpp 等）
- 实时翻译结果保存为字幕文件（.srt/.ass）
- 截图翻译
- 多显示器支持（选择在哪块屏幕显示字幕）
- 自定义字体/背景/主题
- macOS / Windows 移植

---

*本文档为设计阶段产物，将在实现前根据实际情况调整。*
