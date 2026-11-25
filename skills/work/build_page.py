#!/usr/bin/env python3
"""Build the /work status page: one tab per project that has a DECISIONS.md.

Reads WIP.md (features, steps, where we are, open, last session) and
DECISIONS.md (every decision and its status) of each project, and writes one
self-contained HTML file. Standard library only.

    python3 build_page.py [--root DIR ...] [--out FILE]

The projects shown are those listed in configurations/config.json of the claude-setup repository,
found through paths.json next to this file ({"config": "<path>"}, written by
setup_work.py). config.json names each folder's projects, and their order:
{"projects": {"~/software": ["project-1", "project-2"], "~/work": ["project-3"]},
 "order": ["project-2", "project-3", "project-1"]}.
Only listed projects are shown, in the order of "order", which must name them all (the
build stops otherwise); a name in "order" that is not listed is ignored, and a listed
project with no DECISIONS.md is skipped, both with a warning. --root DIR (repeatable) shows instead every project found in
those folders, alphabetically, for testing; with neither, every project in ~/software.
Prints the path of the HTML file it wrote. A build from config.json also writes its config
("projects" and "order") to last_build_config.json next to config.json, which setup_work.py compares
with config.json.
"""
import argparse
import glob
import html
import itertools
import json
import os
import re
import sys
import tempfile
from datetime import datetime

# Statuses of a decision that is not settled (CLAUDE.md, "Decisions not settled").
NOT_SETTLED = ("Open", "Pending", "Parked", "Unverified")


def find_projects(roots):
    """Folders that hold a DECISIONS.md: each root itself, and up to two levels under it."""
    paths = []

    for root in roots:
        root = os.path.expanduser(root)
        paths += glob.glob(os.path.join(root, "DECISIONS.md")) + glob.glob(os.path.join(root, "*", "DECISIONS.md"))
        paths += glob.glob(os.path.join(root, "*", "*", "DECISIONS.md"))

    return sorted({os.path.dirname(os.path.realpath(p)) for p in paths})


def split_row(line):
    """Cells of a markdown table row; an escaped pipe stays inside its cell."""
    cells = re.split(r"(?<!\\)\|", line.strip().strip("|"))
    return [c.strip().replace("\\|", "|") for c in cells]


def parse_decisions(path):
    """Every row of the Decisions table of DECISIONS.md: number, date, status and its first word
    (kind), context, question, options, and the chosen option without its letter and bold."""
    decisions = []

    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.startswith('| <a id="decision-'):
                continue

            cells = split_row(line) + [""] * 6
            number = int(re.search(r"D(\d+)", cells[0]).group(1))
            options = cells[5].split("<br>")
            chosen = next((o for o in options if "**" in o), "")
            decisions.append({
                "n": number, "date": cells[1], "status": cells[2], "kind": cells[2].split(" ")[0],
                "context": cells[3], "question": cells[4], "options": options,
                "chosen": re.sub(r"^\s*\*\*[A-Za-z]:\s*|\*\*", "", chosen).strip(),
            })

    return decisions


def parse_wip(path):
    """Features of WIP.md (one per `##` heading, except "Last session"), with their steps and the
    decisions they cite. The text of WIP.md (where we are, open, last session) is not read, as
    the page does not show it."""
    features = []
    in_feature = False  # whether the step rows that follow belong to the last feature

    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()

    for line in lines:
        heading = re.match(r"^## (.*)$", line)
        if heading:
            in_feature = not heading.group(1).startswith("Last session")
            if in_feature:
                features.append({"title": heading.group(1), "steps": []})
        elif in_feature and line.startswith('| <a id="step-'):
            cells = split_row(line) + [""] * 6
            status, commit = cells[4], cells[5]

            # a commit written in the Status cell ("Done 1a2b3c4") is moved to its own cell
            glued = re.match(r"^(Done|Not started)\s+(\S+)$", status)
            if glued:
                status, commit = glued.group(1), commit or glued.group(2)

            features[-1]["steps"].append({
                "n": int(re.search(r"S(\d+)", cells[0]).group(1)), "added": cells[1], "date": cells[2],
                "text": cells[3], "status": status, "commit": commit,
            })

    # dropped work is not shown: a feature whose heading says "dropped", a step whose text starts with "Dropped",
    # and a feature whose steps were all dropped
    features = [f for f in features if not re.search(r"(?i)\bdropped\b", f["title"].split("(")[0])]

    for feature in features:
        had_steps = bool(feature["steps"])
        feature["steps"] = [s for s in feature["steps"] if not re.match(r"^(\*\*)?Dropped\b", s["text"])]
        feature["all_dropped"] = had_steps and not feature["steps"]

    features = [f for f in features if not f["all_dropped"]]

    for feature in features:
        rng = re.search(r"\[D(\d+)\]\(DECISIONS\.md#decision-\d+\)\s*[–-]\s*\[D(\d+)\]", feature["title"])
        feature["range"] = set(range(int(rng.group(1)), int(rng.group(2)) + 1)) if rng else set()
        cited = set(feature["range"])

        for text in [feature["title"]] + [s["text"] for s in feature["steps"]]:
            cited.update(int(n) for n in re.findall(r"\[D(\d+)\]\((?:DECISIONS\.md)?#decision-\d+\)", text))

        feature["decisions"] = cited

    return features


