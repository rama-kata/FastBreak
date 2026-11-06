---
name: FastBreak
description: NBA answers printed as a box score, with the proof under every headline.
colors:
  paper: "#e9e8e3"
  sheet: "#f4f3ef"
  ink: "#151515"
  ink-soft: "#383733"
  muted: "#5c5b56"
  rule: "#c4c2ba"
  spot: "#c8231e"
typography:
  display:
    fontFamily: "Libre Franklin, system-ui, sans-serif"
    fontSize: "clamp(44px, 6.4vw, 92px)"
    fontWeight: 900
    lineHeight: 0.94
    letterSpacing: "-0.04em"
  headline:
    fontFamily: "Libre Franklin, system-ui, sans-serif"
    fontSize: "44px"
    fontWeight: 800
    lineHeight: 1.06
    letterSpacing: "-0.025em"
  title:
    fontFamily: "Libre Franklin, system-ui, sans-serif"
    fontSize: "30px"
    fontWeight: 900
    lineHeight: 1
    letterSpacing: "-0.025em"
  deck:
    fontFamily: "Libre Franklin, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 400
    lineHeight: 1.375
  body:
    fontFamily: "Libre Franklin, system-ui, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
    fontFeature: "tnum"
  agate:
    fontFamily: "Archivo Narrow, Arial Narrow, sans-serif"
    fontSize: "15px"
    fontWeight: 400
    lineHeight: 1.375
    fontFeature: "tnum"
  label:
    fontFamily: "Archivo Narrow, Arial Narrow, sans-serif"
    fontSize: "13px"
    fontWeight: 700
    letterSpacing: "0.08em"
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: "12.5px"
    fontWeight: 400
    lineHeight: 1.65
rounded:
  none: "0px"
  dot: "9999px"
spacing:
  cell-y: "6px"
  cell-x: "12px"
  gutter: "20px"
  gutter-wide: "40px"
  stack: "20px"
  proof-gap: "32px"
  story-gap: "40px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.label}"
    rounded: "{rounded.none}"
    padding: "0 16px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.ink-soft}"
    textColor: "{colors.paper}"
  button-secondary:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0 16px"
    height: "44px"
  button-secondary-hover:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
  button-ask:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.none}"
    padding: "0 24px"
    height: "52px"
  input-question:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.none}"
    padding: "14px 16px"
    height: "52px"
  tag-final:
    textColor: "{colors.spot}"
    typography: "{typography.label}"
  box-score-cell:
    textColor: "{colors.ink}"
    typography: "{typography.agate}"
    padding: "{spacing.cell-y} {spacing.cell-x}"
  sql-block:
    backgroundColor: "{colors.sheet}"
    textColor: "{colors.ink-soft}"
    typography: "{typography.mono}"
    rounded: "{rounded.none}"
    padding: "16px"
---

# Design System: FastBreak

## Overview

**Creative North Star: "The Box Score"**

FastBreak prints like the sports page of a daily paper. Every answer is set as a game story: the question is the deck, the answer is the headline, the result rows are the agate box score under it, and the SQL is the "how we got it" line beside the box. The page is newsprint grey with black ink; one edition spot red marks the few things an editor would mark. Proof sits under the headline, never behind a toggle.

Density is a newspaper's: tight agate tables, condensed labels, rules instead of boxes. The shell never moves. A left rail carries the flag, the edition line and Your questions; last night's line scores run across the top as a strip; the question box sits at the foot. Depth comes from rules and ink weight, not from shadows or cards. Motion is small and editorial: the pen ring drawing on, a pulsing Live dot, an arrow nudging on hover.

The world rejects the chat-bubble thread with collapsed sources: no bubbles, no avatars beside messages, no rounded cards, no drop shadows.

**Key Characteristics:**
- Newsprint ground, black ink, one spot red with a fixed list of jobs.
- Heavy Franklin Gothic headlines; condensed agate for every table, label and line score; mono only for SQL.
- Graded rules: a 4px double ink rule under the flag, 2px ink rules where a section starts (under standing heads and under the answer headline), hairline grey rules for every other edge and divider.
- Square corners everywhere; the only round things are status dots.
- Tabular figures on the whole document.
- Signature: the editor's red pen rings a number in the headline and the cell it came from.

## Colors

A two-ink newspaper: black on newsprint, plus one spot red that is rationed.

### Primary
- **Edition Spot Red** (spot): the only accent. Its jobs are fixed: the "Break" in the FastBreak flag, the FINAL tags in the games strip, "See the proof." in the home headline, the underline under grounded numbers in an answer, the Live dot while a question runs, the pen ring, struck ungrounded numbers in a held-back draft, the hollow offline dot, the text caret and the global focus ring.

