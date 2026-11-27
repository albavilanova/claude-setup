#!/usr/bin/env python3
"""Apply the working agreement of this folder to one project.

    python3 setup_project.py [<project folder>] [--name NAME]

- Creates CLAUDE.md, WIP.md, DECISIONS.md and MINIMAP.md from templates/, with the project's
  name. For a file the project already has, it asks whether to overwrite it; if so,
  the old version is kept as <file>.bak (.bak2… if taken).
- Adds those four files, WIP-archive.md and DECISIONS-archive.md (written by the /work skill's
  archive.py), and their .bak copies, to the project's .gitignore.

Asks for anything not given. Standard library only. Safe to run again. The Work status page
(/work skill) is set up separately, with setup_work.py.
"""
import argparse
import os

HERE = os.path.dirname(os.path.abspath(__file__))


def ask(question, default=""):
    """Ask on the terminal; an empty answer gives the default."""
    answer = input(f"{question} [{default}]: " if default else f"{question}: ").strip()
    return answer or default


def apply_files(project, name):
    """Copy the four templates into the project.

    A file the project already has is overwritten only if the user says so, after its old version
    is renamed to <file>.bak (or .bak2, .bak3… if taken). Returns (created, overwritten, skipped),
    overwritten being (file, its copy) pairs.
    """
    sources = {
        "CLAUDE.md": os.path.join(HERE, "templates", "CLAUDE.template.md"),
        "WIP.md": os.path.join(HERE, "templates", "WIP.template.md"),
        "DECISIONS.md": os.path.join(HERE, "templates", "DECISIONS.template.md"),
        "MINIMAP.md": os.path.join(HERE, "templates", "MINIMAP.template.md"),
    }
    created, overwritten, skipped = [], [], []

    for target, source in sources.items():
        path = os.path.join(project, target)
        if os.path.exists(path):
            if ask(f"{target} exists. Overwrite it? [y/N]").lower() not in ("y", "yes"):
                skipped.append(target)
                continue

            copy, n = path + ".bak", 1
            while os.path.exists(copy):
                n += 1
                copy = f"{path}.bak{n}"

            os.rename(path, copy)
            overwritten.append((target, os.path.basename(copy)))
        else:
            created.append(target)

        with open(source, encoding="utf-8") as f:
            text = f.read().replace("<PROJECT NAME>", name)

        with open(path, "w", encoding="utf-8") as f:
            f.write(text)

    return created, overwritten, skipped


def update_gitignore(project):
    """Add the four memory files, their two archives, and their .bak copies to the project's .gitignore; return the lines added."""
    path = os.path.join(project, ".gitignore")
    lines = open(path, encoding="utf-8").read().splitlines() if os.path.exists(path) else []
    wanted = [f + suffix for suffix in ("", ".bak*") for f in ("CLAUDE.md", "MINIMAP.md", "WIP.md", "WIP-archive.md", "DECISIONS.md", "DECISIONS-archive.md")]
    added = [f for f in wanted if f not in lines and "/" + f not in lines]

    if added:
        with open(path, "a", encoding="utf-8") as f:
            if lines and lines[-1].strip():
                f.write("\n")
            f.write(f"# Claude Code working agreement and memory files ({HERE})\n" + "\n".join(added) + "\n")

    return added


def main():
    # the project folder and its name, from the command line or asked
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("project", nargs="?", help="the project's folder (asked if not given)")
    parser.add_argument("--name", help="the project's name in the titles of CLAUDE.md, WIP.md and MINIMAP.md (asked if not given)")
    args = parser.parse_args()

    project = os.path.realpath(os.path.expanduser(args.project or ask("Project folder", os.getcwd())))

    if not os.path.isdir(project):
        parser.error(f"{project} is not a folder")

    name = args.name or ask("Project name", os.path.basename(project))

    # write the four files, then keep them out of the project's git
    created, overwritten, skipped = apply_files(project, name)
    ignored = update_gitignore(project)

    # report what was done
    print(f"\nProject: {project}")
    print("  Created: " + (", ".join(created) or "nothing"))

    if overwritten:
        print("  Overwritten, the old version kept as: " + ", ".join(f"{t} -> {c}" for t, c in overwritten))

    if skipped:
        print("  Kept as they were: " + ", ".join(skipped))

    print("  Added to .gitignore: " + (", ".join(ignored) or "nothing, already there"))

    # a new CLAUDE.md still has its <...> placeholders: say how to fill them
    if "CLAUDE.md" in created or "CLAUDE.md" in dict(overwritten):
        print("\n  To do: CLAUDE.md has <...> placeholders for what is specific to this project: how to test it,")
        print("  where its dependencies and modules are, and what Claude must ask you about before changing")
        print("  (settings, public APIs, commands, patterns). To fill them, start Claude Code in the project and ask:")
        print('    "Read this project and fill in the <...> placeholders of CLAUDE.md; show me Before and After."')

    # the four files are ignored by git, so nothing else keeps their history
    print("\nGit keeps no history of the four files: keep a copy elsewhere.")


if __name__ == "__main__":
    main()
