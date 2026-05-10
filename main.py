#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "data" / "raw.html"
DEFAULT_OUTPUT = ROOT / "output" / "bdb.html"
DEFAULT_ENTRIES_OUTPUT = ROOT / "output" / "entries.html"
DEFAULT_LEXICAL_INDEX = ROOT / "data" / "LexicalIndex.xml"
BWHEBB_TSV = ROOT / "data" / "bhwebb-unicode-map.tsv"
BWHEBB_AUTHORITATIVE = ROOT / "fixtures" / "bwhebb_authoritative_map.json"
BWHEBB_OVERRIDES = ROOT / "fixtures" / "bwhebb_overrides.json"
BWHEBB_X_AS_TSADI = ROOT / "fixtures" / "bwhebb_x_as_tsadi.json"
SCRIPT_OVERRIDES = ROOT / "fixtures" / "script_overrides.json"
XBR_OVERRIDES = ROOT / "fixtures" / "xbr_overrides.json"
ENTRY_BDB_OVERRIDES = ROOT / "fixtures" / "entry_bdb_overrides.json"

SPECIAL_SPAN_CLASSES = {
    "Bwhebb",
    "greek",
    "arabic",
    "syriac",
    "ethiopic",
    "samaritan",
    "persian",
}

DIAGNOSTIC_SCRIPT_CLASSES = ("arabic", "syriac", "ethiopic", "samaritan", "persian", "greek")
ESCAPED_TAG_LEAK_PATTERNS = (
    '&lt;span class="arabic"&gt;',
    '&lt;span class="Bwhebb"&gt;',
    "&lt;em&gt;",
    "&lt;/em&gt;",
    "&lt;strong&gt;",
    "&lt;/strong&gt;",
)

HEBREW_LETTERS = tuple(chr(codepoint) for codepoint in range(0x05D0, 0x05EB))
HEBREW_LETTER_SET = set(HEBREW_LETTERS)
HEBREW_COMBINING_MARKS = set(chr(codepoint) for codepoint in range(0x0591, 0x05C8))
HEBREW_CLUSTER_TRAILERS = HEBREW_COMBINING_MARKS | {"\u05be", "\u05c0", "\u05c3", "\u05f3", "\u05f4"}
HEBREW_CLUSTER_PATTERN = re.compile(r"[\u05d0-\u05ea][\u0591-\u05c7\u05be\u05c0\u05c3\u05f3\u05f4]*")
GREEK_MARKS = {
    "/": "\u0301",
    "\\": "\u0300",
    "=": "\u0342",
    ")": "\u0313",
    "(": "\u0314",
    "|": "\u0345",
    "+": "\u0308",
}

GREEK_BASE_MAP = {
    "a": "α",
    "b": "β",
    "g": "γ",
    "d": "δ",
    "e": "ε",
    "z": "ζ",
    "h": "η",
    "q": "θ",
    "i": "ι",
    "k": "κ",
    "l": "λ",
    "m": "μ",
    "n": "ν",
    "c": "ξ",
    "o": "ο",
    "p": "π",
    "r": "ρ",
    "s": "σ",
    "t": "τ",
    "u": "υ",
    "f": "φ",
    "x": "χ",
    "y": "ψ",
    "w": "ω",
    "v": "ς",
    "j": "ϳ",
}

ARABIC_DIGRAPH_MAP = {
    "h.": "ح",
    "s.": "ص",
    "d.": "ض",
    "t.": "ط",
    "z.": "ظ",
    "h;": "ة",
}

ARABIC_CONSONANT_MAP = {
    "b": "ب",
    "t": "ت",
    "3": "ث",
    "j": "ج",
    "g": "غ",
    "x": "خ",
    "d": "د",
    "r": "ر",
    "z": "ز",
    "s": "س",
    "4": "ش",
    "9": "ع",
    "f": "ف",
    "q": "ق",
    "k": "ك",
    "l": "ل",
    "m": "م",
    "n": "ن",
    "h": "ه",
    "w": "و",
    "y": "ي",
    "p": "پ",
    "c": "چ",
    "v": "ڤ",
}

ARABIC_VOWEL_MARKS = {
    "a": "َ",
    "u": "ُ",
    "i": "ِ",
    "o": "ْ",
}

ARABIC_TANWEEN_MARKS = {
    "a": "ً",
    "u": "ٌ",
    "i": "ٍ",
}

ARABIC_IGNORABLE_TOKENS = {"-", "!", "*"}

SYRIAC_CONSONANT_MAP = {
    "0": "ܐ",
    "3": "ܥ",
    "b": "ܒ",
    "g": "ܓ",
    "g.": "ܓ",
    "d": "ܕ",
    "d.": "ܕ",
    "h": "ܗ",
    "w": "ܘ",
    "z": "ܙ",
    "h.": "ܚ",
    "t.": "ܛ",
    "y": "ܝ",
    "k": "ܟ",
    "l": "ܠ",
    "m": "ܡ",
    "n": "ܢ",
    "s": "ܣ",
    "9": "ܥ",
    "p": "ܦ",
    "s.": "ܨ",
    "q": "ܩ",
    "q.": "ܩ",
    "r": "ܪ",
    "4": "ܫ",
    "t": "ܬ",
}

SYRIAC_VOWELS = {"a", "e", "i", "o", "u"}

ETHIOPIC_SERIES = {
    "0": ("አ", "ኡ", "ኢ", "ኣ", "ኤ", "እ", "ኦ"),
    "9": ("ዐ", "ዑ", "ዒ", "ዓ", "ዔ", "ዕ", "ዖ"),
    "h": ("ሀ", "ሁ", "ሂ", "ሃ", "ሄ", "ህ", "ሆ"),
    "l": ("ለ", "ሉ", "ሊ", "ላ", "ሌ", "ል", "ሎ"),
    "h.": ("ሐ", "ሑ", "ሒ", "ሓ", "ሔ", "ሕ", "ሖ"),
    "m": ("መ", "ሙ", "ሚ", "ማ", "ሜ", "ም", "ሞ"),
    "4": ("ሠ", "ሡ", "ሢ", "ሣ", "ሤ", "ሥ", "ሦ"),
    "r": ("ረ", "ሩ", "ሪ", "ራ", "ሬ", "ር", "ሮ"),
    "s": ("ሰ", "ሱ", "ሲ", "ሳ", "ሴ", "ስ", "ሶ"),
    "3": ("ሸ", "ሹ", "ሺ", "ሻ", "ሼ", "ሽ", "ሾ"),
    "q": ("ቀ", "ቁ", "ቂ", "ቃ", "ቄ", "ቅ", "ቆ"),
    "b": ("በ", "ቡ", "ቢ", "ባ", "ቤ", "ብ", "ቦ"),
    "t": ("ተ", "ቱ", "ቲ", "ታ", "ቴ", "ት", "ቶ"),
    "x": ("ኀ", "ኁ", "ኂ", "ኃ", "ኄ", "ኅ", "ኆ"),
    "n": ("ነ", "ኑ", "ኒ", "ና", "ኔ", "ን", "ኖ"),
    "k": ("ከ", "ኩ", "ኪ", "ካ", "ኬ", "ክ", "ኮ"),
    "w": ("ወ", "ዉ", "ዊ", "ዋ", "ዌ", "ው", "ዎ"),
    "z": ("ዘ", "ዙ", "ዚ", "ዛ", "ዜ", "ዝ", "ዞ"),
    "z.": ("ዘ", "ዙ", "ዚ", "ዛ", "ዜ", "ዝ", "ዞ"),
    "z'": ("ዠ", "ዡ", "ዢ", "ዣ", "ዤ", "ዥ", "ዦ"),
    "y": ("የ", "ዩ", "ዪ", "ያ", "ዬ", "ይ", "ዮ"),
    "d": ("ደ", "ዱ", "ዲ", "ዳ", "ዴ", "ድ", "ዶ"),
    "d.": ("ደ", "ዱ", "ዲ", "ዳ", "ዴ", "ድ", "ዶ"),
    "j": ("ጀ", "ጁ", "ጂ", "ጃ", "ጄ", "ጅ", "ጆ"),
    "g": ("ገ", "ጉ", "ጊ", "ጋ", "ጌ", "ግ", "ጎ"),
    "t.": ("ጠ", "ጡ", "ጢ", "ጣ", "ጤ", "ጥ", "ጦ"),
    "t'": ("ጠ", "ጡ", "ጢ", "ጣ", "ጤ", "ጥ", "ጦ"),
    "c": ("ጨ", "ጩ", "ጪ", "ጫ", "ጬ", "ጭ", "ጮ"),
    "q.": ("ቀ", "ቁ", "ቂ", "ቃ", "ቄ", "ቅ", "ቆ"),
    "q=": ("ቀ", "ቁ", "ቂ", "ቃ", "ቄ", "ቅ", "ቆ"),
    "s.": ("ጸ", "ጹ", "ጺ", "ጻ", "ጼ", "ጽ", "ጾ"),
    "s'": ("ፀ", "ፁ", "ፂ", "ፃ", "ፄ", "ፅ", "ፆ"),
    "f": ("ፈ", "ፉ", "ፊ", "ፋ", "ፌ", "ፍ", "ፎ"),
    "p": ("ፐ", "ፑ", "ፒ", "ፓ", "ፔ", "ፕ", "ፖ"),
}

