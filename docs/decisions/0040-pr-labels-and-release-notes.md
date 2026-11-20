# 0040 - Pull request labels and generated release notes

- **Status:** accepted
- **Date:** 2026-11-19
- **Decided by:** Daniel

## Context
The COMP 490 course asks for a release on GitHub, saved as a draft, with automatically generated
release notes, by one of two routes (course assignment, 2026-11-19; not part of the advisors'
roadmap). The repository had no workflows, tags or releases, and its 34 merged PRs carried no
labels. Decision 0039's number is held for the scorecard's record.

## Options considered
1. **GitHub's generated release notes, sorted by labels** that
   [actions/labeler](https://github.com/actions/labeler) (v7.0.0, released 2026-07-21, accessed
   2026-11-19) applies to every PR from `.github/labeler.yml`; sections in `.github/release.yml`
   ([GitHub's docs](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes),
   accessed 2026-11-19). Adds one workflow that only adds labels; releases stay manual and can
   be drafts.
2. **[Release Please](https://github.com/googleapis/release-please-action)** (v5.0.0): versions
   and notes from Conventional Commits, which we already write. It needs the repository setting
   "Allow GitHub Actions to create and approve pull requests", opens a release PR on every push
   to `main`, keeps a `CHANGELOG.md`, and publishes releases unless configured otherwise: more
   automation touching every teammate's work.

## Decision
Option 1 (Daniel, 2026-11-19). The course's `feature` rule (a head branch starting with or
containing `feature`) is kept, and `^feat/` is added so our own branches match; `fix/` gives
`bug`. The demonstration PR's branch is named `feature/...`, an exception to CLAUDE.md's `feat/`
prefix. The PRs merged before this were labelled once by branch prefix, so the first release
(`v0.1.0`, the backend's version) is grouped like later ones.

## Consequences
- Every PR, teammates' included, gets labels from the bot. They are additive; people can add or
  remove labels by hand.
- The rules apply from `main` (`pull_request_target`): a rule change is tested on the PR after
  the one that merges it.
- A PR that would get more than `changed-files-labels-limit` (8) new file labels gets none.
- To reverse: delete the three files under `.github/`; the labels stay harmless.
- How to use it: `docs/releasing.md`.
