#!/usr/bin/env python3
"""End-to-end check for the template itself.

This repo is a template, not a running service: the agent package directory is
literally named `{{AGENT_NAME_LOWER}}`, which is not an importable Python
identifier. So the thing worth testing end to end is the *generation contract* --
that a session following EXECUTION_PROMPT.md produces a repo that builds.

    python bin/e2e.py

Everything that needs GCP, Azure DevOps or a live gateway prints an explicit
SKIP with the reason rather than being left out. Exit code 0 only if every
check passed.
"""
from __future__ import annotations

import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PASS: list[tuple[str, str]] = []
FAIL: list[tuple[str, str, str]] = []
SKIP: list[tuple[str, str]] = []

TOKENS = [
    "AGENT_NAME",
    "AGENT_NAME_LOWER",
    "SERVICE_PREFIX",
    "AGENT_DISPLAY_NAME",
    "DEPLOYMENT_GROUP_EMAIL",
]

SKIP_PARTS = {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".lock"}


# Binary files cannot be grepped, so each one listed here has been opened
# and looked at. Adding a path to this list asserts that someone did.
REVIEWED_BINARIES = [
]

class _Skip(Exception):
    pass


def check(name):
    def wrap(fn):
        try:
            detail = fn()
        except _Skip as exc:
            SKIP.append((name, str(exc)))
        except Exception as exc:  # noqa: BLE001 - the harness reports, never crashes
            FAIL.append((name, f"{type(exc).__name__}: {exc}", traceback.format_exc()))
        else:
            PASS.append((name, detail or ""))
        return fn
    return wrap


def text_files():
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or set(p.parts) & SKIP_PARTS:
            continue
        if p.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            yield p, p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


# --------------------------------------------------------------------------
# The substitution contract
# --------------------------------------------------------------------------

@check("documented substitution order is safe against the substring trap")
def _order():
    config = (ROOT / "template.config.yml").read_text(encoding="utf-8")
    order = re.findall(r"#\s+\d+\.\s+\{\{([A-Z_]+)\}\}", config)
    assert order, "no numbered substitution order found in template.config.yml"
    assert set(order) == set(TOKENS), f"order lists {order}, expected {TOKENS}"

    # A token must never be substituted before a token it is a substring of:
    # replacing {{AGENT_NAME}} first turns {{AGENT_NAME_LOWER}} into value_LOWER}}.
    for i, earlier in enumerate(order):
        for later in order[i + 1:]:
            assert earlier not in later or earlier == later, (
                f"{earlier} is substituted before {later}, but is a substring of it - "
                f"substituting it first would corrupt {later}"
            )
    return " -> ".join(order)


@check("every token in the tree is declared in template.config.yml")
def _declared():
    config = (ROOT / "template.config.yml").read_text(encoding="utf-8")
    declared = set(re.findall(r"^\s{2}([A-Z_]+):", config, re.MULTILINE))
    used: dict[str, list[str]] = {}
    for p, t in text_files():
        for tok in re.findall(r"\{\{([A-Z_]+)\}\}", t):
            used.setdefault(tok, []).append(str(p.relative_to(ROOT)))
    undeclared = {k: v[:2] for k, v in used.items() if k not in declared}
    assert not undeclared, f"tokens used but not declared: {undeclared}"
    return f"{len(used)} tokens used, all declared"


@check("every declared token is actually used somewhere")
def _used():
    blob = "".join(t for _, t in text_files())
    unused = [tok for tok in TOKENS if f"{{{{{tok}}}}}" not in blob]
    assert not unused, f"declared but never used: {unused} - dead tokens mislead the generator"
    return f"all {len(TOKENS)} tokens appear in the tree"


@check("the two token-named directories exist and are the only ones")
def _token_dirs():
    expected = {
        ROOT / "agents" / "{{AGENT_NAME_LOWER}}",
        ROOT / "InfrastructureAsCode" / "{{SERVICE_PREFIX}}",
    }
    found = {
        p for p in ROOT.rglob("*")
        if p.is_dir() and "{{" in p.name and not set(p.parts) & SKIP_PARTS
    }
    assert found == expected, (
        f"token-named directories drifted from EXECUTION_PROMPT.md's rename step.\n"
        f"  expected: {sorted(str(p.relative_to(ROOT)) for p in expected)}\n"
        f"  found:    {sorted(str(p.relative_to(ROOT)) for p in found)}"
    )
    return "agents/ and InfrastructureAsCode/ only"


# --------------------------------------------------------------------------
# The ADK contract the generated repo has to satisfy
# --------------------------------------------------------------------------

@check("the agent package exposes root_agent")
def _root_agent():
    src = (ROOT / "agents" / "{{AGENT_NAME_LOWER}}" / "agent.py").read_text(
        encoding="utf-8"
    )
    assert re.search(r"^root_agent\s*=", src, re.MULTILINE), (
        "ADK resolves the agent by a module-level variable named exactly root_agent"
    )
    return "root_agent assigned at module level"


