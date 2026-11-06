# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences, served equally:

- **NBA fans** settling an argument or checking a stat: who has the most 20-point bench games since 2015, a team's record in a season, what a player scored on a given night. They want the answer fast and want to trust it.
- **Technical visitors** (recruiters, engineers) judging how FastBreak is built. They want to see how an answer is produced, how it's checked, and how well it scores on a test.

The site is a fan tool on the surface, with a clear path for a technical visitor to see how it works and how accurate it is.

## Product Purpose

Answer plain-English questions about NBA games since 2015-16 from a real database that updates every night, and show the proof under every answer: the SQL it ran and the rows it came from. Success is a visitor who gets an answer and can check it, not one who has to take it on faith.

## Positioning

Every number in an answer comes from a query result the visitor can see. If a number in the reply isn't in the result rows, the reply doesn't go out as a checked answer. FastBreak is also open about how often it's right, measured on a hand-written test set, rather than presenting itself as always correct.

## Operating Context

- The visitor types a question; the answer streams in steps: writing the query, running it, writing the answer and checking every number, then the answer with its SQL and rows.
- The homepage shows last night's games (final scores, top scorers) and how fresh the data is ("Data through Nov 5, 2026 · 14,251 games").
- History of a visitor's questions is kept in their browser only.
- Each question is answered on its own, with no memory of earlier ones, so a question has to name the player, team and season.
- Data is NBA.com box scores, loaded nightly, regular season and playoffs from 2015-16 on.

## Capabilities and Constraints

- The model (`qwen3:14b`) and database run on a home PC; the web app on Vercel reaches them through a tunnel. When the PC is off, the site must still load and say the data server is offline.
- The live site runs with thinking off: a typical answer takes about 6 s, a slow one about 26 s. A thinking mode (1–3 minutes per hard question) exists but isn't used live.
- One question at a time across all visitors; 10 questions per visitor per hour, 150 per day in total. A second question while one is running gets a "busy" message.
- Queries are read-only and limited to 10 seconds.
- An answer can be wrong even when every number is grounded: the query can answer a different question than the one asked (e.g. a season total instead of a single game).
- Stack: Next.js 16 (App Router, cache components), React 19, Tailwind CSS 4, deployed on Vercel from `web/`.

## Brand Commitments

- The name **FastBreak**.
- The robot mascot: a robot with a headset holding a basketball. The original art is `web/public/mascot.png` (on navy) and `web/public/avatar.png`; the app uses `web/public/mascot-cut.png`, the same art with the navy background removed.
- The line **"Ask anything. See the proof."**

## Evidence on Hand

- Test set: 50 hand-written questions with correct answers (`evals/questions.toml`). Live mode (thinking off) scored 36/50 (72%) on the latest run; routed 40/50 (80%); thinking on 44/50 (88%). With 50 questions, 72% means somewhere between 58% and 82% (95% range). Results and history are in `README.md` and `DECISIONS.md`.
- Real data: about 14,250 games since 2015-16, refreshed nightly.
- No users, testimonials, press or usage numbers exist. Don't invent any.

## Product Principles

1. **Proof over polish.** The query and rows behind an answer are the product, not a footnote.
2. **Honest about accuracy.** Say on the site how often FastBreak is right on its test and that answers can be wrong; make checking easy.
3. **Fast answer first, depth on demand.** The answer leads; the SQL, rows and how-it-works are one step away for whoever wants them.
4. **Fails in the open.** Offline, busy, a query that wouldn't run, a number that isn't in the rows: each is said plainly, never hidden.
