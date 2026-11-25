# Working agreement for <PROJECT NAME>

<!-- Template from the claude-setup folder of setup_project.py (see its README.md). Replace every <...> placeholder, and
     delete the lines that do not apply to this project. -->

## Roles
- I make architecture and design decisions. You propose, explain clearly, and implement.
- I want to understand and own every change. Prioritize clarity of reasoning over speed.
- Always explain the reason behind your actions.

## Planning
- For anything beyond a small, obvious change, describe your plan first and wait for my OK.
- Always ask when you don't understand a requirement or any part of it.
- Plan new features in steps that can be committed one by one so that it is easy to review.
- Work in small, reviewable steps.
- After each part of each feature is complete, tell me how to test it: the steps, where to look (<the pages, commands or endpoints of this project>), how to run it locally, and on which machine it has to run, or whether the tests are enough.

## Stop and ask me before
- adding a dependency (<where dependencies are listed, e.g. `pyproject.toml`>)
- creating a new module, page, endpoint or command (<where they live>)
- changing anything users or other code rely on:
  - <settings files and their keys>
  - <public APIs: endpoints, functions, their arguments and answers>
  - <files the program writes that others read>
  - <command-line commands and options>
- introducing a new pattern: <caching, callback wiring, logging and error reporting, job submission, connections or credentials of this project>
- touching more than ~3 files or ~150 lines in one go

## Asking me to decide
- When there's a real design choice, give me 2–3 options with trade-offs and your recommendation, then let me pick. Don't decide silently.
- Always label the options with letters (A, B, C). When asking several questions at once, number the questions and letter the options (1A, 1B, 2A), so I can answer "1B 2A".
- Always end the options with a lettered "Other" option, so I can answer with an option of my own (for example "1D: <my idea>"). When I choose it, record my option in DECISIONS.md as that letter, in my words.
- When I don't answer with an option, do not assume I want what you recommend, ask again.
- When I finish answering all questions, plan again and wait for my OK before writing any code.

## Proposing and making changes
- Show proposed changes as Before and After code blocks, not +/- diffs.
- Never rewrite working code I wrote just to match your style. Suggest instead.
- When a step is complete and before I commit it, update the matching section of `README.md` if the step affects users or developers (new setting, new option, changed behaviour, new run step, a file moved or a new file someone will need to find, a feature or a public API changed), so that the README change goes into the same commit.
- Never commit any change.

## Code style
- Don't define functions inside functions (nested functions or closures). Use module-level functions or methods instead.
- Don't create empty functions or very short functions (maximum 5 lines) that are only called from one place unless necessary.
- Don't define module-level variables (constants) that are only used in one function. Define them inside that function instead.
- Never reference steps (SN) or decisions (DN) in code comments or docstrings: the comment says the reason itself.

## Agents and automation
- Don't spawn subagents or run large parallel/multi-step tasks unless I ask.

## Project memory files: MINIMAP.md, WIP.md and DECISIONS.md

Three files at the repo root carry knowledge between sessions. They are ignored by git (`.gitignore`), so git keeps no history of them: copy a file before deleting anything from it.

- **MINIMAP.md**: orientation, conventions and traps. What the project is, its stack, links to the README sections on running it and where things live (the README is the only copy of those), a numbered list of gotchas, a log of weird bugs, the standing rules, and a short list of the decisions not settled yet.
- **WIP.md**: the features in progress, one `##` section each: a table of its steps (`SN`, with the date added and the date of the current status), where we are, what is open; and the last session at the end. Empty when nothing is in progress.
- **DECISIONS.md**: every decision I take. It is not read at the start of a session, see "When to read DECISIONS.md".

The `/work` skill (`~/.claude/skills/work/`) builds the private "Work status" page on claude.ai from WIP.md and DECISIONS.md of every project in the folders listed in `~/.claude/skills/work/config.json`: one tab per project, its features, steps and decisions, and a button to copy an answer to a decision. It relies on the formats below.

### Start of every session

Before anything else, read MINIMAP.md, WIP.md and README.md, even for a small question. Do not assume what a file says from memory of an earlier session.

### When to read DECISIONS.md

Search it for the files, fields or feature involved, rather than reading it whole:

- before asking me a question, so that you do not ask again something I decided, or offer an option that goes against an earlier decision without saying so
- before starting a step whose WIP row or plan cites a decision: read those rows
- when I mention a decision (e.g. "as in D48"): read that row
- at wrapup (see below)

### While working

- When something costs real time (a surprising bug, a silent failure, a rule that is not obvious from the code), add a **gotcha** to MINIMAP.md right then. Do not wait for wrapup.
- Keep the gotcha short and factual: the trap, the cause, what to do instead. Number it with the next free number and never renumber.
- If a bug looked like one thing and was another, also add a row to the "Weird bugs log" table (date, symptom, root cause, status).
- Register every decision that I take in the "Decisions" table of DECISIONS.md right when I take it, not at wrapup, and list it under "Decisions not settled" in MINIMAP.md while it is not settled. A rule I set without a question goes in the "Rules" table of MINIMAP.md instead. All formats are under "Table formats" below.
- Assign every new decision to a feature of WIP.md when you register it: it falls in the decision range of the feature's heading, or a step row of the feature cites it as a link. When something new comes up that fits no feature in progress, ask me whether to create a new feature in WIP.md for it.
- Whenever you change a DECISIONS.md, or finish, add or drop a step in a WIP.md, of this project or another one, by any means (an edit tool or a script), rebuild and republish the "Work status" page before ending your reply, as steps 3 and 4 of the `/work` skill describe (`~/.claude/skills/work/SKILL.md`), and give me its link. This needs no wrapup.
- When I paste a line starting "Update decisions log:" (copied from the Work status page), record that answer as the `/work` skill describes.
- If I contradict an earlier decision, tell me before acting on it.

