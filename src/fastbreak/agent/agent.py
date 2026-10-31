import time
from dataclasses import dataclass, field

from fastbreak.agent.grounding import ungrounded_numbers
from fastbreak.agent.prompt import ANSWER_SYSTEM_PROMPT, answer_user_prompt, sql_system_prompt
from fastbreak.agent.router import route
from fastbreak.agent.sql import QueryError, extract_sql, run_readonly

MAX_SQL_ATTEMPTS = 2  # the first query, and one retry that sees the error


@dataclass
class Result:
    question: str
    sql: str = ""
    columns: list = field(default_factory=list)
    rows: list = field(default_factory=list)
    truncated: bool = False
    answer: str | None = None  # None when the query failed or the answer wasn't grounded
    draft_answer: str = ""  # what the model wrote, kept even when it doesn't go out
    ungrounded: list = field(default_factory=list)  # numbers in the draft not in the rows
    error: str | None = None
    query_ran: bool = False  # True once a query ran, even if the answer then failed
    sql_attempts: int = 0
    route: str | None = None  # 'simple' or 'hard' when the question was routed
    # One entry per step, in order: model calls ('route', 'sql', 'answer'), each query run
    # ('query') and the grounding check ('grounding'). These become the spans of a trace.
    steps: list = field(default_factory=list)

    @property
    def calls(self):
        """The model calls among the steps."""
        return [s for s in self.steps if s["step"] in MODEL_STEPS]

    @property
    def seconds(self):
        return sum(s["seconds"] for s in self.steps)


MODEL_STEPS = ("route", "sql", "answer")


class Routed:
    """One model run two ways: `fast` (thinking off) for simple questions, `thinking` for
    hard ones, with `fast` deciding which a question is. Pass it to `ask` like a model."""

    def __init__(self, fast, thinking):
        self.fast = fast
        self.thinking = thinking
        self.name = f"{fast.name} (routed)"


def _record(result, step, reply):
    result.steps.append(
        {
            "step": step,
            "seconds": round(reply.seconds, 3),
            "prompt_tokens": reply.prompt_tokens,
            "output_tokens": reply.output_tokens,
            "thinking_chars": len(reply.thinking),
            "cut_off": reply.cut_off,
        }
    )


def _timed(result, step, started, error=None):
    seconds = round(time.perf_counter() - started, 3)
    result.steps.append({"step": step, "seconds": seconds, "error": error})


def ask(question, llm, db_path, today=None):
    """Answer `question`: write SQL, run it read-only, then answer from the rows.

    The answer only goes out if every number in it is in the rows (or the question). If a
    query fails, the model sees the error and gets one more try. With a `Routed` model, a
    quick call first decides whether the question goes to thinking off or on.
    """
    result = Result(question)
    if isinstance(llm, Routed):
        result.route, reply = route(question, llm.fast)
        _record(result, "route", reply)
        llm = llm.thinking if result.route == "hard" else llm.fast
    messages = [
        {"role": "system", "content": sql_system_prompt(today)},
        {"role": "user", "content": question},
    ]
    for attempt in range(1, MAX_SQL_ATTEMPTS + 1):
        reply = llm.chat(messages)
        _record(result, "sql", reply)
        result.sql_attempts = attempt
        result.sql = extract_sql(reply.text)
        if reply.cut_off:
            # Not sent back: the half-finished reply would only fill the context of the retry.
            result.error = "query failed: the reply was cut off before it finished"
            messages.append(
                {
                    "role": "user",
                    "content": "Your last reply was cut off before it finished. "
                    "Write the query again, with less working and a shorter query.",
                }
            )
            continue
        started = time.perf_counter()
        try:
            query = run_readonly(db_path, result.sql)
            _timed(result, "query", started)
            result.error = None
            break
        except QueryError as e:
            _timed(result, "query", started, str(e))
            result.error = f"query failed: {e}"
            messages += [
                {"role": "assistant", "content": reply.text},
                {"role": "user", "content": f"That query failed: {e}\nWrite a corrected query."},
            ]
    else:
        return result

    result.columns, result.rows, result.truncated = query.columns, query.rows, query.truncated
    result.query_ran = True
    reply = llm.chat(
        [
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": answer_user_prompt(
                    question, result.sql, query.columns, query.rows, query.truncated
                ),
            },
        ]
    )
    _record(result, "answer", reply)
    result.draft_answer = reply.text.strip()
    started = time.perf_counter()
    result.ungrounded = ungrounded_numbers(result.draft_answer, query.rows, question)
    _timed(result, "grounding", started)
    if reply.cut_off:
        result.error = "the answer was cut off before it finished"
    elif not result.ungrounded:
        result.answer = result.draft_answer
    return result