ETHIOPIC_LABIALIZED_SERIES = {
    "k=": {
        "a": "ኰ",
        "i": "ኲ",
        "4": "ኳ",
        "e": "ኴ",
        "u": "ኵ",
        "": "ኵ",
    },
    "q=": {
        "a": "ቈ",
        "i": "ቊ",
        "4": "ቋ",
        "e": "ቌ",
        "u": "ቍ",
        "": "ቍ",
    },
    "w=": {
        "a": "ዋ",
        "i": "ዊ",
        "4": "ዋ",
        "e": "ዌ",
        "u": "ው",
        "": "ው",
    },
}

ETHIOPIC_ORDER_BY_MARKER = {
    "a": 0,
    "u": 1,
    "i": 2,
    "4": 3,
    "e": 4,
    "": 5,
    "o": 6,
}

ETHIOPIC_DIGRAPHS = ("h.", "s.", "d.", "t.", "z.", "s'", "z'", "t'", "q=", "k=", "w=")

SAMARITAN_CONSONANT_MAP = {
    "0": "ࠀ",
    "b": "ࠁ",
    "g": "ࠂ",
    "d": "ࠃ",
    "h": "ࠄ",
    "w": "ࠅ",
    "z": "ࠆ",
    "h.": "ࠇ",
    "t.": "ࠈ",
    "y": "ࠉ",
    "k": "ࠊ",
    "l": "ࠋ",
    "m": "ࠌ",
    "n": "ࠍ",
    "s": "ࠎ",
    "9": "ࠏ",
    "p": "ࠐ",
    "s.": "ࠑ",
    "q": "ࠒ",
    "r": "ࠓ",
    "4": "ࠔ",
    "t": "ࠕ",
}

ASCII_PLACEHOLDER_MAP = {
    "arabic": [
        ("h.", "ḥ"),
        ("s.", "ṣ"),
        ("d.", "ḍ"),
        ("t.", "ṭ"),
        ("z.", "ẓ"),
        ("g.", "ġ"),
        ("4", "š"),
        ("3", "ʿ"),
        ("0", "ʾ"),
        ("'", "ʾ"),
        ("’", "ʾ"),
    ],
    "syriac": [
        ("h.", "ḥ"),
        ("s.", "ṣ"),
        ("t.", "ṭ"),
        ("q.", "q"),
        ("9", "ʿ"),
        ("0", "ʾ"),
        ("'", "ʾ"),
        ("’", "ʾ"),
    ],
    "ethiopic": [
        ("s'", "ś"),
        ("z'", "ź"),
        ("4", "š"),
        ("3", "ʿ"),
        ("0", "ʾ"),
        ("'", "ʾ"),
        ("’", "ʾ"),
    ],
    "samaritan": [
        ("9", "ʿ"),
        ("0", "ʾ"),
        ("'", "ʾ"),
        ("’", "ʾ"),
    ],
    "persian": [
        ("4", "š"),
        ("0", "ʾ"),
        ("'", "ʾ"),
        ("’", "ʾ"),
    ],
}

# Some legacy <xbr> tags in the source wrap bibliography page numbers or years
# that only resemble scripture refs. Keep the clickable ref treatment for
# structurally plausible citations and fall back to plain text otherwise.
BOOK_CHAPTER_LIMITS = {
    "GE": 50,
    "GN": 50,
    "EX": 40,
    "LE": 27,
    "LV": 27,
    "NU": 36,
    "DE": 34,
    "DT": 34,
    "JOS": 24,
    "JO": 24,
    "JDG": 21,
    "RU": 4,
    "1SA": 31,
    "2SA": 24,
    "1KI": 22,
    "2KI": 25,
    "1CH": 29,
    "2CH": 36,
    "EZ": 10,
    "EZR": 10,
    "NE": 13,
    "ES": 10,
    "JOB": 42,
    "PS": 150,
    "PR": 31,
    "EC": 12,
    "SO": 8,
    "IS": 66,
    "JE": 52,
    "LA": 5,
    "EZE": 48,
    "DA": 12,
    "HO": 14,
    "JOE": 4,
    "AM": 9,
    "OB": 1,
    "JON": 4,
    "MIC": 7,
    "NA": 3,
    "HAB": 3,
    "HAG": 2,
    "ZEC": 14,
    "ZEP": 3,
    "MAL": 4,
    "MT": 28,
    "MK": 16,
    "LU": 24,
    "JN": 21,
    "AC": 28,
    "RO": 16,
    "1CO": 16,
    "GA": 6,
    "EPH": 6,
    "PHP": 4,
    "TIT": 3,
    "HEB": 13,
    "JAM": 5,
    "1PE": 5,
    "2PE": 3,
    "1JN": 5,
    "REV": 22,
    "TOB": 14,
    "JUD": 16,
    "WIS": 19,
    "SIR": 51,
    "BAR": 6,
    "BEL": 1,
    "1MA": 16,
    "2MA": 15,
}

SINGLE_CHAPTER_BOOK_VERSE_LIMITS = {
    "OB": 21,
    "BEL": 42,
}

SIMPLE_SCRIPTURE_REF_PATTERN = re.compile(
    r"^(?P<book>[1-3]?[A-Za-z]+)\.?\s+(?P<chapter>\d+)(?::(?P<verse>\d+))?(?P<suffix>[a-z]?)$"
)
CHAPTER_RANGE_PATTERN = re.compile(r"^(?P<book>[1-3]?[A-Za-z]+)\.?\s+(?P<start>\d+)-(?P<end>\d+)$")
CHAPTER_TO_VERSE_RANGE_PATTERN = re.compile(
    r"^(?P<book>[1-3]?[A-Za-z]+)\.?\s+(?P<start>\d+)-(?P<end>\d+):(?P<verse>\d+)$"
)
VERSE_RANGE_PATTERN = re.compile(
    r"^(?P<book>[1-3]?[A-Za-z]+)\.?\s+(?P<chapter>\d+):(?P<start>\d+)-(?P<end>\d+)$"
)
CROSS_CHAPTER_RANGE_PATTERN = re.compile(
    r"^(?P<book>[1-3]?[A-Za-z]+)\.?\s+(?P<start_chapter>\d+):(?P<start_verse>\d+)-(?P<end_chapter>\d+):(?P<end_verse>\d+)$"
)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_entry_bdb_overrides(path: Path) -> dict[int, str]:
    raw_overrides = load_json(path)
    if not raw_overrides:
        return {}
    if not isinstance(raw_overrides, dict):
        raise ValueError(f"{path} must contain a JSON object mapping entry numbers to BDB codes.")

    overrides: dict[int, str] = {}
    for raw_entrynum, raw_bdb in raw_overrides.items():
        if not isinstance(raw_entrynum, str) or not raw_entrynum.isdigit():
            raise ValueError(f"{path} has an invalid entry number key: {raw_entrynum!r}")
        if not isinstance(raw_bdb, str) or not raw_bdb.strip():
            raise ValueError(f"{path} has an invalid BDB code for entry {raw_entrynum!r}: {raw_bdb!r}")
        overrides[int(raw_entrynum)] = raw_bdb.strip()
    return overrides


def load_bwhebb_x_as_tsadi(path: Path) -> tuple[dict[str, tuple[int, ...]], dict[int, dict[str, tuple[int, ...]]]]:
    raw_overrides = load_json(path)

    def valid_positions(key: str, raw_positions: object) -> tuple[int, ...] | None:
        if not isinstance(key, str) or "x" not in key or not isinstance(raw_positions, list):
            return None
        positions = tuple(
            sorted(
                {
                    position
                    for position in raw_positions
                    if isinstance(position, int) and 0 <= position < len(key) and key[position] == "x"
                }
            )
        )
        return positions

    global_profiles: dict[str, tuple[int, ...]] = {}
    for key, raw_positions in raw_overrides.get("global_profiles", {}).items():
        positions = valid_positions(key, raw_positions)
        if positions is not None:
            global_profiles[key] = positions

    entry_profiles: dict[int, dict[str, tuple[int, ...]]] = {}
    for raw_entrynum, raw_profiles in raw_overrides.get("entry_profiles", {}).items():
        if not raw_entrynum.isdigit() or not isinstance(raw_profiles, dict):
            continue
        profiles = {
            key: positions
            for key, raw_positions in raw_profiles.items()
            if (positions := valid_positions(key, raw_positions)) is not None
        }
        if profiles:
            entry_profiles[int(raw_entrynum)] = profiles

    # Backward compatibility for the first small hand-written fixture. These old
    # entries only represented words with one ambiguous x, so all x positions are
    # the intended tsadi positions.
    for skeleton in raw_overrides.get("global_skeletons", []):
        if isinstance(skeleton, str) and "x" in skeleton:
            global_profiles.setdefault(skeleton, tuple(i for i, character in enumerate(skeleton) if character == "x"))
    for raw_entrynum, raw_skeletons in raw_overrides.get("entry_skeletons", {}).items():
        if not raw_entrynum.isdigit() or not isinstance(raw_skeletons, list):
            continue
        profiles = entry_profiles.setdefault(int(raw_entrynum), {})
        for skeleton in raw_skeletons:
            if isinstance(skeleton, str) and "x" in skeleton:
                profiles.setdefault(skeleton, tuple(i for i, character in enumerate(skeleton) if character == "x"))

    return global_profiles, entry_profiles


