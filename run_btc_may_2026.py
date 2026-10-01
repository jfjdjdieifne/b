"""Single-command wrapper (owner entry point). See README_OWNER.txt."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from field_runner.runner_btc_may_2026 import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
