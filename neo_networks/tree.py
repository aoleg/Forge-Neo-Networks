"""The folder each network file sits in, and the folder tree of an Extra Networks page.

The tree holds only folders with a model in them or somewhere below them. It is built from the folders of the
models Forge lists on the page, so the disk is never searched: a download cache with thousands of folders and no
model costs nothing. Several model folders (--lora-dirs, --ckpt-dirs) merge by relative path. Paths use "/".
"""

import os
import re
from collections.abc import Iterable

_DIGITS = re.compile("([0-9]+)")


def natural_sort_key(text: str) -> list:
    """Same order as Forge's shared.natural_sort_key: digit runs compare as numbers, the rest ignores case."""
    return [int(part) if part.isdigit() else part.lower() for part in _DIGITS.split(text)]


def is_hidden(name: str) -> bool:
    return name.startswith(".")


def _as_lists(node: dict) -> dict:
    children = sorted(node["children"].values(), key=lambda child: natural_sort_key(child["name"]))
    return {"name": node["name"], "children": [_as_lists(child) for child in children]}


def tree_from_folders(folders: Iterable[str], *, show_hidden: bool = True) -> dict:
    """Return {"name": "", "children": [{"name": ..., "children": [...]}, ...]} from the folder of each model.

    `folders` has one entry per model, as relative_folder gives it: "" for a model outside any folder, else "a/b".
    Every folder on the way to a model is in the tree; a folder with no model in it or below it is not.

    With show_hidden off, a folder whose name starts with "." is left out together with everything below it. The
    folders above it stay: they still hold that model.
    """
    top = {"name": "", "children": {}}
    done = set()
    for folder in folders:
        if not folder or folder in done:
            continue
        done.add(folder)

        node = top
        for part in folder.split("/"):
            if is_hidden(part) and not show_hidden:
                break
            child = node["children"].get(part)
            if child is None:
                child = node["children"][part] = {"name": part, "children": {}}
            node = child
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
