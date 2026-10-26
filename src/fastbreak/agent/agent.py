from dataclasses import dataclass, field

from fastbreak.agent.grounding import ungrounded_numbers
from fastbreak.agent.prompt import ANSWER_SYSTEM_PROMPT, answer_user_prompt, sql_system_prompt
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
    sql_attempts: int = 0
    calls: list = field(default_factory=list)  # one entry per model call

    @property
    def seconds(self):
        return sum(c["seconds"] for c in self.calls)


def _record(result, step, reply):
    result.calls.append(
        {
            "step": step,
            "seconds": round(reply.seconds, 3),
            "prompt_tokens": reply.prompt_tokens,
            "output_tokens": reply.output_tokens,
            "thinking_chars": len(reply.thinking),
            "cut_off": reply.cut_off,
        }
    )


def ask(question, llm, db_path, today=None):
    """Answer `question`: write SQL, run it read-only, then answer from the rows.

    The answer only goes out if every number in it is in the rows (or the question). If a
    query fails, the model sees the error and gets one more try.
    """
    result = Result(question)
    messages = [
        {"role": "system", "content": sql_system_prompt(today)},
        {"role": "user", "content": question},
    ]
    for attempt in range(1, MAX_SQL_ATTEMPTS + 1):
        reply = llm.chat(messages)
        _record(result, "sql", reply)
        result.sql_attempts = attempt
        result.sql = extract_sql(reply.text)
        try:
            if reply.cut_off:
                raise QueryError("the reply was cut off before it finished; write a shorter query")
            query = run_readonly(db_path, result.sql)
            result.error = None
            break
        except QueryError as e:
            result.error = f"query failed: {e}"
            messages += [
                {"role": "assistant", "content": reply.text},
                {"role": "user", "content": f"That query failed: {e}\nWrite a corrected query."},
            ]
    else:
        return result

    result.columns, result.rows, result.truncated = query.columns, query.rows, query.truncated
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
    result.ungrounded = ungrounded_numbers(result.draft_answer, query.rows, question)
    if reply.cut_off:
        result.error = "the answer was cut off before it finished"
    elif not result.ungrounded:
        result.answer = result.draft_answer
    return result
