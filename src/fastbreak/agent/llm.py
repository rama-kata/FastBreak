import time
from dataclasses import dataclass

import httpx

OLLAMA_URL = "http://localhost:11434"
# Ollama's default context is 4,096 tokens. A thinking reply can run past 9,000, and past
# the context Ollama silently drops the oldest text, which can be the schema in the prompt.
CONTEXT_TOKENS = 16_384
MAX_REPLY_TOKENS = {False: 2_048, True: 12_000}  # by whether thinking is on


class LLMError(Exception):
    """Raised when the model can't be reached or returns an error."""


@dataclass(frozen=True)
class Reply:
    text: str
    thinking: str
    prompt_tokens: int
    output_tokens: int
    seconds: float
    cut_off: bool = False  # the reply hit the token cap before it finished


class Ollama:
    """A chat model served by the local Ollama, called over its HTTP API.

    Temperature 0, so the same prompt gives the same reply as far as the model allows.
    `think` turns qwen3's reasoning on or off; the reasoning comes back separately from
    the reply. `keep_alive` says how long Ollama keeps the model loaded after the last call.
    """

    def __init__(self, model, think=False, url=OLLAMA_URL, timeout=600, keep_alive="10m"):
        self.model = model
        self.think = think
        self.keep_alive = keep_alive
        self.client = httpx.Client(base_url=url, timeout=timeout)

    @property
    def name(self):
        return f"{self.model}{' (thinking)' if self.think else ''}"

    def chat(self, messages):
        body = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": self.think,
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": 0,
                "num_ctx": CONTEXT_TOKENS,
                "num_predict": MAX_REPLY_TOKENS[bool(self.think)],
            },
        }
        start = time.monotonic()
        try:
            response = self.client.post("/api/chat", json=body)
            response.raise_for_status()
        except httpx.HTTPError as e:
            raise LLMError(f"{self.model}: {e}") from e
        data = response.json()
        if data.get("error"):
            raise LLMError(f"{self.model}: {data['error']}")
        message = data.get("message", {})
        return Reply(
            text=message.get("content", ""),
            thinking=message.get("thinking") or "",
            prompt_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            seconds=time.monotonic() - start,
            cut_off=data.get("done_reason") == "length",
        )
