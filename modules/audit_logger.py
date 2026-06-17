"""
audit_logger.py
----------------
A tiny, dependency-free logger that records every transformation the
cleaning pipeline performs so it can be shown to the user and exported
as a downloadable audit report. This is what makes the cleaning
process traceable/explainable instead of a black box.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Dict, Tuple


class AuditLogger:
    """Collects a timestamped, human-readable trail of cleaning steps."""

    def __init__(self) -> None:
        self.steps: List[Dict[str, str]] = []

    def log(self, step_name: str, details: str = "") -> None:
        """Record one cleaning step.

        Args:
            step_name: Short title of the step, e.g. "Removed duplicate rows".
            details: Optional extra context, e.g. "12 duplicate rows removed".
        """
        self.steps.append(
            {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "step": step_name,
                "details": details,
            }
        )

    def to_markdown(
        self,
        original_shape: Tuple[int, int],
        final_shape: Tuple[int, int],
        filename: str = "dataset.csv",
    ) -> str:
        """Render the recorded steps as a Markdown audit report."""
        lines = [
            "# Data Cleaning Audit Report",
            "",
            f"**Source file:** {filename}",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Original shape:** {original_shape[0]} rows x {original_shape[1]} columns",
            f"**Final shape:** {final_shape[0]} rows x {final_shape[1]} columns",
            "",
            "## Steps Performed",
            "",
        ]

        if not self.steps:
            lines.append("_No cleaning steps were recorded._")
        else:
            for i, step in enumerate(self.steps, start=1):
                lines.append(f"{i}. **{step['step']}** — _{step['time']}_")
                if step["details"]:
                    lines.append(f"   - {step['details']}")

        return "\n".join(lines)