@check("the model keeps its openai/ prefix")
def _model_prefix():
    src = (ROOT / "agents" / "{{AGENT_NAME_LOWER}}" / "agent.py").read_text(
        encoding="utf-8"
    )
    assert 'openai/' in src, (
        "the openai/ prefix bypasses Agent Engine's GOOGLE_GENAI_USE_VERTEXAI "
        "injection; without it the gateway route breaks on deploy"
    )
    assert "LiteLlm" in src, "the gateway route goes through ADK's LiteLlm wrapper"
    return "LiteLlm with an openai/ model prefix"


@check("the ADK agent name token is a valid Python identifier")
def _identifier():
    config = (ROOT / "template.config.yml").read_text(encoding="utf-8")
    m = re.search(r'AGENT_NAME_LOWER:\s*"([^"]+)"', config)
    assert m, "AGENT_NAME_LOWER has no example value in template.config.yml"
    example = m.group(1)
    assert example.isidentifier(), (
        f"the example value {example!r} is not a Python identifier; ADK rejects "
        f"hyphens in agent names"
    )
    assert example.islower(), f"{example!r} should be lowercase"
    return f"example {example!r} is a valid identifier"


@check("prompts contain no bare curly braces")
def _prompt_braces():
    src = (ROOT / "agents" / "{{AGENT_NAME_LOWER}}" / "prompts.py").read_text(
        encoding="utf-8"
    )
    stripped = re.sub(r"\{\{[A-Z_]+\}\}", "", src)
    body = stripped.split("SYSTEM_INSTRUCTION", 1)[-1]
    bare = re.findall(r"(?<!\{)\{([a-z_][a-z_0-9]*)\}(?!\})", body)
    assert not bare, (
        f"ADK reads {{braces}} in an instruction as session-state references: {bare}"
    )
    return "no accidental session-state references"


# --------------------------------------------------------------------------
# Dependency and reference integrity
# --------------------------------------------------------------------------