### Table formats

All three tables: rows are numbered in order with a prefix (D, R, S), and numbers are never reused or renumbered. Each row has an anchor (`<a id="decision-N"></a>DN`, `rule-N`, `step-N`). Refer to rows by number, not by date: `[DN](DECISIONS.md#decision-N)` (`[DN](#decision-N)` inside DECISIONS.md), `[RN](#rule-N)`, `[SN](WIP.md#step-N)`. Whenever a decision is mentioned, in chat or in a file, say what it decided in parentheses right after its number, e.g. "D109 (separate plot endpoints, not a generic `/plot`)". In WIP.md, always cite a decision as a link, not as plain text: the Work status page only finds links.

**Decisions** (DECISIONS.md), newest first:
- One row per question, and one per round if it was asked in rounds.
- Columns: #, Date, Status, Context, Question, Options.
- Status: Applied (only after checking the code), Pending (decided, work not done), Replaced by [DN](#decision-N) (applied, then replaced), Unverified (not confirmed from the code), Open (waiting for an answer) or Parked (set aside on purpose, including a choice whose work waits).
- Question: as it was asked, cut to one sentence. Always record it: the Work status page shows it, and copies it with an answer.
- Options: every option offered, one per line (`<br>`), each with its letter and written out in full, with no question number (1A is written A). The chosen one is in bold and states the whole decision, so the row reads on its own.
- Notes go on a last line. If a row changes an earlier decision, write "**Updates [DM](#decision-M)**: <what it changes>" on the new row and "**Updated by [DN](#decision-N)**: <what no longer holds>" on the old one.

**Decisions not settled** (MINIMAP.md): one line per row of DECISIONS.md whose Status is Open, Pending, Parked or Unverified, newest first: `- [DN](DECISIONS.md#decision-N), <Status>: <what is decided or asked, in a few words>`. A line is removed when its row becomes Applied or Replaced.

**Rules** (MINIMAP.md), newest first:
- Columns: #, Date, Context, Rule.
- A rule is a standing way of working that I set without being asked a question.

**Features** (WIP.md): one `##` section per feature, newest first, its heading the feature's name, then in parentheses the branch and its decision range: `## <name> (branch <branch>, [DA](DECISIONS.md#decision-A)–[DB](DECISIONS.md#decision-B))`. Then its step table, `### Where we are (<date>)` and `### Open`. A dropped feature says "dropped" in its heading. The last section is `## Last session (<date>: <topic>)`.

**Steps** (WIP.md), in order (S1 first):
- One table per feature in progress.
- Columns: #, Added, Status date, Step, Status, Commit.
- Added is the date the step entered the table. Status date is the date of its current status.
- Status: Done or Not started. What comes next goes in "Where we are", and what a step is waiting on goes in the "Open" list. A step that will not be done keeps its row, its text starting "Dropped ([DN](DECISIONS.md#decision-N)): ".
- When a step can only start after other steps, its Step text ends with `**After:**` and those steps, a step of another project with that project's name: `**After:** S12, project-3 S63`. What a step blocks is not written: the Work status page finds it from the other steps' markers. In a step without the marker, the page guesses from the wording ("after", "waits on", "needs", "before").
- Commit: the short hash (or hashes) of the commit that holds the step. Empty while the step is Not started, and "Not found" when it is Done but no commit could be found.

### When I say "wrapup"

Do all of these, in order, and tell me what you changed in each file:

1. **WIP.md**: in the step table of the current feature, update the status and status date of each step that changed, and add new steps with the next free number (`<a id="step-N"></a>SN`, never renumbered). Update "Where we are" and the "Open" list. Then replace "Last session" with:
   - **Seen**: what you actually verified (a test run, a browser at named widths, a real job on a server, a real request) and the result.
   - **Not seen**: what you did not verify. Never imply something was checked when it was not.
   - **Server/deploy facts**: only what I pasted back to you. Do not infer them.
   - **Tests**: the counts, and any failure that already existed before this session.
2. **MINIMAP.md and DECISIONS.md**: add any gotcha from this session that is not yet recorded. Check that every decision taken this session is in the "Decisions" table of DECISIONS.md, in its format, and add any that are missing. Change Pending to Applied for rows whose work you checked in the code. Check that "Decisions not settled" lists exactly the rows that are Open, Pending, Parked or Unverified. Re-read the entries you touched and fix any that are now false.
3. **Work status page**: rebuild and republish it (steps 3 and 4 of the `/work` skill), and give me its link.
