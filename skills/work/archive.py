#!/usr/bin/env python3
"""Keep in WIP.md and DECISIONS.md only what the active features need, and the rest in their archives.

    python3 archive.py [--dry-run] [--root DIR ...]

For each project listed in config.json (found as build_page.py finds them):

- A feature of WIP.md (a `##` section) is active while it has a step not done or an Open
  decision; a dropped feature never is. The active features, and the features a step of theirs
  names (`S12`, `providentia S63`, in any listed project), stay in WIP.md. Every other feature's
  section moves, as it is, to WIP-archive.md, newest first (by its largest step number), and
  moves back when it qualifies again, placed among the features of WIP.md by its largest step
  number. The lines above the first feature and the other `##` sections ("Last session") stay.
- A decision stays in DECISIONS.md when it is Open, Pending, Parked or Unverified, or belongs to
  a feature that stays in WIP.md: its heading's range, or a link of its steps, as on the Work
  status page. Every other decision moves to DECISIONS-archive.md, newest first, and moves back
  when it qualifies again.

Links to a step or decision that moved are rewritten in every .md file at the root of every
listed project, links from other projects included, and the links inside a moved row or section
are rewritten for the file it moves to.

Prints, for each project, what moved each way and the links changed in each file; with --dry-run
it writes nothing. --root DIR works as in build_page.py, for testing on copies. Standard library
only.
"""
import argparse
import glob
import os
import re
import sys

from build_page import NOT_SETTLED, plain, project_dirs, read_config, read_projects, step_refs, wip_features

DECISION_FILES = ("DECISIONS.md", "DECISIONS-archive.md")
WIP_FILES = ("WIP.md", "WIP-archive.md")
FILES = {"decision": DECISION_FILES, "step": WIP_FILES}


def read_table(path):
    """The lines before the Decisions table's rows, its rows by number, and the lines after them;
    (None, {}, []) when the file does not exist. Stops if a line between two rows is not a row,
    as it would be lost when the rows are written again."""
    if not os.path.exists(path):
        return None, {}, []

    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    at = [i for i, line in enumerate(lines) if line.startswith('| <a id="decision-')]

    if not at:
        return lines, {}, []

    if len(at) != at[-1] - at[0] + 1:
        sys.exit(f"{path}: the Decisions table has lines that are not rows between its rows. Nothing was changed.")

    rows = {int(re.search(r'decision-(\d+)"', lines[i]).group(1)): lines[i] for i in at}
    return lines[:at[0]], rows, lines[at[-1] + 1:]


def read_wip(path):
    """A WIP file as blocks, in order: ("text", lines) for the lines above the first `##` heading
    and for each `##` section that is not a feature ("Last session"), and ("feature", feature)
    for each feature, from wip_features, with its file, its section's lines, its step numbers
    (dropped steps included) and its largest step number. None when the file does not exist."""
    if not os.path.exists(path):
        return None

    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    features = {f["start"]: f for f in wip_features(lines)}
    starts = sorted(set([0] + [i for i, line in enumerate(lines) if line.startswith("## ")]))
    blocks = []

    for start, end in zip(starts, starts[1:] + [len(lines)]):
        if start in features:
            f = features[start]
            f["file"], f["lines"] = path, lines[start:end]
            f["numbers"] = [int(n) for n in re.findall(r'<a id="step-(\d+)">', "\n".join(f["lines"]))]
            f["top"] = max(f["numbers"], default=0)
            blocks.append(("feature", f))
        elif end > start:
            blocks.append(("text", lines[start:end]))

    return blocks


def kept(projects):
    """The features that stay in WIP.md, as ids, and for each project slug the numbers of the
    decisions that stay in DECISIONS.md. A project's "features" here are those of both WIP
    files, dropped ones included, and its decisions those of both decision files."""
    names = {p["name"].lower(): p["slug"] for p in projects}
    feature_of, staying = {}, set()

    for p in projects:
        for f in p["features"]:
            feature_of.update({f"{p['slug']}:S{n}": id(f) for n in f["numbers"]})

    for p in projects:
        kinds = {d["n"]: d["kind"] for d in p["decisions"]}
        for f in p["features"]:
            finished = all(s["status"].startswith("Done") for s in f["steps"]) and not any(kinds.get(n) == "Open" for n in f["decisions"])
            if f["dropped"] or finished:
                continue
            staying.add(id(f))
            for s in f["steps"]:
                staying.update(feature_of[key] for key, _, _ in step_refs(plain(s["text"]), p["slug"], names) if key in feature_of)

    decisions = {}

    for p in projects:
        decisions[p["slug"]] = {d["n"] for d in p["decisions"] if d["kind"] in NOT_SETTLED}
        for f in p["features"]:
            if id(f) in staying:
                decisions[p["slug"]] |= f["decisions"]

    return staying, decisions


