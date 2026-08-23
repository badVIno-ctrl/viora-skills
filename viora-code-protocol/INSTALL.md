# Viora Code Protocol - install into any agent

*Viora Studio engineering standard. Companion to Viora Design Skills.*

The protocol is plain Markdown plus four read-only scripts. Nothing is tied to a particular assistant, vendor, IDE or CLI. Pick the pattern that matches what your agent can do.

## Pattern A - the agent auto-loads a skills / plugins folder

Copy the whole `viora-code-protocol/` folder into that folder (typically a user-level or project-level skills directory). The agent discovers it by the `name` and `description` in the front matter of `SKILL.md` and loads the body when a coding task starts.

```
<agent skills dir>/viora-code-protocol/
    SKILL.md  references/  templates/  scripts/
```

## Pattern B - the agent reads a project instruction file

Put the folder in the repository (root or `.agent/`, `tools/`, `docs/`) and add one line to whatever instruction file your agent reads at the repo root:

```md
## Engineering protocol
Before any code change, read and follow `./viora-code-protocol/SKILL.md`.
Run `python3 viora-code-protocol/scripts/find_duplicates.py .` before creating new files,
and `bash viora-code-protocol/scripts/verify.sh .` before claiming completion.
```

## Pattern C - the agent has a system prompt / custom instructions box only

Paste sections **3 (the 12-step checklist)**, **5 (hard limits)**, **6 (gates)** and **7 (report contract)** of `SKILL.md`. That is the compact core (~2 pages) and it is enough to change behavior. Keep the rest of the repo files available for the agent to open on demand.

## Pattern D - no filesystem at all (chat-only assistant)

Paste section 3 as the working checklist and section 9 (banned excuses). Ask the assistant to answer in the report format from section 7. The scripts are optional; the fallback commands in section 10 are pure `grep`.

## Pattern E - workspace documentation tool

Keep `SKILL.md` as a page and the reference files as sub-pages, one level deep. Link the archive with the scripts on the main page so a coding agent can download it into the repo it works on.

---

## Verify the installation (30 seconds)

Ask the agent, in a repository:

> Add a date formatting helper for the report screen. Follow the Viora Code Protocol.

A correct response, before writing any code:
1. states the lane and mode (e.g. `Lane: LITE | Mode: FEATURE`);
2. searches for an existing formatter and reports the owner it found (`src/lib/format.ts:14`);
3. names the ladder rung it chose;
4. lists the files it will touch;
5. after implementing, shows an evidence table with the repo's real commands.

If it starts by creating `src/utils/dateHelper2.ts`, the protocol is not loaded.

## Requirements for the scripts (optional but recommended)

- `python3` 3.8+ for the three scanners (standard library only, no installs, no network, read-only).
- `bash` for `verify.sh`; it only runs commands the repository itself defines.
- Everything works without them - section 10 of `SKILL.md` has `grep`-only fallbacks.

## Customizing it for your repo

Edit these places and nothing else:
- section 5 of `SKILL.md`: the numeric limits, if your codebase has different conventions;
- section 1 of `references/04-performance-and-resources.md`: your performance budgets;
- `references/08-stack-notes.md`: add a section for your stack;
- `scripts/verify.sh`: add your gate commands if detection misses them.

Keep the gates, the ladder, the evidence law and the report contract intact - they are what actually prevent bad code.
