---
version: 1
slug: "web-src-app-page-tsx"
primary_target: "web/src/app/page.tsx"
related_targets: ["web/src/components/ChatApp.tsx","web/src/components/Answer.tsx","web/src/components/GamesStrip.tsx"]
---

# FastBreak web app (home + answers)

Scope: the whole web app at web/ — home, the answer thread, History, last night's games, the how-it-works panel. Mode: Operate. Audience and truth: PRODUCT.md.

Must keep: chat layout + History (browser-only), last night's games with top scorers and "Ask about it", live step-by-step progress, the mascot, the name, "Ask anything. See the proof." Accuracy said on every screen ("Right on 36 of 50 test questions"), opening a how-it-works panel. Must not feel like a generic AI chatbot, a sportsbook, a dry developer tool, or cartoonish.

## Direction contract

THESIS: Every answer is printed as a box score: the answer is the headline, the result rows are the agate under it, the SQL is the "how we got it" line. Refuses the chat-bubble thread with collapsed sources.

OWN-WORLD: Newsprint grey ground, black ink, one edition spot red used for the flag, FINAL tags and the editor's pen ring. Franklin Gothic-style heavy headline face (Libre Franklin 800/900), condensed agate for tables and labels (Archivo Narrow), JetBrains Mono only for SQL. 1px ink rules and double rules, no shadows, no rounded cards, tabular figures everywhere.

STORY: A fan asks, watches a play-by-play log of the steps, reads the headline answer, and can check every number against the box score below it; a technical visitor sees the SQL and the accuracy line and opens how it works.

FIRST VIEWPORT: Left rail: masthead flag with the mascot ear, edition line with data freshness, New question, Your questions list, the tagline at the foot. Top of the page: last night's line scores as an agate strip. Main: the question as a deck line, the answer as a 44px headline, a rule with time and check status, then two columns: box score rows and the query. Baseline: question box with black Ask button and the accuracy line.

FORM: Box Score, position 1 on my ordered list (taken as IMPECCABLE'S PICK). seed:e61314b431a14c19. Signature move: point at or focus a number in the headline and the editor's red pen rings the cells it came from in the box score. Progress is a timestamped play-by-play log. Kept from declined challengers: the shell never moves (Developer Console), whole-cell game strip (Convention Catalog), tabular figures (Datamatics), ring the object under the eye (Star Atlas).

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