def rewrite_links(text, source, dest, where):
    """text, read in the file source and written to the file dest of the same folder, with every
    link to a step or decision pointed at the file it is in now. where maps (folder of a project,
    "step" or "decision", number) to the name of its file. Returns the text and the links changed."""
    pieces, end, changed = [], 0, 0

    for m in re.finditer(r"\]\(([^)#\s]*)#(decision|step)-(\d+)\)", text):
        link, kind = m.group(1), m.group(2)
        target = os.path.normpath(os.path.join(os.path.dirname(source), link)) if link else source
        if os.path.basename(target) not in FILES[kind]:
            continue

        now = where.get((os.path.dirname(target), kind, int(m.group(3))))
        new_target = os.path.join(os.path.dirname(target), now) if now else target

        if new_target == dest:
            new = ""
        elif os.path.dirname(new_target) == os.path.dirname(dest):
            new = os.path.basename(new_target)
        else:
            new = os.path.join(os.path.dirname(link), os.path.basename(new_target))

        if new != link:
            pieces += [text[end:m.start(1)], new]
            end, changed = m.end(1), changed + 1

    return "".join(pieces) + text[end:], changed


def wip_texts(p, staying, where, links):
    """The new WIP.md and WIP-archive.md of project p, as {path: text} (an archive is not created
    while no feature goes there), with their links rewritten and counted in links; and the names
    of the features moved, as {name of the file they moved to: [names]}."""
    blocks, out, moved = p["wip"], {}, {name: [] for name in WIP_FILES}
    main_blocks = [b for b in blocks["WIP.md"] or [] if b[0] == "text" or id(b[1]) in staying]
    archived = [b for name in WIP_FILES for b in blocks[name] or [] if b[0] == "feature" and id(b[1]) not in staying]
    incoming = [b for b in blocks["WIP-archive.md"] or [] if b[0] == "feature" and id(b[1]) in staying]

    # a feature coming back goes before the first feature of WIP.md with a smaller largest step,
    # else after the last feature, else before the first other section ("Last session")
    for block in sorted(incoming, key=lambda b: b[1]["top"], reverse=True):
        features = [i for i, b in enumerate(main_blocks) if b[0] == "feature"]
        later = [i for i in features if main_blocks[i][1]["top"] < block[1]["top"]]
        sections = [i for i, b in enumerate(main_blocks) if b[0] == "text" and b[1][0].startswith("## ")]
        at = later[0] if later else (features[-1] + 1 if features else (sections[0] if sections else len(main_blocks)))
        main_blocks.insert(at, block)

    # the archive keeps its own text above the features, or gets this one when it is created
    archive_text = [b for b in blocks["WIP-archive.md"] or [] if b[0] == "text"] or [("text", [
        "# WIP archive", "",
        "The finished features no active feature needs, moved here from WIP.md by `archive.py` of the `/work` skill at wrapup, "
        "newest first; a feature moves back when it is active again or a step of an active feature names it. "
        "Not read at the start of a session. Format: see \"Table formats\" in CLAUDE.md.", ""])]
    archive_blocks = archive_text + sorted(archived, key=lambda b: b[1]["top"], reverse=True)

    for name, file_blocks in (("WIP.md", main_blocks), ("WIP-archive.md", archive_blocks)):
        if blocks[name] is None and not any(b[0] == "feature" for b in file_blocks):
            continue
        dest, parts = os.path.join(p["dir"], name), []

        for kind, content in file_blocks:
            source, lines = (dest, content) if kind == "text" else (content["file"], content["lines"])
            if source != dest:
                # a moved section ends with one blank line, whatever it had where it was
                moved[name].append(plain(re.sub(r"\s*\((?:branch|\[D).*\)\s*$", "", content["title"])))
                lines = "\n".join(lines).rstrip().split("\n") + [""]
            text, changed = rewrite_links("\n".join(lines), source, dest, where)
            links[name] = links.get(name, 0) + changed
            parts.append(text)

        out[dest] = "\n".join(parts).rstrip("\n") + "\n"

    return out, moved


