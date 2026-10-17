# 0007 - Phase 0 tooling: uv_build, Python 3.12 only, ruff, Oxlint, explicit TypeScript strict

- **Status:** accepted
- **Date:** 2026-10-16
- **Decided by:** team (Daniel approved the Phase 0 plan)

## Context
Phase 0 of `docs/poc-plan.md` scaffolds the backend and dashboard. Decision 0001 fixed the stack (Python +
FastAPI, React + TypeScript); this record covers the smaller tooling choices made while scaffolding.
Versions are the latest on 2026-10-16, read from https://pypi.org/pypi/<name>/json and
https://registry.npmjs.org (accessed 2026-10-16). Facts marked "observed" were checked on Daniel's machine
that day; commands are in `docs/worklog/2026-10-16.md`.

## Options considered
1. **Python build backend.**
   - `uv_build` (uv 0.13.1, MIT OR Apache-2.0): what `uv init --package` writes by default (observed:
     `requires = ["uv_build>=0.13.1,<0.14.0"]`). Same vendor as uv, one small build-time download (1.3 MB).
   - hatchling or setuptools: well known, but one more tool to learn for no PoC benefit.
2. **Python version range.**
   - `>=3.12,<3.13`: matches CLAUDE.md ("Python 3.12") and Isaac Sim's pip install, which requires
     Python 3.12 (https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/install_python.html).
   - `>=3.12`: wider, but would let teammates run untested versions (Daniel's machine also has 3.14).
3. **Python lint rules (ruff 0.17.1).**
   - `select = ["E", "F", "I"]`, line length 100 (the contract's longest line is 97 characters).
   - ruff's own default set. Observed: with no config, ruff 0.17.1 enables 407 rules (including B, UP,
     SIM, RUF and Pylint rules), not only pyflakes and a subset of pycodestyle. On our code it reports 32
     findings, all in `contracts/pipeline_result.py` and all style (UP045 `Optional[X]` -> `X | None`,
     UP007, UP037). Observed on a scratch copy: `ruff --fix` clears all 32 and the generated JSON Schema
     is unchanged.
4. **Dashboard linter.** create-vite 9.2.1's React templates offer "--eslint / --no-eslint: use ESLint
   instead of Oxlint" (help text in https://cdn.jsdelivr.net/npm/create-vite@9.2.1/dist/index.js).
   - Oxlint 1.88 (MIT): the template default; one package plus a native binary (13.3 MB unpacked).
   - ESLint: the same CLI would add `eslint` ^10.10.0, `@eslint/js`, `typescript-eslint` ^8.69.0,
     `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh` and `globals` (same source). Larger plugin
     ecosystem; more packages.
5. **TypeScript strict mode.** The template's `tsconfig.app.json` and `tsconfig.node.json` do not set
   `strict`. Observed: TypeScript 6.0.3 already behaves as strict by default (an implicit `any` parameter
   and `null` assigned to `number` are errors without flags and pass with `--strict false`).
   - Rely on the compiler default, or set `"strict": true` explicitly.
6. **Contract JSON Schema drift.** `pipeline_result.schema.json` was generated once by hand, and CLAUDE.md
   says TypeScript types will be generated from it.
   - Leave it, or add a generator plus a test that fails when the file no longer matches the models.

## Decision
`uv_build`; Python `>=3.12,<3.13` with `.python-version` = 3.12; ruff with E, F, I at line length 100
(adopting ruff's broader defaults is left to the team because it rewrites the contract file); Oxlint;
`"strict": true` set explicitly in both tsconfigs; and `moonwalkers.contracts.json_schema` plus
`tests/test_contract_schema.py` to regenerate and check the schema.

## Consequences
- Every tool comes from one `uv sync` or `npm ci`; versions are pinned in `uv.lock` and `package-lock.json`.
- Python 3.13+ is refused until we widen the range on purpose.
- Our ruff rules are narrower than ruff's current defaults. Switching later is one config line plus one
  `ruff --fix` on the contract (style only; the schema test confirms nothing changed).
- Oxlint exits 0 on warnings (observed with a `debugger` probe). If we want warnings to fail lint or CI,
  add `--deny-warnings` to the `lint` script.
- Strict mode no longer depends on the compiler's default.
- A contract change that forgets to regenerate the schema fails `uv run pytest`, with the regenerate
  command in the failure message.
- Reversing any of these is a config edit; nothing else depends on them.