def resolve_href(href, ctx):
    """Page anchor for a link to a decision or step of a known project, the URL for a web link, else None."""
    if re.match(r"^https?://", href):
        return href

    path, _, frag = href.partition("#")
    target = os.path.normpath(os.path.join(ctx["dir"], path)) if path else os.path.join(ctx["dir"], ctx["file"])
    slug = ctx["slugs"].get(os.path.dirname(target))
    kind = re.match(r"^(decision|step)-(\d+)$", frag)

    if not (slug and kind and os.path.basename(target) == {"decision": "DECISIONS.md", "step": "WIP.md"}[kind.group(1)]):
        return None

    if kind.group(1) == "decision" and int(kind.group(2)) not in ctx["shown"][slug]:
        return None  # a decision in no feature and not to take is not on the page

    return f"#{slug}-{frag}"


def anchor_id(ctx, n):
    """The id attribute for decision n, on its first appearance in the page only."""
    anchor = f'{ctx["slug"]}-decision-{n}'

    if anchor in ctx["placed"]:
        return ""

    ctx["placed"].add(anchor)
    return f' id="{anchor}"'


def inline(text, ctx):
    """Markdown of one line or table cell (code, bold, links, <br>) as HTML."""
    codes = []
    text = re.sub(r'<a id="[^"]*"></a>', "", text)

    for code in re.findall(r"`([^`]+)`", text):
        codes.append(f"<code>{html.escape(code)}</code>")

    # code spans become numbered placeholders, in order, so bold and links around them still match
    count = iter(range(len(codes)))
    text = re.sub(r"`[^`]+`", lambda m: f"\x00{next(count)}\x00", text)
    text = html.escape(text, quote=False).replace("&lt;br&gt;", "<br>")
    links = re.findall(r"\[([^\]]+)\]\(([^)\s]+)\)", text)

    for label, href in links:
        target = resolve_href(html.unescape(href), ctx)
        if target is None:
            new = f'<span class="ref">{label}</span>'
        else:
            new = f'<a href="{html.escape(target)}">{label}</a>'
        text = text.replace(f"[{label}]({href})", new, 1)

    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], text)