def apply_codepoint_overrides(mapping: dict[str, str], overrides: dict[str, str]) -> None:
    for source, target in overrides.items():
        if re.fullmatch(r"0x[0-9A-Fa-f]+", source):
            mapping[chr(int(source, 16))] = target
            continue
        mapping[source] = target


def load_bwhebb_map(tsv_path: Path, authoritative_path: Path, overrides_path: Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    lines = tsv_path.read_text(encoding="utf-8").splitlines()
    for line in lines[1:]:
        if not line.strip():
            continue
        source, target = line.split("\t", 1)
        source_char = chr(int(source, 16))
        codepoints = re.findall(r"u_([0-9A-Fa-f]{4,6})", target)
        mapping[source_char] = "".join(chr(int(codepoint, 16)) for codepoint in codepoints)

    apply_codepoint_overrides(mapping, load_json(authoritative_path))
    apply_codepoint_overrides(mapping, load_json(overrides_path))
    return mapping


def bwhebb_source_key(text: str, bwhebb_map: dict[str, str]) -> str:
    key: list[str] = []
    for character in text:
        mapped = bwhebb_map.get(character, "")
        if any(is_hebrew_letter(mapped_character) for mapped_character in mapped):
            key.append(character)
    return "".join(key)


def source_parts(text: str) -> list[str]:
    return re.split(r"([\s-]+)", text)


def clean_comment(content: str) -> str:
    stripped = content.strip()
    if stripped.startswith("<~?~>"):
        return ""
    if stripped in {"</>", "<cbr>", "</cbr>", "~"}:
        return ""
    if stripped.startswith("&") and stripped.endswith(";"):
        return ""
    if stripped.startswith('<span class="Bwhebb">') or stripped.startswith("<span class='Bwhebb'>"):
        return ""
    if stripped.startswith("<"):
        return content
    if stripped and not re.search(r"\s", stripped) and len(stripped) <= 16:
        return content
    if stripped and stripped.isdigit():
        return content
    if stripped == "o":
        return content
    return ""


def normalize_raw_html(raw_html: str) -> str:
    normalized = re.sub(r"<!--(.*?)-->", lambda match: clean_comment(match.group(1)), raw_html, flags=re.S)
    normalized = normalized.replace("<arabic>", '<span class="arabic">').replace("</arabic>", "</span>")
    normalized = re.sub(r"<img\b[^>]*?/?>", "", normalized)
    normalized = normalized.replace("<head></head>", '<head><meta charset="utf-8"/></head>')
    return normalized


def is_hebrew_letter(character: str) -> bool:
    return character in HEBREW_LETTER_SET


def normalize_hebrew_output(text: str) -> str:
    # Collapse impossible duplicate accents/vowels left by the legacy source map.
    normalized = re.sub(r"([\u0591-\u05c7])\1+", r"\1", text)
    # The raw encoding stores maqaf as its own backwards token, so after reversal it
    # ends up one cluster too far to the right unless we swap it back into position.
    normalized = re.sub(rf"({HEBREW_CLUSTER_PATTERN.pattern})\u05be", "־" + r"\1", normalized)
    return normalized


def convert_bwhebb_text(
    text: str,
    bwhebb_map: dict[str, str],
    overrides: dict[str, str],
    *,
    global_tsadi_profiles: dict[str, tuple[int, ...]] | None = None,
    entry_tsadi_profiles: dict[str, tuple[int, ...]] | None = None,
) -> str:
    exact_text = text.strip()
    if text in overrides:
        return overrides[text]
    if exact_text in overrides:
        return overrides[exact_text]
    decoded = html.unescape(exact_text)

    def tsadi_profile_for_key(key: str) -> tuple[int, ...] | None:
        if entry_tsadi_profiles and key in entry_tsadi_profiles:
            return entry_tsadi_profiles[key]
        if global_tsadi_profiles and key in global_tsadi_profiles:
            return global_tsadi_profiles[key]
        return None

    part_profiles = [
        (part, tsadi_profile_for_key(bwhebb_source_key(part, bwhebb_map)))
        for part in source_parts(decoded)
    ]
    should_apply_tsadi_override = any(positions is not None for _, positions in part_profiles)
    should_skip_exact_bwhebb_map = should_apply_tsadi_override and "x" in exact_text
    if not should_skip_exact_bwhebb_map and text in bwhebb_map:
        return bwhebb_map[text]
    if not should_skip_exact_bwhebb_map and exact_text in bwhebb_map:
        return bwhebb_map[exact_text]

    if not should_apply_tsadi_override:
        mapped = "".join(bwhebb_map.get(character, character) for character in decoded)
    else:
        mapped_parts: list[str] = []
        for part, tsadi_positions in part_profiles:
            consonant_index = 0
            mapped_characters: list[str] = []
            for character in part:
                mapped_character = bwhebb_map.get(character, character)
                is_source_consonant = any(is_hebrew_letter(mapped_part) for mapped_part in bwhebb_map.get(character, ""))
                if character == "x" and tsadi_positions is not None and consonant_index in tsadi_positions:
                    mapped_character = "צ"
                mapped_characters.append(mapped_character)
                if is_source_consonant:
                    consonant_index += 1
            mapped_parts.append("".join(mapped_characters))
        mapped = "".join(mapped_parts)

    tokens: list[str] = []
    current = ""
    for character in mapped:
        if is_hebrew_letter(character):
            if current:
                tokens.append(current)
            current = character
            continue

        if current and character in HEBREW_CLUSTER_TRAILERS:
            current += character
            continue

        if current:
            tokens.append(current)
            current = ""
        tokens.append(character)

    if current:
        tokens.append(current)

    return normalize_hebrew_output("".join(reversed(tokens)))


def normalize_script_text(text: str) -> str:
    cleaned = html.unescape(text)
    cleaned = cleaned.replace("<!--", "").replace("-->", "")
    cleaned = cleaned.replace("~", "")
    if "<" in cleaned:
        cleaned = cleaned.split("<", 1)[0]
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def convert_greek_text(text: str, overrides: dict[str, str]) -> str:
    normalized = normalize_script_text(text)
    if normalized in overrides:
        return overrides[normalized]

    parts = re.split(r"(\s+)", normalized)
    converted_parts = []
    for part in parts:
        if not part or part.isspace():
            converted_parts.append(part)
            continue
        converted_parts.append(convert_greek_word(part))
    return "".join(converted_parts)


def convert_greek_word(word: str) -> str:
    result: list[str] = []
    pending_marks: list[str] = []
    index = 0

    while index < len(word):
        character = word[index]
        if character in GREEK_MARKS:
            pending_marks.append(GREEK_MARKS[character])
            index += 1
            continue

        lower = character.lower()
        if lower in GREEK_BASE_MAP:
            letter = GREEK_BASE_MAP[lower]
            if character.isupper():
                letter = letter.upper()

            trailing_marks: list[str] = []
            lookahead = index + 1
            while lookahead < len(word) and word[lookahead] in GREEK_MARKS:
                trailing_marks.append(GREEK_MARKS[word[lookahead]])
                lookahead += 1

            if lower == "s" and lookahead >= len(word):
                letter = "ς" if character.islower() else "Σ"

            result.append(letter + "".join(pending_marks) + "".join(trailing_marks))
            pending_marks.clear()
            index = lookahead
            continue

        if pending_marks and result:
            result[-1] += "".join(pending_marks)
            pending_marks.clear()

        result.append(character)
        index += 1

    if pending_marks and result:
        result[-1] += "".join(pending_marks)

    return "".join(result)


def tokenize_arabic_word(word: str) -> list[str]:
    cleaned = word.replace("0’", "0").replace("0'", "0").replace("’", "'")
    tokens: list[str] = []
    index = 0
    while index < len(cleaned):
        chunk = cleaned[index : index + 2]
        if chunk in ARABIC_DIGRAPH_MAP:
            tokens.append(chunk)
            index += 2
            continue
        tokens.append(cleaned[index])
        index += 1
    return tokens


def is_arabic_consonant_token(token: str) -> bool:
    return token in ARABIC_DIGRAPH_MAP or token in ARABIC_CONSONANT_MAP


def append_arabic_mark(clusters: list[str], mark: str) -> None:
    if not clusters:
        clusters.append(mark)
        return
    clusters[-1] += mark


def apply_arabic_tanween(clusters: list[str], vowel: str) -> bool:
    if not clusters:
        return False
    vowel_mark = ARABIC_VOWEL_MARKS[vowel]
    tanween_mark = ARABIC_TANWEEN_MARKS[vowel]
    if clusters[-1].endswith(vowel_mark):
        clusters[-1] = clusters[-1][:-1] + tanween_mark
        return True
    if vowel == "a" and clusters[-1].endswith("ة"):
        clusters[-1] += tanween_mark
        return True
    return False


def convert_arabic_word(word: str, overrides: dict[str, str]) -> str:
    if word in overrides:
        return overrides[word]

    tokens = tokenize_arabic_word(word)
    clusters: list[str] = []
    index = 0

    while index < len(tokens):
        token = tokens[index]
        previous_token = tokens[index - 1] if index else ""
        next_token = tokens[index + 1] if index + 1 < len(tokens) else ""
        after_next = tokens[index + 2] if index + 2 < len(tokens) else ""

        if token in ARABIC_IGNORABLE_TOKENS:
            index += 1
            continue

        if token == "0":
            if previous_token in ARABIC_VOWEL_MARKS:
                if next_token:
                    if next_token in ARABIC_VOWEL_MARKS:
                        clusters.append("إ" if next_token == "i" else "أ")
                    elif next_token == "'":
                        clusters.append("ء")
                    else:
                        clusters.append("ء")
                else:
                    clusters.append("ء")
            else:
                if next_token == "i":
                    clusters.append("إ")
                elif next_token in {"a", "u"}:
                    clusters.append("أ")
                else:
                    clusters.append("ا")
            index += 1
            continue

        if token == "'":
            if previous_token == "0":
                index += 1
                continue
            clusters.append("ء")
            index += 1
            continue

        if token == "=":
            append_arabic_mark(clusters, "ّ")
            index += 1
            continue

        if token in ARABIC_VOWEL_MARKS:
            if token == "o":
                append_arabic_mark(clusters, ARABIC_VOWEL_MARKS[token])
                index += 1
                continue

            if next_token == "0" and (not after_next or is_arabic_consonant_token(after_next) or after_next in {"h;", " "}):
                append_arabic_mark(clusters, ARABIC_VOWEL_MARKS[token])
                if token == "a":
                    clusters.append("اء" if not after_next else "ا")
                elif token == "u":
                    clusters.append("و")
                else:
                    clusters.append("ي")
                index += 2
                continue

            append_arabic_mark(clusters, ARABIC_VOWEL_MARKS[token])
            index += 1
            continue

        if token == "n" and index == len(tokens) - 1 and previous_token in ARABIC_TANWEEN_MARKS:
            if apply_arabic_tanween(clusters, previous_token):
                index += 1
                continue

        if token in ARABIC_DIGRAPH_MAP:
            clusters.append(ARABIC_DIGRAPH_MAP[token])
            index += 1
            continue

        if token in ARABIC_CONSONANT_MAP:
            clusters.append(ARABIC_CONSONANT_MAP[token])
            index += 1
            continue

        if token in {",", ";", ":", "/", "\\", "(", ")", "[", "]"}:
            clusters.append(token)
            index += 1
            continue

        clusters.append(token)
        index += 1

    return "".join(clusters)


def convert_arabic_text(text: str, overrides: dict[str, str]) -> str:
    normalized = normalize_script_text(text)
    if normalized in overrides:
        return overrides[normalized]

    parts = re.split(r"(\s+)", normalized)
    converted_parts = []
    for part in parts:
        if not part or part.isspace():
            converted_parts.append(part)
            continue
        converted_parts.append(convert_arabic_word(part, overrides))
    return "".join(converted_parts)


def split_preserving_whitespace(text: str) -> list[str]:
    return re.split(r"(\s+)", text)


def tokenize_script_word(word: str, digraphs: tuple[str, ...]) -> list[str]:
    normalized = word.replace("’", "'")
    tokens: list[str] = []
    index = 0
    while index < len(normalized):
        for digraph in digraphs:
            if normalized.startswith(digraph, index):
                tokens.append(digraph)
                index += len(digraph)
                break
        else:
            tokens.append(normalized[index])
            index += 1
    return tokens


def convert_syriac_word(word: str, overrides: dict[str, str]) -> str:
    if word in overrides:
        return overrides[word]

    tokens = tokenize_script_word(word, ("h.", "s.", "d.", "t.", "q.", "g."))
    converted: list[str] = []
    for token in tokens:
        if token in SYRIAC_CONSONANT_MAP:
            converted.append(SYRIAC_CONSONANT_MAP[token])
            continue
        if token in SYRIAC_VOWELS or token in {".", "=", "*", "]", "["}:
            continue
        if token in {"(", ")", "-", ":"}:
            converted.append(token)
            continue
        if token == "'":
            continue
    return "".join(converted)


def convert_syriac_text(text: str, overrides: dict[str, str]) -> str:
    normalized = normalize_script_text(text).replace("’", "'")
    if normalized in overrides:
        return overrides[normalized]

    converted_parts: list[str] = []
    for part in split_preserving_whitespace(normalized):
        if not part or part.isspace():
            converted_parts.append(part)
            continue
        converted_parts.append(convert_syriac_word(part, overrides))
    return "".join(converted_parts)


def parse_ethiopic_consonant(word: str, index: int) -> tuple[str | None, int]:
    for digraph in ETHIOPIC_DIGRAPHS:
        if word.startswith(digraph, index):
            return digraph, index + len(digraph)
    character = word[index]
    if character in ETHIOPIC_SERIES:
        return character, index + 1
    if character == "4":
        return "4", index + 1
    return None, index


def is_ethiopic_consonant_start(word: str, index: int) -> bool:
    consonant, next_index = parse_ethiopic_consonant(word, index)
    if consonant is None:
        return False
    if consonant == "4" and index > 0:
        previous = word[index - 1]
        if previous not in {":", " ", "-", "("} and previous not in ETHIOPIC_ORDER_BY_MARKER:
            return False
    return next_index > index


def convert_ethiopic_word(word: str, overrides: dict[str, str]) -> str:
    if word in overrides:
        return overrides[word]

    normalized = word.replace("’", "'").replace("0'", "0")
    converted: list[str] = []
    index = 0
    while index < len(normalized):
        character = normalized[index]

        if character == ":":
            converted.append("፡")
            index += 1
            continue
        if character == "?":
            converted.append("፧")
            index += 1
            continue
        if character in {"(", ")", "-", "[", "]"}:
            converted.append(character)
            index += 1
            continue
        if character == "'":
            index += 1
            continue

        consonant, next_index = parse_ethiopic_consonant(normalized, index)
        if consonant is not None and is_ethiopic_consonant_start(normalized, index):
            marker = ""
            if next_index < len(normalized):
                next_character = normalized[next_index]
                if next_character in ETHIOPIC_ORDER_BY_MARKER and not (
                    next_character == "4" and not is_ethiopic_consonant_start(normalized, next_index)
                ):
                    marker = next_character
                    next_index += 1
            if consonant in ETHIOPIC_LABIALIZED_SERIES:
                converted.append(ETHIOPIC_LABIALIZED_SERIES[consonant].get(marker, ETHIOPIC_LABIALIZED_SERIES[consonant][""]))
            else:
                converted.append(ETHIOPIC_SERIES[consonant][ETHIOPIC_ORDER_BY_MARKER[marker]])
            index = next_index
            continue

        if character in ETHIOPIC_ORDER_BY_MARKER:
            converted.append(ETHIOPIC_SERIES["0"][ETHIOPIC_ORDER_BY_MARKER[character]])
            index += 1
            continue

        index += 1

    return "".join(converted)


def convert_ethiopic_text(text: str, overrides: dict[str, str]) -> str:
    normalized = normalize_script_text(text).replace("’", "'")
    if normalized in overrides:
        return overrides[normalized]

    converted_parts: list[str] = []
    for part in split_preserving_whitespace(normalized):
        if not part or part.isspace():
            converted_parts.append(part)
            continue
        converted_parts.append(convert_ethiopic_word(part, overrides))
    return "".join(converted_parts)


def convert_samaritan_word(word: str, overrides: dict[str, str]) -> str:
    if word in overrides:
        return overrides[word]

    tokens = tokenize_script_word(word, ("h.", "s.", "t."))
    converted: list[str] = []
    for token in tokens:
        if token in SAMARITAN_CONSONANT_MAP:
            converted.append(SAMARITAN_CONSONANT_MAP[token])
            continue
        if token in {"a", "e", "i", "o", "u", ".", "'"}:
            continue
    return "".join(converted)


def convert_samaritan_text(text: str, overrides: dict[str, str]) -> str:
    normalized = normalize_script_text(text).replace("’", "'")
    if normalized in overrides:
        return overrides[normalized]

    converted_parts: list[str] = []
    for part in split_preserving_whitespace(normalized):
        if not part or part.isspace():
            converted_parts.append(part)
            continue
        converted_parts.append(convert_samaritan_word(part, overrides))
    return "".join(converted_parts)


def convert_persian_text(text: str, overrides: dict[str, str]) -> str:
    normalized = normalize_script_text(text)
    if normalized in overrides:
        return overrides[normalized]

    converted_parts: list[str] = []
    for part in split_preserving_whitespace(normalized):
        if not part or part.isspace():
            converted_parts.append(part)
            continue
        converted_parts.append(overrides.get(part, part))
    return "".join(converted_parts)


def convert_placeholder_script_text(script: str, text: str, overrides: dict[str, dict[str, str]]) -> str:
    normalized = normalize_script_text(text)
    script_overrides = overrides.get(script, {})
    if normalized in script_overrides:
        return script_overrides[normalized]

    converted = normalized
    for source, target in ASCII_PLACEHOLDER_MAP.get(script, []):
        converted = converted.replace(source, target)
    converted = converted.replace("ʾʾ", "ʾ").replace("ʿʿ", "ʿ")
    return converted


def render_start_tag(tag: str, attrs: list[tuple[str, str | None]], self_closing: bool = False) -> str:
    rendered_attrs = []
    for key, value in attrs:
        if value is None:
            rendered_attrs.append(key)
            continue
        rendered_attrs.append(f'{key}="{html.escape(value, quote=True)}"')
    attr_blob = f" {' '.join(rendered_attrs)}" if rendered_attrs else ""
    closer = " /" if self_closing else ""
    return f"<{tag}{attr_blob}{closer}>"


def is_plausible_scripture_ref(target: str) -> bool:
    normalized = target.strip()

    def get_limits(book_token: str) -> tuple[str, int] | None:
        book = book_token.upper()
        max_chapters = BOOK_CHAPTER_LIMITS.get(book)
        if max_chapters is None:
            return None
        return book, max_chapters

    def is_valid_chapter(book: str, max_chapters: int, chapter: int) -> bool:
        if max_chapters == 1:
            max_verse = SINGLE_CHAPTER_BOOK_VERSE_LIMITS.get(book)
            return max_verse is None or 1 <= chapter <= max_verse
        return 1 <= chapter <= max_chapters

    def is_valid_verse(book: str, max_chapters: int, chapter: int, verse: int) -> bool:
        if verse < 1 or chapter < 1 or chapter > max_chapters:
            return False
        if max_chapters == 1:
            max_verse = SINGLE_CHAPTER_BOOK_VERSE_LIMITS.get(book)
            return chapter == 1 and (max_verse is None or verse <= max_verse)
        return True

    match = SIMPLE_SCRIPTURE_REF_PATTERN.fullmatch(normalized)
    if match:
        limits = get_limits(match.group("book"))
        if limits is None:
            return False
        book, max_chapters = limits
        chapter = int(match.group("chapter"))
        verse_text = match.group("verse")
        if verse_text is None:
            return is_valid_chapter(book, max_chapters, chapter)
        return is_valid_verse(book, max_chapters, chapter, int(verse_text))

    match = CHAPTER_RANGE_PATTERN.fullmatch(normalized)
    if match:
        limits = get_limits(match.group("book"))
        if limits is None:
            return False
        book, max_chapters = limits
        start = int(match.group("start"))
        end = int(match.group("end"))
        if start > end:
            return False
        if max_chapters == 1:
            max_verse = SINGLE_CHAPTER_BOOK_VERSE_LIMITS.get(book)
            return max_verse is None or (1 <= start <= end <= max_verse)
        return is_valid_chapter(book, max_chapters, start) and is_valid_chapter(book, max_chapters, end)

    match = CHAPTER_TO_VERSE_RANGE_PATTERN.fullmatch(normalized)
    if match:
        limits = get_limits(match.group("book"))
        if limits is None:
            return False
        book, max_chapters = limits
        start = int(match.group("start"))
        end = int(match.group("end"))
        verse = int(match.group("verse"))
        return start <= end and is_valid_chapter(book, max_chapters, start) and is_valid_verse(book, max_chapters, end, verse)

    match = VERSE_RANGE_PATTERN.fullmatch(normalized)
    if match:
        limits = get_limits(match.group("book"))
        if limits is None:
            return False
        book, max_chapters = limits
        chapter = int(match.group("chapter"))
        start = int(match.group("start"))
        end = int(match.group("end"))
        return start <= end and is_valid_verse(book, max_chapters, chapter, start) and is_valid_verse(
            book, max_chapters, chapter, end
        )

    match = CROSS_CHAPTER_RANGE_PATTERN.fullmatch(normalized)
    if match:
        limits = get_limits(match.group("book"))
        if limits is None:
            return False
        book, max_chapters = limits
        start_chapter = int(match.group("start_chapter"))
        start_verse = int(match.group("start_verse"))
        end_chapter = int(match.group("end_chapter"))
        end_verse = int(match.group("end_verse"))
        if (start_chapter, start_verse) > (end_chapter, end_verse):
            return False
        return is_valid_verse(book, max_chapters, start_chapter, start_verse) and is_valid_verse(
            book, max_chapters, end_chapter, end_verse
        )

    return False


class LexiconHTMLConverter(HTMLParser):
    def __init__(
        self,
        bwhebb_map: dict[str, str],
        script_overrides: dict[str, dict[str, str]],
        xbr_overrides: dict[str, str],
        global_x_as_tsadi_profiles: dict[str, tuple[int, ...]],
        entry_x_as_tsadi_profiles: dict[int, dict[str, tuple[int, ...]]],
    ):
        super().__init__(convert_charrefs=True)
        self.bwhebb_map = bwhebb_map
        self.script_overrides = script_overrides
        self.xbr_overrides = xbr_overrides
        self.global_x_as_tsadi_profiles = global_x_as_tsadi_profiles
        self.entry_x_as_tsadi_profiles = entry_x_as_tsadi_profiles
        self.output: list[str] = []
        self.capture_stack: list[dict] = []
        self.current_entrynum: int | None = None

    def append_text(self, text: str) -> None:
        if not text:
            return
        self.output.append(html.escape(text, quote=False))

    def handle_decl(self, decl: str) -> None:
        self.output.append(f"<!{decl}>")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.capture_stack:
            self.capture_stack[-1]["buffer"].append(render_start_tag(tag, attrs))
            return

        attr_map = dict(attrs)
        if tag == "img":
            return

        if tag == "strongs":
            self.capture_stack.append({"kind": "strongs", "buffer": []})
            return

        if tag == "entry":
            self.current_entrynum = None
            self.output.append(render_start_tag(tag, attrs))
            return

        if tag == "entrynum":
            self.capture_stack.append({"kind": "entrynum", "buffer": []})
            return

        if tag == "xbr":
            self.capture_stack.append({"kind": "xbr", "buffer": [], "target": attr_map.get("t", "")})
            return

        if tag == "span" and attr_map.get("class") in SPECIAL_SPAN_CLASSES:
            self.capture_stack.append(
                {
                    "kind": "span",
                    "class": attr_map.get("class"),
                    "attrs": attrs,
                    "buffer": [],
                }
            )
            return

        self.output.append(render_start_tag(tag, attrs))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "img":
            self.output.append(render_start_tag(tag, attrs, self_closing=True))

    def handle_endtag(self, tag: str) -> None:
        if self.capture_stack and self.capture_stack[-1]["kind"] == "strongs" and tag == "strongs":
            text = "".join(self.capture_stack.pop()["buffer"]).strip()
            self.output.append(f"<span class=\"strongs-number\">{html.escape(text, quote=False)}</span>")
            return

        if self.capture_stack and self.capture_stack[-1]["kind"] == "entrynum" and tag == "entrynum":
            text = "".join(self.capture_stack.pop()["buffer"]).strip()
            if text.isdigit():
                self.current_entrynum = int(text)
            self.output.append(f"<entrynum>{html.escape(text, quote=False)}</entrynum>")
            return

        if self.capture_stack and self.capture_stack[-1]["kind"] == "xbr" and tag == "xbr":
            capture = self.capture_stack.pop()
            text = "".join(capture["buffer"]).strip()
            target = self.xbr_overrides.get(capture["target"], capture["target"])
            if is_plausible_scripture_ref(target):
                escaped_target = html.escape(target, quote=True)
                self.output.append(
                    f"<span class=\"ref\" data-ref=\"{escaped_target}\">{html.escape(text, quote=False)}</span>"
                )
            else:
                self.output.append(html.escape(text, quote=False))
            return

        if self.capture_stack and self.capture_stack[-1]["kind"] == "span" and tag == "span":
            capture = self.capture_stack.pop()
            original_class = capture["class"]
            text = "".join(capture["buffer"])
            converted = self.convert_span_text(original_class, text)
            output_class = "hebrew" if original_class == "Bwhebb" else original_class.lower()
            self.output.append(f"<span class=\"{output_class}\">{html.escape(converted, quote=False)}</span>")
            return

        if self.capture_stack:
            self.capture_stack[-1]["buffer"].append(f"</{tag}>")
            return

        self.output.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if self.capture_stack:
            self.capture_stack[-1]["buffer"].append(data)
            return
        self.append_text(data)

    def handle_entityref(self, name: str) -> None:
        self.handle_data(html.unescape(f"&{name};"))

    def handle_charref(self, name: str) -> None:
        self.handle_data(html.unescape(f"&#{name};"))

    def convert_span_text(self, script_class: str, text: str) -> str:
        if script_class == "Bwhebb":
            return convert_bwhebb_text(
                text,
                self.bwhebb_map,
                self.script_overrides.get("Bwhebb", {}),
                global_tsadi_profiles=self.global_x_as_tsadi_profiles,
                entry_tsadi_profiles=self.entry_x_as_tsadi_profiles.get(self.current_entrynum),
            )
        if script_class == "greek":
            return convert_greek_text(text, self.script_overrides.get("greek", {}))
        if script_class == "arabic":
            return convert_arabic_text(text, self.script_overrides.get("arabic", {}))
        if script_class == "syriac":
            return convert_syriac_text(text, self.script_overrides.get("syriac", {}))
        if script_class == "ethiopic":
            return convert_ethiopic_text(text, self.script_overrides.get("ethiopic", {}))
        if script_class == "samaritan":
            return convert_samaritan_text(text, self.script_overrides.get("samaritan", {}))
        if script_class == "persian":
            return convert_persian_text(text, self.script_overrides.get("persian", {}))
        return convert_placeholder_script_text(script_class, text, self.script_overrides)

    def get_output(self) -> str:
        return "".join(self.output)


def convert_document(
    raw_html: str,
    bwhebb_map: dict[str, str],
    script_overrides: dict[str, dict[str, str]],
    xbr_overrides: dict[str, str],
    global_x_as_tsadi_profiles: dict[str, tuple[int, ...]],
    entry_x_as_tsadi_profiles: dict[int, dict[str, tuple[int, ...]]],
) -> str:
    parser = LexiconHTMLConverter(
        bwhebb_map=bwhebb_map,
        script_overrides=script_overrides,
        xbr_overrides=xbr_overrides,
        global_x_as_tsadi_profiles=global_x_as_tsadi_profiles,
        entry_x_as_tsadi_profiles=entry_x_as_tsadi_profiles,
    )
    parser.feed(normalize_raw_html(raw_html))
    parser.close()
    output = parser.get_output()
    if "<meta charset=" not in output:
        output = output.replace("<head>", '<head><meta charset="utf-8"/>', 1)
    if "<!DOCTYPE" not in output:
        output = "<!DOCTYPE html>\n" + output
    return output


def find_image_only_script_gaps(raw_html: str) -> tuple[int, list[str]]:
    image_pattern = re.compile(r'<img\b[^>]*?src="([^"]+)"[^>]*?>', re.I)
    gaps: list[str] = []
    for match in image_pattern.finditer(raw_html):
        start, end = match.span()
        window = raw_html[max(0, start - 220) : min(len(raw_html), end + 220)]
        if any(f'class="{script_class}"' in window for script_class in DIAGNOSTIC_SCRIPT_CLASSES):
            continue
        gaps.append(match.group(1))
    return len(gaps), gaps[:10]


def build_report(raw_html: str, converted_html: str) -> dict[str, object]:
    span_counts = {
        script_class: len(re.findall(rf'<span class="{script_class}">', converted_html))
        for script_class in ("hebrew", "greek", "arabic", "syriac", "ethiopic", "samaritan", "persian")
    }

    hebrew_pattern = re.compile(r'<span class="hebrew">([^<]*)</span>')
    bad_hebrew_spans: list[dict[str, object]] = []
    allowed_hebrew_punctuation = set("-־׀׃׳״+.,;:!?()[]{}…/\\\"'")
    for match in hebrew_pattern.finditer(converted_html):
        text = match.group(1)
        bad_chars = [
            character
            for character in text
            if not (
                ("\u0590" <= character <= "\u05FF")
                or character.isspace()
                or character in allowed_hebrew_punctuation
            )
        ]
        if bad_chars:
            bad_hebrew_spans.append(
                {
                    "text": text,
                    "bad_codepoints": [f"U+{ord(character):04X}" for character in bad_chars],
                }
            )

    hebrew_suspect_patterns = {
        "duplicate_combining_marks": re.compile(r"([\u0591-\u05c7])\1+"),
        "spaced_maqaf": re.compile(r"(?:\s\u05be|\u05be\s)"),
        "double_mem_sequences": re.compile(r"מּמ"),
    }
    hebrew_pattern_counts = {
        label: sum(
            1
            for match in hebrew_pattern.finditer(converted_html)
            if pattern.search(match.group(1))
        )
        for label, pattern in hebrew_suspect_patterns.items()
    }
    hebrew_pattern_examples = {
        label: [
            match.group(1)
            for match in hebrew_pattern.finditer(converted_html)
            if pattern.search(match.group(1))
        ][:10]
        for label, pattern in hebrew_suspect_patterns.items()
    }

    image_gap_count, image_gap_examples = find_image_only_script_gaps(raw_html)

    latin_artifact_counts: dict[str, int] = {}
    latin_artifact_examples: dict[str, list[str]] = {}
    for script_class in ("greek", "arabic", "syriac", "ethiopic", "samaritan", "persian"):
        script_pattern = re.compile(rf'<span class="{script_class}">([^<]*)</span>')
        bad_spans: list[str] = []
        for match in script_pattern.finditer(converted_html):
            text = match.group(1)
            if re.search(r"[A-Za-z&]", text):
                bad_spans.append(text)
        latin_artifact_counts[script_class] = len(bad_spans)
        if bad_spans:
            latin_artifact_examples[script_class] = bad_spans[:10]

    ethiopic_pattern = re.compile(r'<span class="ethiopic">([^<]*)</span>')
    ethiopic_suspect_patterns = {
        "broken_labialized_split": re.compile(r"(?:ክአ|ቅቅ|ውአ)"),
    }
    ethiopic_pattern_counts = {
        label: sum(
            1
            for match in ethiopic_pattern.finditer(converted_html)
            if pattern.search(match.group(1))
        )
        for label, pattern in ethiopic_suspect_patterns.items()
    }
    ethiopic_pattern_examples = {
        label: [
            match.group(1)
            for match in ethiopic_pattern.finditer(converted_html)
            if pattern.search(match.group(1))
        ][:10]
        for label, pattern in ethiopic_suspect_patterns.items()
    }

    return {
        "span_counts": span_counts,
        "hebrew_spans_with_non_hebrew_chars": len(bad_hebrew_spans),
        "bad_hebrew_examples": bad_hebrew_spans[:10],
        "hebrew_suspect_pattern_counts": hebrew_pattern_counts,
        "hebrew_suspect_pattern_examples": {k: v for k, v in hebrew_pattern_examples.items() if v},
        "ethiopic_suspect_pattern_counts": ethiopic_pattern_counts,
        "ethiopic_suspect_pattern_examples": {k: v for k, v in ethiopic_pattern_examples.items() if v},
        "script_spans_with_latin_artifacts": latin_artifact_counts,
        "latin_artifact_examples": latin_artifact_examples,
        "escaped_tag_leaks": {
            pattern: converted_html.count(pattern)
            for pattern in ESCAPED_TAG_LEAK_PATTERNS
            if converted_html.count(pattern)
        },
        "literal_bwhebb_class_leaks": converted_html.count('class="Bwhebb"'),
        "commented_bwhebb_spans_in_source": len(
            re.findall(r'<!--<span class="Bwhebb">.*?</span>-->', raw_html, flags=re.S)
        ),
        "image_only_script_gaps_without_local_text": image_gap_count,
        "image_gap_examples": image_gap_examples,
    }


@dataclass(frozen=True)
class LexicalEntry:
    lexical_id: str
    bdb: str
    word: str
    normalized_word: str
    xlit: str
    pos: str
    definition: str
    strongs: tuple[str, ...]
    twot: str
    etym_type: str


@dataclass(frozen=True)
class ConvertedEntry:
    entrynum: int
    paragraph_attrs: str
    page_html: str
    page_text: str
    body_html: str
    strongs: tuple[str, ...]
    hebrew_keys: tuple[str, ...]


ENTRY_PARAGRAPH_PATTERN = re.compile(
    r"<p\b(?P<attrs>[^>]*)>\s*<entry><entrynum>(?P<entrynum>\d+)</entrynum>(?P<body>.*?)</p>",
    re.S,
)
PAGE_PATTERN = re.compile(r"^\s*<page>(?P<page>.*?)</page>", re.S)
LEFTOVER_PAGE_START_PATTERN = re.compile(r"<(?P<prefix>[^<>/]*?)page(?:\s[^<>]*)?>", re.I)
LEFTOVER_PAGE_END_PATTERN = re.compile(r"</page\s*>", re.I)
TAG_PATTERN = re.compile(r"<[^>]+>")


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(element: ET.Element, name: str) -> str:
    for child in element:
        if local_name(child.tag) == name:
            return "".join(child.itertext()).strip()
    return ""


def child_element(element: ET.Element, name: str) -> ET.Element | None:
    for child in element:
        if local_name(child.tag) == name:
            return child
    return None


def normalize_hebrew_key(text: str) -> str:
    normalized = unicodedata.normalize("NFD", html.unescape(text))
    return "".join(character for character in normalized if "\u05d0" <= character <= "\u05ea")


def strip_tags(fragment: str) -> str:
    return html.unescape(TAG_PATTERN.sub("", fragment)).strip()


def clean_leftover_page_markup(fragment: str) -> str:
    def replace_start(match: re.Match[str]) -> str:
        return html.escape(match.group("prefix"), quote=False)

    fragment = LEFTOVER_PAGE_START_PATTERN.sub(replace_start, fragment)
    return LEFTOVER_PAGE_END_PATTERN.sub("", fragment)


def parse_lexical_index(path: Path) -> list[LexicalEntry]:
    root = ET.parse(path).getroot()
    entries: list[LexicalEntry] = []
    for element in root.iter():
        if local_name(element.tag) != "entry":
            continue
        xref = child_element(element, "xref")
        if xref is None:
            continue
        bdb = xref.attrib.get("bdb", "").strip()
        if not bdb:
            continue
        word = child_text(element, "w")
        word_element = child_element(element, "w")
        etym_element = child_element(element, "etym")
        entries.append(
            LexicalEntry(
                lexical_id=element.attrib.get("id", ""),
                bdb=bdb,
                word=word,
                normalized_word=normalize_hebrew_key(word),
                xlit=word_element.attrib.get("xlit", "") if word_element is not None else "",
                pos=child_text(element, "pos"),
                definition=child_text(element, "def"),
                strongs=tuple(re.findall(r"\d+", xref.attrib.get("strong", ""))),
                twot=xref.attrib.get("twot", ""),
                etym_type=etym_element.attrib.get("type", "") if etym_element is not None else "",
            )
        )
    return entries


def parse_converted_entries(converted_html: str) -> list[ConvertedEntry]:
    entries: list[ConvertedEntry] = []
    for match in ENTRY_PARAGRAPH_PATTERN.finditer(converted_html):
        body_html = match.group("body")
        page_html = ""
        page_text = ""
        page_match = PAGE_PATTERN.match(body_html)
        if page_match:
            page_html = page_match.group("page")
            page_text = strip_tags(page_html).rstrip(":")
            body_html = body_html[page_match.end() :]
        body_html = clean_leftover_page_markup(body_html)

        strong_match = re.search(r'<span class="strongs-number">([^<]+)</span>', body_html)
        strongs = tuple(re.findall(r"\d+", html.unescape(strong_match.group(1)))) if strong_match else ()
        hebrew_keys = tuple(
            key
            for key in (normalize_hebrew_key(text) for text in re.findall(r'<span class="hebrew">([^<]*)</span>', body_html))
            if key
        )
        entries.append(
            ConvertedEntry(
                entrynum=int(match.group("entrynum")),
                paragraph_attrs=match.group("attrs"),
                page_html=page_html,
                page_text=page_text,
                body_html=body_html.strip(),
                strongs=strongs,
                hebrew_keys=hebrew_keys[:8],
            )
        )
    return entries


def bdb_group(bdb: str) -> str:
    parts = bdb.split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else bdb


def bdb_sort_key(bdb: str) -> tuple[str, ...]:
    return tuple(bdb.split("."))


def bdb_id(bdb: str) -> str:
    return "bdb-" + re.sub(r"[^0-9A-Za-z]+", "-", bdb).strip("-")


def unique_preserving_order(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique.append(value)
    return unique


def lexical_indexes(entries: list[LexicalEntry]) -> tuple[dict[str, list[LexicalEntry]], dict[str, list[LexicalEntry]], dict[str, int]]:
    by_strong: dict[str, list[LexicalEntry]] = {}
    by_word: dict[str, list[LexicalEntry]] = {}
    order: dict[str, int] = {}
    for index, entry in enumerate(entries):
        order[entry.lexical_id or f"{entry.bdb}:{index}"] = index
        if entry.normalized_word:
            by_word.setdefault(entry.normalized_word, []).append(entry)
        for strong in entry.strongs:
            by_strong.setdefault(strong, []).append(entry)
    return by_strong, by_word, order


def lexical_order_key(entry: LexicalEntry, lexical_order: dict[str, int]) -> str:
    if entry.lexical_id and entry.lexical_id in lexical_order:
        return entry.lexical_id
    return entry.bdb


def score_lexical_candidate(
    converted_entry: ConvertedEntry,
    lexical_entry: LexicalEntry,
    lexical_order: dict[str, int],
    previous_index: int | None,
    used_bdb_counts: dict[str, int],
) -> tuple[int, int, int, int]:
    score = 0
    first_key = converted_entry.hebrew_keys[0] if converted_entry.hebrew_keys else ""
    key_set = set(converted_entry.hebrew_keys)
    strong_set = set(converted_entry.strongs)

    if lexical_entry.strongs and strong_set.intersection(lexical_entry.strongs):
        score += 45
    if first_key and lexical_entry.normalized_word == first_key:
        score += 100
    elif lexical_entry.normalized_word in key_set:
        score += 70
    elif first_key and lexical_entry.normalized_word and (
        first_key.startswith(lexical_entry.normalized_word) or lexical_entry.normalized_word.startswith(first_key)
    ):
        score += 25
    if lexical_entry.etym_type == "main" and not converted_entry.strongs:
        score += 10

    index = lexical_order.get(lexical_order_key(lexical_entry, lexical_order), 0)
    distance = abs(index - previous_index) if previous_index is not None else index
    if previous_index is not None:
        score += max(0, 25 - min(distance, 25))
        if index + 20 < previous_index and not strong_set:
            score -= 20
    if lexical_entry.bdb.startswith("xa.") and previous_index is not None and previous_index < index - 500:
        score -= 15

    return (-score, used_bdb_counts.get(lexical_entry.bdb, 0), distance, index)


def map_entries_to_bdb(
    converted_entries: list[ConvertedEntry],
    lexical_entries: list[LexicalEntry],
    entry_bdb_overrides: dict[int, str] | None = None,
) -> tuple[dict[str, list[ConvertedEntry]], list[ConvertedEntry]]:
    by_strong, by_word, lexical_order = lexical_indexes(lexical_entries)
    entry_bdb_overrides = entry_bdb_overrides or {}
    valid_bdbs = {entry.bdb for entry in lexical_entries}
    invalid_overrides = {
        entrynum: bdb
        for entrynum, bdb in entry_bdb_overrides.items()
        if bdb not in valid_bdbs
    }
    if invalid_overrides:
        details = ", ".join(f"{entrynum}: {bdb}" for entrynum, bdb in sorted(invalid_overrides.items())[:10])
        raise ValueError(f"entry BDB override fixture references unknown BDB codes: {details}")

    bdb_first_index: dict[str, int] = {}
    for lexical_entry in lexical_entries:
        index = lexical_order.get(lexical_order_key(lexical_entry, lexical_order))
        if index is not None:
            bdb_first_index.setdefault(lexical_entry.bdb, index)

    mapped: dict[str, list[ConvertedEntry]] = {}
    unmapped: list[ConvertedEntry] = []
    used_bdb_counts: dict[str, int] = {}
    previous_index: int | None = None

    for converted_entry in converted_entries:
        override_bdb = entry_bdb_overrides.get(converted_entry.entrynum)
        if override_bdb:
            mapped.setdefault(override_bdb, []).append(converted_entry)
            used_bdb_counts[override_bdb] = used_bdb_counts.get(override_bdb, 0) + 1
            previous_index = bdb_first_index.get(override_bdb, previous_index)
            continue

        candidate_pool: list[LexicalEntry] = []
        for strong in converted_entry.strongs:
            candidate_pool.extend(by_strong.get(strong, []))
        if converted_entry.hebrew_keys:
            candidate_pool.extend(by_word.get(converted_entry.hebrew_keys[0], []))
        candidate_pool = list({entry.lexical_id or entry.bdb: entry for entry in candidate_pool}.values())

        candidates = [
            entry
            for entry in candidate_pool
            if converted_entry.hebrew_keys
            and (
                entry.normalized_word in set(converted_entry.hebrew_keys)
                or (entry.normalized_word and entry.normalized_word.startswith(converted_entry.hebrew_keys[0]))
                or (entry.normalized_word and converted_entry.hebrew_keys[0].startswith(entry.normalized_word))
            )
        ]
        if not candidates:
            unmapped.append(converted_entry)
            continue

        candidates.sort(
            key=lambda entry: score_lexical_candidate(
                converted_entry,
                entry,
                lexical_order,
                previous_index,
                used_bdb_counts,
            )
        )
        lexical_entry = candidates[0]
        mapped.setdefault(lexical_entry.bdb, []).append(converted_entry)
        used_bdb_counts[lexical_entry.bdb] = used_bdb_counts.get(lexical_entry.bdb, 0) + 1
        previous_index = lexical_order.get(lexical_order_key(lexical_entry, lexical_order), previous_index)

    return mapped, unmapped


def render_meta_span(label: str, value: str) -> str:
    return f"<span><b>{html.escape(label)}:</b> {html.escape(value)}</span>"


def indent_lines(fragment: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line if line else line for line in fragment.splitlines())


def render_entry_paragraph(entry: ConvertedEntry, indent: int = 0) -> str:
    attrs = entry.paragraph_attrs
    return f'{" " * indent}<p{attrs} data-entrynum="{entry.entrynum}">{entry.body_html}</p>'


def render_section(
    bdb: str,
    lexical_entries: list[LexicalEntry],
    converted_entries: list[ConvertedEntry],
    indent: int = 0,
) -> str:
    words = unique_preserving_order([entry.word for entry in lexical_entries])
    definitions = unique_preserving_order([entry.definition for entry in lexical_entries])
    poses = unique_preserving_order([entry.pos for entry in lexical_entries])
    strongs = unique_preserving_order([strong for entry in lexical_entries for strong in entry.strongs])
    twots = unique_preserving_order([entry.twot for entry in lexical_entries])
    lexical_ids = unique_preserving_order([entry.lexical_id for entry in lexical_entries])
    entrynums = ", ".join(str(entry.entrynum) for entry in converted_entries)
    pages = unique_preserving_order([entry.page_text for entry in converted_entries])

    heading_words = " / ".join(words[:4]) or "Unindexed"
    heading = (
        f'<h3 id="{bdb_id(bdb)}"><span class="bdb-code">{html.escape(bdb)}</span> '
        f'<span class="headwords" dir="rtl">{html.escape(heading_words)}</span></h3>'
    )
    summary = f'<p class="section-definition">{html.escape("; ".join(definitions[:3]))}</p>' if definitions else ""
    meta_values = [
        ("Entries", entrynums),
        ("Pages", ", ".join(pages)),
        ("POS", ", ".join(poses)),
        ("Strong", ", ".join(strongs)),
        ("TWOT", ", ".join(twots)),
        ("Lexical IDs", ", ".join(lexical_ids)),
    ]
    lines = [
        f'{" " * indent}<section class="bdb-subentry" data-bdb="{html.escape(bdb)}">',
        indent_lines(heading, indent + 2),
    ]
    if summary:
        lines.append(indent_lines(summary, indent + 2))
    meta_spans = [render_meta_span(label, value) for label, value in meta_values if value]
    if meta_spans:
        lines.append(f'{" " * (indent + 2)}<div class="entry-meta">')
        lines.extend(indent_lines(span, indent + 4) for span in meta_spans)
        lines.append(f'{" " * (indent + 2)}</div>')
    lines.extend(render_entry_paragraph(entry, indent + 2) for entry in converted_entries)
    lines.append(f'{" " * indent}</section>')
    return "\n".join(lines)


def canonical_group_entry(group: str, lexical_entries: list[LexicalEntry]) -> LexicalEntry:
    group_entries = [entry for entry in lexical_entries if bdb_group(entry.bdb) == group]
    for entry in group_entries:
        if entry.etym_type == "main":
            return entry
    for entry in group_entries:
        if entry.bdb.endswith(".aa"):
            return entry
    return group_entries[0]


def render_article(
    group: str,
    group_bdbs: list[str],
    entries_by_bdb: dict[str, list[LexicalEntry]],
    converted_by_bdb: dict[str, list[ConvertedEntry]],
    lexical_entries: list[LexicalEntry],
    indent: int = 0,
) -> str:
    canonical = canonical_group_entry(group, lexical_entries)
    section_html = "\n".join(
        render_section(bdb, entries_by_bdb.get(bdb, []), converted_by_bdb[bdb], indent + 2)
        for bdb in group_bdbs
        if converted_by_bdb.get(bdb)
    )
    definition = f'<p class="article-definition">{html.escape(canonical.definition)}</p>' if canonical.definition else ""
    lines = [
        f'{" " * indent}<article class="bdb-entry" id="{bdb_id(group)}" data-bdb-group="{html.escape(group)}">',
        f'{" " * (indent + 2)}<header class="article-header">',
        (
            f'{" " * (indent + 4)}<h2><span class="bdb-code">{html.escape(group)}</span> '
            f'<span class="headwords" dir="rtl">{html.escape(canonical.word)}</span></h2>'
        ),
    ]
    if definition:
        lines.append(indent_lines(definition, indent + 4))
    lines.append(f'{" " * (indent + 2)}</header>')
    if section_html:
        lines.append(section_html)
    lines.append(f'{" " * indent}</article>')
    return "\n".join(lines)


def render_unmapped_entries(unmapped_entries: list[ConvertedEntry], indent: int = 0) -> str:
    if not unmapped_entries:
        return ""
    body = "\n".join(render_entry_paragraph(entry, indent + 2) for entry in unmapped_entries)
    return "\n".join(
        [
            f'{" " * indent}<section class="unmapped-entries" id="unindexed-entries">',
            f'{" " * (indent + 2)}<h2>Unindexed Entries</h2>',
            (
                f'{" " * (indent + 2)}<p class="article-definition">'
                "Entries that could not be confidently aligned with LexicalIndex.xml.</p>"
            ),
            body,
            f'{" " * indent}</section>',
        ]
    )


def entries_styles() -> str:
    return """
body {
  margin: 0;
  color: #1d1d1b;
  background: #fbfaf7;
  font-family: Georgia, "Times New Roman", serif;
  line-height: 1.55;
}
main {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 24px 80px;
}
.document-header {
  border-bottom: 2px solid #1d1d1b;
  margin-bottom: 28px;
  padding-bottom: 16px;
}
h1, h2, h3 {
  line-height: 1.2;
  margin: 0;
}
h1 {
  font-size: 2rem;
}
.bdb-entry {
  border-top: 1px solid #bbb4a8;
  padding: 26px 0 8px;
}
.article-header {
  margin-bottom: 18px;
}
.article-header h2 {
  align-items: baseline;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 1.55rem;
}
.bdb-subentry {
  margin: 18px 0 24px;
  padding-left: 18px;
  border-left: 4px solid #d4c8ad;
}
.bdb-subentry h3 {
  align-items: baseline;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 1.15rem;
}
.bdb-code {
  color: #6a4f1c;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
  font-size: 0.82em;
}
.headwords,
.hebrew {
  font-family: "SBL Hebrew", "Ezra SIL", "Times New Roman", serif;
}
.section-definition,
.article-definition {
  color: #57524a;
  margin: 6px 0 10px;
}
.entry-meta {
  color: #5d5a54;
  display: flex;
  flex-wrap: wrap;
  font-family: ui-sans-serif, system-ui, sans-serif;
  font-size: 0.78rem;
  gap: 6px 14px;
  margin: 8px 0 10px;
}
.entry-meta span {
  white-space: nowrap;
}
p.p {
  margin: 10px 0;
}
.strongs-number {
  color: #785f28;
  font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
}
.ref {
  color: #245f73;
}
.arabic,
.syriac,
.samaritan,
.persian {
  direction: rtl;
  unicode-bidi: isolate;
}
.unmapped-entries {
  border-top: 2px solid #8c7b61;
  margin-top: 36px;
  padding-top: 24px;
}
"""


def build_entries_document(converted_html: str, lexical_index_path: Path, entry_bdb_overrides_path: Path) -> str:
    lexical_entries = parse_lexical_index(lexical_index_path)
    converted_entries = parse_converted_entries(converted_html)
    entry_bdb_overrides = load_entry_bdb_overrides(entry_bdb_overrides_path)
    converted_by_bdb, unmapped_entries = map_entries_to_bdb(
        converted_entries,
        lexical_entries,
        entry_bdb_overrides,
    )

    entries_by_bdb: dict[str, list[LexicalEntry]] = {}
    for entry in lexical_entries:
        entries_by_bdb.setdefault(entry.bdb, []).append(entry)

    bdbs_by_group: dict[str, list[str]] = {}
    for bdb in sorted(converted_by_bdb, key=bdb_sort_key):
        bdbs_by_group.setdefault(bdb_group(bdb), []).append(bdb)

    articles = "\n".join(
        render_article(group, bdbs, entries_by_bdb, converted_by_bdb, lexical_entries, 6)
        for group, bdbs in sorted(bdbs_by_group.items(), key=lambda item: bdb_sort_key(item[0]))
    )
    unmapped = render_unmapped_entries(unmapped_entries, 6)
    styles = indent_lines(entries_styles().strip(), 6)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "  <head>\n"
        '    <meta charset="utf-8"/>\n'
        "    <title>BDB Entries</title>\n"
        "    <style>\n"
        f"{styles}\n"
        "    </style>\n"
        "  </head>\n"
        "  <body>\n"
        "    <main>\n"
        '      <header class="document-header">\n'
        '        <h1>The Brown-Driver-Briggs Hebrew and English Lexicon: Entries</h1>\n'
        "      </header>\n"
        f"{articles}\n"
        f"{unmapped}\n"
        "    </main>\n"
        "  </body>\n"
        "</html>\n"
    )


def main() -> None:
    argument_parser = argparse.ArgumentParser(description="Convert BDB raw HTML into normalized Unicode HTML.")
    argument_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to the raw source HTML.")
    argument_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path to write the converted HTML.")
    argument_parser.add_argument(
        "--entries-output",
        type=Path,
        default=DEFAULT_ENTRIES_OUTPUT,
        help="Path to write the entry-structured HTML.",
    )
    argument_parser.add_argument(
        "--lexical-index",
        type=Path,
        default=DEFAULT_LEXICAL_INDEX,
        help="Path to LexicalIndex.xml for BDB entry grouping.",
    )
    argument_parser.add_argument(
        "--entry-bdb-overrides",
        type=Path,
        default=ENTRY_BDB_OVERRIDES,
        help="Path to JSON overrides for assigning converted entry numbers to BDB codes.",
    )
    argument_parser.add_argument(
        "--report",
        action="store_true",
        help="Print a JSON report describing remaining anomalies and recovery gaps.",
    )
    args = argument_parser.parse_args()

    bwhebb_map = load_bwhebb_map(BWHEBB_TSV, BWHEBB_AUTHORITATIVE, BWHEBB_OVERRIDES)
    script_overrides = load_json(SCRIPT_OVERRIDES)
    xbr_overrides = load_json(XBR_OVERRIDES)
    global_x_as_tsadi_profiles, entry_x_as_tsadi_profiles = load_bwhebb_x_as_tsadi(BWHEBB_X_AS_TSADI)
    raw_html = args.input.read_text(encoding="utf-8")
    converted = convert_document(
        raw_html,
        bwhebb_map=bwhebb_map,
        script_overrides=script_overrides,
        xbr_overrides=xbr_overrides,
        global_x_as_tsadi_profiles=global_x_as_tsadi_profiles,
        entry_x_as_tsadi_profiles=entry_x_as_tsadi_profiles,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(converted, encoding="utf-8")
    entries_html = build_entries_document(converted, args.lexical_index, args.entry_bdb_overrides)
    args.entries_output.parent.mkdir(parents=True, exist_ok=True)
    args.entries_output.write_text(entries_html, encoding="utf-8")
    if args.report:
        print(json.dumps(build_report(raw_html, converted), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
