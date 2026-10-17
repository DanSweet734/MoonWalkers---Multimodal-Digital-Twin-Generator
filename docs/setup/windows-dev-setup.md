# Windows 11 development setup

Machine: Windows 11, NVIDIA GeForce RTX 4090 (24 GB). Each step lists its source.

## Claude Code
- Install (PowerShell): `irm https://claude.ai/install.ps1 | iex`, then check with `claude --version`
  and `claude doctor` (https://code.claude.com/docs/en/setup).
- Install Git for Windows. "Git for Windows is recommended on native Windows so Claude Code can use the
  Bash tool. If Git for Windows is not installed, Claude Code uses PowerShell as the shell tool instead."
  (same page). `.claude/settings.json` has rules for both shells.
- Sign in with the Claude Pro account. Usage limits are shared with claude.ai and reset every five hours
  (https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan).

## Python, uv, Node
- Python 3.12 via uv: https://docs.astral.sh/uv/getting-started/installation/ (Isaac Sim's pip install
  requires Python 3.12: https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/install_python.html).
- Node.js (current LTS) for the dashboard: https://nodejs.org/
- GitHub CLI for pull requests: https://cli.github.com/ , then `gh auth login`.

## Isaac Sim 6.2.0 (for opening and checking twins)
- Requirements: Windows 11 is supported; minimum GeForce RTX 4080 16 GB; 32 GB RAM minimum; Windows driver
  595.97 or newer (https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/requirements.html).
- Workstation install: download the Windows zip, unzip to `C:\isaacsim`, run `post_install.bat`, then
  `isaac-sim.bat`; first launch "can take 5-10 minutes"
  (https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/install_workstation.html).

## Image-to-3D generators
- Each generator gets its own environment; see `docs/decisions/0006-image-to-3d-generator.md` and each
  project's README for install steps. Ask before installing; record versions in the worklog.
- Hugging Face access: `docs/setup/huggingface.md`.
