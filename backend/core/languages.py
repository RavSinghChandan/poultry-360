"""Languages the app speaks, and how a string carries all of them.

WHY THIS EXISTS
---------------
The first two features hardcoded two languages into their field names:
`name_en`, `note_hi`. That works for exactly two languages and breaks the
moment a third is needed — and a poultry farmer in West Bengal does not read
Hindi any more than one in Bihar reads Bengali.

A `Text` is a mapping from language code to string. Features write one; the
platform picks the reader's language at the edge. Adding a language is adding
entries to a dict, not editing every feature.

FALLBACK
--------
Never show a farmer an empty screen because a translation is missing. Each
language declares what to fall back to, ending at English, which every entry
must have. A missing Bhojpuri string shows the Hindi one rather than nothing,
because a Bhojpuri speaker can very likely read Hindi — that chain is a
linguistic judgement, written down here rather than scattered through the code.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    name_native: str        # what a speaker calls their own language
    name_en: str
    fallback: str | None    # tried when this language has no string


# Ordered as shown in the language picker. Bengali first: it is the default.
LANGUAGES: dict[str, Language] = {
    "bn": Language("bn", "বাংলা", "Bengali", "en"),
    "hi": Language("hi", "हिन्दी", "Hindi", "en"),
    "bho": Language("bho", "भोजपुरी", "Bhojpuri", "hi"),
    "mai": Language("mai", "मैथिली", "Maithili", "hi"),
    "en": Language("en", "English", "English", None),
}

DEFAULT_LANGUAGE = "bn"
FALLBACK_LANGUAGE = "en"

# A Text maps language code -> string. Not every code need be present.
Text = dict[str, str]


def normalise(code: str | None) -> str:
    """Map a requested code to one we actually speak.

    Accepts things a browser sends: "bn-IN", "HI", "en-GB".
    """
    if not code:
        return DEFAULT_LANGUAGE
    code = code.strip().lower().replace("_", "-")
    if code in LANGUAGES:
        return code
    base = code.split("-")[0]
    if base in LANGUAGES:
        return base
    return DEFAULT_LANGUAGE


def resolve(text: Text, language: str) -> str:
    """The best available string for this reader.

    Walks the fallback chain, so a missing Bhojpuri string yields Hindi, then
    English. Returns "" only if the Text is empty, which selfcheck catches.
    """
    if not text:
        return ""
    seen: set[str] = set()
    code: str | None = normalise(language)
    while code and code not in seen:
        if text.get(code):
            return text[code]
        seen.add(code)
        entry = LANGUAGES.get(code)
        code = entry.fallback if entry else None
    if text.get(FALLBACK_LANGUAGE):
        return text[FALLBACK_LANGUAGE]
    return next(iter(text.values()), "")


def missing_languages(text: Text, required: tuple[str, ...] = (FALLBACK_LANGUAGE,)) -> list[str]:
    """Which required languages this Text lacks. For selfcheck()."""
    return [code for code in required if not text.get(code)]


def catalogue() -> list[dict]:
    """The picker's contents, for /api/languages."""
    return [
        {
            "code": lang.code,
            "native": lang.name_native,
            "english": lang.name_en,
            "default": lang.code == DEFAULT_LANGUAGE,
        }
        for lang in LANGUAGES.values()
    ]
