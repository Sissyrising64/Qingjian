---
name: 轻拣 Qingjian
description: A photo-lab pickup counter for sorting prints into ten keyed envelopes (Windows desktop, PySide6 Qt Widgets)
colors:
  counter: "#1C1916"
  mat: "#141210"
  raised: "#25211D"
  raised-hover: "#2E2924"
  sunk-panel: "#211D1A"
  pressed: "#3A332C"
  line: "#352F29"
  line-control: "#7A6E60"
  paper: "#EFE9DD"
  paper-bright: "#F7F2E8"
  paper-pressed: "#DCD4C6"
  paper-dim: "#BDB3A4"
  faint: "#978C7E"
  disabled: "#6A5F53"
  kraft: "#BD9A6F"
  kraft-hover: "#C7A67C"
  kraft-edge: "#8E7050"
  kraft-rule: "#7A5E42"
  ink: "#2A1F16"
  ink-soft: "#5E4F40"
  ballpoint: "#1A2B63"
  ballpoint-light: "#8DA6E8"
  stamp: "#7E1F19"
  grease: "#E0594D"
  amber: "#D9A866"
  label-red: "#E5534B"
  label-yellow: "#E2B340"
  label-green: "#57AB5A"
  label-blue: "#539BF5"
  label-purple: "#986EE2"
typography:
  headline:
    fontFamily: "Microsoft YaHei UI"
    fontSize: "20px"
    fontWeight: 700
  wordmark:
    fontFamily: "Microsoft YaHei UI"
    fontSize: "18px"
    fontWeight: 800
  title:
    fontFamily: "Microsoft YaHei UI"
    fontSize: "14px"
    fontWeight: 700
  body:
    fontFamily: "Microsoft YaHei UI"
    fontSize: "13px"
    fontWeight: 400
  label:
    fontFamily: "Microsoft YaHei UI"
    fontSize: "12px"
    fontWeight: 600
  caption:
    fontFamily: "Microsoft YaHei UI"
    fontSize: "11px"
    fontWeight: 400
  envelope-key:
    fontFamily: "Bahnschrift SemiCondensed, Segoe UI, Microsoft YaHei UI"
    fontSize: "24px"
    fontWeight: 600
    fontFeature: "tnum"
  numeral:
    fontFamily: "Bahnschrift, Segoe UI, Microsoft YaHei UI"
    fontSize: "14px"
    fontWeight: 600
    fontFeature: "tnum"
  mono:
    fontFamily: "Cascadia Mono, Consolas, monospace"
    fontSize: "13px"
    fontWeight: 400
rounded:
  hairline: "2px"
  printed: "3px"
  control: "4px"
spacing:
  window-x: "16px"
  window-y: "8px"
  band-gap: "6px"
  gap-compact: "6px"
  gap-standard: "8px"
  gap-roomy: "10px"
  pad-compact: "11px"
  pad-standard: "14px"
  pad-roomy: "17px"
components:
  button-primary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "32px"
  button-primary-hover:
    backgroundColor: "{colors.paper-bright}"
  button-primary-pressed:
    backgroundColor: "{colors.paper-pressed}"
  button-secondary:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "0 14px"
    height: "32px"
  button-secondary-hover:
    backgroundColor: "{colors.raised-hover}"
  button-compact:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "0 10px"
    height: "27px"
  button-quiet:
    textColor: "{colors.paper-dim}"
    rounded: "{rounded.control}"
    padding: "0 8px"
    height: "27px"
  button-danger:
    textColor: "{colors.grease}"
    rounded: "{rounded.control}"
    height: "32px"
  button-ink:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "0 18px"
  input-field:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "4px 9px"
  segment-tab:
    textColor: "{colors.paper-dim}"
    typography: "{typography.label}"
    padding: "0 11px"
    height: "23px"
  segment-tab-checked:
    textColor: "{colors.paper}"
  binding-envelope:
    backgroundColor: "{colors.kraft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.printed}"
    height: "70px"
  folder-slip:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.paper}"
    rounded: "{rounded.printed}"
    height: "32px"
  menu:
    backgroundColor: "{colors.raised}"
    textColor: "{colors.paper}"
    padding: "4px"
  tooltip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    padding: "5px 8px"
---

# Design System: 轻拣 Qingjian

## Overview

**Creative North Star: "The Photo-Lab Pickup Counter" (冲印店取件台)**

