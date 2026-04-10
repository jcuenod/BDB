#!/usr/bin/env python3

from __future__ import annotations

import argparse
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "data" / "raw.html"
DEFAULT_OUTPUT = ROOT / "data" / "legal_unicode.html"
BWHEBB_TSV = ROOT / "data" / "bhwebb-unicode-map.tsv"
BWHEBB_AUTHORITATIVE = ROOT / "fixtures" / "bwhebb_authoritative_map.json"
BWHEBB_OVERRIDES = ROOT / "fixtures" / "bwhebb_overrides.json"
SCRIPT_OVERRIDES = ROOT / "fixtures" / "script_overrides.json"

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


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def convert_bwhebb_text(text: str, bwhebb_map: dict[str, str], overrides: dict[str, str]) -> str:
    exact_text = text.strip()
    if text in overrides:
        return overrides[text]
    if exact_text in overrides:
        return overrides[exact_text]
    if text in bwhebb_map:
        return bwhebb_map[text]
    if exact_text in bwhebb_map:
        return bwhebb_map[exact_text]

    decoded = html.unescape(exact_text)
    mapped = "".join(bwhebb_map.get(character, character) for character in decoded)

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


class LexiconHTMLConverter(HTMLParser):
    def __init__(self, bwhebb_map: dict[str, str], script_overrides: dict[str, dict[str, str]]):
        super().__init__(convert_charrefs=True)
        self.bwhebb_map = bwhebb_map
        self.script_overrides = script_overrides
        self.output: list[str] = []
        self.capture_stack: list[dict] = []

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

        if self.capture_stack and self.capture_stack[-1]["kind"] == "xbr" and tag == "xbr":
            capture = self.capture_stack.pop()
            text = "".join(capture["buffer"]).strip()
            target = html.escape(capture["target"], quote=True)
            self.output.append(f"<span class=\"ref\" data-ref=\"{target}\">{html.escape(text, quote=False)}</span>")
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
            return convert_bwhebb_text(text, self.bwhebb_map, self.script_overrides.get("Bwhebb", {}))
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


def convert_document(raw_html: str, bwhebb_map: dict[str, str], script_overrides: dict[str, dict[str, str]]) -> str:
    parser = LexiconHTMLConverter(bwhebb_map=bwhebb_map, script_overrides=script_overrides)
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


def main() -> None:
    argument_parser = argparse.ArgumentParser(description="Convert BDB raw HTML into normalized Unicode HTML.")
    argument_parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to the raw source HTML.")
    argument_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Path to write the converted HTML.")
    argument_parser.add_argument(
        "--report",
        action="store_true",
        help="Print a JSON report describing remaining anomalies and recovery gaps.",
    )
    args = argument_parser.parse_args()

    bwhebb_map = load_bwhebb_map(BWHEBB_TSV, BWHEBB_AUTHORITATIVE, BWHEBB_OVERRIDES)
    script_overrides = load_json(SCRIPT_OVERRIDES)
    raw_html = args.input.read_text(encoding="utf-8")
    converted = convert_document(raw_html, bwhebb_map=bwhebb_map, script_overrides=script_overrides)
    args.output.write_text(converted, encoding="utf-8")
    if args.report:
        print(json.dumps(build_report(raw_html, converted), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
