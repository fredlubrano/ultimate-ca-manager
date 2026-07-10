"""Regression test: api.v2 modules must import on non-POSIX platforms.

`api/v2/__init__.py` eagerly imports every submodule, so a single module doing an
UNCONDITIONAL top-level `import pwd` (or another POSIX-only stdlib module) makes the
entire `api.v2` package — and therefore the whole test suite — fail to import on
Windows with `ModuleNotFoundError: No module named 'pwd'`. POSIX-only modules must be
imported lazily (inside the function that needs them) or guarded, so the module still
loads everywhere and the POSIX-only behavior degrades gracefully.

Regression for the `api/v2/system/https.py` `import pwd` that broke Windows imports.
"""
import ast
import os

API_V2 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api", "v2")

# stdlib modules that only exist on POSIX; a top-level import of any breaks import on Windows.
POSIX_ONLY = {"pwd", "grp", "fcntl", "termios", "crypt", "spwd", "nis", "posix", "resource", "syslog"}


def _toplevel_posix_imports(path):
    """POSIX-only modules imported UNCONDITIONALLY at module level (direct children of the
    module body — so lazy imports inside functions and guarded try/except imports are fine)."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    hits = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            hits += [(a.name, node.lineno) for a in node.names if a.name.split(".")[0] in POSIX_ONLY]
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] in POSIX_ONLY:
            hits.append((node.module, node.lineno))
    return hits


def test_no_toplevel_posix_only_imports_in_api_v2():
    offenders = {}
    for dirpath, _, filenames in os.walk(API_V2):
        for fn in filenames:
            if fn.endswith(".py"):
                path = os.path.join(dirpath, fn)
                hits = _toplevel_posix_imports(path)
                if hits:
                    offenders[os.path.relpath(path, API_V2)] = hits
    assert not offenders, (
        "api.v2 modules must import on non-POSIX platforms (api/v2/__init__.py imports them all "
        "eagerly); import POSIX-only modules lazily/guarded instead. Offenders: " + repr(offenders)
    )