Sorting is filing fresh prints into named envelopes at a lab counter. The window is a warm near-black counter. The photograph lies large on a darker mat as a print with a paper border. Ten kraft envelopes wait along the front edge: each has a big printed key digit, the destination handwritten in ballpoint on a dotted form rule, and a tabular count. Every surface comes from that counter: paper, kraft, printed ink, ballpoint, red grease pencil and a rubber stamp. The system is dense and keyboard-first. The chrome stays in low-contrast warm darks so the print is the brightest thing on screen.

This is a Windows 10/11 desktop app built with PySide6 Qt Widgets. Every token lives as a Python constant in `qingjian/ui/theme.py`. One Qt stylesheet, generated per density, applies them, along with a Fusion-based `CounterStyle` (QProxyStyle) that draws check boxes, radios, chevrons and focus rings by hand. Components that have no stylesheet equivalent are painted with QPainter in `widgets.py`, `browsers.py` and `preview.py`. There are no CSS variables.

The world turns away from the category default: grey Lightroom-style panels, a list of destinations down the right side, and a purple or blue accent chip on everything. Accent colour here is a physical mark, never a fill.

**Key Characteristics:**
- Warm near-black counter, darker mat under the print, prints with real paper borders.
- Ten kraft envelopes are the primary action surface. You file by pressing a key or clicking an envelope.
- Red grease pencil marks what is chosen. A paper fill marks what to do.
- Every number is set in Bahnschrift with tabular figures. All other text uses Microsoft YaHei UI.
- Square-ish printed-matter controls (4px), hairline outlines, drawn line icons.
- Motion is limited to state changes and is quick. The one flourish is 装袋, bagging a print.

## Colors

The palette is warm browns and blacks, paper and kraft, with two ink marks (red grease pencil and navy ballpoint) and one rust stamp.

### Primary
- **Paper** (paper): the print border, primary text, the primary button fill, tooltips, checked check boxes and radios, the switch track when on, lit stars, the empty-state slip. Paper Bright is its hover state and Paper Pressed its pressed state.
- **Kraft** (kraft): the envelope body. Kraft Hover appears when an envelope lifts. Kraft Edge is the envelope's bottom band and the dashed outline of an unconfigured envelope. Kraft Rule is the dotted form rule. Kraft also fills progress bars and the burst chip on thumbnails.

### Secondary
- **Grease Pencil Red** (grease): the current or selected frame box in the strip and grid, the checked segment and tab underline, the active review toggle, the mark tag, danger buttons, and error status text. On an unconfigured envelope it is also the stamp ring.
- **Ballpoint Navy** (ballpoint): handwriting on kraft only, meaning the destination folder name on an envelope.
- **Light Ballpoint** (ballpoint-light): the keyboard focus ring, the focused field border, success status text and links. This is ballpoint seen on the dark counter.

### Tertiary
- **Stamp Rust** (stamp): the ring stamped on an envelope after filing, and the count while the stamp is fresh.
- **Amber** (amber): warnings only. Used for the warning button, the warning status tone and a full snapshot quota bar.
- **Dot stickers** (label-red, label-yellow, label-green, label-blue, label-purple): colour labels, in the order Alt+1..5 assigns them. They only ever appear as round stickers.

### Neutral
- **Counter** (counter): the window and dialog background, tables and lists.
- **Mat** (mat): under the print stage, the contact-sheet grid and the video surface.
- **Raised** (raised): fields, buttons, menus, header sections, the folder slip. Raised Hover is its hover state.
- **Sunk Panel** (sunk-panel): settings cards, setting rows, notes, alternate table rows.
- **Pressed** (pressed): pressed controls, chosen rows and menu items, scrollbar handles, slider grooves.
- **Line** (line): hairlines whose only job is to divide.
- **Control Outline** (line-control): outlines that identify a control. It meets 3:1 against the counter.
- **Paper Dim** (paper-dim): secondary text, icons at rest, hover outlines.
- **Faint** (faint): captions, placeholders, the status line. It meets 4.5:1 on fields.
- **Disabled** (disabled): disabled text.
- **Ink** (ink) and **Soft Ink** (ink-soft): text printed on paper and kraft.

### Named Rules
**The Grease Pencil Rule.** Grease pencil red means "this one": the current frame, a selection, the active tab or toggle. The same red also carries errors and destructive actions. Never use it as a fill. It appears only as a 2px stroke, a 1px outline or text.

**The Paper Fill Rule.** A paper fill with ink text means "the thing to do". Each view gets at most one primary button. Secondary controls stay Raised with a Control Outline hairline.

**The Two Lines Rule.** Line divides and Control Outline identifies. A hairline around something clickable uses Control Outline. A rule between regions uses Line.

## Typography