def answer_panel(d, ctx):
    """The options and answer box of a decision not settled, opened under its row.

    Its lettered options can be picked, an "Other" box takes the user's own words, and "Copy
    answer" copies the "Update decisions log: …" line to paste into a chat (or shows it in a box
    to copy by hand, when the browser refuses the clipboard).
    """
    items = []

    for o in d["options"]:
        if not o.strip():
            continue

        lettered = re.match(r"^\s*(?:\*\*)?([A-Za-z])[:)]\s*(.*)$", o)
        words = re.sub(r"\*\*|`", "", re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", lettered.group(2) if lettered else o)).strip()
        if lettered and not re.match(r"(?i)^other\b", words):
            items.append(
                f'<li class="pickopt {"chosen" if "**" in o else ""}" role="radio" aria-checked="false" tabindex="0" '
                f'data-answer="{html.escape(lettered.group(1).upper() + ": " + words)}">{inline(o, ctx)}</li>'
            )
        elif not lettered:  # an option without a letter is shown, and the "Other" option is the box below
            items.append(f'<li class="{"chosen" if "**" in o else ""}">{inline(o, ctx)}</li>')

    # the question as plain text (no links, bold or code marks), for the copied answer
    question = re.sub(r"[*`]", "", re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", d["question"]))
    verb = "Answer" if d["kind"] == "Open" else "Change this decision"
    box = f'{ctx["slug"]}-other-{d["n"]}-{next(ctx["ids"])}'  # a decision can show in more than one table
    return (
        f'<div class="dec answerable" data-project="{html.escape(ctx["name"])}" data-n="{d["n"]}" data-kind="{html.escape(d["kind"])}" '
        f'data-question="{html.escape(question)}">'
        f'<p class="ahead">{verb}: pick an option, or write your own</p>'
        f'<ul class="opts" role="radiogroup">{"".join(items)}</ul>'
        f'<label class="olabel" for="{box}">Other (your words)</label>'
        f'<textarea class="other" id="{box}" rows="2"></textarea>'
        f'<div class="arow"><button type="button" class="send" disabled>Copy answer</button>'
        f'<span class="sendmsg" aria-live="polite"></span></div>'
        f'<textarea class="copybox" rows="3" readonly hidden aria-label="Answer to copy"></textarea></div>'
    )


def decisions_table(items, ctx, answer):
    """Decisions as a table like the steps: # | Question | Decision | Status | Date.

    With answer, a decision not settled has an Answer or Change button that opens its
    answer panel in a row underneath.
    """
    rows = []

    for d in items:
        answerable = answer and d["kind"] in NOT_SETTLED
        opener = (f'<button type="button" class="opener" aria-expanded="false">{"Answer" if d["kind"] == "Open" else "Change"}</button>'
                  if answerable else "")
        rows.append(
            f'<tr{anchor_id(ctx, d["n"])} class="drow"><td class="sn"><a class="num" href="#{ctx["slug"]}-decision-{d["n"]}">D{d["n"]}</a></td>'
            f'<td>{inline(d["question"], ctx)}<span class="sdate">{inline(d["context"], ctx)}</span></td>'
            f'<td>{inline(d["chosen"], ctx)}</td>'
            f'<td><span class="tag t-{d["kind"].lower()}">{html.escape(d["kind"])}</span></td>'
            f'<td class="commit">{d["date"]}</td><td class="act">{opener}</td></tr>'
            + (f'<tr class="ansrow" hidden><td class="full" colspan="6">{answer_panel(d, ctx)}</td></tr>' if answerable else "")
        )

    return ('<div class="scroll"><table class="steps stack dtable"><thead><tr><th>#</th><th>Question</th><th>Decision</th>'
            f'<th>Status</th><th>Date</th><th class="act">Answer / change</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def project_tab(project, ctx):
    """The HTML of one project's tab: its title and figures, the map of its features (active,
    past, and the decisions to take outside every feature), and one view per feature with its
    steps and decisions."""
    features, decisions = project["features"], project["decisions"]
    by_number = {d["n"]: d for d in decisions}
    dctx = dict(ctx, file="DECISIONS.md")  # links in decision cells are relative to DECISIONS.md

    # a feature is active while it has a step not done or a decision to take, else past
    rows, cards, finished_rows, finished_cards = [], [], [], []

    for i, f in enumerate(features):
        fid = f"{ctx['slug']}-feature-{i + 1}"
        done = sum(s["status"].startswith("Done") for s in f["steps"])
        mine = [by_number[n] for n in sorted(f["decisions"], reverse=True) if n in by_number]

        # to take: Open only; the rest is taken, and Pending, Parked or Unverified can still be changed
        waiting = [d for d in mine if d["kind"] == "Open"]
        changeable = [d for d in mine if d["kind"] in NOT_SETTLED and d["kind"] != "Open"]
        closed = [d for d in mine if d["kind"] not in NOT_SETTLED]

        # the feature's name without "(branch …, [D…]–[D…])", in the map and as the view's heading
        name = inline(re.sub(r"\s*\((?:branch|\[D).*\)\s*$", "", f["title"]), ctx)
        cells = "".join(
            f'<a href="#{ctx["slug"]}-step-{s["n"]}" class="cell {"on" if s["status"].startswith("Done") else ""}" '
            f'title="S{s["n"]}: {html.escape(s["status"])}"></a>' for s in f["steps"]
        )
        marks = "".join(f'<a href="#{ctx["slug"]}-decision-{d["n"]}" class="mark" title="D{d["n"]}: {html.escape(d["kind"])}"></a>' for d in waiting)
        active = done < len(f["steps"]) or waiting
        row = (
            f'<div class="frow"><a class="fname pick" href="#{fid}">{name}</a><div class="cells">{cells}</div>'
            f'<div class="fcount"><span class="marks">{marks}</span></div></div>'
        )
        (rows if active else finished_rows).append(row)

        # the steps, as a table
        steps = "".join(
            f'<tr id="{ctx["slug"]}-step-{s["n"]}"><td class="sn">S{s["n"]}</td><td>{inline(s["text"], ctx)}'
            f'<span class="sdate">added {s["added"]}, status {s["date"]}</span></td>'
            f'<td><span class="tag {"t-done" if s["status"].startswith("Done") else "t-todo"}">{html.escape(s["status"])}</span></td>'
            f'<td class="commit">{inline(s["commit"], ctx)}</td></tr>' for s in f["steps"]
        )
        table = (f'<div class="scroll"><table class="steps stack"><thead><tr><th>#</th><th>Step</th><th>Status</th>'
                 f'<th>Commit</th></tr></thead><tbody>{steps}</tbody></table></div>') if steps else ""

        # the decisions of a feature in four groups, one shown at a time
        groups = [(key, label, items, full) for key, label, items, full in (
            ("take", "To take", waiting, True),
            ("taken", "Taken, not yet applied", changeable, True),
            ("applied", "Applied", [d for d in closed if d["kind"] != "Replaced"], False),
            ("replaced", "Replaced", [d for d in closed if d["kind"] == "Replaced"], False),
        ) if items]
        dbuttons = "".join(
            f'<button type="button" class="dsw" data-group="{key}" aria-pressed="{"true" if i == 0 else "false"}">{label} ({len(items)})</button>'
            for i, (key, label, items, _) in enumerate(groups)
        )
        dgroups = "".join(
            f'<div class="dgroup" data-group="{key}"{"" if i == 0 else " hidden"}>'
            + decisions_table(items, dctx, answer)
            + "</div>" for i, (key, _, items, answer) in enumerate(groups)
        )
        decisions_html = f'<div class="dtoggle" role="group" aria-label="Decisions shown">{dbuttons}</div>{dgroups}' if groups else ""
        pct = round(100 * done / len(f["steps"])) if f["steps"] else 0

        # one part shown at a time, chosen with the buttons: steps, decisions
        panels = [(key, label, body) for key, label, body in (
            ("steps", f"Steps ({done}/{len(f['steps'])})", table),
            ("decisions", f"Decisions ({len(waiting)} to take)", decisions_html),
        ) if body]
        buttons = "".join(
            f'<button type="button" class="psw" data-part="{key}" aria-pressed="{"true" if i == 0 else "false"}">{label}</button>'
            for i, (key, label, _) in enumerate(panels)
        )
        bodies = "".join(f'<div class="panel" data-part="{key}"{"" if i == 0 else " hidden"}>{body}</div>' for i, (key, _, body) in enumerate(panels))

        # the view: heading, progress bar, the part switches and the parts
        card = (
            f'<article class="feature view" id="{fid}"><h2>{name}</h2>'
            f'<div class="bar"><i style="width:{pct}%"></i></div><p class="barlab">{done} of {len(f["steps"])} steps done</p>'
            f'<div class="ptoggle" role="group" aria-label="Part shown">{buttons}</div>{bodies}</article>'
        )
        (cards if active else finished_cards).append(card)

    unlinked = project["unlinked"]
    todo = sum(not s["status"].startswith("Done") for f in features for s in f["steps"])
    to_take = sum(d["kind"] == "Open" for d in decisions)
    return (
        f'<section class="tab" id="{ctx["slug"]}" data-slug="{ctx["slug"]}" hidden>'
        f'<div class="band top"><div class="title"><h1>{html.escape(project["name"])}</h1>'
        f'<p class="path">{html.escape(project["dir"])}</p></div>'
        f'<div class="figs"><div><b>{len(rows)}</b><span>features in progress</span></div>'
        f'<div><b>{todo}</b><span>steps not started</span></div>'
        f'<div class="hot"><b>{to_take}</b><span>decisions to take</span></div></div>'
        f'<div class="map"><div class="ftoggle" role="group" aria-label="Features shown">'
        f'<button type="button" class="fsw" data-set="active" aria-pressed="true">Active features ({len(rows)})</button>'
        f'<button type="button" class="fsw" data-set="past" aria-pressed="false">Past features ({len(finished_rows)})</button>'
        + (f'<button type="button" class="fsw" data-set="unlinked" aria-pressed="false">Decisions not linked to a feature ({len(unlinked)})</button>' if unlinked else "")
        + '</div>'
        f'<div class="maphead"><span>Feature</span><span>Steps</span><span>Decisions to take</span></div>'
        f'<div class="fset" data-set="active">{"".join(rows) or "<p>No feature in progress.</p>"}</div>'
        f'<div class="fset" data-set="past" hidden>{"".join(finished_rows) or "<p>No past feature: every feature has a step not started or a decision to take.</p>"}</div>'
        + ('<div class="fset" data-set="unlinked" hidden></div>' if unlinked else "")  # no row: the button shows the view
        + '</div></div><div class="band cards">' + "".join(cards) + "".join(finished_cards)
        + (f'<article class="feature view" id="{ctx["slug"]}-unlinked"><h2>Decisions not linked to a feature ({len(unlinked)})</h2>'
           f'<p class="barlab">Decisions to take (Open), outside every feature\'s decision range and step rows.</p>'
           + decisions_table(unlinked, dctx, True) + "</article>" if unlinked else "")
        + "</div></section>"
    )


def plain(text):
    """A markdown cell as plain text: no anchors, link targets, bold or code marks, and <br> as a space."""
    text = re.sub(r'<a id="[^"]*"></a>', "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)\s]+\)", r"\1", text)
    return re.sub(r"\s+", " ", re.sub(r"\*\*|`", "", text.replace("<br>", " "))).strip()


def step_refs(text, slug, names):
    """The steps a text names, as (key, start, end), the key being "<project slug>:S<n>".

    "S63" is a step of the project slug; "Project-2 S63" or "my-project-2 S84" is a step of
    the project of that name (names: lowercase name -> slug), whatever its capitals.
    """
    alternatives = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    refs = []

    for m in re.finditer(rf"(?<![\w-])(?:(?i:({alternatives}))\s+)?S(\d+)\b", text):
        project = names.get(m.group(1).lower(), slug) if m.group(1) else slug
        refs.append((f"{project}:S{m.group(2)}", m.start(), m.end()))

    return refs


def step_links(text, slug, names):
    """What one step's text says about other steps, as (key, kind, source) for each reference.

    kind is "waits" (this step waits on that one), "blocks" (that one waits on this step) or ""
    (connected without blocking); source is "marker" or "wording". The `**After:**` marker at the
    end of the text lists the steps it waits on, and with a marker every other reference is only
    connected. Without one, the kind is guessed from the words just before a reference ("after",
    "waits on", "needs", "once"…, and "before" the other way round), carried along a list ("after
    S80 and S81"), or from "S84, waits on it" after it.
    """
    marker = re.search(r"\*\*After:\*\*(.*)$", text)
    links = [(key, "waits", "marker") for key, _, _ in step_refs(plain(marker.group(1)), slug, names)] if marker else []
    body = plain(text[:marker.start()] if marker else text)
    kind, end = "", 0

    for key, start, stop in step_refs(body, slug, names):
        if not (end and re.fullmatch(r"\s*(?:,|and|or|\+|&)\s*", body[end:start])):  # in a list, the kind carries on
            word = re.search(r"(?i)\b(after|waits? (?:on|for)|needs?|once|requires?|depends? on|blocked by|before)\b"
                             r"(?:\s+[^\s,;.()]+){0,2}?\s*\(?$", body[end:start])
            kind = ("blocks" if word.group(1).lower() == "before" else "waits") if word else ""
            if re.match(r"(?i),?\s*(?:waits? (?:on|for)|needs?|depends? on|is blocked by) (?:it|this)\b", body[stop:]):
                kind = "blocks"
        links.append((key, "" if marker else kind, "wording"))
        end = stop

    return links


def step_index(projects, names):
    """Every step of every project for the search, by key, with its feature, status, text, the
    decisions it links to, the steps it waits on and blocks, and those connected without blocking."""
    steps, edges, mentions = {}, {}, set()

    for p in projects:
        for i, f in enumerate(p["features"]):
            feature = plain(re.sub(r"\s*\((?:branch|\[D).*\)\s*$", "", f["title"]))
            for s in f["steps"]:
                key = f"{p['slug']}:S{s['n']}"
                cited = re.findall(r"\[D(\d+)\]\((?:DECISIONS\.md)?#decision-\d+\)", s["text"])
                steps[key] = {"p": p["slug"], "n": s["n"], "status": s["status"], "text": plain(s["text"]), "feature": feature,
                              "features": [{"name": feature, "href": f"#{p['slug']}-feature-{i + 1}", "how": ""}],
                              "href": f"#{p['slug']}-step-{s['n']}", "decisions": [f"{p['slug']}:D{n}" for n in dict.fromkeys(cited)]}

                for other, kind, source in step_links(s["text"], p["slug"], names):
                    if other == key:
                        continue
                    if not kind:
                        mentions.add(tuple(sorted((key, other))))
                    elif edges.get((key, other) if kind == "waits" else (other, key)) != "marker":
                        # (the step that waits, the step that blocks it): a marker wins over a guess
                        edges[(key, other) if kind == "waits" else (other, key)] = source

    for key, step in steps.items():
        step["waits"] = [[blocker, source] for (waiter, blocker), source in edges.items() if waiter == key]
        step["blocks"] = [[waiter, source] for (waiter, blocker), source in edges.items() if blocker == key]
        linked = {k for k, _ in step["waits"] + step["blocks"]}
        step["connected"] = sorted({b if a == key else a for a, b in mentions if key in (a, b)} - linked)

    return steps


def decision_features(project, n):
    """The features decision n belongs to, as on the page, each with its name, its anchor and how:
    its decision range holds it ("by range"), its heading links to it, or some of its steps do."""
    link = rf"\[D{n}\]\((?:DECISIONS\.md)?#decision-{n}\)"
    found = []

    for i, f in enumerate(project["features"]):
        how = ["by range"] if n in f["range"] else (["named in its heading"] if re.search(link, f["title"]) else [])
        citing = [f"S{s['n']}" for s in f["steps"] if re.search(link, s["text"])]
        if citing:
            how.append("cited by " + ", ".join(citing))
        if how:
            found.append({"name": plain(re.sub(r"\s*\((?:branch|\[D).*\)\s*$", "", f["title"])),
                          "href": f"#{project['slug']}-feature-{i + 1}", "how": "; ".join(how)})

    return found


def decision_index(projects, steps, names, shown):
    """Every decision of every project for the search, by key, with its question and choice, and
    what it is linked to: the steps that link to it, the steps its own row names, the features it
    belongs to, and the decisions it updates or that update it."""
    decisions = {}

    for p in projects:
        slug = p["slug"]
        for d in p["decisions"]:
            key = f"{slug}:D{d['n']}"
            row = " ".join([d["status"], d["context"], d["question"]] + d["options"])
            decisions[key] = {
                "p": slug, "n": d["n"], "status": d["kind"], "date": d["date"], "question": plain(d["question"]),
                "chosen": plain(d["chosen"]), "href": f"#{slug}-decision-{d['n']}" if d["n"] in shown[slug] else "",
                "linked": [k for k, s in steps.items() if key in s["decisions"]],
                "named": list(dict.fromkeys(k for k, _, _ in step_refs(plain(row), slug, names))),
                "features": decision_features(p, d["n"]),
                "updates": list(dict.fromkeys(f"{slug}:D{n}" for n in re.findall(r"\*\*Updates \[D(\d+)\]", row))),
                "updated_by": list(dict.fromkeys(f"{slug}:D{n}" for n in re.findall(r"(?:\*\*Updated by|Replaced by) \[D(\d+)\]", row))),
            }

    # an update written on only one of the two rows is shown on both
    for key, d in decisions.items():
        for other in d["updates"]:
            if other in decisions and key not in decisions[other]["updated_by"]:
                decisions[other]["updated_by"].append(key)
        for other in d["updated_by"]:
            if other in decisions and key not in decisions[other]["updates"]:
                decisions[other]["updates"].append(key)

    return decisions


def page(projects, generated, index):
    """The whole HTML page: the project buttons, the search button and its popup, and every
    project's tab, with style.css and script.js (next to this file) written inline, so the page is
    one self-contained file. index (steps and decisions with their links) is written in as JSON
    for the search. The script shows one tab, feature, part and group at a time, copies answers
    and searches."""
    here = os.path.dirname(os.path.abspath(__file__))

    with open(os.path.join(here, "style.css"), encoding="utf-8") as f:
        css = f.read()

    with open(os.path.join(here, "script.js"), encoding="utf-8") as f:
        js = f.read()

    buttons = "".join(
        f'<button class="tabbtn" type="button" data-slug="{p["slug"]}" aria-selected="false">{html.escape(p["name"])}'
        f'</button>' for p in projects
    )
    tabs = "".join(p["html"] for p in projects)
    data = json.dumps(index, ensure_ascii=False).replace("</", "<\\/")  # "</" cannot appear inside a script element
    return (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1"><title>Work status</title>'
        f"<style>\n{css}</style></head><body>"
        f'<header class="strip"><nav aria-label="Projects">{buttons}</nav>'
        '<button type="button" class="searchbtn" aria-haspopup="dialog">Search</button>'
        f'<span class="gen">Last update: {generated}</span></header>'
        '<dialog class="search" aria-label="Search steps and decisions"><div class="shead">'
        '<select class="spick" aria-label="Project searched"><option value="">All projects</option>'
        + "".join(f'<option value="{p["slug"]}">{html.escape(p["name"])}</option>' for p in projects)
        + '</select>'
        '<input type="search" class="sq" placeholder="S87, D314, 87, or words" aria-label="Search"></div>'
        '<p class="shint">A number finds that step or decision, and a project\'s name and a number '
        f'({html.escape(projects[0]["name"]) if projects else "project"} S12) that one; words find the steps whose text, '
        'and the decisions whose question, has them all.</p>'
        '<div class="sresults"></div><div class="sitem" hidden></div></dialog>'
        f"<main>{tabs}</main>"
        f'<script type="application/json" id="work-index">{data}</script>'
        f"<script>{js}</script></body></html>"
    )


def read_config(roots):
    """The path of config.json and its content ({} if there is none).

    The path comes from paths.json next to this file (written by setup_work.py); a copy run on
    its own, for testing, looks for config.json next to itself. Stops if paths.json names a
    config that does not exist, unless roots (--root) are given, which do not need one.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(here, "config.json")
    paths_file = os.path.join(here, "paths.json")

    if os.path.exists(paths_file):
        with open(paths_file, encoding="utf-8") as f:
            config_path = json.load(f)["config"]
        if not roots and not os.path.exists(config_path):
            sys.exit(f"{config_path}, named in {paths_file}, does not exist. "
                     "Run setup_work.py again from the claude-setup repository.")

    config = {}

    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

    return config_path, config


def project_dirs(config, config_path, roots):
    """The folders of the projects to show, in the order of their tabs.

    With roots (--root) or no config.json, every project found there (or in ~/software),
    alphabetically, for testing. Otherwise the projects listed in config.json, in the order of
    "order": it stops if "order" misses a project or a name is listed twice, and warns about a
    name in "order" only, or a listed project with no DECISIONS.md.
    """
    listed = config.get("projects")

    if roots or not isinstance(listed, dict) or not listed:
        return sorted(find_projects(roots or ["~/software"]), key=os.path.basename)

    order = config.get("order", [])
    missing = [name for wanted in listed.values() for name in wanted if name not in order]

    if missing:
        sys.exit(f'In {config_path}, "order" must name every project of "projects". Missing: ' + ", ".join(missing))

    names = [name for wanted in listed.values() for name in wanted]
    repeated = sorted({name for name in names if names.count(name) > 1})

    if repeated:
        sys.exit(f'In {config_path}, a project can be listed only once in "projects". Listed more than once: '
                 + ", ".join(repeated) + ". Rename one of the folders.")

    for name in order:
        if not any(name in wanted for wanted in listed.values()):
            print(f'Warning: {name} is in "order" in {config_path}, but not in "projects": ignored', file=sys.stderr)

    dirs = []

    for folder, wanted in listed.items():
        found = {}
        for d in find_projects([folder]):
            found.setdefault(os.path.basename(d), d)
        for name in wanted:
            if name in found:
                dirs.append(found[name])
            else:
                print(f"Warning: {name} is listed under {folder} in {config_path}, but has no DECISIONS.md there", file=sys.stderr)

    return sorted(dirs, key=lambda d: order.index(os.path.basename(d)))


def read_projects(dirs):
    """Each project's name, slug, features and decisions, and the decisions each one shows.

    A project's name is its folder's name, with the parent folder's name when two projects
    share it (possible with --root only). The decisions on the page are those of a feature and
    the ones to take outside every feature; they are found for all projects first, so that
    links across projects know which decisions exist on the page.
    """
    counts = {}

    for d in dirs:
        counts[os.path.basename(d)] = counts.get(os.path.basename(d), 0) + 1

    names = {d: os.path.basename(d) if counts[os.path.basename(d)] == 1 else os.path.join(os.path.basename(os.path.dirname(d)), os.path.basename(d))
             for d in dirs}
    slugs = {d: re.sub(r"[^a-z0-9]+", "-", names[d].lower()).strip("-") for d in dirs}
    projects, shown = [], {}

    for d in dirs:
        wip = os.path.join(d, "WIP.md")
        features = parse_wip(wip) if os.path.exists(wip) else []
        decisions = parse_decisions(os.path.join(d, "DECISIONS.md"))
        linked = set().union(*(f["decisions"] for f in features))
        unlinked = [x for x in decisions if x["kind"] == "Open" and x["n"] not in linked]
        shown[slugs[d]] = (linked & {x["n"] for x in decisions}) | {x["n"] for x in unlinked}
        projects.append({"dir": d, "name": names[d], "slug": slugs[d], "features": features,
                         "decisions": decisions, "unlinked": unlinked})

    return projects, slugs, shown


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", action="append", help="show every project found in this folder (repeat for several), instead of config.json")
    parser.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "work_status.html"), help="HTML file to write")
    args = parser.parse_args()
    config_path, config = read_config(args.root)
    projects, slugs, shown = read_projects(project_dirs(config, config_path, args.root))

    # ids (answer boxes) and placed (decision anchors) are shared by all tabs, as ids must be unique in the page
    ids, placed = itertools.count(1), set()

    for project in projects:
        project["html"] = project_tab(project, {"dir": project["dir"], "slug": project["slug"], "slugs": slugs, "file": "WIP.md",
                                                "name": project["name"], "ids": ids, "shown": shown, "placed": placed})

    # the steps and decisions of every project with their links, for the search
    names = {p["name"].lower(): p["slug"] for p in projects}
    steps = step_index(projects, names)
    index = {"projects": [{"slug": p["slug"], "name": p["name"]} for p in projects],
             "steps": steps, "decisions": decision_index(projects, steps, names, shown)}

    with open(args.out, "w", encoding="utf-8") as f:
        f.write(page(projects, datetime.now().strftime("%Y-%m-%d %H:%M"), index))

    if not args.root and isinstance(config.get("projects"), dict) and config["projects"]:
        # the config of this build, next to config.json, for setup_work.py to compare with config.json
        try:
            with open(os.path.join(os.path.dirname(config_path), "last_build_config.json"), "w", encoding="utf-8") as f:
                json.dump({"projects": config["projects"], "order": config.get("order", [])}, f, indent=2)
        except OSError as e:
            print(f"Warning: the config of this build was not saved: {e}", file=sys.stderr)

    print(args.out)


if __name__ == "__main__":
    main()
