---
version: 1
slug: "qingjian-ui-mainwindow-py"
primary_target: "qingjian/ui/mainwindow.py"
related_targets: ["qingjian/ui/theme.py","qingjian/ui/widgets.py","qingjian/ui/browsers.py","qingjian/ui/preview.py","qingjian/ui/dialogs.py","qingjian/ui/editors.py","qingjian/ui/duplicates.py","qingjian/ui/icons.py","qingjian/ui/thumbs.py"]
---

# Main window and its dialogs

## Scope

The whole Qt Widgets interface: main window (single view, grid view, empty and loading states), the ten key bindings, preview and video controls, and the dialogs (bindings, templates, settings, duplicates, history, statistics, backups, conflicts, sidecars). Visitor mode: **Operate**.

## Audience and task

Ordinary people on a Windows PC, often in the evening, filing hundreds of photos and clips in a row, keyboard first. Always visible while sorting: where each key files to, progress, the current file's details, the previous and next thumbnails. The user's own bar: the photo is the hero, and a redesign that makes the photo smaller, slower or laggier is broken. Unchanged: every function, every shortcut, the speed work (held-arrow flipping, lazy thumbnails, background queue), no confirmation on recycle, no auto-advance after rating.

## Chosen direction

冲印店取件台 (photo-lab pickup counter), chosen by the user on the decision page, code-led, no steer. Memorable moment: 装袋, a print dropping into its envelope while the next print is already on the counter.

## Record

- 2026-09-16 finish review: disposition fix. Two verdict passes resolved every material fix.
- Measured against the pre-redesign build f6b28b8:
  - The photo is drawn larger at 1180, 1280, 1540 and 1920 px windows.
  - Flipping and filing run at parity. The drop's setup adds about 2 ms after the next print is up.
- The width-fitted status line (`_fit_ledger`) was fixed after the second verdict and has not been re-reviewed.
- DESIGN.md and .impeccable/design.json were written from the build.

## Unresolved

- Video and animated images keep a plain dark mat; there is no paper border around moving media.
- "MEDIA SORTER" beside the wordmark is 8px letter-spaced caps. It is a brand commitment in PRODUCT.md, but it is hard to read at that size.
- Three hover and border colours sit outside the theme constants: #3A201C, #3A2C20, #CFC6B6.

## Direction contract

THESIS: Sorting is filing fresh prints into named envelopes at a lab counter. The print lies large on a dark counter and ten kraft envelopes wait along its front edge. Refuses the category default: grey Lightroom-style panels with a right-hand destination list and a purple or blue accent chip on everything.

OWN-WORLD:
- Counter and prints: a warm near-black counter (#1C1916) with a darker mat (#141210) under the print. Photos are prints, with a warm paper border (#EFE9DD) sized to the photo and a tight shadow painted round it, never under it.
- Envelopes: ten kraft envelopes (#BD9A6F) with a shallow thumb notch cut in the top edge. Each carries a big printed key digit in dark ink (#2A1F16), the destination in ballpoint navy (#1A2B63) on a dotted form rule, and a tabular count. The two hexes are tuned from #B89468 and #1E3170 for 4.5:1 text. A printed box appears only for actions that are not a plain move.
- Folder: a pickup-slip stub (count | perforation | folder).
- Marks: current and selected frames get a red grease-pencil box (#E0594D). Colour labels are round dot stickers. Stars are paper, not yellow.
- Controls: printed matter with 4px corners on controls, 3px on paper objects and 2px on chips. Primary is a paper fill with ink text; secondary is a warm hairline. The active tab has a grease-pencil underline.
- Type: every number is Bahnschrift with tabular figures; all other text is Microsoft YaHei UI.

STORY: Open a folder and the first print is already on the counter. Read each envelope's key and name without looking away, press the key: the print drops into that envelope, its count ticks, and the next print is there. Ctrl+Z takes it back out. The user believes nothing is lost and they set the pace.

FIRST VIEWPORT: At 1540x940:
- A 40px top counter edge on one line: wordmark with its subtitle, slip stub, choose-folder button, rescan, view tabs, filter, sort with reverse, subfolders, duplicates, more, language, settings.
- A stage of about 1508x662 with the print centred.
- A backprint line: filename and capture details on the left; stars, label stickers and the review queue, then info, rotate, 1 / 26, previous and next on the right. In grid view the stars, stickers and review queue move to the grid toolbar and mark the selection.
- A 76px index strip.
- A 67px envelope row: ten equal envelopes. The primary action is a key press or an envelope click.
- A status line: preset, search, edit keys and key hints; the last status message and handled files; undo and redo; session progress; snapshots. The message outranks the controls around it as the width narrows.

FORM: 冲印店取件台, #1 on the grounded list (taken as IMPECCABLE'S PICK over the rolled #4 发牌台), seed key 97aa8e68, code-led.
- Signature interaction 装袋: on filing, a copy of the print leaves from the print's own rect. It is shown only once it is under half size, and shrinks into the target envelope's notch in 180ms (OutExpo) while the next print is already shown. The envelope then shows a red stamp ring that fades over 420ms; this is the one motion allowed past 200ms.
- Motion grammar: state-only, ease-out, 200ms or less. Flipping never animates. Motion is off when Windows animations are off.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
