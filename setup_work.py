#!/usr/bin/env python3
"""Install or update the /work skill, for the projects listed in config.json.

    python3 setup_work.py

configurations/config.json, in this folder, is yours and ignored by git
(configurations/config.example.json shows the format):

    {"projects": {"<folder>": ["<project>", ...], ...}, "order": ["<project>", ...]}

"projects" names, for each folder where projects live, the projects to show on the page: a
project is a folder with a DECISIONS.md, the folder itself or one or two levels below it.
"order" gives the order of the tabs, and must name every project of "projects".

- Stops, installing nothing, if config.json is missing or a project is missing from "order".
- Copies skills/work/ (SKILL.md, build_page.py, style.css, script.js) to ~/.claude/skills/work/.
  An installed file that differs from this version is overwritten only if the user says so,
  after its old version is kept as <file>.bak (.bak2… if taken); an identical one is left as it is.
- Tells the installed skill where config.json is (~/.claude/skills/work/paths.json).
- Prints the tabs in order, and for each folder the listed projects with no DECISIONS.md; names
  in "order" that are not in "projects" are ignored.
- Compares config.json with the config the page was last built with
  (configurations/last_build_config.json, written by build_page.py when /work builds the page;
  folders compared after expanding ~), and says to run /work if a folder's projects or the
  order changed.

Standard library only. Safe to run again.
"""
import argparse
import glob
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def read_config(config_path):
    """Read config.json and check it: it exists, "order" names every project of "projects", and
    no project is listed twice. Stops, installing nothing, otherwise.

    Returns (projects, order, listed): the folders with their projects, the tab order, and every
    listed project name.
    """
    if not os.path.exists(config_path):
        sys.exit(f"{config_path} does not exist. Create it with your folders, projects and their order\n"
                 f"(see {os.path.join(HERE, 'configurations', 'config.example.json')}), then run this again. Nothing was installed.")

    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    projects = config.get("projects") if isinstance(config.get("projects"), dict) else {}
    order = config.get("order", [])
    listed = [name for names in projects.values() for name in names]
    not_ordered = [name for name in listed if name not in order]

    if not_ordered:
        sys.exit(f'In {config_path}, "order" must name every project of "projects". Missing: '
                 + ", ".join(not_ordered) + ". Nothing was installed.")

    # one name per project: the page and the answers copied from it name projects by folder name
    repeated = sorted({name for name in listed if listed.count(name) > 1})

    if repeated:
        sys.exit(f'In {config_path}, a project can be listed only once in "projects". Listed more than once: '
                 + ", ".join(repeated) + ". Rename one of the folders. Nothing was installed.")

    return projects, order, listed


def install_skill(skill_dir, config_path):
    """Copy SKILL.md, build_page.py, style.css and script.js into skill_dir, and write paths.json there.

    An installed file that differs from this version is overwritten only if the user says so,
    after it is renamed to <file>.bak (.bak2, .bak3… if taken). Returns the lists (installed,
    same, overwritten, kept), overwritten being (file, its copy) pairs.
    """
    os.makedirs(skill_dir, exist_ok=True)
    installed, same, overwritten, kept = [], [], [], []

    for f in ("SKILL.md", "build_page.py", "style.css", "script.js"):
        source, target = os.path.join(HERE, "skills", "work", f), os.path.join(skill_dir, f)
        if os.path.exists(target):
            with open(source, "rb") as a, open(target, "rb") as b:
                if a.read() == b.read():
                    same.append(f)
                    continue

            answer = input(f"{f} exists in {skill_dir} and differs from this version. Overwrite it? [y/N]: ").strip()
            if answer.lower() not in ("y", "yes"):
                kept.append(f)
                continue

            # the first free name among <file>.bak, <file>.bak2, <file>.bak3…
            copy, n = target + ".bak", 1
            while os.path.exists(copy):
                n += 1
                copy = f"{target}.bak{n}"

            os.rename(target, copy)
            overwritten.append((f, os.path.basename(copy)))
        else:
            installed.append(f)
        shutil.copy2(source, target)

    # the installed build_page.py is outside this repository: paths.json tells it where config.json is
    with open(os.path.join(skill_dir, "paths.json"), "w", encoding="utf-8") as f:
        json.dump({"config": config_path}, f, indent=2)
        f.write("\n")

    return installed, same, overwritten, kept