@check("requirements.txt and pyproject.toml agree")
def _deps_in_sync():
    reqs_path = ROOT / "agents" / "{{AGENT_NAME_LOWER}}" / "requirements.txt"
    reqs = {
        re.split(r"[<>=\[]", line.strip())[0].lower()
        for line in reqs_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    # Split on the closing bracket at column 0: a naive split on "]" stops
    # inside an extras marker like google-adk[extensions].
    after = pyproject.split("dependencies = [", 1)[1]
    block = re.split(r"^\]", after, maxsplit=1, flags=re.MULTILINE)[0]
    pins = {
        re.split(r"[<>=\[]", m)[0].lower()
        for m in re.findall(r'"([^"]+)"', block)
    }
    assert pins, "parsed no dependencies out of pyproject.toml - the check would be vacuous"
    assert reqs, "parsed no dependencies out of requirements.txt"
    missing = pins - reqs
    assert not missing, (
        f"in pyproject but not requirements.txt: {sorted(missing)}. Agent Engine "
        f"builds its remote venv from requirements.txt, so a gap here fails at deploy, "
        f"not at build."
    )
    return f"{len(pins)} runtime deps present in both"


@check("no .env is tracked, only .env.example")
def _no_env():
    tracked = [
        str(p.relative_to(ROOT))
        for p in ROOT.rglob(".env*")
        if p.is_file() and not set(p.parts) & SKIP_PARTS and p.name != ".env.example"
    ]
    assert not tracked, f"these should not be in the repo: {tracked}"
    assert (ROOT / ".env.example").exists(), ".env.example is missing"
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert re.search(r"^\.env\s*$", gitignore, re.MULTILINE), ".gitignore must cover .env"
    return ".env.example only; .env is ignored"


@check("files referenced by docs and configs exist")
def _refs_exist():
    missing: list[str] = []
    for p, t in text_files():
        if p.suffix not in {".md", ".yml", ".yaml", ".sh"}:
            continue
        for m in re.finditer(r"(?:docs|bin|ADOYaml|tests)/[A-Za-z0-9_./{}-]+\.\w+", t):
            ref = m.group(0)
            if "{" in ref or (ROOT / ref).exists():
                continue
            tail = t[m.end():m.end() + 2]
            head = t[max(0, m.start() - 40):m.start()]
            # External repo resources: `template: ADOYaml/x.yml@OtherRepo`.
            if tail.startswith("@") or "templates/" in ref:
                continue
            # Part of a URL, not a path in this repo.
            if "://" in head:
                continue
            missing.append(f"{p.relative_to(ROOT)} -> {ref}")
    assert not missing, "dangling references:\n  " + "\n  ".join(sorted(set(missing)))
    return "no dangling in-repo references"


@check("every bin/ script is strict-mode bash")
def _bin_strict():
    scripts = sorted((ROOT / "bin").glob("*.sh"))
    assert scripts, "bin/ has no shell scripts"
    for s in scripts:
        head = s.read_text(encoding="utf-8")[:400]
        assert "errexit" in head and "nounset" in head and "pipefail" in head, (
            f"{s.name} is missing strict mode; a silent failure in CI is worse than a loud one"
        )
    return f"{len(scripts)} scripts, all errexit/nounset/pipefail"


@check("the deploy script encodes the four Agent Engine gotchas")
def _deploy_script():
    src = (ROOT / "bin" / "deploy-agent-engine.sh").read_text(encoding="utf-8")
    for needle, why in (
        ("uv run adk", "the build image's ADK can differ from the project pin"),
        ("agent_engine_id", "without it every deploy creates a duplicate engine"),
        ("PYTHONIOENCODING", "ADK prints emoji; the Windows console codepage crashes"),
        ("cd ", "ADK resolves the agent by package name relative to cwd"),
    ):
        assert needle in src, f"missing {needle!r}: {why}"
    return "all four present"


@check("the pipeline YAML parses in template form")
def _yaml_parses():
    try:
        import yaml
    except ImportError:
        raise _Skip("pyyaml not installed") from None

    # A bare double-brace token at the start of a YAML value opens a flow mapping, so an
    # unquoted token makes the file unparseable until it is substituted. Quoting
    # costs nothing and keeps the template itself valid.
    for p in sorted((ROOT / "ADOYaml").glob("*.yml")):
        try:
            yaml.safe_load(p.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            raise AssertionError(
                f"{p.name} does not parse as YAML in template form: "
                f"{str(exc).splitlines()[0]}"
            ) from None
    return f"{len(list((ROOT / 'ADOYaml').glob('*.yml')))} pipelines parse unsubstituted"


# --------------------------------------------------------------------------
# No employer identifiers survived sanitisation
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Not covered here - stated explicitly rather than omitted
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Pre-publication leak gate (shared; see bin/leakcheck.py)
# --------------------------------------------------------------------------

@check("no employer identifiers in the working tree")
def _leak_tree():
    sys.path.insert(0, str(ROOT / "bin"))
    import leakcheck

    hits = leakcheck.scan_tree(ROOT, self_path=Path(leakcheck.__file__))
    assert not hits, "\n  " + "\n  ".join(hits[:12])
    return "clean, lockfiles included"


@check("no employer identifiers anywhere in git history")
def _leak_history():
    sys.path.insert(0, str(ROOT / "bin"))
    import leakcheck

    if not (ROOT / ".git").exists():
        raise _Skip("not a git repository")
    hits = leakcheck.scan_history(ROOT)
    assert not hits, (
        "a fresh history is only clean if nothing was committed and then removed:\n  "
        + "\n  ".join(hits[:12])
    )
    return "clean across all commits"


@check("every binary file has been reviewed by eye")
def _binaries():
    sys.path.insert(0, str(ROOT / "bin"))
    import leakcheck

    found = set(leakcheck.binaries(ROOT))
    allowed = set(REVIEWED_BINARIES)
    unreviewed = sorted(found - allowed)
    stale = sorted(allowed - found)
    assert not unreviewed, (
        f"these cannot be grepped and are not on the reviewed list, so nobody has "
        f"confirmed what they show: {unreviewed}"
    )
    assert not stale, f"REVIEWED_BINARIES lists files that no longer exist: {stale}"
    return f"{len(found)} binaries, all reviewed"


UNCOVERED = [
    ("Actually importing the agent package", "the directory is named {{AGENT_NAME_LOWER}}; only a generated repo can import"),
    ("pytest / ruff / pyright on the template", "same reason - run them in a generated repo via bin/*.sh"),
    ("terragrunt plan", "needs GCP credentials, a state bucket and a real module registry"),
    ("Azure DevOps pipeline runs", "needs an ADO org, self-hosted pools and the shared stage templates"),
    ("WIF token exchange", "needs an Entra app registration and a configured pool"),
    ("adk deploy agent_engine", "needs GCP, a staging bucket, and mints a billable engine"),
    ("An end-to-end EXECUTION_PROMPT.md run", "needs an interactive LLM session and a human at four gates"),
]


def main() -> int:
    for name, reason in UNCOVERED:
        SKIP.append((name, reason))

    width = max(len(n) for n, *_ in PASS + FAIL + SKIP)
    for name, detail in PASS:
        print(f"PASS  {name:<{width}}  {detail}")
    for name, reason in SKIP:
        print(f"SKIP  {name:<{width}}  {reason}")
    for name, msg, tb in FAIL:
        print(f"FAIL  {name:<{width}}  {msg}")
        print("".join("        " + line for line in tb.splitlines(keepends=True)))

    print(f"\n{len(PASS)} passed, {len(FAIL)} failed, {len(SKIP)} skipped")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
