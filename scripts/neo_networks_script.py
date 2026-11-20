"""Forge-Neo-Networks: the settings, and the route the folder bar reads its data from.

GET /forge-neo-networks/tree?page=<extra networks tab name, e.g. lora, checkpoints, textual_inversion>

    presets   the UI Presets on offer now, built-in ones and those added by other extensions
    matches   first-level folder -> the presets it belongs to (folders with no preset are left out)
    tree      every folder below the page's model folders, {"name": "", "children": [{"name", "children"}, ...]}
    items     card name -> the folder its file is in, "" for a file directly in a model folder, else "a/b"

No Forge file is patched: the browser draws the bar from this data inside the stock one.
"""

import os

from fastapi import FastAPI
from fastapi.exceptions import HTTPException
from starlette.responses import JSONResponse

from modules import script_callbacks, scripts, shared, ui_extra_networks
from neo_networks import aliases, tree

EXTENSION_DIR = scripts.basedir()
DEFAULT_ALIASES = os.path.join(EXTENSION_DIR, "aliases.default.txt")
USER_ALIASES = os.path.join(EXTENSION_DIR, "aliases.txt")

ROUTE = "/forge-neo-networks/tree"
SECTION = ("extra_networks", "Extra Networks")

OPTION_ENABLED = "fnn_enabled"
OPTION_LAYOUT = "fnn_layout"
OPTION_DEFAULT_SELECTION = "fnn_default_selection"

_reported: set[str] = set()


def current_presets() -> list[str]:
    """Read on every request: other extensions add presets while they load."""
    from modules_forge.presets import PresetArch

    disabled = set(getattr(shared.cmd_opts, "disable_preset", None) or ())
    return [preset for preset in PresetArch.choices() if preset not in disabled]


def _report(problems: list[str]) -> None:
    for problem in problems:
        if problem not in _reported:
            _reported.add(problem)
            print(f"[Forge-Neo-Networks] {problem}")


def build_payload(page: ui_extra_networks.ExtraNetworksPage) -> dict:
    roots = [os.path.abspath(str(root)) for root in page.allowed_directories_for_previews() if root]
    show_hidden = bool(getattr(shared.opts, "extra_networks_show_hidden_directories", True))

    folders = tree.build_tree(roots, show_hidden=show_hidden)
    presets = current_presets()
    alias_map, problems = aliases.load(DEFAULT_ALIASES, USER_ALIASES)
    _report(problems)

    first_level = [child["name"] for child in folders["children"]]
    # a copy of the dict: the page is rebuilt on another thread when Refresh is pressed
    items = {name: tree.relative_folder(item.get("filename") or "", roots) for name, item in list(page.items.items())}

    return {
        "presets": presets,
        "matches": aliases.match_all(first_level, presets, alias_map),
        "tree": folders,
        "items": items,
    }


def get_tree(page: str = ""):
    found = next((p for p in ui_extra_networks.extra_pages if p.extra_networks_tabname == page), None)
    if found is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return JSONResponse(build_payload(found))


def on_app_started(_, app: FastAPI) -> None:
    app.add_api_route(ROUTE, get_tree, methods=["GET"])


def on_ui_settings() -> None:
    import gradio as gr

    from modules.options import OptionInfo

    options = {
        OPTION_ENABLED: OptionInfo(True, "Folder bar by first-level folder and UI Preset", section=SECTION).info(
            "Forge-Neo-Networks ; off brings back the stock Dir buttons after Refresh"
        ),
        OPTION_LAYOUT: OptionInfo("Rows", "Folder bar: subfolders", gr.Radio, {"choices": ("Rows", "Flat")}, section=SECTION).info(
            "Rows: one row per folder level ; Flat: every subfolder of the selected first-level folder in one row"
        ),
        OPTION_DEFAULT_SELECTION: OptionInfo("Auto", "Folder bar: selection when the page opens", gr.Radio, {"choices": ("Auto", "All")}, section=SECTION).info(
            "Auto: the folders that belong to the UI Preset, and the files outside any folder"
        ),
    }
    for key, info in options.items():
        if key not in shared.opts.data_labels:
            shared.opts.add_option(key, info)


script_callbacks.on_app_started(on_app_started)
script_callbacks.on_ui_settings(on_ui_settings)