### Neutral
- **Newsprint** (paper): the page ground for the rail, main column, games strip, How it works sheet and sticky table heads.
- **Fresh Stock** (sheet): the same paper with less ink. Used for the question field, the SQL block and the hover fill of secondary buttons.
- **Press Black** (ink): headlines, body text, the double rule and 2px section rules, the 1px rule under the rail's standing head, the outline button border, primary button fill, the online data dot, text selection.
- **Second Impression** (ink-soft): text under a headline (the deck, intro copy, datelines, panel body, SQL text, losing team lines) and the hover fill of black buttons.
- **Faded Agate** (muted): timestamps in the play-by-play, helper lines, empty states, the working headline while a question runs, the placeholder.
- **Hairline Grey** (rule): every edge and divider that doesn't start a section: the rail's right edge, the strip's bottom and cell dividers, the line above the question box, the question field's border, story ends, table header and row dividers, list and play-by-play rows, the How it works sheet's edge, the SQL block border, skeleton bars. Never for text.

### Named Rules
**The Spot Red Rule.** Red does one of the jobs listed above and nothing else. Hovers never turn red: links thicken their underline, black buttons lighten to ink-soft, outline buttons fill with sheet.

**The Two Ink Rule.** Everything that is not red is ink, ink-soft, muted or rule on paper or sheet. There is no second accent and no tint of red used as a fill.

## Typography

**Display Font:** Libre Franklin (with system-ui)
**Body Font:** Libre Franklin (with system-ui)
**Label/Agate Font:** Archivo Narrow (with Arial Narrow)
**Mono Font:** JetBrains Mono (with ui-monospace), for SQL and query errors only

**Character:** A Franklin Gothic headline face at 800 and 900 with tight negative tracking does the shouting; condensed Archivo Narrow does the counting, the way agate does on a real sports page.

### Hierarchy
- **Display** (900, clamp 44 to 92px, 0.94, -0.04em): the home headline only, capped at 13ch and balanced.
- **Headline** (800, 44px on wide screens and 30px on phones, 1.06, -0.025em): the answer to a question, capped at 30ch. Long answers step down: over 120 characters to 32/26px, over 220 to 26/22px. The working state uses the same headline in muted ink.
- **Title** (900, 30px, 1, -0.025em): the How it works sheet head. The flag is the same face at 900, 36px in the rail and 24px on phones, -0.035em.
- **Deck** (400, 18px, 1.375): the question repeated above its answer, in ink-soft, capped at 60ch. The home intro is the same voice at 20px.
- **Body** (400, 16px, 1.5): explanatory copy, capped at 62ch. The sheet uses 15px at 1.625.
- **Agate** (400, 15px): box score cells, the play-by-play log, the strip's line scores (14px), datelines (14px). Winning team lines and grounded cells go bold.
- **Label** (700, 13px, 0.08em, uppercase): standing heads over a block of rows: "Box score", "How we got it", "Your questions", "Try one", the sheet's section heads. Table column heads are 11.5px at 0.06em; FINAL tags 11px at 0.1em.
- **Mono** (400, 12.5px, 1.65): SQL, with keywords in bold ink and string literals in italic. Lines wrap and continue indented 2ch under themselves; nothing scrolls sideways.

### Named Rules
**The Tabular Figures Rule.** `font-variant-numeric: tabular-nums` is set on the root, so every figure in every face lines up in columns. Numeric table columns are right-aligned.

**The Standing Head Rule.** An uppercase agate label always heads a block of rows and sits on a 2px ink rule (1px in the rail). It never floats above a headline as a tag line.

## Layout

The shell is fixed to the viewport (100dvh) and never scrolls as a whole; only the story column scrolls.

- **Rail** (md and up): 280px wide, a hairline rule on its right, 24px top padding, 20px sides. Flag and edition line, New question, Your questions, and the tagline "Ask anything. See the proof." on a hairline rule at the foot.
- **Phone**: the rail becomes a header (mascot, small flag, "Your questions" toggle) on a 4px double rule; the toggle opens a drawer up to 70dvh tall with the edition line and the rail contents.
- **Games strip**: across the top of the main column, a hairline rule under it. A 112px date cell, then 216px game cells (half the width on phones) that scroll sideways and snap to whole games.
- **Story column**: max 1120px, centred, 20px gutters on phones and 40px from sm up. Stories stack 40px apart, each closed by a hairline rule. The answer's dateline (check status, rows, time) sits on a 2px ink rule directly under the headline. Inside a story the stack is 16 to 20px.
- **Proof grid**: the answer article is a size container. Below the @3xl container width (48rem) the box score and the query stack; from @3xl up they sit side by side at 1.1fr and 1fr with 32px between and a hairline rule left of the query. The switch follows the article's width, not the viewport, so it holds when the How it works sheet narrows the column.
- **Home**: from lg up, the display headline and intro beside a 300px "Try one" column aligned to the bottom; stacked below lg.
- **Question box**: pinned at the foot on a hairline rule, the field itself in a hairline border so the black Ask button carries the weight, same 1120px measure, with the helper line (hidden on phones) and the accuracy line under it.
- **How it works**: a right-hand sheet, min(460px, 100vw) wide, full height, with a hairline rule on its left. While it is open the main column takes 460px of right padding from lg up, so the sheet sits beside the story instead of over it. On narrower screens it covers the page.

## Elevation & Depth