**UI Font:** Microsoft YaHei UI (the system UI face), at pixel sizes
**Numeral Font:** Bahnschrift with the `tnum` feature, falling back to Segoe UI and then Microsoft YaHei UI. Envelope keys use it SemiCondensed.
**Mono Font:** Cascadia Mono, falling back to Consolas and monospace, for paths and templates

**Character:** A plain, legible CJK system face does the talking. A DIN-like engineering numeral handles every count, so figures read as printed lab tickets and never shift sideways as they tick.

### Hierarchy
Sizes follow the standard density. Base font is 13px. Compact uses 12px and roomy 14px, and each role shifts by the same offset.
- **Headline** (700, base+7 = 20px): dialog titles.
- **Wordmark** (800, base+5 = 18px): the 轻拣 brand. The empty-state slip title uses base+5 at 700 in Ink.
- **Title** (700, base+1 = 14px): section titles in settings. Row titles are base at 600. The filename on the backprint line is base at 700.
- **Body** (400, base = 13px): controls, lists, envelope folder names (13px normal as "handwriting"; action names are 12px DemiBold in Ink).
- **Label** (600, base−1 = 12px): segments, compact, quiet and menu buttons. Checked segments are 700.
- **Caption** (400, base−2 = 11px): subtitles, file details, the status line, notes, row numbers (700), tile names (11px).
- **Hint** (base−3 = 10px): keyboard hints, tag text (700), time label. The envelope badge is 10px Bold in a printed box.
- **Envelope key** (Bahnschrift DemiBold SemiCondensed): 40% of the envelope body height (24px at the 70px envelope). It shrinks in 2px steps, down to 12px, until it fits 42% of the width.
- **Envelope count** (Bahnschrift DemiBold 15px). Inline counts go through `draw_counted` and `CountLabel`: digit runs are set in the numeral face at 1px above the surrounding UI text.

### Named Rules
**The Tabular Count Rule.** Every number a user watches change (counts, positions like 12 / 240, handled totals, quota) is set in Bahnschrift with tabular figures via `numeral_font`, `draw_counted` or `CountLabel`. Never set a live number in the UI face.

**The No Letterspacing Rule.** Qt stylesheets have no letter-spacing, and the system does not fake it. Body and control text keep default tracking.

## Layout

The window is one vertical stack of bands on the counter. Window margins are 16px horizontal and 8px vertical, with 6px between bands:
1. **Header row** (8px gaps): wordmark, the folder slip (stretch factor 6, capped at 560px), choose folder, rescan, view segments, filter and sort combos with reverse, subfolders, duplicates, more, language, settings.
2. **Stage** (stretches): the print centred on the mat. Under it are the backprint line (filename and details on the left; stars, label stickers, review toggle, info, rotate, position and previous/next on the right) and the filmstrip. The grid view replaces the stage with a contact sheet on the mat (6px spacing, 8px padding).
3. **Envelope row**: ten equal kraft envelopes, 70px high by default. They are resized through `set_envelope_height`, never below 56px.
4. **Status line**: preset, search, edit keys, the last filed message and handled files. Undo, redo, queue, session progress and snapshot quota sit on the right.

Density comes in three steps (compact, standard, roomy). Each sets button height (28/32/36px), compact control height (24/27/30px), icon button size (28/32/36px), base font (12/13/14px), gap (6/8/10px) and horizontal button padding (11/14/17px). Roomy exists because English strings run about 60% longer than Chinese.

**No breakpoints.** The window adapts to its own width on every resize:
- `_compact_header`: below 1440px wide, or below 1640px when the language is English, the choose folder, duplicates, more and subfolders controls drop their text and keep only icon and tooltip. Filter and sort combos shrink to a 6-character minimum. The folder slip is protected, because a folder name cut to three letters says nothing.
- `_fit_ledger`: the status line measures the width actually free. If its parts, plus a readable 320px message, do not fit, it hides the preset caption and narrows the search box from 210px to 130px with a short placeholder. The session bar goes from 96px to 64px, and the snapshot label, bar and separator hide together.

### Named Rules
**The Message Outranks Chrome Rule.** When width runs out, the words saying where the last file went keep their room. Captions, wide fields and secondary figures give way first. A bar never shows without its figure.

## Elevation & Depth

Depth is physical and sparse. Chrome is flat, layered by tone from Mat to Counter to Raised to Pressed. Only paper and kraft objects lying on the counter cast shadows, which are painted as stacked translucent black bands with no blur effect.

