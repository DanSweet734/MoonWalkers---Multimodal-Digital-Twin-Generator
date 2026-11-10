# Setting up to work on the platform

For Ava, Kiran and Sarkis, and anyone new to the repository. It takes you from a fresh machine to
passing tests on your own branch. Your pipeline's own work is in
[the pipeline guide](../pipeline-guide.md); this page gets you to its first step.

**Tested on:** a fresh clone of `main` on Windows 11, on 2026-11-06 (worklog of that date). Not yet
tried on macOS or Linux. If a step fails for you, tell Daniel, and the fix goes into this page.

## What you need, and what you can skip
| You need | For |
|---|---|
| Git | The repository |
| uv | Python 3.12 and the backend's packages |
| Node.js (LTS) | The dashboard only. Skip it if you work only on a pipeline |
| GitHub CLI (`gh`) | Optional: opening pull requests from the terminal |
| Claude Code | Optional, but it is how the team works (decision 0003) |

**You can skip** Isaac Sim, the image-to-3D generators, Hugging Face access and an NVIDIA GPU.
Those are for building twins from photos (Pipeline B) and checking them, which Daniel does. No
test you run needs them: `-m "not gpu and not slow"` leaves them out.

## 1. Install the tools
Each command is from the tool's own instructions.

**Windows (PowerShell):**
```powershell
winget install --id Git.Git -e --source winget
winget install --id astral-sh.uv -e
winget install --id OpenJS.NodeJS.LTS -e     # dashboard only
winget install --id GitHub.cli -e            # optional
irm https://claude.ai/install.ps1 | iex      # Claude Code, optional
```

**macOS or Linux:**
```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
curl -fsSL https://claude.ai/install.sh | bash   # Claude Code, optional
```
Install Git, Node.js LTS (https://nodejs.org/) and the GitHub CLI (https://cli.github.com/) the
way your system usually does. On macOS, "Apple ships a binary package of Git with Xcode Command
Line Tools", installed with `xcode-select --install` (https://git-scm.com/install/mac).

Then **open a new terminal** so the new commands are found, and check:
```
git --version
uv --version
```

**Python:** you do not install it yourself. The backend asks for 3.12 (`backend/.python-version`,
and `requires-python = ">=3.12,<3.13"` in `backend/pyproject.toml`), and "By default, uv will
automatically download Python versions if they cannot be found on the system"
(https://docs.astral.sh/uv/concepts/python-versions/).

Sources, accessed 2026-11-09: https://git-scm.com/install/windows (whose page notes that the
`Git.Git` package is not maintained by the Git for Windows project and may lag behind),
https://docs.astral.sh/uv/getting-started/installation/ and https://code.claude.com/docs/en/setup.
The Node.js and GitHub CLI commands are those used on Daniel's machine
([windows-dev-setup.md](windows-dev-setup.md)). Claude Code needs a Pro, Max,
Team, Enterprise or Console account; "The free claude.ai plan does not include Claude Code access"
(same page). On Windows, Git for Windows also gives Claude Code its Bash tool (same page).

## 2. Get the repository
```
git clone https://github.com/DanSweet734/MoonWalkers---Multimodal-Digital-Twin-Generator.git
cd MoonWalkers---Multimodal-Digital-Twin-Generator
```
With the GitHub CLI, run `gh auth login` once first, so you can push.

## 3. Install the packages and run the tests
**Backend** (from `backend/`):
```
uv sync
uv run pytest -m "not gpu and not slow"
uv run ruff check .
uv run ruff format --check .
uv run python -m moonwalkers.pipelines list
```
- `uv sync` builds `backend/.venv` from `uv.lock`, so everyone has the same versions. The first
  run downloads Python and the packages.
- On 2026-11-06 the tests gave "696 passed, 5 deselected" in about 3.5 minutes. The count grows
  as tests are added. What matters is that none fail.
- `pipelines list` shows each pipeline and whether it is in. Until your `create_pipeline()`
  returns your class, yours says "not in yet".

**Dashboard** (from `dashboard/`; skip it if you do not need it):
```
npm ci
npm test
npm run lint
npm run build
```
`npm ci` installs the exact versions in `package-lock.json`. The tests use Node's own test
runner, so they need nothing else.

## 4. Environment variables and data
- **The backend does not read a `.env` file.** It reads variables from your terminal session.
  `example.env` lists their names. Set one in the terminal you run commands from, for example
  `$env:MOONWALKERS_DATA_DIR = "D:\mw-data"` in PowerShell or `export MOONWALKERS_DATA_DIR=...` in
  a POSIX shell.
- **You rarely need any.** Without `MOONWALKERS_DATA_DIR`, the data folder is `data/` in the
  repository.
- **`data/` is not in Git** except its README: photos, manuals, generated meshes and twins stay on
  your machine (CLAUDE.md, rule 5). The pipeline guide says how to get the T33901 manual to try
  your pipeline on.
- **Never commit a secret** (CLAUDE.md, rule 4). `.env` and `.env.*` are ignored by Git, and
  Claude Code is blocked from reading them (`.claude/settings.json`).

## 5. Work on your own branch
```
git fetch origin
git switch -c <your-branch> origin/main
```
- If you already have a branch, bring `main` in with `git merge origin/main`. Do not rebase or
  force-push: others may have your commits (CLAUDE.md, "Git workflow").
- Commits use Conventional Commits, such as `feat: read the data sheet's spindle speeds`.
- Before a pull request, run the four backend checks of step 3, and the dashboard's if you changed
  it.
- Open the pull request on GitHub, or with `gh pr create`. The template asks what changed, how it
  was tested, which documents changed and what is still open.
- Pick the next free number for a decision record: look in `docs/decisions/` on the newest `main`.
- Work on another person's branch only when they ask you to.

## 6. Using Claude Code here
Start it with `claude` in the repository's folder.
- **`CLAUDE.md` loads by itself.** Its "Non-negotiable rules" apply to everyone: cite every fact,
  ask before installing, no secrets, no large files in Git, and keep the contract. Its "Current
  phase" section is Daniel's work on Pipeline B; your own task is in the pipeline guide.
- **Personal notes** go in `CLAUDE.local.md` (copy `CLAUDE.local.md.example`). Git ignores it.
- **The project's permissions** are in `.claude/settings.json`. Claude Code asks before installing
  a package, and is blocked from pushing to `main` and from force-pushing.
- **The `moonwalkers` MCP server** (`.mcp.json`) gives the agent its twin-building tools.
  Claude Code asks once whether to use it. You do not need it for a pipeline, so declining is
  fine. If you approve it, run `uv sync` first, since the server starts with `--no-sync`.

## If something goes wrong
- **`uv` or `claude` is "not recognized"** right after installing: open a new terminal.
- **"`VIRTUAL_ENV=...` does not match the project environment path":** another Python environment
  is active in your terminal. uv uses `backend/.venv` anyway. Run `deactivate`, or open a new
  terminal, to clear it.
- **A test fails on a fresh `main`:** tell Daniel, with the test's name and the last lines of its
  output. Do not change or delete the test to make it pass (CLAUDE.md, "Code conventions").
