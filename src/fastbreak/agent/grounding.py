import re

# A number as written in prose: 30, 3,057, 27.5, +57, -12. A hyphen between digits is a
# range or a season ("2015-16", "24-0"), not a minus sign.
NUMBER = re.compile(r"(?<![\w.])[-+]?\d[\d,]*(?:\.\d+)?|(?<=\d-)\d+(?:\.\d+)?")


def numbers_in(text):
    """Each number in `text` as (value, decimals written)."""
    found = []
    for token in NUMBER.findall(text):
        clean = token.replace(",", "").lstrip("+")
        if clean.count(".") > 1 or clean in ("", "-"):
            continue
        decimals = len(clean.split(".")[1]) if "." in clean else 0
        found.append((float(clean), decimals))
    return found


def _source_values(rows, question):
    """Every number the answer may use: each cell, the numbers inside text cells (dates,
    seasons, names with digits), fractions as percentages, and the question's own numbers."""
    values = []
    for row in rows:
        for cell in row:
            if isinstance(cell, bool) or cell is None:
                continue
            if isinstance(cell, (int, float)):
                values.append(float(cell))
                if -1 <= cell <= 1:
                    values.append(float(cell) * 100)  # 0.454 written as 45.4%
            else:
                values.extend(v for v, _ in numbers_in(str(cell)))
    values.extend(v for v, _ in numbers_in(question))
    return values


def _matches(value, decimals, source):
    """`value`, written with `decimals` places, is `source` rounded to that many places."""
    return abs(source - value) <= 0.5 * 10**-decimals + 1e-9


def ungrounded_numbers(answer, rows, question=""):
    """The numbers in `answer` that aren't in the query results or the question."""
    sources = _source_values(rows, question)
    missing = []
    for value, decimals in numbers_in(answer):
        if not any(_matches(value, decimals, s) for s in sources):
            missing.append(value)
    return missing


def number_spans(answer, rows, question=""):
    """Where each number sits in `answer`, for the web app to mark: a list of
    (start, end, in_rows, grounded). `in_rows` numbers came from the query results;
    `grounded` ones came from the results or the question, so the check allows them."""
    from_rows = _source_values(rows, "")
    from_question = [v for v, _ in numbers_in(question)]
    spans = []
    for m in NUMBER.finditer(answer):
        found = numbers_in(m.group())
        if not found:
            continue
        value, decimals = found[0]
        in_rows = any(_matches(value, decimals, s) for s in from_rows)
        grounded = in_rows or any(_matches(value, decimals, s) for s in from_question)
        spans.append((m.start(), m.end(), in_rows, grounded))
    return spans
