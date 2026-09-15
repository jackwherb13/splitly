**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

## 4. Builds are one click

All builds should be one step builds
Build artifacts should be cleaned from a singular location
.gitignore files should keep the workspace from being polluted.

## 5. All code should be Test-Driven-Development (TDD)

## 6. Track projects and learning in Obsidian

Vault: `C:\Users\jwesl\Documents\Obsidian\Jackson-Windows` — full rules live in that vault's own `CLAUDE.md`/`INDEX.md`, which only auto-load when a session's cwd is inside the vault. This section is a mirror so the rules apply even in sessions elsewhere (e.g. working in a code repo). If the vault's `CLAUDE.md` is available in context, it's the source of truth over this mirror.

When a session outside the vault touches a project decision, a new project, or something learned, write a note into the vault using its absolute path (no need to cd there) — don't wait to be asked:
- New note → `MyNotes/Inbox/<Title>.md`, then immediately triage it into the right subfolder in the same pass (don't leave it sitting in Inbox for a separate session)
- Subfolders: `Learning/` (topic/skill notes), `Projects/<Name>/` (README.md, Status.md, Progress.md, Decisions.md — one folder per project, not a flat note), `Areas/` (ongoing non-project areas), `Journal/` (dated raw capture)
- Frontmatter every note: `title, type (person|project|reference|area|daily|learning), status (active|parked|done|evergreen), created, updated, updated_by, tags`
- Filenames: Title Case With Spaces.md
- One note per topic — check `INDEX.md` and the relevant MOC first; extend an existing note instead of creating a near-duplicate
- Add new notes to `INDEX.md` (or the relevant MOC) and link with `[[wikilinks]]`
- Never delete a note — move to `Archive/` instead
- Bullet points, not prose