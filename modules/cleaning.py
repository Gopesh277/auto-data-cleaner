"""
cleaning.py
----------------
Core, user-configurable data cleaning operations. Every function takes
the DataFrame plus an AuditLogger and returns the transformed
DataFrame, so the pipeline in app.py is just a sequence of calls that
is easy to read, reorder, or unit test.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

# Output formats offered for date conversion (label -> strftime pattern).
DATE_FORMATS = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "DD-Mon-YYYY": "%d-%b-%Y",
    "Month DD, YYYY": "%B %d, %Y",
}


def remove_duplicates(df: pd.DataFrame, logger) -> Tuple[pd.DataFrame, int]:
    """Drop fully duplicated rows. Returns (df, number_removed)."""
    duplicate_count = int(df.duplicated().sum())
    df = df.drop_duplicates()
    logger.log(
        "Removed duplicate rows",
        details=f"{duplicate_count} duplicate row(s) removed.",
    )
    return df, duplicate_count


def clean_column_names(df: pd.DataFrame, logger) -> pd.DataFrame:
    """Strip whitespace and lowercase every column name."""
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower()
    logger.log(
        "Standardized column names",
        details="Stripped whitespace and converted column names to lowercase.",
    )
    return df


def _parse_date_elementwise(series: pd.Series) -> pd.Series:
    """Parse each value individually rather than inferring one format for
    the whole column. This is slower but far more tolerant of columns
    that mix formats (e.g. "2023-01-15" and "01/20/2023" together),
    which a single vectorized format guess would otherwise reject.
    """
    return series.apply(lambda value: pd.to_datetime(value, errors="coerce"))


def detect_date_columns(df: pd.DataFrame, threshold: float = 0.7, sample_size: int = 200) -> List[str]:
    """Heuristically find text columns that look like dates.

    A column qualifies if at least `threshold` fraction of a sample of
    its non-null values can be parsed by pandas as a date.
    """
    candidates: List[str] = []
    for col in df.select_dtypes(include="object").columns:
        series = df[col].dropna()
        if series.empty:
            continue
        sample = series.astype(str).head(sample_size)
        parsed = _parse_date_elementwise(sample)
        success_ratio = parsed.notna().mean()
        if success_ratio >= threshold:
            candidates.append(col)
    return candidates


def convert_date_columns(
    df: pd.DataFrame, columns: List[str], output_format_label: str, logger
) -> Tuple[pd.DataFrame, List[str]]:
    """Parse and reformat the given columns into a consistent date format."""
    df = df.copy()
    fmt = DATE_FORMATS.get(output_format_label, "%Y-%m-%d")
    converted: List[str] = []

    for col in columns:
        if col not in df.columns:
            continue
        try:
            parsed = _parse_date_elementwise(df[col])
            if parsed.notna().sum() == 0:
                # Nothing parsed - leave the column untouched.
                continue
            df[col] = parsed.dt.strftime(fmt)
            converted.append(col)
        except Exception:
            # Skip columns that can't be safely converted rather than
            # failing the whole pipeline.
            continue

    if converted:
        logger.log(
            "Converted date columns",
            details=f"Columns {converted} reformatted to '{output_format_label}'.",
        )
    return df, converted


def handle_missing_values(
    df: pd.DataFrame,
    logger,
    numeric_strategy: str,
    numeric_custom_value: float,
    text_strategy: str,
    text_custom_value: str,
    exclude_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Fill missing values using user-selected strategies.

    numeric_strategy: one of "Median", "Mean", "Mode", "Custom Value", "Leave as is"
    text_strategy: one of '"Unknown" placeholder', "Mode", "Custom Text", "Leave as is"
    """
    df = df.copy()
    exclude_columns = exclude_columns or []
    numeric_filled = 0
    text_filled = 0

    for column in df.columns:
        if column in exclude_columns:
            continue

        missing = int(df[column].isna().sum())
        if missing == 0:
            continue

        if pd.api.types.is_numeric_dtype(df[column]):
            if numeric_strategy == "Median":
                fill_value = df[column].median()
            elif numeric_strategy == "Mean":
                fill_value = df[column].mean()
            elif numeric_strategy == "Mode":
                modes = df[column].mode()
                fill_value = modes.iloc[0] if not modes.empty else 0
            elif numeric_strategy == "Custom Value":
                fill_value = numeric_custom_value
            else:  # "Leave as is"
                continue
            df[column] = df[column].fillna(fill_value)
            numeric_filled += missing
        else:
            if text_strategy == "Mode":
                modes = df[column].mode()
                fill_value = modes.iloc[0] if not modes.empty else "Unknown"
            elif text_strategy == "Custom Text":
                fill_value = text_custom_value
            elif text_strategy == '"Unknown" placeholder':
                fill_value = "Unknown"
            else:  # "Leave as is"
                continue
            df[column] = df[column].fillna(fill_value)
            text_filled += missing

    logger.log(
        "Handled missing values",
        details=(
            f"Numeric columns -> strategy '{numeric_strategy}' "
            f"({numeric_filled} value(s) filled). "
            f"Text columns -> strategy '{text_strategy}' "
            f"({text_filled} value(s) filled)."
        ),
    )
    return df


def standardize_text(
    df: pd.DataFrame, logger, case_option: str, exclude_columns: Optional[List[str]] = None
) -> pd.DataFrame:
    """Trim whitespace on all text columns and apply the chosen case style.

    case_option: one of "UPPERCASE", "lowercase", "Title Case", "No change"
    """
    df = df.copy()
    exclude_columns = exclude_columns or []
    text_cols = [c for c in df.select_dtypes(include="object").columns if c not in exclude_columns]

    for col in text_cols:
        series = df[col].astype(str).str.strip()
        if case_option == "UPPERCASE":
            series = series.str.upper()
        elif case_option == "lowercase":
            series = series.str.lower()
        elif case_option == "Title Case":
            series = series.str.title()
        # "No change" -> keep the stripped values as-is.
        df[col] = series

    logger.log(
        "Standardized text columns",
        details=f"Applied case style '{case_option}' to columns: {text_cols}.",
    )
    return df


def remove_outliers(df: pd.DataFrame, logger, enabled: bool, multiplier: float) -> pd.DataFrame:
    """Drop rows outside [Q1 - multiplier*IQR, Q3 + multiplier*IQR] for every numeric column."""
    if not enabled:
        logger.log("Outlier removal skipped", details="Disabled by user.")
        return df

    df = df.copy()
    rows_before = df.shape[0]
    numeric_cols = df.select_dtypes(include=np.number).columns

    for col in numeric_cols:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - multiplier * iqr
        upper = q3 + multiplier * iqr
        df = df[(df[col] >= lower) & (df[col] <= upper)]

    rows_removed = rows_before - df.shape[0]
    logger.log(
        "Removed outliers",
        details=f"IQR multiplier={multiplier}; {rows_removed} row(s) removed.",
    )
    return df
