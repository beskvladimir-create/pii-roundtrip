"""Assembles a document from fragments with exact annotation of entity positions."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from bench.generator import ids

STRUCTURED = {"PASSPORT_RU", "SNILS", "INN", "BANK_ACCOUNT_RU", "NHS", "NINO", "CARD", "IBAN"}
_ID_KIND = {
    "PASSPORT_RU": "passport_ru",
    "SNILS": "snils",
    "INN": "inn",
    "BANK_ACCOUNT_RU": "rs",
    "NHS": "nhs",
    "NINO": "nino",
    "CARD": "card",
    "IBAN": "iban",
}

_WORD = re.compile(r"[A-Za-zА-Яа-яЁё]{5,}")


@dataclass
class Noise:
    """Noise parameters. Zero noise for clean documents."""

    double_space: float = 0.0  # probability of doubling a space in ordinary text
    typo: float = 0.0  # probability of a typo in a word of ordinary text
    name_typo: float = 0.0  # probability of a typo in a name
    alt_format: float = 0.0  # probability of a non-standard way of writing a number
    hard_format: float = 0.0  # probability of a hard form: in words, with dots, with a digit typo


DIGIT_WORDS = {
    "ru": ("ноль", "один", "два", "три", "четыре", "пять", "шесть", "семь", "восемь", "девять"),
    "uk": ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"),
}


def hard_variant(rng: random.Random, surface: str, lang: str) -> str:
    """Hard form of a number: digits in words, groups separated by dots, a typo in one digit
    (the checksum no longer matches, but it is still personal data)."""
    kind = rng.choice(("words", "dots", "typo"))
    digits = [i for i, c in enumerate(surface) if c.isdigit()]
    if kind == "typo" and digits:
        i = rng.choice(digits)
        return surface[:i] + str((int(surface[i]) + rng.randint(1, 9)) % 10) + surface[i + 1 :]
    if kind == "dots":
        return re.sub(r"[ -]", ".", surface)
    if not surface.replace(" ", "").replace("-", "").isdigit():
        return re.sub(r"[ -]", ".", surface)  # alphanumeric ones (NI, IBAN) are not written in words
    words = DIGIT_WORDS[lang]
    groups = re.split(r"[ -]+", surface)
    return " - ".join(" ".join(words[int(c)] for c in g) for g in groups)


@dataclass
class Doc:
    rng: random.Random
    noise: Noise
    lang: str = "ru"
    _parts: list[str] = field(default_factory=list)
    _len: int = 0
    entities: list[dict] = field(default_factory=list)

    def t(self, s: str) -> Doc:
        s = self._noisy_text(s)
        self._parts.append(s)
        self._len += len(s)
        return self

    def e(
        self,
        etype: str,
        surface: str,
        canonical: str | None = None,
        pid: str | None = None,
        quasi: bool = False,
    ) -> Doc:
        if etype in STRUCTURED:
            canonical = canonical or ids_canonical(etype, surface)
            variants = ids.format_variants(_ID_KIND[etype], canonical)
            surface = variants[0]
            if self.rng.random() < self.noise.alt_format:
                surface = self.rng.choice(variants[1:] or variants)
            if self.noise.hard_format and self.rng.random() < self.noise.hard_format:
                surface = hard_variant(self.rng, surface, self.lang)
                if any(c.isdigit() for c in surface):
                    canonical = ids_canonical(etype, surface)
        elif etype == "PERSON" and self.rng.random() < self.noise.name_typo:
            surface = _typo(self.rng, surface)
        start = self._len
        self._parts.append(surface)
        self._len += len(surface)
        ent = {"type": etype, "start": start, "end": self._len, "value": surface}
        ent["canonical"] = canonical if canonical is not None else surface
        if pid:
            ent["person_id"] = pid
        if quasi:
            ent["quasi"] = True
        self.entities.append(ent)
        return self

    def text(self) -> str:
        return "".join(self._parts)

    def _noisy_text(self, s: str) -> str:
        n = self.noise
        if n.typo:
            s = _WORD.sub(lambda m: _typo(self.rng, m.group()) if self.rng.random() < n.typo else m.group(), s)
        if n.double_space:
            s = re.sub(r"(?<=\S) (?=\S)", lambda m: "  " if self.rng.random() < n.double_space else " ", s)
        return s


def ids_canonical(etype: str, value: str) -> str:
    if etype in ("NINO", "IBAN"):
        return "".join(value.split()).upper()
    return "".join(c for c in value if c.isdigit())


def _typo(rng: random.Random, word: str) -> str:
    """Swaps two adjacent letters inside a word (not the first letter)."""
    letters = [i for i in range(1, len(word) - 1) if word[i].isalpha() and word[i + 1].isalpha()]
    if not letters:
        return word
    i = rng.choice(letters)
    return word[:i] + word[i + 1] + word[i] + word[i + 2 :]
