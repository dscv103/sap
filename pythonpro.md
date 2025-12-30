Updated artifact below adds Ruff, ty, pytest, coverage tooling, and Bandit as **development dependency groups** managed by uv (so they don’t ship as runtime deps), and provides Hatch scripts to run them consistently.[1][2][3]

```markdown
# uv + Hatch CLI project (Typer + Rich) with `src/` layout (Python 3.13+) + dev tooling

This setup uses uv for fast, reproducible environments + lockfiles and Hatch for project lifecycle tasks (e.g., building distributions), matching the “uv + Hatch” workflow described in the referenced article. [file:1]

## 0) Prerequisites
- Install `uv` on dev machines and CI (example installer is shown in the article). [file:1]
- Install `hatch`. [file:1]
- Target Python **3.13+** and declare it in `pyproject.toml` via `requires-python`. [page:6]

## 1) Create the project skeleton (`src/` layout)
1. Create and enter the repo directory:
   ```bash
   mkdir acme-tool
   cd acme-tool
   ```

2. Initialize a Hatch project:
   ```bash
   hatch new --init
   ```

3. Create a `src/` layout for your import package:
   ```bash
   mkdir -p src/acme_tool
   touch src/acme_tool/__init__.py
   ```

## 2) Configure `pyproject.toml` (runtime deps, dev tooling, entry point, `src/`)
Edit `pyproject.toml` to contain:

- Runtime metadata + deps in `[project]` (Typer + Rich).  
- A console script entry in `[project.scripts]` to install `acme-tool`.  
- Hatch build config so Hatchling packages from `src/acme_tool`.  
- A uv **development dependency group** under `[dependency-groups].dev` for:
  - `ruff`
  - `ty`
  - `pytest`
  - `pytest-cov`
  - `coverage`
  - `bandit`

Use this template (adjust metadata as needed):

```toml
[build-system]
requires = [“hatchling>=1.26”]
build-backend = “hatchling.build”

[project]
name = “acme-tool”
version = “0.1.0”
description = “Example Typer + Rich CLI”
readme = “README.md”
requires-python = “>=3.13”
dependencies = [
  “typer”,
  “rich”,
]

[project.scripts]
acme-tool = “acme_tool.cli:app”

# Build config for src/ layout
[tool.hatch.build.targets.wheel]
packages = [“src/acme_tool”]

# Dev tooling (not published as runtime deps)
[dependency-groups]
dev = [
  “ruff”,
  “ty”,
  “pytest”,
  “pytest-cov”,
  “coverage”,
  “bandit”,
]

# Team-consistent command aliases (optional but recommended)
[tool.hatch.envs.default.scripts]
# Linting / formatting
lint = “ruff check .”
format = “ruff format .”

# Typing
typecheck = “ty check src”

# Tests
test = “pytest -q”

# Coverage
coverage = “pytest -q --cov=acme_tool --cov-report=term-missing”

# Security (static checks)
security = “bandit -r src”
```

## 3) Implement the Typer CLI (autocomplete enabled)
1. Create `src/acme_tool/cli.py`:

```python
import typer
from rich.console import Console

# Keep completion enabled:
app = typer.Typer(add_completion=True)

console = Console()

@app.command()
def hello(name: str = “world”) -> None:
    console.print(f”[bold green]Hello {name}![/]”)

@app.command()
def version() -> None:
    console.print(“acme-tool 0.1.0”)
```

2. (Optional) Add `src/acme_tool/__main__.py` to support `python -m acme_tool --help`:

```python
from .cli import app
app(prog_name=“acme-tool”)
```

## 4) Create env + lock + sync (editable) with uv (Python 3.13)
1. Create a venv using Python 3.13:
   ```bash
   uv venv --python 3.13
   ```

2. Add runtime dependencies (writes to `[project].dependencies`):
   ```bash
   uv add typer rich
   ```

3. Add dev tooling dependencies (writes to `[dependency-groups].dev`):
   ```bash
   uv add --dev ruff ty pytest pytest-cov coverage bandit
   ```

4. Create/update the lockfile:
   ```bash
   uv lock
   ```

5. Sync the environment from the lockfile:
   ```bash
   uv sync
   ```

6. Run the CLI:
   ```bash
   uv run acme-tool --help
   uv run acme-tool hello --name Alice
   ```

## 5) Dev commands (choose uv or Hatch)
Because uv syncs dev dependencies by default when they are in the `dev` dependency group, either approach below works:

Option A (recommended): run via uv (auto lock+sync before execution)
```bash
uv run ruff check .
uv run ruff format .
uv run ty check src
uv run pytest -q
uv run pytest -q --cov=acme_tool --cov-report=term-missing
uv run bandit -r src
```

Option B: run via Hatch scripts (team-friendly aliases)
```bash
hatch run lint
hatch run format
hatch run typecheck
hatch run test
hatch run coverage
hatch run security
```

## 6) Shell completion (end users)
After installing your package, a user can install completion for their shell:
```bash
acme-tool --install-completion
```

## 7) Build + CI (frozen)
1. Build wheel + sdist:
   ```bash
   hatch build
   ```

2. CI install must forbid dependency drift:
   ```bash
   uv sync --frozen
   ```

```

