"""Which UI presets a first-level folder belongs to.

A folder matches a preset when its name equals the preset name, or matches one of the preset's alias patterns. The
comparison is case-insensitive and against the whole folder name. A pattern may use * (any run of characters) and
? (one character); nothing else is special.

Alias file format, one preset per line:

    # a comment (the # must be the first character of the line)
    klein = flux2, flux2-klein, klein-turbo
    wan   = wan*

Lines for the same preset inside one file add up. A line in the user's file replaces what the default file says for
that preset, and a line with nothing after the = removes it.
"""

import os
import re
from functools import lru_cache

AliasMap = dict[str, list[str]]


def parse(text: str) -> tuple[AliasMap, list[str]]:
    """Return (preset -> patterns, problems). Preset names and patterns come back case-folded."""
    result: AliasMap = {}
    problems: list[str] = []

    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        preset, sep, patterns = line.partition("=")
        preset = preset.strip().casefold()
        if not sep or not preset:
            problems.append(f"line {number}: expected 'preset = folder, folder'")
            continue

        entries = result.setdefault(preset, [])
        for pattern in patterns.split(","):
            pattern = pattern.strip().casefold()
            if pattern and pattern not in entries:
                entries.append(pattern)

    return result, problems


def _read(path: str) -> tuple[AliasMap, list[str]]:
    if not path or not os.path.isfile(path):
        return {}, []
    try:
        # utf-8-sig: Notepad may save the file with a byte order mark
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            text = f.read()
    except OSError as e:
        return {}, [f"{os.path.basename(path)}: {e}"]

    result, problems = parse(text)
    return result, [f"{os.path.basename(path)}: {p}" for p in problems]


def load(default_path: str, user_path: str) -> tuple[AliasMap, list[str]]:
    """Read the shipped file, then the user's file on top of it. A missing file is not a problem."""
    result, problems = _read(default_path)
    user, user_problems = _read(user_path)
    result.update(user)
    return result, problems + user_problems


@lru_cache(maxsize=1024)
def _compile(pattern: str) -> re.Pattern:
    parts = []
    for char in pattern:
        if char == "*":
            parts.append(".*")
        elif char == "?":
            parts.append(".")
        else:
            parts.append(re.escape(char))
    return re.compile("".join(parts), re.DOTALL)


def match(folder: str, presets: list[str], alias_map: AliasMap) -> list[str]:
    """The presets this folder belongs to, in the order of `presets`."""
    name = folder.casefold()
    found = []
    for preset in presets:
        key = preset.casefold()
        if name == key or any(_compile(p).fullmatch(name) for p in alias_map.get(key, ())):
            found.append(preset)
    return found


def match_all(folders: list[str], presets: list[str], alias_map: AliasMap) -> dict[str, list[str]]:
    """folder -> presets, only for the folders that match at least one preset."""
    result = {}
    for folder in folders:
        found = match(folder, presets, alias_map)
        if found:
            result[folder] = found
    return result
