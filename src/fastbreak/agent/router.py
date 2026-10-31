"""Routing: a quick call with thinking off decides whether a question is simple or hard.

Simple questions go to the model with thinking off (about 6 s), hard ones to thinking on
(about 55 s, but 11/15 hard test questions right instead of 5/15). The prompt describes the
kind of query a hard question needs, not test questions, so the eval's check of how often
the router agrees with the test set's labels isn't fitted to them.
"""

import re

ROUTER_PROMPT = """You sort questions about NBA stats by how hard the SQL query that answers
them is. The data is one row per player per game, and one row per game with both teams.

Reply with exactly one word: simple or hard.

simple: one filter and one count, sum, average or sort. For example a player's stat in a
given game or season, the single best game by some stat, or how many games matched a
condition.

hard: anything that needs more than that, such as
- runs of consecutive games (streaks)
- a split or comparison: home against away, two seasons, two teams against each other
- a share or rate built from totals of different groups
- a condition built from several stats in the same game (double-doubles, triple-doubles)
- grouping by season or team first, then picking the best, especially with a minimum
- counting distinct teams or seasons per player
"""

LABELS = ("simple", "hard")


def route(question, llm):
    """Return ('simple' or 'hard', the model's reply). Anything unclear counts as hard,
    since a hard question sent the fast way is the costly mistake."""
    reply = llm.chat(
        [{"role": "system", "content": ROUTER_PROMPT}, {"role": "user", "content": question}]
    )
    words = re.findall(r"[a-z]+", reply.text.lower())
    label = words[-1] if words and words[-1] in LABELS else "hard"
    return label, reply