def decision_texts(p, where, links):
    """The new DECISIONS.md and DECISIONS-archive.md of project p, as {path: text}, with their
    links rewritten and counted in links; and the decisions moved, as {name of the file they
    moved to: [numbers]}."""
    tables, out = p["tables"], {}
    new_rows, moved = {name: {} for name in DECISION_FILES}, {name: [] for name in DECISION_FILES}
    archive_head = [
        "# Decisions archive", "",
        "The decisions no active feature needs, moved here from DECISIONS.md by `archive.py` of the `/work` skill at "
        "wrapup; a decision moves back when its feature is active again or it is no longer settled. "
        "Format: see \"Table formats\" in CLAUDE.md.", "",
        "| # | Date | Status | Context | Question | Options |", "|---|---|---|---|---|---|",
    ]

    for source_name in DECISION_FILES:
        source = os.path.join(p["dir"], source_name)
        for n, row in tables[source_name][1].items():
            dest_name = where[(p["dir"], "decision", n)]
            row, changed = rewrite_links(row, source, os.path.join(p["dir"], dest_name), where)
            new_rows[dest_name][n] = row
            links[dest_name] = links.get(dest_name, 0) + changed
            if dest_name != source_name:
                moved[dest_name].append(n)

    for name in DECISION_FILES:
        head, _, tail = tables[name]
        if head is None and not new_rows[name]:
            continue
        path = os.path.join(p["dir"], name)
        # the lines around the table (its introduction) can link to decisions too
        around, changed = rewrite_links("\n".join((head if head is not None else archive_head) + ["\0"] + tail), path, path, where)
        links[name] = links.get(name, 0) + changed
        before, after = around.split("\0")
        body = [new_rows[name][n] for n in sorted(new_rows[name], reverse=True)]
        out[path] = before + "\n".join(body) + after + "\n"

    return out, moved


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="print what would move and which links would change, and write nothing")
    parser.add_argument("--root", action="append", help="every project found in this folder (repeat for several), instead of config.json")
    args = parser.parse_args()
    config_path, config = read_config(args.root)
    projects, _, _ = read_projects([os.path.normpath(os.path.abspath(d)) for d in project_dirs(config, config_path, args.root)])

    for p in projects:
        p["tables"] = {name: read_table(os.path.join(p["dir"], name)) for name in DECISION_FILES}
        p["wip"] = {name: read_wip(os.path.join(p["dir"], name)) for name in WIP_FILES}
        p["features"] = [f for name in WIP_FILES for kind, f in p["wip"][name] or [] if kind == "feature"]

    staying, decisions = kept(projects)

    # the file each step and decision is in after the move, for every project, before any link is rewritten
    where = {}

    for p in projects:
        main_rows, archive_rows = p["tables"]["DECISIONS.md"][1], p["tables"]["DECISIONS-archive.md"][1]
        both = sorted(set(main_rows) & set(archive_rows))
        if both:
            sys.exit(f"{p['name']}: D" + ", D".join(map(str, both)) + " are in both DECISIONS.md and DECISIONS-archive.md. Nothing was changed.")
        for n in list(main_rows) + list(archive_rows):
            where[(p["dir"], "decision", n)] = "DECISIONS.md" if n in decisions[p["slug"]] else "DECISIONS-archive.md"
        for f in p["features"]:
            for n in f["numbers"]:
                if (p["dir"], "step", n) in where:
                    sys.exit(f"{p['name']}: S{n} is in WIP.md and WIP-archive.md, or twice in one of them. Nothing was changed.")
                where[(p["dir"], "step", n)] = "WIP.md" if id(f) in staying else "WIP-archive.md"

    writes, report = {}, []

    for p in projects:
        links = {}
        wip_out, features_moved = wip_texts(p, staying, where, links)
        decision_out, decisions_moved = decision_texts(p, where, links)
        writes.update(wip_out)
        writes.update(decision_out)

        # the other .md files of the project only have their links rewritten
        for path in sorted(glob.glob(os.path.join(p["dir"], "*.md"))):
            if os.path.basename(path) in DECISION_FILES + WIP_FILES:
                continue
            with open(path, encoding="utf-8") as f:
                text = f.read()
            text, changed = rewrite_links(text, path, path, where)
            if changed:
                writes[path], links[os.path.basename(path)] = text, changed

        count = {(kind, name): 0 for kind in FILES for name in FILES[kind]}
        for (d, kind, _), name in where.items():
            if d == p["dir"] and kind == "decision":
                count[(kind, name)] += 1
        in_wip = sum(1 for f in p["features"] if id(f) in staying)
        out_d, back_d = sorted(decisions_moved["DECISIONS-archive.md"], reverse=True), sorted(decisions_moved["DECISIONS.md"], reverse=True)
        report += [
            f"{p['name']}: {in_wip} features in WIP.md, {len(p['features']) - in_wip} in WIP-archive.md; "
            f"{count[('decision', 'DECISIONS.md')]} decisions in DECISIONS.md, {count[('decision', 'DECISIONS-archive.md')]} in DECISIONS-archive.md",
            f"  features to the archive ({len(features_moved['WIP-archive.md'])}): " + ("; ".join(features_moved["WIP-archive.md"]) or "none"),
            f"  features back to WIP.md ({len(features_moved['WIP.md'])}): " + ("; ".join(features_moved["WIP.md"]) or "none"),
            f"  decisions to the archive ({len(out_d)}): " + (", ".join(f"D{n}" for n in out_d) or "none"),
            f"  decisions back to DECISIONS.md ({len(back_d)}): " + (", ".join(f"D{n}" for n in back_d) or "none"),
            "  links changed: " + (", ".join(f"{name} {c}" for name, c in sorted(links.items()) if c) or "none"),
        ]

    print("\n".join(report))

    if args.dry_run:
        print("Dry run: nothing was written.")
        return

    for path, text in writes.items():
        old = None
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                old = f.read()
        if text != old:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"Wrote {path}")


if __name__ == "__main__":
    main()
