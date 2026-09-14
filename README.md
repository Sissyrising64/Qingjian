# Qingjian (轻拣)

> A keyboard-first, local-first media sorter for quickly reviewing and organizing photos and videos on Windows.

[English](#qingjian-轻拣) · [中文](#中文说明)

## Overview

Qingjian helps you turn an unsorted media folder into an organized library with a fast review loop: preview one item, press a configured key, and continue to the next item. It supports images and videos, configurable destinations, safe file transactions, duplicate review, and a complete undo/recovery workflow.

Version **2.0.4** is the current tested build. The 2.0.4 maintenance release restores the tested 2.0.3 visual baseline and fixes the startup state of the Undo and “Restore previous step” actions.

## Highlights

- **Fast keyboard workflow** — bind `1`–`0` (or other supported keys) to move, copy, favorite, rename, review later, recycle, reveal, or tag media.
- **Image and video support** — preview common image formats, RAW files, MP4/MOV media, and video metadata in one queue.
- **Configurable destinations** — assign a key to a folder, path template, and filename template; nested folders are created as needed.
- **Collision protection** — when a destination name already exists, choose Replace or keep both with an automatic numbered suffix.
- **Undo and recovery** — operations are journaled before files move. `Ctrl+Z` undoes; `Ctrl+Y` restores the previous step. Both actions are disabled until a source folder is selected and an applicable history entry exists.
- **Sidecar-aware transactions** — matching RAW, XMP, AAE, and Live Photo video sidecars can travel with the primary file and are undone as one unit.
- **Duplicate review** — exact duplicates, perceptual near-duplicates, and burst groups; opening a duplicate previews the actual media, and Ignore records a per-source exclusion without moving or deleting files.
- **Ratings and labels** — rate items and apply color labels while reviewing.
- **Review queue and filters** — search, filter, sort, browse as a grid or single item, and postpone items for later review.
- **Local-first and privacy-conscious** — no account, server, or media upload is required. Diagnostics exclude media files.

## Download and run (Windows)

1. Download the latest `轻拣2.0.4-已测试版.zip` from the repository Releases page.
2. Extract the archive to a local folder.
3. Run `MediaSorter.exe`.
4. Select a source folder, configure the key bindings, and start reviewing.

The executable intentionally keeps the ASCII name `MediaSorter.exe`: some Windows native-window configurations have issues with non-ASCII executable names. The UI is still named **轻拣 / Qingjian**.

## Build from source

Requirements: Windows 10/11 and Python 3.12 or 3.13.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Build a standalone executable with PyInstaller:

```powershell
python -m PyInstaller --noconfirm --clean qingjian.spec
```

Run the built-in verification before distributing a build:

```powershell
python main.py --selfcheck
```

The self-check creates a temporary library, exercises core operations, drives the real Qt window offscreen, opens the dialogs, switches languages and views, performs classify/undo, and verifies that a fresh window has both Undo and Restore Previous Step disabled. It does not touch user media.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `1`–`0` | Run the configured binding |
| `Left` / `Right` | Previous / next item |
| `S` | Send to review queue |
| `G` | Toggle single/grid view |
| `F2` | Rename |
| `Delete` | Recycle |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Restore previous step |
| `Shift+1`–`5`, `Shift+0` | Rating / clear rating |
| `Alt+1`–`5`, `Alt+0` | Color label / clear label |
| `/`, `Ctrl+F` | Search destination folders |
| `Space`, `J`, `K`, `L`, `,`, `.` | Video playback and frame stepping |
| `Ctrl+D` | Duplicate review |
| `Ctrl+I` | Media information |
| `Ctrl+R` | Review queue |
| `F5` / `F11` / `Esc` | Rescan / fullscreen / leave fullscreen |

## Templates and file safety

Each binding can define a destination and filename template. Supported values include dates, the original name and extension, source folder, camera/lens/ISO, rating, label, and a sequence number. For example:

```text
Destination: D:\Photos\Keepers\{YYYY}\{YYYY-MM}
Filename:    {YYYY-MM-DD}_{seq:4}_{name}
```

The transaction store provides:

- a durable journal written before file changes;
- pre-operation identity checks to avoid overwriting externally changed files;
- atomic same-volume moves where possible;
- bounded recovery snapshots and cleanup policies;
- reversible recycle-bin operations.

If the application is interrupted, use the startup recovery action before continuing. Do not delete journal or snapshot files manually.

## Data location

By default, application data is stored under:

```text
%APPDATA%\LocalMediaTools\Qingjian\
    settings.json
    state\state.db
    store\
    cache\hashes.db
    logs\
```

For a portable setup, create an empty `qingjian-portable` directory next to the executable, or pass `--data-dir <path>`.

## Project structure

```text
qingjian/
  core/       Qt-free scanning, metadata, templates, transactions, state, and duplicates
  ui/         PySide6 application, preview, dialogs, bindings, and duplicate review
tests/        unit and integrity tests
main.py       application and self-check entry point
qingjian.spec PyInstaller recipe
```

The core layer does not import Qt. The UI calls the engine layer instead of manipulating filesystem operations directly.

## AI-assisted development disclosure

This project was developed with human direction, review, and testing, with assistance from multiple AI tools:

- **OpenAI Codex** — implementation, debugging, code review, regression checks, UI-state verification, and PyInstaller packaging.
- **Anthropic Claude** — earlier feature implementation and iteration of the application.
- **xAI Grok** — UI critique and visual direction suggestions.
- **Design guidance** — Impeccable, `frontend-design`, `web-design-guidelines`, `react-best-practices`, `shadcn`, and `ui-ux-pro-max` were consulted for interface and interaction decisions.

AI-generated suggestions were reviewed and integrated by the maintainer. The project is tested locally; AI assistance is not a claim of zero defects or a substitute for review.

## 中文说明

轻拣（Qingjian）是一款面向 Windows 的本地图片与视频快速分类工具。选择来源文件夹后，可以用 `1`–`0` 等快捷键把当前媒体移动、复制、收藏、重命名、回收或打标签，并自动进入下一项。

主要功能包括：图片/视频预览、可配置按键与目标目录、路径和命名模板、同名文件 Replace/自动编号、伴随文件事务处理、查重与忽略、评分和色标、待复查队列，以及可恢复的撤销流程。2.0.4 还修复了启动时“撤销”和“恢复上一步”误亮的问题。

本项目使用 AI 辅助开发：OpenAI Codex 负责当前版本的实现、测试和打包；Anthropic Claude 参与早期版本迭代；xAI Grok 提供 UI 评审建议；Impeccable、`frontend-design`、`web-design-guidelines`、`react-best-practices`、`shadcn` 和 `ui-ux-pro-max` 提供界面设计参考。所有改动均经过维护者审核和本地测试。

## License

No license has been selected for this repository yet. Until a license file is added, all rights are reserved by the copyright holder.