Sources
[1] uv: An extremely fast Python package and project manager, written ... https://news.ycombinator.com/item?id=44357411
[2] Uv’s killer feature is making ad-hoc environments easy - Hacker News https://news.ycombinator.com/item?id=42676432
[3] python-packaging-2025-uv-hatch-and-the-end-of-it-works-locally-906264fc2aa5 https://freedium.cfd/https:/medium.com/@Modexa/python-packaging-2025-uv-hatch-and-the-end-of-it-works-locally-906264fc2aa5
[4] PEP 621 – Storing project metadata in pyproject.toml | peps.python.org https://peps.python.org/pep-0621/
[5] PEP 621 dynamic and optional-dependencies - Packaging https://discuss.python.org/t/pep-621-dynamic-and-optional-dependencies/18930
[6] Managing dependencies | main | Documentation - Poetry https://python-poetry.org/docs/main/managing-dependencies/
[7] PEP 621 is now Final! You can store project metadata in pyproject ... https://www.reddit.com/r/Python/comments/lwreon/pep_621_is_now_final_you_can_store_project/
[8] Question: What’s the difference between optional-dependencies and ... https://github.com/astral-sh/uv/issues/9011
[9] Use Hatch environments with your pure Python package - pyOpenSci https://www.pyopensci.org/python-package-guide/tutorials/develop-python-package-hatch.html
[10] chatnoir-api/pyproject.toml at main - GitHub https://github.com/chatnoir-eu/chatnoir-api/blob/main/pyproject.toml
[11] PEP 621 Metadata - PDM https://pdm-project.org/latest/reference/pep621/
[12] How to dynamically set environment variables (`envs.ENV.env-vars`)? https://github.com/pypa/hatch/discussions/1554
[13] lightspeed-service/pyproject.toml at main - GitHub https://github.com/openshift/lightspeed-service/blob/main/pyproject.toml
[14] Recursive Optional Dependencies in Python - Hynek Schlawack https://hynek.me/articles/python-recursive-optional-dependencies/
[15] Default env scripts listed by hatch env show as being avilable to all ... https://github.com/pypa/hatch/discussions/1435
[16] dev-dependencies in workspace pyproject.toml not installed with `uv ... https://github.com/astral-sh/uv/issues/7487
[17] Writing your pyproject.toml - Python Packaging User Guide https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
[18] Environment Tools: Hatch - Playful Python https://www.playfulpython.com/environment-tools-hatch/
[19] Python Lint And Format - A code to remember - Copdips.com https://copdips.com/2021/01/python-lint-and-format.html
[20] Optional dependencies in distutils / pip - python - Stack Overflow https://stackoverflow.com/questions/6237946/optional-dependencies-in-distutils-pip
[21] Environments - Hatch https://hatch.pypa.io/1.8/environment/
[22] I built an ultra-strict typing setup in Python (FastAPI + LangGraph + ... https://www.reddit.com/r/Python/comments/1o53ave/i_built_an_ultrastrict_typing_setup_in_python/
[23] Managing dependencies | uv - Astral Docs https://docs.astral.sh/uv/concepts/projects/dependencies/
[24] CLI | ty - Astral Docs https://docs.astral.sh/ty/reference/cli/
[25] ty - Astral Docs https://docs.astral.sh/ty/
[26] Astral’s ty: A New Blazing-Fast Type Checker for Python https://realpython.com/python-ty/
[27] astral-sh/ty: An extremely fast Python type checker and ... - GitHub https://github.com/astral-sh/ty
[28] How to try the ty type checker - Python Developer Tooling Handbook https://pydevtools.com/handbook/how-to/how-to-try-the-ty-type-checker/
[29] ty: Astral’s New Type Checker (Formerly Red-Knot) - Talk Python https://talkpython.fm/episodes/show/506/ty-astrals-new-type-checker-formerly-red-knot
[30] ty: Astral’s New Python Type Checker Released https://pydevtools.com/blog/ty-beta/
[31] Type checking | ty - Astral Docs https://docs.astral.sh/ty/type-checking/
[32] MyPy Is DEAD! Astral’s TY Is The New Future Of Python ... - YouTube https://www.youtube.com/watch?v=UviMQ7Muuko
[33] ty, a fast Python type checker by the uv devs, is now in beta - Reddit https://www.reddit.com/r/programming/comments/1pokx5j/ty_a_fast_python_type_checker_by_the_uv_devs_is/
[34] ty - Python type-checker from Astral (uv and ruff creators)! - YouTube https://www.youtube.com/watch?v=aDViJRLQr30
[35] ty - PyPI https://pypi.org/project/ty/0.0.0a8/
[36] Ty: An extremely fast Python type checker and language server ... https://www.reddit.com/r/Python/comments/1kgzxs0/ty_an_extremely_fast_python_type_checker_and/
[37] An Intro to ty - The Extremely Fast Python type checker https://www.blog.pythonlibrary.org/2025/06/25/an-intro-to-ty-the-extremely-fast-python-type-checker/
