# Releases and pull request labels

How a pull request gets its labels, and how those labels sort GitHub's automatically generated
release notes. Set up on 2026-11-19 for the COMP 490 release-notes assignment
([decision 0040](decisions/0040-pr-labels-and-release-notes.md)).

## The three files

| File | What it does |
|---|---|
| [`.github/labeler.yml`](../.github/labeler.yml) | The rules: which label a PR gets from its branch names and the files it changes. |
| [`.github/workflows/auto-label.yml`](../.github/workflows/auto-label.yml) | A GitHub Actions workflow that runs [actions/labeler](https://github.com/actions/labeler) (v7) on every PR and applies those rules. |
| [`.github/release.yml`](../.github/release.yml) | The sections of the generated release notes, by label. |

## The labels a PR gets

| Label | When |
|---|---|
| `feature` | The head branch starts with `feature` or contains `feature`, or starts with `feat/` |
| `bug` | The head branch starts with `fix/` |
| `release` | The PR is opened against `main` |
| `AnyChange` | Any file changes |
| `documentation` | A file under `docs/`, or any `.md` file, changes |
| `backend` | A file under `backend/`, outside `backend/tests/`, changes |
| `dashboard` | A file under `dashboard/` changes |
| `tests` | A file under `backend/tests/`, or a `*.test.ts` file, changes |
| `ci` | A file under `.github/` changes |

The labeler only adds labels; it never removes one a person added. Labels can still be added
by hand, for example `ignore-for-release` to leave a PR out of the notes, or `breaking-change`.

Two things to know:
- The workflow runs on `pull_request_target`, which uses the workflow and its rules **as they are
  on the PR's base branch**. A change to `labeler.yml` takes effect for PRs opened after it is
  merged into `main`.
- `changed-files-labels-limit` in `labeler.yml` is 8. If a PR would get more new labels from
  file rules than that, it gets **none** of them (the labeler's documented behaviour). Raise the
  limit when adding a file rule.

## Making a release

1. Merge the PRs that belong in it into `main`.
2. Tag the release commit, for example `git tag -a v0.1.0 -m "..."` on `main`'s merge commit,
   then `git push origin v0.1.0`. The version follows `backend/pyproject.toml`, which
   `uv run python -m moonwalkers --version` prints (from `backend/`).
3. On GitHub, **Releases > Draft a new release**, choose the tag, then **Generate release
   notes**. GitHub lists every PR merged since the previous release, each under the first
   section of `release.yml` whose labels it carries; a PR with no matching label goes under
   "Other Changes".
4. Edit the notes if needed (a summary at the top), and **Save draft**, or publish.

The same with the `gh` command line:
`gh release create v0.1.0 --draft --verify-tag --generate-notes --title "..."`.
To preview the generated notes without creating anything:
`gh api -X POST repos/{owner}/{repo}/releases/generate-notes -f tag_name=v0.1.0 --jq .body`.

## The first release

PRs merged before 2026-11-19 had no labels. They were labelled once by their branch's prefix
(`feat/` → `feature`, `fix/` → `bug`, `docs/` → `documentation`), so that the first release's
notes are grouped like the later ones. The one `chore/` PR (#1, the Phase 0 scaffold) was left
unlabelled, under "Other Changes".
