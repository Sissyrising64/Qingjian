# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Ordinary people tidying up a personal photo and video collection on a Windows PC: phone exports, download folders and card dumps that have grown into large, messy piles of pictures and clips. They are not assumed to be photographers or to run a catalog workflow. The job is to go through a folder quickly, decide what each item is, and end with organised folders: keepers filed, duplicates and misses cleared out.

## Product Purpose

Qingjian (轻拣) turns an unsorted media folder into organised folders through a fast review loop: preview one item, press one key, and the next item is already on screen. Success is getting through a large folder quickly and without friction while nothing is lost: every file lands where the user meant it to, companion files travel with their photo, and any mistake is one Ctrl+Z away.

## Positioning

- **One key per decision, keyboard first.** Look at an item, press a configured key (move, copy, favourite, review later, rename, recycle, reveal, tag) and move on. Opening a folder is enough to start: no catalog, no import step, unlike Lightroom-style tools.
- **Safe and undoable.** Every file operation is journaled before files change and recovers after an interruption; Ctrl+Z and Ctrl+Y undo and restore. RAW, XMP, AAE and Live Photo companions move with their photo as one unit.
- **Fully local.** No network, no account, no upload; media never leaves the computer.
- **Duplicate and burst review.** Exact duplicates, near-duplicates and burst groups can be reviewed to pick what to keep; ignoring an item never moves or deletes it.

## Operating Context

- A Windows 10/11 PC. The source is a local folder, optionally with its subfolders, opened from the folder picker, by drag and drop, from the command line, or from Explorer's "Open with Qingjian" folder menu when it is switched on.
- Sessions are long and repetitive: many items in a row, mostly keyboard-driven, with the mouse available for everything.
- Collections can be large (tens of thousands of files) and mix ordinary photos, RAW files, animated images and videos.
- Settings, history and restore data live in `%APPDATA%\LocalMediaTools\Qingjian\`, or in a `qingjian-portable` folder beside the executable.

## Capabilities and Constraints

- **Platform note.** `web` above is only the closest value Impeccable's platform field accepts. Qingjian is a Windows desktop application (Python 3.12/3.13, PySide6 Qt Widgets styled with Qt stylesheets, Pillow, NumPy, PyAV, Send2Trash), packaged with PyInstaller as the `dist/MediaSorter` folder. There is no browser: web-only mechanics such as CSS breakpoints, mobile viewports, browser live mode and the web design detector do not apply. The surface is the desktop window, its keyboard shortcuts and Qt's rendering.
- Ten configurable key bindings per preset, each with an action, a target folder, and path and filename templates (dates, camera metadata, original name, sequence number). Keys the window already uses (arrows, Space, G, S, J, K, L, M and others) cannot be bound.
- Preview of images, RAW files (embedded preview), animated images and video (playback and frame stepping); single-item and grid views; filters, sorting, star ratings (Shift+1–5), colour labels (Alt+1–5), a review-later queue and search over target folders.
- A name clash asks whether to replace the existing file or keep both with an automatic number.
- Recycling moves files into a hidden `.qingjian-trash` folder beside them: instant, restored by Ctrl+Z, and cleared by the retention policy. Sending to the Windows recycle bin is an option.
- Bilingual interface in Simplified Chinese and English, following the system language by default; every user-facing string lives in the translation catalog (`qingjian/core/i18n.py`).
- The core layer (`qingjian/core`) never imports Qt, and the interface asks the engine to act instead of touching files itself.
- The executable name must stay ASCII (`MediaSorter.exe`): a non-ASCII executable name reproduced a native-window crash.

## Brand Commitments

- Name: 轻拣 / Qingjian; executable `MediaSorter.exe`; the window's brand subtitle reads "MEDIA SORTER".
- Open source under the MIT License, © 2026 p1ziYu, published at github.com/p1ziYu/Qingjian with releases.
- The README discloses AI-assisted development; that disclosure must stay accurate.

## Evidence on Hand

- `README.md` (English and Chinese) and the maintenance notes and 2.0.4 build and verification report in `docs/`.
- Automated tests in `tests/` (371 passing on 2026-09-16) and a built-in self-check (`python main.py --selfcheck`, 7 checks).
- Measurements on a Windows PC, 2026-09-16: a 20,000-file folder opens in 0.34 s; a same-drive move takes about 20 ms; recycling a 300 MB file takes about 23 ms; start-up overhead is about 0.9 s.
- There are no user testimonials, usage numbers, reviews or press. Future work must not invent any.

## Product Principles

1. **Fast and effortless first.** Every step of the review loop should feel instant and cost as few keystrokes and dialogs as possible.
2. **Undo instead of asking.** Actions happen at once and stay reversible; confirmation dialogs are not how mistakes are prevented, so Delete recycles immediately.
3. **Never lose a file.** Companion files travel together, changes are journaled, and outside changes are detected before anything is overwritten.
4. **The user sets the pace.** Holding an arrow key flips through quickly; rating or labelling an item does not jump to the next one by itself.
5. **Local and private by default.**
