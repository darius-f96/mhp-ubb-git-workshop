# mhp-ubb-git-workshop

A hands-on Git workshop built around one HTML file and one CI check.

Every participant adds a row to a ledger and re-adds the total **by hand**.
Because everyone edits the same three lines of the same file, the group
collectively produces branch conflicts, stale totals and broken merges — and a
GitHub Action catches all of it. The breakage is the curriculum, not a risk.

**Repository:** <https://github.com/darius-f96/mhp-ubb-git-workshop>

## What participants practise

| Topic | Where it shows up |
| --- | --- |
| `clone`, `status`, `log`, `diff` | Getting the repo and reading your own change |
| Branches | Everyone works on `add-row-<name>`, never on `main` |
| Commits | One focused commit with a real message |
| `pull` | Syncing `main` before and after opening a PR |
| `push` | Publishing the branch, `-u` on the first push |
| Pull requests | Opening one, reading the checks, iterating on it |
| Merge conflicts | Guaranteed — the whole cohort edits the same region |
| CI/CD | `Verify Ledger Sum` runs on every PR and on `main` |
| Semantic vs. textual merge | Two green branches merging into a red `main` |

The last row is the point of the exercise. Git merges lines, and it will merge
this file correctly every time. It cannot know that one of those lines is
supposed to be the sum of the others.

## Repository layout

```
index.html                     the ledger + all participant instructions
scripts/verify_sum.py          the check; runs identically locally and in CI
scripts/test_verify_sum.py     tests for the check itself
.github/workflows/verify-sum.yml
.gitignore                     keeps __pycache__ out of participants' commits
```

`index.html` is self-contained — no build step, no external assets, no
dependencies. It is also the handout: open it in a browser and it walks
participants through every step, including the conflict resolution.

Python 3 is the only requirement, and the scripts use the standard library only.

## Facilitator setup (before the session)

1. **The repository is already created and public:**
   <https://github.com/darius-f96/mhp-ubb-git-workshop>

   ```bash
   git clone https://github.com/darius-f96/mhp-ubb-git-workshop.git
   ```

   Public is what you want here: on the Free plan, branch protection rules and
   GitHub Pages are available for public repositories but restricted for private
   ones.

2. **Enable GitHub Pages** (Settings → Pages → deploy from `main`, root).
   Participants can then read the handout at
   <https://darius-f96.github.io/mhp-ubb-git-workshop/> instead of opening a
   local file, which matters for anyone following along on a phone.

3. **Collect emails** with your form, then invite everyone under
   Settings → Collaborators. They must **accept the invite** before `git push`
   will work — chase this before the session starts, not during it. Anyone who
   cannot be added in time can fork instead; the page documents that path too.

4. **Add a branch protection rule on `main`** (Settings → Branches):
   - Require a pull request before merging
   - Require status checks to pass → select `validate`
   - **Require branches to be up to date before merging**

   That last option is the forcing function. It makes GitHub refuse to merge a
   PR whose branch is behind `main`, so each participant is pushed into merging
   `main` into their branch and meeting the conflict face to face. Without it,
   late PRs merge silently and you lose the best part of the session.

5. **Seed the ledger.** `index.html` ships with one row (`Instructor`, `10`) and
   a matching total, so the very first CI run is green. Leave it that way — a
   red `main` before anyone starts makes it impossible to tell whose fault a
   failure is.

## Running the session

A workable shape for ~90 minutes:

1. **10 min** — Talk through the story before the commands: branches are cheap,
   `main` is shared, and a pull request is a conversation with a robot attached.
2. **5 min** — Everyone clones, creates `add-row-<name>`, opens `index.html`.
   Have them open the Pages URL rather than the file if you enabled it.
3. **15 min** — Everyone adds a row, picks a number, updates the total, runs
   `python scripts/verify_sum.py`, commits and pushes. **Do not let anyone
   merge yet.** The cohort must all be branched off the same base commit — that
   is what makes the collisions come later.