### Shadow Vocabulary
- **Print shadow** (stage): three bands on the left, right and bottom of the paper border. Their (spread, drop, alpha) values, in border widths, are (0.3, 0.5, 72), (0.7, 0.9, 40) and (1.1, 1.3, 18). The border itself is 1.8% of the photo's shorter side, at least 2px.
- **Tile drop** (strip and grid thumbnails): one black band at alpha 110, offset 2px straight down.
- **Envelope shadow**: two rounded bands at alpha 34 and 46 below the body. They deepen by up to 1.4× as the envelope lifts 2px on hover.
- **Slip shadow** (empty and loading paper slip): three bands with (spread, drop, alpha) of (2, 5, 60), (6, 8, 30) and (11, 11, 12) px.

### Named Rules
**The Paper Casts Rule.** Only things that are paper or kraft cast shadows. Buttons, fields, menus and panels never do. Never use a hard, zero-blur offset shadow block on chrome.

## Shapes

Printed matter is cut nearly square. Controls, fields, cards and settings panels use 4px corners. Painted paper objects (envelopes, the folder slip, focus rings, selection boxes, tags, menu items) use 3px. Chips, progress bars and the slip's paper use 2px. Pills appear only on the Switch track and slider handle. Round shapes are reserved for dot stickers, radios and the stamp ring.

Envelopes have a thumb notch cut from the top edge (a 28×13px ellipse subtracted from the body). An unconfigured envelope is a dashed Kraft Edge outline (3/3 dash) with no fill. The folder slip is split by a perforation into a count stub and the folder. Icons are drawn line recipes on a 24×24 grid with round caps and joins, tinted to the colour of the control they sit in. There are no glyph fonts or SVGs.

## Components

### Buttons
- **Shape:** 4px corners, 1px outline. Height is the density's button height (32px standard), or its compact height (27px) for compact, quiet, warning and review buttons.
- **Primary** (`#primaryButton`): Paper fill, Ink text, 700. Hover Paper Bright, pressed Paper Pressed. When disabled it becomes a Pressed fill with Faint text.
- **Secondary** (default QPushButton): Raised fill, Control Outline, Paper text, 400. Hover is Raised Hover with a Paper Dim outline, pressed is Pressed. When disabled it becomes transparent with a Line outline and Disabled text.
- **Ink** (`#inkButton`): Ink fill with Paper text, 18px padding. Used only on a paper slip (the empty state).
- **Quiet** (`#quietButton`, `#menuButton`, icon buttons): transparent until hover, then Raised Hover with a Line outline.
- **Danger** (`#dangerButton`): transparent with a Grease outline and text, hover `#3A201C`. **Warning** (`#warningButton`) is the same pattern in Amber.
- **Focus:** a 1px Light Ballpoint ring at 3px radius, drawn only after keyboard focus moves (`State_KeyboardFocusChange`). Item views get a quieter 1px Paper Dim cell outline.

### Segmented tabs
- **Style** (`#segment` in `#segmentBar`): no fill or radius, Paper Dim text at base−1 and 600, with a Line hairline under the bar. Hover shows Raised Hover and Paper text.
- **Checked:** Paper text at 700 with a 2px Grease underline, a grease-pencil stroke under the chosen view. QTabBar tabs follow the same rule.

### Inputs / Fields
- **Style:** Raised fill, 1px Control Outline, 4px corners, 4px 9px padding. Selection is Paper Dim with Ink text.
- **Hover / Focus:** the outline turns Paper Dim on hover and Light Ballpoint on focus.
- **Disabled:** transparent, Line outline, Disabled text. The search field (`#search`) uses the compact height minus 6px.
- **Check boxes and radios** (16px, drawn by CounterStyle): unchecked is a Raised box with a Control Outline. Checked is a Paper fill with a round-capped Ink tick or an Ink centre dot. Disabled draws at 45% opacity.
- **Switch:** a pill track, Paper when on and Raised with an outline when off. The knob is Ink when on and Faint when off.

### Cards / Containers
- **Settings card and row** (`#settingsCard`, `#settingsRow`, `#note`): Sunk Panel fill, 1px Line, 4px corners. Notes use 10px 12px padding.
- **Menus:** Raised fill, 1px Control Outline, 4px padding. Items use 6px 22px 6px 12px padding and 3px corners, and turn Pressed when selected.
- **Tooltip:** Paper fill, Ink text, `#CFC6B6` hairline, 5px 8px padding. A tooltip is a slip of paper.

