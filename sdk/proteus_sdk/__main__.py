# Copyright (c) 2026 CuongKenn & ICTU Team
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Entrypoint cho `python -m proteus_sdk <command>`."""

from __future__ import annotations

import sys

from proteus_sdk.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
