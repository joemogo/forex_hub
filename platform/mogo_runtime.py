#!/usr/bin/env python3
"""MOGO Automation Platform runtime -- operator launcher.

Thin entry point. Inserts `platform/src` on sys.path -- the ONE path entry the
platform ever adds, documented in platform/README.md -- and delegates to
mogo_platform.runtime.cli.

Invoked exactly as the repository's other operator tools are:

    python3 platform/mogo_runtime.py init
    python3 platform/mogo_runtime.py demo
    python3 platform/mogo_runtime.py status
    python3 platform/mogo_runtime.py audit --workflow <id>
    python3 platform/mogo_runtime.py verify

This file deliberately contains no logic beyond the path bridge, so that the
bridge disappears in one edit once ADR-012 D-01's package manifest exists and
`mogo_platform` becomes installable.
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_HERE, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from mogo_platform.runtime import cli  # noqa: E402

if __name__ == "__main__":
    sys.exit(cli.main())