def report_projects(projects, order, listed):
    """Print the tabs in order, the names in "order" that are ignored, and, per folder, the
    listed projects with no DECISIONS.md (the page skips them)."""
    print("  " + (", ".join(name for name in order if name in listed) or "none: add folders and projects to config.json"))
    unknown = [name for name in order if name not in listed]

    if unknown:
        print('  In "order" but not in "projects", ignored: ' + ", ".join(unknown))

    for folder, names in projects.items():
        # a project is found in the folder itself or one or two levels below it, as build_page.py does
        found = sorted({os.path.basename(os.path.dirname(p)) for pattern in ("DECISIONS.md", "*/DECISIONS.md", "*/*/DECISIONS.md")
                        for p in glob.glob(os.path.join(os.path.expanduser(folder), pattern))})
        no_decisions = [p for p in names if p not in found]
        if no_decisions:
            print(f"  {folder}: listed, but no DECISIONS.md found: " + ", ".join(no_decisions))


def report_changes(projects, order, build_path):
    """Compare config.json with the config the page was last built from (build_path, written by
    build_page.py), and print what changed and whether to run /work."""
    if not os.path.exists(build_path):
        print("\nNo record of the page's last build yet: /work writes it when it builds the page.")
        return

    with open(build_path, encoding="utf-8") as f:
        built = json.load(f)

    # folders compared after expanding ~, so a folder written in two ways is the same folder
    old = {os.path.expanduser(k): v for k, v in built.get("projects", {}).items()}
    new = {os.path.expanduser(k): v for k, v in projects.items()}
    changes = []

    for folder in list(old) + [k for k in new if k not in old]:
        removed = [p for p in old.get(folder, []) if p not in new.get(folder, [])]
        added = [p for p in new.get(folder, []) if p not in old.get(folder, [])]
        if removed:
            changes.append(f"{folder}: removed " + ", ".join(removed))

        if added:
            changes.append(f"{folder}: added " + ", ".join(added))

    # the order is compared only on the projects in both, so an added or removed one is not also an order change
    old_order = [p for p in built.get("order", []) if p in order]

    if old_order != [p for p in order if p in old_order]:
        changes.append("order changed (was: " + ", ".join(built.get("order", [])) + ")")

    if changes:
        print("\nChanged in config.json since the page was last built:")
        for change in changes:
            print("  " + change)
        print("Run /work in Claude Code to update the page.")
    else:
        print("\nThe page was built with this config.json.")


def main():
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    config_path = os.path.join(HERE, "configurations", "config.json")
    projects, order, listed = read_config(config_path)
    skill_dir = os.path.expanduser("~/.claude/skills/work")
    installed, same, overwritten, kept = install_skill(skill_dir, config_path)
    print(f"/work skill in {skill_dir}")

    if installed:
        print("  Installed: " + ", ".join(installed))

    if same:
        print("  Already up to date: " + ", ".join(same))

    if overwritten:
        print("  Updated, the old version kept as: " + ", ".join(f"{f} -> {c}" for f, c in overwritten))

    if kept:
        print("  Kept as they were (not updated): " + ", ".join(kept))

    print(f"\nTabs, in order ({config_path}):")
    report_projects(projects, order, listed)
    report_changes(projects, order, os.path.join(HERE, "configurations", "last_build_config.json"))
    print("\nIn Claude Code, type /work to wrap up and publish the Work status page.")


if __name__ == "__main__":
    main()
