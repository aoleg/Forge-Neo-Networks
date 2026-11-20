"""Forge-Neo-Networks: the settings, and the route the folder bar reads its data from.

POST /forge-neo-networks/layout?layout=Rows|Flat   sets and saves the setting "Folder bar: subfolders"

GET /forge-neo-networks/tree?page=<extra networks tab name, e.g. lora, checkpoints, textual_inversion>

    presets   the UI Presets on offer now, built-in ones and those added by other extensions
    matches   first-level folder -> the presets it belongs to (folders with no preset are left out)
    tree      the folders with a model in them or below them, {"name": "", "children": [{"name", "children"}, ...]}
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
LAYOUT_ROUTE = "/forge-neo-networks/layout"
LAYOUTS = ("Rows", "Flat")
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

    # The folder of every model the page lists. Thousands of files share a few dozen directories, so each
    # directory is worked out once. A copy of the dict: the page is rebuilt on another thread on Refresh.
    folder_of_directory: dict[str, str] = {}
    items: dict[str, str] = {}
    for name, item in list(page.items.items()):
        filename = item.get("filename") or ""
        directory = os.path.dirname(filename)
        folder = folder_of_directory.get(directory) if directory else None
        if folder is None:
            folder = tree.relative_folder(filename, roots)
            if directory:
                folder_of_directory[directory] = folder
        items[name] = folder

    # Only folders that hold a model get a button, and the models are known already: the disk is not searched.
    folders = tree.tree_from_folders(items.values(), show_hidden=show_hidden)
    presets = current_presets()
    alias_map, problems = aliases.load(DEFAULT_ALIASES, USER_ALIASES)
    _report(problems)

    first_level = [child["name"] for child in folders["children"]]
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


def set_layout(layout: str = ""):
    """The Rows / Flat button in the bar: change the setting and save it, as "Apply settings" would."""
    if layout not in LAYOUTS:
        raise HTTPException(status_code=400, detail="Unknown layout")
    try:
        shared.opts.set(OPTION_LAYOUT, layout)
        shared.opts.save(shared.config_filename)
    except (AssertionError, RuntimeError) as e:  # settings frozen on the command line
        return JSONResponse({"saved": False, "reason": str(e)})
    return JSONResponse({"saved": True, "layout": layout})


def on_app_started(_, app: FastAPI) -> None:
    app.add_api_route(ROUTE, get_tree, methods=["GET"])
    app.add_api_route(LAYOUT_ROUTE, set_layout, methods=["POST"])


def on_ui_settings() -> None:
    import gradio as gr

    from modules.options import OptionInfo

    options = {
        OPTION_ENABLED: OptionInfo(True, "Folder bar by first-level folder and UI Preset", section=SECTION).info(
            "Forge-Neo-Networks ; off brings back the stock Dir buttons after Refresh"
        ),
        OPTION_LAYOUT: OptionInfo("Rows", "Folder bar: subfolders", gr.Radio, {"choices": LAYOUTS}, section=SECTION).info(
            "Rows: one row per folder level ; Flat: every subfolder of the selected first-level folder in one row ; "
            "the Rows / Flat button in the bar changes this setting"
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
