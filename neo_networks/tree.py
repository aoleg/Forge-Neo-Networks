"""The folder tree under the roots of an Extra Networks page, and the folder each network file sits in.

Folders are found the way Forge Neo's own Dirs bar finds them: every directory below a root, links followed, empty
ones included. Several roots (--lora-dirs, --ckpt-dirs) are merged by relative path. Paths in the output use "/".
"""

import os
import re

_DIGITS = re.compile("([0-9]+)")


def natural_sort_key(text: str) -> list:
    """Same order as Forge's shared.natural_sort_key: digit runs compare as numbers, the rest ignores case."""
    return [int(part) if part.isdigit() else part.lower() for part in _DIGITS.split(text)]


def is_hidden(name: str) -> bool:
    return name.startswith(".")


def _subdirs(path: str) -> list[str]:
    try:
        with os.scandir(path) as entries:
            names = [entry.name for entry in entries if entry.is_dir()]
    except OSError:
        return []
    return sorted(names, key=natural_sort_key)


def _walk(path: str, node: dict, show_hidden: bool, ancestors: frozenset) -> None:
    # A link that points back at one of its own parents would never end
    real = os.path.normcase(os.path.realpath(path))
    if real in ancestors:
        return
    ancestors = ancestors | {real}

    for name in _subdirs(path):
        if is_hidden(name) and not show_hidden:
            continue
        child = node["children"].get(name)
        if child is None:
            child = node["children"][name] = {"name": name, "children": {}}
        _walk(os.path.join(path, name), child, show_hidden, ancestors)


def _as_lists(node: dict) -> dict:
    children = sorted(node["children"].values(), key=lambda child: natural_sort_key(child["name"]))
    return {"name": node["name"], "children": [_as_lists(child) for child in children]}


def build_tree(roots: list[str], *, show_hidden: bool = True) -> dict:
    """Return {"name": "", "children": [{"name": ..., "children": [...]}, ...]} for all the roots together.

    With show_hidden off, a folder whose name starts with "." is left out together with everything below it.
    """
    top = {"name": "", "children": {}}
    for root in roots:
        if root and os.path.isdir(root):
            _walk(os.path.abspath(root), top, show_hidden, frozenset())
    return _as_lists(top)


def relative_folder(filename: str, roots: list[str]) -> str:
    """The folder of `filename` relative to the root that holds it: "" for a file in the root itself, else "a/b".

    A file outside every root also gives "": it has no folder button to belong to, so it is treated as a loose file.
    """
    if not filename:
        return ""

    path = os.path.abspath(filename)
    best = None
    for root in roots:
        if not root:
            continue
        try:
            relative = os.path.relpath(path, os.path.abspath(root))
        except ValueError:  # another drive
            continue
        if relative == os.pardir or relative.startswith(os.pardir + os.sep):
            continue
        # nested roots: the nearest one gives the shortest path
        if best is None or len(relative) < len(best):
            best = relative

    if best is None:
        return ""
    return "/".join(best.split(os.sep)[:-1])
