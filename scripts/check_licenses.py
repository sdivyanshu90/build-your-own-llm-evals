"""Fail CI when locked direct dependencies use a denied license."""

from __future__ import annotations

import importlib.metadata
import sys

DENIED = ("GNU GENERAL PUBLIC LICENSE", "AGPL", "SSPL", "BUSINESS SOURCE LICENSE")


def main() -> int:
    """Inspect installed distributions without network access."""

    violations: list[str] = []
    missing: list[str] = []
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get("Name", "unknown")
        expression = distribution.metadata.get("License-Expression", "")
        classifiers = [
            value
            for value in distribution.metadata.get_all("Classifier", [])
            if value.startswith("License ::")
        ]
        # Some binary scientific wheels append notices for bundled runtime
        # libraries to the full License field. Prefer the package's SPDX
        # expression or declared Trove license so an incidental notice does
        # not reclassify the distribution itself.
        declared = expression or " ".join(classifiers)
        if not declared:
            declared = distribution.metadata.get("License", "")[:2_000]
        declared = declared.upper()
        if any(denied in declared for denied in DENIED):
            violations.append(f"{name}: denied license metadata")
        if not declared.strip():
            missing.append(name)
    if violations:
        print("\n".join(sorted(violations)))
        return 1
    print(
        "installed distribution license metadata passed; "
        f"{len(missing)} distributions had no machine-readable license metadata"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
