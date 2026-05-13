"""Exercise the API client + the pure-Python slice of the integration.

Bypasses Home Assistant (which we don't have installed locally) but does
import the API + const modules to confirm there are no syntax errors and
that the parsed Collection rows look sensible against the live account.

Run: python3 scripts/smoke_integration.py
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import sys
from datetime import date

import aiohttp

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def _load_env(path: pathlib.Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        if "=" not in line or line.startswith("#"):
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


async def main() -> int:
    _load_env(pathlib.Path(__file__).resolve().parent.parent / ".env")

    # Load api.py / const.py directly so we don't trigger __init__.py's
    # homeassistant imports (HA isn't installed in this dev env).
    import importlib.util

    pkg_dir = (
        pathlib.Path(__file__).resolve().parent.parent
        / "custom_components"
        / "havant_waste"
    )

    def _load(name: str, filename: str):
        spec = importlib.util.spec_from_file_location(name, pkg_dir / filename)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module

    const = _load("havant_waste_const_only", "const.py")
    sys.modules["custom_components.havant_waste.const"] = const  # for api.py's relative import
    sys.modules["custom_components"] = type(sys)("custom_components")
    sys.modules["custom_components.havant_waste"] = type(sys)("custom_components.havant_waste")
    sys.modules["custom_components.havant_waste"].const = const
    sys.modules["custom_components.havant_waste"].__path__ = [str(pkg_dir)]
    api = _load("custom_components.havant_waste.api", "api.py")
    HavantWasteClient = api.HavantWasteClient
    ICON_MAP = const.ICON_MAP
    DEFAULT_ICON = const.DEFAULT_ICON

    async with aiohttp.ClientSession() as session:
        client = HavantWasteClient(
            session=session,
            username=os.environ["HAVANT_USERNAME"],
            password=os.environ["HAVANT_PASSWORD"],
        )
        collections = await client.async_fetch_collections()

    today = date.today()
    upcoming = [c for c in collections if c.collection_date >= today]
    if not upcoming:
        print("no upcoming collections — schedule may be empty", file=sys.stderr)
        return 1

    types = sorted({c.waste_type for c in collections})
    unmapped = [t for t in types if t not in ICON_MAP]

    nxt = upcoming[0]
    print(
        f"NEXT: {nxt.collection_date} {nxt.waste_type!r} "
        f"status={nxt.status!r} ({(nxt.collection_date - today).days} days)"
    )
    print("upcoming (first 6):")
    for c in upcoming[:6]:
        icon = ICON_MAP.get(c.waste_type, DEFAULT_ICON)
        print(
            f"  {c.collection_date} | {c.waste_type:<20} | "
            f"status={c.status:<14} | icon={icon}"
        )
    print(f"types seen: {types}")
    if unmapped:
        print(f"WARNING — unmapped waste types: {unmapped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
