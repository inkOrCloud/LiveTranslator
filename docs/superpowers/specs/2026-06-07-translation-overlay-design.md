# Translation Overlay Window Design

## Overview

Replace the existing `SubtitleWindow` (single-sentence floating overlay) with a new `TranslationOverlayWindow` that displays a scrollable translation history (top 2/3) and real-time ASR partial content (bottom 1/3) in a 1:2 aspect ratio floating window.

## Motivation

The current subtitle window shows only the latest sentence pair and has no history, making it impossible to review past translations during a conversation. The new overlay provides full translation history context while keeping real-time ASR feedback visible.

## Architecture

### Window

`TranslationOverlayWindow` — a frameless, always-on-top, translucent, draggable overlay built with standard Qt Widgets.

- Window flags: `FramelessWindowHint | WindowStaysOnTopHint | Tool`
- Attributes: `WA_TranslucentBackground`, `WA_ShowWithoutActivating`
- Keep-alive timer (2s) re-raises window to maintain always-on-top
- Fixed 1:2 aspect ratio enforced via `resizeEvent`
- Drag via `mousePressEvent` / `mouseMoveEvent` / `mouseReleaseEvent`
- Background drawn via `paintEvent` (semi-transparent black rounded rect)
- Internal layout: `QVBoxLayout` with zero margins, all padding handled by child widgets

### Internal Layout

```
TranslationOverlayWindow (QWidget, 1:2 ratio, e.g. 300×600)
├── QVBoxLayout (margin: 0, spacing: 0)
│
│   ├── [QScrollArea] ─── Translation history (stretch=2)
│   │   ├── Frame: no border, transparent background
│   │   ├── Inner QWidget + QVBoxLayout
│   │   │   ├── HistoryItem (original + translated)
│   │   │   ├── HistoryItem
│   │   │   └── ...
│   │   ├── Auto-scroll to bottom on new entry
│   │   └── Soft cap: 500 entries, oldest dropped
│   │
│   ├── [QSplitter / QFrame] ─── 1px divider line
│   │
│   └── [PartialWidget] ─── Real-time partial (stretch=1)
│       ├── "实时转写" label (color: #666, 9px)
│       ├── Partial text label (color: #8bc34a, 11px)
│       └── Styled with green left border + dark green background
```

### Components

**HistoryItem** (QFrame)
- Left border (2px) — dim gray for past items, cyan (#4fc3f7) for the latest
- Original text label (color: #aaa, 11px)
- Translated text label (color: #ddd, 11px)
- Padding: 8px horizontal, 4px vertical
- Rounded background: rgba(24, 24, 24, 0.9)

**PartialWidget** (QFrame)
- Left border (3px solid #4caf50)
- Background: rgba(13, 40, 24, 0.85)
- "实时转写" label (9px, #666)
- Partial text label (11px, #8bc34a)
- Translated partial label (hidden initially, for future use)

### Data Flow

```
Pipeline ASR partial
    → app._on_partial(text)
        → overlay.show_partial(text)           # updates partial area

Pipeline ASR final + translation
    → app._on_translation(original, translated)
        → overlay.add_history(original, translated)  # appends to history
        → overlay.show_partial("")                   # clears partial area
```

### Public API

```python
class TranslationOverlayWindow(QWidget):
    def add_history(self, original: str, translated: str) -> None: ...
    def show_partial(self, text: str) -> None: ...
    def clear(self) -> None: ...
```

### Styling

QSS applied via `setStyleSheet` for internal widgets:
- Transparent scroll area background
- Thin dark scrollbar (6px, #555 handle)
- All label colors via palette or inline style

Background drawn in `paintEvent` for rounded translucent effect (QSS can't do rounded translucent window backgrounds reliably).

### XWayland Compatibility

Keep the existing `ensure_xwayland_for_kde()` helper — it remains unchanged. The new window uses the same window flags pattern as `SubtitleWindow`.

## Files Changed

| File | Action |
|---|---|
| `live_translator/gui/translation_overlay.py` | **New** — TranslationOverlayWindow |
| `live_translator/gui/subtitle_window.py` | **Delete** — replaced entirely |
| `live_translator/gui/app.py` | **Modify** — wire new overlay, update callbacks |
| `tests/test_gui/test_translation_overlay.py` | **New** — tests for new window |
| `tests/test_gui/test_subtitle_window.py` | **Delete** — old tests removed |
| `tests/test_gui/conftest.py` | Maybe modify — add fixture if needed |

## Testing

- Window creation and flags
- `add_history` appends items, auto-scrolls to bottom
- `add_history` drops oldest entries beyond 500 cap
- `show_partial` updates displayed text
- `clear` clears history and partial text, hides window
- Drag behavior (mouse event simulation)
- 1:2 aspect ratio enforced on resize
- Empty state renders gracefully
- Long text wraps correctly inside history items
