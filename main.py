"""Entry point for both the source checkout and the frozen build."""
from __future__ import annotations

import sys
from pathlib import Path

if __package__ in (None, "") and str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))


def main() -> int:
    if "--selfcheck" in sys.argv:
        from qingjian.selfcheck import run
        return run(sys.argv[sys.argv.index("--selfcheck") + 1:])
    from qingjian.ui.app import main as run_app
    return run_app(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
