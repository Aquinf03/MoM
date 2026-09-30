"""CLI entry: `mom-ping` / `python -m mom`."""

from __future__ import annotations

import mom


def main() -> None:
    print(f"mom {mom.__version__} native={mom.NATIVE} ping={mom.ping()!r}")


if __name__ == "__main__":
    main()