### Binding Envelope (signature)
A kraft photo envelope, one per key.
- **Body:** Kraft fill (Kraft Hover when lifted), 3px corners, the thumb notch, a 2px Kraft Edge band along the bottom, and the envelope shadow.
- **Key:** the digit printed in Ink, top-left, in the envelope key style.
- **Destination:** the folder name in Ballpoint Navy (13px normal) on a dotted Kraft Rule (1/2.5 dash) along the bottom, middle-elided. Action names (recycle, choose folder) are in Ink at 12px DemiBold.
- **Count:** Bahnschrift 15px, right-aligned on the rule.
- **Badge:** non-move actions (copy, undoable) get a 10px Bold label in a 1px Ink printed box, top-right. It is omitted if it would need truncating.
- **States:** hover lifts the envelope 2px (110ms OutCubic) and a press sinks it 1px. Unconfigured envelopes are a dashed outline with Kraft key ink and Faint name ink. Right-click chooses the folder.

### 装袋 Bagging (signature interaction)
When a print is filed in the single view, the next print is already on the stage. On the next event-loop turn a paper-bordered copy (`FlyingPrint`) shrinks from the print's rect into a 22px-wide target at the envelope's mouth, over 180ms with OutExpo easing. The copy stays hidden until the easing reaches 45%, so it never covers the new print. A drop that is still flying finishes immediately if the next key arrives. On landing, the envelope shows a 2px Stamp Rust ring around its key digit (Grease on an unconfigured envelope), tightening by 3px as it fades over 420ms with OutCubic easing. The count shows in Stamp Rust while the stamp is above 35%. With motion off or outside the single image view, only the stamp plays. Flipping between prints never animates.

### Folder Slip
The pickup slip in the header is a Raised body with a 3px corner and a Control Outline (Paper Dim and Raised Hover on hover). It holds a count stub in the numeral face, a perforation and the folder with its name (13px DemiBold, Paper) and path (11px, Faint). It is 32px tall, between 180px minimum and 560px maximum width. Clicking it chooses another folder.

### Prints and the contact sheet
- **Stage print:** the photo with a Paper border and the print shadow, centred on the Mat.
- **Tiles** (`print_tile`, filmstrip and grid): the thumbnail with a 3px Paper border and a 2px tile drop. Hover draws a 1px Control Outline box and selection a 2px Grease box, each 3.5px outside the print with 3px corners. Names are 11px Faint, or Paper when selected, on a common baseline under the row.
- **Tile chips** (2px corners): Paper chips with Ink text for stars and RAW, Kraft for bursts, a translucent counter black `rgba(20,18,16,190)` for video duration. Label stickers are drawn as dots with a dark ring.
- **Empty and loading state:** a Paper slip with the slip shadow, a Soft Ink line icon, a title in Ink and the Ink button.

### Stars and Label Stickers
Stars are paper, never yellow: lit stars are Paper (Paper Bright on hover) and unlit stars are a Control Outline stroke. Label stickers are 13px round dots in the label colours, growing to about 14.4px on hover. The chosen sticker gets a Paper ring, and the clear option is an outlined ring.

## Do's and Don'ts

### Do:
- **Do** take every colour, size and density value from `theme.py` constants and `theme.metrics(density)`. Never hard-code a hex in a widget.
- **Do** mark the current or selected item with a Grease stroke (2px box or 2px underline), and the one action to take with a Paper fill and Ink text.
- **Do** set live numbers with `numeral_font`, `draw_counted` or `CountLabel` (Bahnschrift, tabular figures).
- **Do** let photographs and paper objects be the only things that cast shadows, using stacked translucent bands.
- **Do** draw new icons as 24×24 line recipes in `icons.py`, tinted to the control's text colour.
- **Do** show focus rings only after keyboard navigation, as a 1px Light Ballpoint ring at 3px radius.
- **Do** adapt to width by dropping text labels to icons plus tooltips and narrowing secondary fields, protecting the folder name and the status message.
- **Do** keep state motion at 200ms or less with ease-out curves. The only longer motion is the 420ms stamp fade after filing. Flipping between prints never animates.

### Don't:
- **Don't** use grey Lightroom-style panels, a right-hand destination list, or a purple or blue accent chip as a fill.
- **Don't** colour stars yellow or render colour labels as anything but round dot stickers.
- **Don't** fill a surface with Grease Pencil Red or Ballpoint Navy. They are marks, not backgrounds.
- **Don't** put Ballpoint Navy on the dark counter. On the counter, ballpoint is Light Ballpoint.
- **Don't** put shadows on buttons, fields, menus or panels.
- **Don't** round controls beyond 4px. Pills belong only to the Switch and slider handle.
- **Don't** use glyph fonts, emoji or SVG files for icons.
