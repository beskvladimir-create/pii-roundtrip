"""A local neural model as a detector (Ollama, temperature 0, no thinking mode).

The model returns JSON with a list of the values and types it found; the values are
searched for in the text (all occurrences). Long documents are split into windows.
"""

from __future__ import annotations

import json
import re
import urllib.request

from bench.runners.base import Runner, Span, resolve_overlaps
from bench.runners.chunking import chunks

OLLAMA = "http://127.0.0.1:11434/api/chat"

TYPES = {
    "PERSON": "full or partial personal name, including initials forms like 'Иванов И.И.'",
    "ADDRESS": "postal address or any part of it (city, street, house, postcode)",
    "ORG": "organisation or company name",
    "PHONE": "phone number",
    "EMAIL": "email address",
    "DATE_OF_BIRTH": "date of birth",
    "PASSPORT_RU": "Russian passport series and number",
    "SNILS": "Russian SNILS",
    "INN": "Russian INN (taxpayer number)",
    "BANK_ACCOUNT_RU": "Russian bank account (20 digits)",
    "CARD": "bank card number",
    "NHS": "UK NHS number",
    "NINO": "UK National Insurance number",
    "IBAN": "IBAN or other bank account number",
    "OTHER_ID": "any other personal identifier (document, policy, customer, licence number)",
}

PROMPT = """You are a PII detector. Find ALL personal data in the text below.
Return JSON: {{"entities": [{{"type": TYPE, "value": EXACT_SUBSTRING}}]}}.
TYPE is one of: {types}.
Rules: VALUE must be copied character-for-character from the text. List every occurrence form separately
(e.g. a name in different grammatical cases). Recall matters more than precision: when unsure, include it.
Do not explain.

TEXT:
{text}"""


class LlmDetector(Runner):
    name = "llm_detector"

    def __init__(self, model: str = "qwen3.5:9b"):
        self.model = model
        self.name = f"llm_detector_{model.replace(':', '_').replace('.', '_')}"

    def config(self) -> dict:
        return {
            "backend": "ollama",
            "model": self.model,
            "temperature": 0,
            "think": False,
            "chunk_chars": 1200,
            "prompt": PROMPT,
        }

    def _ask(self, text: str) -> list[dict]:
        types = "; ".join(f"{k} ({v})" for k, v in TYPES.items())
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": PROMPT.format(types=types, text=text)}],
            "format": "json",
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "seed": 0, "num_ctx": 8192},
        }
        req = urllib.request.Request(
            OLLAMA, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=600) as r:
            content = json.loads(r.read())["message"]["content"]
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return []
        ents = data.get("entities", []) if isinstance(data, dict) else []
        return [e for e in ents if isinstance(e, dict) and isinstance(e.get("value"), str)]

    def detect(self, text: str, lang: str) -> list[Span]:
        spans: list[Span] = []
        for off, part in chunks(text):
            for e in self._ask(part):
                v = e["value"].strip()
                if len(v) < 2:
                    continue
                for m in re.finditer(re.escape(v), part):
                    spans.append(Span(str(e.get("type", "OTHER_ID")).upper(), off + m.start(), off + m.end()))
        return resolve_overlaps(spans)


class LlmDetectorGemma(LlmDetector):
    def __init__(self):
        super().__init__("gemma4:12b")
