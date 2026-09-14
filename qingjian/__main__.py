"""``python -m qingjian``."""
from __future__ import annotations

import sys


def main() -> int:
    if "--selfcheck" in sys.argv:
        from .selfcheck import run
        return run(sys.argv[sys.argv.index("--selfcheck") + 1:])
    from .ui.app import main as run_app
    return run_app(sys.argv)


if __name__ == "__main__":
    raise SystemExit(main())
