"""
new_column.py
----------------
Lets a user build a new column from two existing columns using
if-then rules, e.g.:

    IF Column 1 > 100        THEN "High"
    IF Column 2 contains "x" THEN "{COL1}-flag"
    ELSE                          "Normal"

Rules run top to bottom; the first matching rule wins. Output values
may reference {COL1} / {COL2} to insert that row's actual values
(useful for concatenation-style outputs).
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pandas as pd

OPERATOR_LABELS = ["=", "!=", ">", "<", ">=", "<=", "contains", "is null", "is not null"]


def _to_number(value: Any):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _values_equal(a: Any, b: Any) -> bool:
    num_a, num_b = _to_number(a), _to_number(b)
    if num_a is not None and num_b is not None:
        return num_a == num_b
    return str(a).strip().lower() == str(b).strip().lower()


def _compare(a: Any, b: Any) -> int:
    """Return -1, 0, or 1, comparing numerically if possible, else as strings."""
    num_a, num_b = _to_number(a), _to_number(b)
    if num_a is not None and num_b is not None:
        return (num_a > num_b) - (num_a < num_b)
    str_a, str_b = str(a), str(b)
    return (str_a > str_b) - (str_a < str_b)


def evaluate_condition(value: Any, operator: str, compare_value: Any) -> bool:
    """Evaluate one rule's condition against a single cell value."""
    if operator == "is null":
        return pd.isna(value)
    if operator == "is not null":
        return not pd.isna(value)
    if operator == "=":
        return _values_equal(value, compare_value)
    if operator == "!=":
        return not _values_equal(value, compare_value)
    if operator == ">":
        return _compare(value, compare_value) > 0
    if operator == "<":
        return _compare(value, compare_value) < 0
    if operator == ">=":
        return _compare(value, compare_value) >= 0
    if operator == "<=":
        return _compare(value, compare_value) <= 0
    if operator == "contains":
        return str(compare_value).lower() in str(value).lower()
    raise ValueError(f"Unknown operator: {operator}")


def _substitute(template: str, row: pd.Series, col1: str, col2: str) -> str:
    if template is None:
        return ""
    text = str(template)
    text = text.replace("{COL1}", str(row[col1])).replace("{COL2}", str(row[col2]))
    return text


def validate_rules(rules: List[Dict], else_value: str) -> Tuple[bool, str]:
    """Basic validation before applying rules to a DataFrame."""
    if not rules:
        return False, "Add at least one rule."
    for i, rule in enumerate(rules, start=1):
        if rule.get("operator") not in OPERATOR_LABELS:
            return False, f"Rule {i} has an unrecognized operator."
        needs_value = rule["operator"] not in ("is null", "is not null")
        if needs_value and str(rule.get("compare_value", "")).strip() == "":
            return False, f"Rule {i} is missing a comparison value."
    return True, ""


def apply_new_column(
    df: pd.DataFrame,
    col1: str,
    col2: str,
    new_col_name: str,
    rules: List[Dict],
    else_value: str,
    logger=None,
) -> pd.DataFrame:
    """Create `new_col_name` on `df` by evaluating `rules` row by row."""
    if col1 not in df.columns or col2 not in df.columns:
        raise ValueError("Selected source columns no longer exist in the dataset.")

    def compute(row: pd.Series) -> str:
        for rule in rules:
            source_col = col1 if rule["source"] == "Column 1" else col2
            cell_value = row[source_col]
            try:
                matched = evaluate_condition(cell_value, rule["operator"], rule["compare_value"])
            except Exception:
                matched = False
            if matched:
                return _substitute(rule["output_value"], row, col1, col2)
        return _substitute(else_value, row, col1, col2)

    df = df.copy()
    df[new_col_name] = df.apply(compute, axis=1)

    if logger is not None:
        logger.log(
            f"Added derived column '{new_col_name}'",
            details=(
                f"Built from '{col1}' and '{col2}' using {len(rules)} rule(s); "
                f"default value when no rule matches: '{else_value}'."
            ),
        )
    return df
