"""Runs every registered rule check over a Declarations object."""
from __future__ import annotations

from . import font_size, mandatory_declarations, placement
from .schema import ComplianceReport, Declarations, RULESET_VERSION

ALL_CHECKS = [*mandatory_declarations.ALL_CHECKS, *font_size.ALL_CHECKS, *placement.ALL_CHECKS]


def run_all_checks(declarations: Declarations) -> ComplianceReport:
    results = [check(declarations) for check in ALL_CHECKS]
    return ComplianceReport(ruleset_version=RULESET_VERSION, results=results)
