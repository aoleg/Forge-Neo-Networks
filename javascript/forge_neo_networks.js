// Forge-Neo-Networks: the folder bar of the Extra Networks pages.
//
// The stock bar lists every subfolder at every depth and filters by typing the folder into the search box. This
// one shows the first-level folders, opens the subfolders of the selected folder only, and filters by the folder a
// card's file really sits in, so the search box stays free and works inside the selected folder. "Auto" selects
// the folders that belong to the current UI Preset and follows the preset when it changes.
//
// Nothing in Forge is replaced: the rows are drawn inside the stock bar element, and the stock filter still runs
// first. If the data cannot be fetched, the stock bar is left as it is.

(function () {
    "use strict";

    const ROUTE = "./forge-neo-networks/tree";
    const LOG = "[Forge-Neo-Networks]";

    /** "<tab>_<page>" (txt2img_lora, img2img_checkpoints, ...) -> state of that page */
    const states = {};
    /** page -> the request in flight, shared by txt2img and img2img */
    const requests = {};
    /** card element -> its lower-case search text */
    const cardText = new WeakMap();

    function isEnabled() {
        return typeof opts === "undefined" || opts.fnn_enabled !== false;
    }

    function defaultMode() {
        return typeof opts !== "undefined" && opts.fnn_default_selection === "All" ? "all" : "auto";
    }

    function fetchData(page) {
        if (!requests[page]) {
            requests[page] = fetch(ROUTE + "?page=" + encodeURIComponent(page))
                .then(function (response) {
                    if (!response.ok) throw new Error("HTTP " + response.status);
                    return response.json();
                })
                .then(function (data) {
                    // Maps: a card or a folder may be named "constructor"
                    data.items = new Map(Object.entries(data.items || {}));
                    data.matches = new Map(Object.entries(data.matches || {}));
                    data.presets = data.presets || [];
                    return data;
                })
                .finally(function () {
                    delete requests[page];
                });
        }
        return requests[page];
    }

    // --- the UI Preset -----------------------------------------------------

    /** The preset in the UI Preset dropdown. While someone types in the dropdown its text is no preset: keep the last one. */
    function readPreset(st) {
        const input = gradioApp().querySelector("#forge_ui_preset input");
        const value = input ? input.value : "";
        return st.data.presets.indexOf(value) !== -1 ? value : st.preset;
    }

    /** Take the current preset and work out which first-level folders belong to it. */
    function updatePreset(st) {
        st.preset = readPreset(st);
        st.matching = st.data.tree.children.filter(function (node) {
            return st.preset && (st.data.matches.get(node.name) || []).indexOf(st.preset) !== -1;
        });
        st.matchingNames = new Set(
            st.matching.map(function (node) {
                return node.name;
            }),
        );
    }

    // --- selection ---------------------------------------------------------
    //
    // mode "all":    every card.
    // mode "folder": the folder at `path`, picked by hand from row 1 downwards. `path` is never empty.
    // mode "auto":   follows the preset. An empty `path` is the Auto root: every folder of the preset, and the
    //                files outside any folder. Otherwise `path` starts with one of the preset's folders.

    function childNamed(node, name) {
        return node.children.find(function (child) {
            return child.name === name;
        });
    }

    /** Bring the selection in line with the folders and the preset as they are now. */
    function settleSelection(st) {
        // drop the part of the path that no longer exists (a folder removed before Refresh)
        let node = st.data.tree;
        let depth = 0;
        while (depth < st.path.length) {
            node = childNamed(node, st.path[depth]);
            if (!node) break;
            depth++;
        }
        st.path = st.path.slice(0, depth);

        if (st.mode === "auto") {
            if (!st.preset) {
                st.mode = "all";
                st.path = [];
            } else if (st.path.length && !st.matchingNames.has(st.path[0])) {
                st.path = []; // the preset changed: back to the root of the new one
            }
        } else if (st.mode === "folder" && !st.path.length) {
            st.mode = "all";
        } else if (st.mode === "all") {
            st.path = [];
        }
    }

    function select(st, mode, path) {
        st.mode = mode;
        st.path = path;
        draw(st);
        applyScope(st);
    }

    // --- drawing -----------------------------------------------------------

    function barElement(st) {
        return gradioApp().getElementById(st.id + "_dirs");
    }

    function addRow(bar) {
        const row = document.createElement("div");
        row.className = "fnn-row";
        bar.appendChild(row);
        return row;
    }

    function addButton(row, label, selected, title, onClick) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "lg secondary gradio-button custom-button fnn-button";
        if (selected) button.classList.add("fnn-selected");
        button.textContent = label;
        if (title) button.title = title;
        button.addEventListener("click", onClick);
        row.appendChild(button);
        return button;
    }

    /** A button for the folder `node` inside `parentPath`. Clicking it selects that folder and clears what was below. */
    function addFolderButton(st, row, node, parentPath, mode, selected) {
        const path = parentPath.concat(node.name);
        const button = addButton(row, node.name, selected, path.join("/"), function () {
            select(st, mode, path);
        });
        if (node.children.length) button.classList.add("fnn-has-subfolders");
        return button;
    }

    function addNote(bar, text) {
        const row = addRow(bar);
        const note = document.createElement("span");
        note.className = "fnn-note";
        note.textContent = text;
        row.appendChild(note);
    }

    function draw(st) {
        const bar = barElement(st);
        if (!bar) return;

        updatePreset(st);
        settleSelection(st);
        bar.textContent = "";
        bar.classList.add("fnn-bar");

        const tree = st.data.tree;
        if (!tree.children.length) return; // as stock: no folders, no bar

        const auto = st.mode === "auto";
        const atAutoRoot = auto && !st.path.length;

        // row 1: Auto, All, All (preset), then the first-level folders
        const first = addRow(bar);
        if (st.preset) {
            const title = 'The folders of the UI Preset "' + st.preset + '", and the files outside any folder';
            addButton(first, "Auto", auto, title + " ; follows the preset", function () {
                select(st, "auto", []);
            }).classList.add("fnn-auto");
        }
        addButton(first, "All", st.mode === "all", "Everything", function () {
            select(st, "all", []);
        }).classList.add("fnn-all");
        if (st.preset) {
            const title = 'Everything for the UI Preset "' + st.preset + '": its folders, and the files outside any folder';
            addButton(first, "All (" + st.preset + ")", atAutoRoot, title, function () {
                select(st, "auto", []);
            }).classList.add("fnn-all-preset");
        }
        tree.children.forEach(function (node) {
            const selected = st.mode === "folder" && st.path[0] === node.name;
            const button = addFolderButton(st, first, node, [], "folder", selected);
            if (st.matchingNames.has(node.name)) button.classList.add("fnn-match");
        });

        // The folder whose subfolders make the next row, and its path.
        let node = null;
        let nodePath = [];
        if (st.mode === "folder") {
            node = childNamed(tree, st.path[0]);
            nodePath = [st.path[0]];
        } else if (auto) {
            if (st.matching.length === 1) {
                // one folder for the preset: its subfolders come straight away
                node = st.matching[0];
                nodePath = [node.name];
            } else if (st.matching.length > 1) {
                // several folders for the preset: they make a row of their own
                const row = addRow(bar);
                st.matching.forEach(function (match) {
                    addFolderButton(st, row, match, [], "auto", st.path[0] === match.name);
                });
                if (st.path.length) {
                    node = childNamed(tree, st.path[0]);
                    nodePath = [st.path[0]];
                }
            } else {
                addNote(bar, 'No folder belongs to the UI Preset "' + st.preset + '".');
            }
        }

        // one more row for each selected folder that has subfolders
        while (node && node.children.length) {
            const row = addRow(bar);
            const selectedName = st.path[nodePath.length];
            const parentPath = nodePath;
            node.children.forEach(function (sub) {
                addFolderButton(st, row, sub, parentPath, st.mode, selectedName === sub.name);
            });
            if (selectedName === undefined) break;
            node = childNamed(node, selectedName);
            nodePath = nodePath.concat(selectedName);
        }
    }

    // --- filtering ---------------------------------------------------------

    function textOf(card) {
        let text = cardText.get(card);
        if (text === undefined) {
            text = Array.prototype.map
                .call(card.querySelectorAll(".search_terms, .description"), function (el) {
                    return el.textContent.toLowerCase();
                })
                .join(" ");
            cardText.set(card, text);
        }
        return text;
    }

    /** Is a card whose file is in `folder` ("" for a file outside any folder) inside the selection? */
    function inScope(st, folder, prefix) {
        if (st.mode === "all") return true;
        if (st.path.length) return folder === prefix || folder.startsWith(prefix + "/");

        // the Auto root
        if (folder === "") return true;
        const cut = folder.indexOf("/");
        return st.matchingNames.has(cut === -1 ? folder : folder.slice(0, cut));
    }

    /**
     * Decide which cards of this page show: inside the selection, matching the search box (the stock rule: every
     * space-separated part must be found), and not a hidden-folder card unless the search is long enough.
     * Runs after the stock filter and overrules it for this page's cards.
     */
    function applyScope(st) {
        if (!st.data) return;

        const term = st.search ? st.search.value.toLowerCase() : "";
        const parts = term.split(" ");
        const prefix = st.path.join("/");
        const items = st.data.items;

        gradioApp()
            .querySelectorAll("#" + st.id + " div.card")
            .forEach(function (card) {
                // a card the server did not list (added since the last Refresh) counts as a file outside any folder
                const folder = items.get(card.dataset.name) || "";
                let visible = inScope(st, folder, prefix);

                if (visible && card.querySelector(".search_only") && term.length < 4) visible = false;

                if (visible && term) {
                    const text = textOf(card);
                    visible = parts.every(function (part) {
                        return text.indexOf(part) !== -1;
                    });
                }

                card.classList.toggle("hidden", !visible);
            });
    }

    // --- keeping in step with the page -------------------------------------

    /**
     * Called after anything that may have changed the page: the stock filter ran (tab selected, Refresh, UI Preset
     * changed), the search box changed, or the page's HTML changed. Refresh replaces the whole pane, stock bar
     * included; the bar is then drawn again from fresh data.
     */
    function sync(st) {
        const bar = barElement(st);
        if (!bar) return; // Tree style has no bar element: nothing to do

        if (bar.classList.contains("fnn-bar")) {
            if (readPreset(st) !== st.preset) draw(st);
            applyScope(st);
            return;
        }
        if (bar.dataset.fnnFailed || st.loading || !isEnabled()) return;

        st.loading = true;
        fetchData(st.page)
            .then(function (data) {
                st.data = data;
                draw(st);
                applyScope(st);
            })
            .catch(function (error) {
                // leave the stock bar in place, and do not ask again until the pane is rebuilt
                const current = barElement(st);
                if (current) current.dataset.fnnFailed = "1";
                st.data = null;
                console.error(LOG, st.id, error);
            })
            .finally(function () {
                st.loading = false;
            });
    }

    function setupPage(id) {
        const cut = id.indexOf("_");
        const tabElement = gradioApp().getElementById(id);
        if (cut < 1 || !tabElement) return;

        const st = {
            id: id,
            tab: id.slice(0, cut),
            page: id.slice(cut + 1),
            data: null,
            mode: defaultMode(),
            path: [],
            preset: "",
            matching: [],
            matchingNames: new Set(),
            search: null,
            loading: false,
            timer: null,
        };
        states[id] = st;

        // The stock setup moved the search box into the tab bar; after a Refresh a second, unused one sits in the pane.
        st.search =
            gradioApp().querySelector("#" + st.tab + "_extra_tabs .extra-networks-controls-div #" + id + "_extra_search") ||
            gradioApp().getElementById(id + "_extra_search");
        if (st.search) {
            // registered after the stock listener, so it runs after the stock filter
            st.search.addEventListener("input", function () {
                sync(st);
            });
        }

        // Tab selection, Refresh and a UI Preset change all go through this table.
        const stockFilter = extraNetworksApplyFilter[id];
        extraNetworksApplyFilter[id] = function (force) {
            try {
                stockFilter(force);
            } finally {
                sync(st);
            }
        };

        new MutationObserver(function () {
            clearTimeout(st.timer);
            st.timer = setTimeout(function () {
                sync(st);
            }, 30);
        }).observe(tabElement, { childList: true, subtree: true });

        sync(st);
    }

    /**
     * Forge tells the pages about a new UI Preset only after the server has handled the change, which can take
     * seconds, and not at all for a page that is not open. Looking at the dropdown is cheap and has no such gaps.
     */
    function watchPreset() {
        let lastText = null;
        setInterval(function () {
            const input = gradioApp().querySelector("#forge_ui_preset input");
            const text = input ? input.value : "";
            if (text === lastText) return;
            lastText = text;
            Object.keys(states).forEach(function (id) {
                sync(states[id]);
            });
        }, 400);
    }

    function stockIsReady() {
        return typeof extraNetworksApplyFilter !== "undefined" && Object.keys(extraNetworksApplyFilter).length > 0;
    }

    onUiLoaded(function () {
        // The stock setup runs some time after onUiLoaded, once the pages' HTML has arrived.
        let tries = 0;
        const timer = setInterval(function () {
            if (stockIsReady()) {
                clearInterval(timer);
                Object.keys(extraNetworksApplyFilter).forEach(setupPage);
                watchPreset();
            } else if (++tries > 1200) {
                clearInterval(timer);
                console.warn(LOG, "the Extra Networks pages were not found");
            }
        }, 250);
    });
})();
