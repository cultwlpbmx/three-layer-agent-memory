"""
Scaffold a new project memory library from the canonical template.

Usage:
    from three_layer_memory import init
    init("/path/to/my-project-memory", locale="zh")        # or "en" or "auto"
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .core import ZH, EN, detect_locale


def _template_root(locale: str) -> Path:
    """Return the template dir bundled with this package.

    Lookup order: inside the installed package first (site-packages layout,
    ships in the wheel/sdist since v0.8.4), then next to the package
    (repo checkout / editable install).
    """
    here = Path(__file__).resolve().parent
    pkg_root = here.parent
    for root in (here, pkg_root):
        if locale == "en":
            p = root / "_template-en"
            if p.is_dir():
                return p
        p = root / "_template"
        if p.is_dir():
            return p
    raise FileNotFoundError(
        f"template dir not found (looked inside package {here} and next to it "
        f"{pkg_root}). Reinstall the package or run from a repo checkout."
    )


def init(target_dir: str | Path, locale: str = "auto",
         *, with_unknowns: bool = True) -> Path:
    """Create a new project memory library at `target_dir` from the template.

    `locale`: "zh" (canonical Chinese 表层/中层/深层), "en" (Surface/Middle/Deep),
              or "auto" (detect from system / default to zh).

    `with_unknowns`: include the optional 02-未知与开放问题 / 02-unknowns.md
                     (recommended since v0.3).

    Returns the created library root path.
    """
    target = Path(target_dir).resolve()
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"target dir not empty: {target} (init refuses to clobber)")

    # resolve locale
    if locale == "auto":
        # no reliable system-locale→layer-locale mapping; default to zh (canonical)
        locale = "zh"

    tmpl = _template_root(locale)
    target.mkdir(parents=True, exist_ok=True)

    # copy template contents into target
    for item in tmpl.iterdir():
        dst = target / item.name
        if item.is_dir():
            shutil.copytree(item, dst)
        else:
            shutil.copy2(item, dst)

    # optionally drop the unknowns file
    if not with_unknowns:
        loc = ZH if locale == "zh" else EN
        unknowns = target / loc["surface"] / loc["unknowns"]
        if unknowns.exists():
            unknowns.unlink()

    return target