4. **10 min** — Open PRs. Watch the checks go green. Point out that every single
   PR is green *in isolation*.
5. **20 min** — Merge them one at a time, on the projector. The first merges
   cleanly. Around the third, GitHub reports a conflict or a red build. This is
   the moment to slow down and narrate.
6. **20 min** — Everyone syncs `main`, resolves their own conflict, re-adds the
   total, pushes. Walk the room; this is where people get stuck.
7. **10 min** — Close with `git log --oneline --graph --all`. The diamond shape
   the cohort just produced together is worth more than any slide.

### Making the conflict reliable

Conflicts only happen when branches overlap in time. If you merge each PR before
the next person pushes, Git fast-forwards happily and nobody learns anything.
So: **all branches first, all merges second.** Step 3 above is deliberately a
hard gate.

If the group is small or fast and you still want a conflict, merge two PRs
yourself from branches you created beforehand, and resolve it live.

### Two failure modes worth contrasting on the projector

- **Red PR.** The participant's own branch does not add up. Their problem, and
  the log tells them exactly what is wrong and by how much.
- **Green PRs, red `main`.** Two branches that each passed, merged in sequence,
  producing a file whose total is stale. Nobody did anything wrong individually.
  This is why checks run after integration and not only before it.

## The check

`scripts/verify_sum.py` parses `index.html`, sums the `class="num"` cells and
compares the result with the value in the `id="total"` cell. It fails on a
stale total, a non-integer number, a row that does not have exactly three cells,
a duplicated total row, an unedited `Your Name` template row, and leftover
conflict markers. It warns — without failing — on duplicated rows and repeated
names.

The parser is deliberately tolerant of things that are not the lesson: extra
whitespace, single-quoted attributes, negative numbers and a missing
`class="num"` (it falls back to cell position). A red build should always mean
something the participant actually needs to think about, never that they
formatted an attribute differently.

Run it the same way CI does:

```bash
python scripts/verify_sum.py          # checks index.html
python scripts/verify_sum.py other.html
python scripts/test_verify_sum.py     # tests the checker itself
```

Note for anyone editing the page: `scripts/verify_sum.py` scans the whole file
for conflict markers and for `id="total"`. The examples in the instructions are
therefore HTML-escaped, and the `=======` separator is written as `&#61;`
entities. If you unescape them, the check will report an unresolved merge in a
perfectly healthy file.

## Variations, if the group finishes early

- **Rebase instead of merge.** Have half the room `git rebase main` and compare
  the resulting `git log --graph`. Same conflict, different history shape, and
  a good excuse to explain why `--force-with-lease` exists.
- **`git bisect`.** Deliberately merge a broken total, then find the commit
  that introduced it.
- **Tags and releases.** Tag the ledger at the end of the session as `v1`.
- **A second CI job.** Add a spell-check or an HTML-validation job and discuss
  what belongs in CI versus what belongs in review.
- **Deliberate sabotage.** As facilitator, merge a row with `7 points` in the
  Number cell and let the group read the failure together.

## Troubleshooting

| Symptom | Cause and fix |
| --- | --- |
| `remote: Permission denied` on push | Invite not accepted, or pushing to the upstream repo from a fork. Check `git remote -v`. |
| `Updates were rejected because the remote contains work that you do not have` | Branch is behind. `git pull` (on `main`) then merge or rebase into your branch. |
| `python: command not found` | Try `python3`. |
| Check fails with `Could not find <table id="ledger">` | The table lost its `id` during a merge. Restore `id="ledger"`. |
| Check fails with `Found 2 cells with id="total"` | A conflict was resolved by keeping both sides. One participant row got absorbed into a duplicated total row — see the trap explained on the page. |
| Browser renders `<<<<<<< HEAD` as text | Conflict markers were committed. Search the file for `<<<<`, `====` and `>>>>`. |
| Page looks unstyled | It has no external assets, so this means the `<style>` block was damaged in a merge. |