There are no shadows anywhere. The page is flat paper, and hierarchy comes from rules and ink weight: a 4px double ink rule under the flag and the sheet head, 2px ink rules where a section starts (standing heads, the answer's dateline under the headline), and hairline grey rules for everything else: region edges (rail, strip, question box, sheet), story ends, table header lines and rows. Only the section starts are black, so the headline and the box score are the darkest things on screen. Sticky table heads use the paper colour to cover rows scrolling under them. The How it works sheet has no backdrop dimming; its hairline rule is its only edge.

### Named Rules
**The Rules Not Boxes Rule.** Divide with a horizontal or vertical rule before reaching for a border. Full borders are reserved for things you type into or read code in (the question field, the SQL block) and for the outline button.

## Shapes

Every corner is square (0px). The only round shapes are 8px status dots: the pulsing red Live dot, the black online dot and the hollow red offline dot. The pen ring is the one hand-drawn shape: an open, tilted ellipse in 2px red with round caps, stretched to the number it circles. Icons are small inline line drawings (plus, check, arrow, external arrow, close) in currentColor at 1.5 to 2.2px stroke with square ends.

## Components

### Buttons
Black slabs and ink outlines, set in bold agate.
- **Shape:** square (0px), at least 44px tall.
- **Primary:** ink fill, paper text, bold Archivo Narrow 15px, 16px side padding. Used for New question (16px text, with a plus), Try again and Ask again.
- **Ask:** the same black slab at 52px tall, 24px side padding, 17px text with a right arrow, stretched to the field's height. Disabled is aria-disabled, unchanged in colour and with no hover.
- **Hover / Focus:** black fills lighten to ink-soft; focus shows the global 2px spot red outline at a 2px offset.
- **Secondary:** 1px ink outline, ink text, fills with sheet on hover. Used for Stop.
- **Text actions:** CSV, Copy, Clear, Close, How it works, "Your questions" are bold agate 13 to 15px with an underline at 3px offset that thickens to 2px on hover.

### Games strip cells
- **Style:** whole-cell line scores in 14px agate, a hairline rule between cells. A red FINAL tag (with "OT" or "2OT" when needed) heads each cell; the winning line goes bold ink, the loser stays ink-soft; the top scorer sits under it in muted 13px. "Ask about it" and "Highlights" are underlined bold links.
- **Loading:** the same cells with rule-grey bars at stepped opacity.

### Box score (result table)
- **Style:** a standing head on a 2px ink rule, then a table in 15px agate with a hairline rule under the column heads and hairline rules between rows. Cells are padded 6px by 12px; numeric columns align right; nulls print as an em dash. Up to 360px tall, then it scrolls with a sticky head.
- **Grounded cells:** numbers the answer used are bold, and take the pen ring when their number is pointed at.

### Inputs / Fields
- **Style:** the question field is a hairline border on sheet, square, 52px minimum, 17px Franklin, growing with its content up to 160px. Placeholder in muted.
- **Focus:** a 2px ink outline flush with the border; the caret is spot red.

### Navigation
- **Your questions:** a list in 14px Franklin, hairline rules between items, two lines at most. Hover underlines; the current question is bold.

### The editor's pen (signature)
In a checked answer, each number found in the result rows is a focusable mark with a 2px spot red underline. Pointing at it or focusing it hides the underline and draws a red ring around it and around every matching bold cell in the box score. The ring is an SVG path drawn on with a dash offset over 360ms on cubic-bezier(0.16, 1, 0.3, 1). With reduced motion it appears already drawn. The ring replaces the focus outline on these marks.

### Play-by-play (working state)
While a question runs: the headline in muted ink says what is happening, then a 2px ink rule with the red Live dot, the elapsed clock and Stop, then a timestamped log in 15px agate (a 3.5rem muted time column, hairline rules between plays). The query so far is a disclosure under it.

### Dateline
A 2px ink rule under the headline with the check status on the left (a check mark and "Every number checked against the rows" in bold ink) and the row count and seconds on the right, in 14px agate.

### Held-back draft
When a number is not in the rows, the headline says so, and the draft sits in a 1px dashed ink box with ungrounded numbers struck through in bold spot red. The rows and query still print below.

## Do's and Don'ts

### Do:
- **Do** set every answer as deck, headline, dateline, then box score and query, with the proof always visible.
- **Do** keep spot red to its listed jobs: flag, FINAL, "See the proof.", grounded-number underlines, Live dot, pen ring, struck numbers, offline dot, caret, focus ring.
- **Do** grade the rules: the 4px double rule under the flag, 2px ink rules only where a section starts, hairline grey for every other edge.
- **Do** set tables, labels, line scores and logs in Archivo Narrow, and right-align numeric columns.
- **Do** let the proof grid switch on the article's container width, so the layout holds when the How it works sheet is open.
- **Do** show the pen ring already drawn when reduced motion is on.

### Don't:
- **Don't** turn anything red on hover; hovers thicken underlines or shift ink and sheet fills.
- **Don't** add shadows, rounded corners or card boxes; corners are 0px and only status dots are round.
- **Don't** use chat bubbles, avatars beside messages or collapsed sources.
- **Don't** use JetBrains Mono for anything but SQL and query errors.
- **Don't** put an uppercase agate tag above a headline; standing heads only head a block of rows.
- **Don't** scroll SQL sideways; wrap it and indent the continuation.
