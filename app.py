"""
app.py — Automatic Data Cleaning System  (#auto_data_cleaner)
================================================================
Upload a CSV, configure cleaning behaviour from the sidebar, optionally
derive a new column with if-then rules, then download the cleaned
dataset plus a full audit report of every step that was performed.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import copy
import traceback

import streamlit as st

from modules.audit_logger import AuditLogger
from modules.cleaning import (
    DATE_FORMATS,
    clean_column_names,
    convert_date_columns,
    detect_date_columns,
    handle_missing_values,
    remove_duplicates,
    remove_outliers,
    standardize_text,
)
from modules.data_loader import DataValidationError, load_csv
from modules.new_column import OPERATOR_LABELS, apply_new_column, validate_rules

# ----------------------------------------------------------------------
# PAGE CONFIG
# ----------------------------------------------------------------------
st.set_page_config(page_title="Automatic Data Cleaning System", layout="wide")

st.title("Automatic Data Cleaning System")
st.write(
    "Upload a CSV file, configure cleaning rules in the sidebar, optionally "
    "add a derived column, then download the cleaned dataset and a full "
    "audit report."
)

DEFAULT_RULE = {"source": "Column 1", "operator": "=", "compare_value": "", "output_value": ""}


# ----------------------------------------------------------------------
# SESSION STATE
# ----------------------------------------------------------------------
def init_session_state() -> None:
    defaults = {
        "applied_new_columns": [],   # confirmed derived columns, persisted across reruns
        "new_col_rules": [dict(DEFAULT_RULE)],  # rules currently being edited
        "last_file_id": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()

# ----------------------------------------------------------------------
# SIDEBAR HEADER / RESET
# ----------------------------------------------------------------------
st.sidebar.title("Cleaning Configuration")
if st.sidebar.button("Reset App", help="Clear the uploaded file and all settings"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# ----------------------------------------------------------------------
# FILE UPLOAD
# ----------------------------------------------------------------------
uploaded_file = st.file_uploader("Upload CSV File", type=["csv"])

if uploaded_file is None:
    st.info("Upload a CSV file to get started.")
    st.stop()

# A new file should start with a clean slate for derived columns.
file_id = f"{uploaded_file.name}-{uploaded_file.size}"
if st.session_state.last_file_id != file_id:
    st.session_state.applied_new_columns = []
    st.session_state.new_col_rules = [dict(DEFAULT_RULE)]
    st.session_state.last_file_id = file_id

audit = AuditLogger()

# ----------------------------------------------------------------------
# LOAD & VALIDATE
# ----------------------------------------------------------------------
try:
    df = load_csv(uploaded_file)
except DataValidationError as exc:
    st.error(str(exc))
    st.stop()
except Exception as exc:  # noqa: BLE001 - surfaced to the user deliberately
    st.error(f"Unexpected error while reading the file: {exc}")
    with st.expander("Show technical details"):
        st.code(traceback.format_exc())
    st.stop()

original_shape = df.shape

st.subheader("Original Dataset")
st.dataframe(df, use_container_width=True)

info_col1, info_col2 = st.columns(2)
info_col1.metric("Rows", df.shape[0])
info_col2.metric("Columns", df.shape[1])

st.write("**Column names:**", df.columns.tolist())

st.subheader("Missing Values (Before Cleaning)")
st.dataframe(df.isnull().sum().rename("Missing Count"), use_container_width=True)

# ----------------------------------------------------------------------
# SIDEBAR — CLEANING CONFIGURATION (format-by-user controls)
# ----------------------------------------------------------------------
with st.sidebar.expander("Text Formatting", expanded=True):
    case_option = st.selectbox(
        "Text case for all text columns",
        ["UPPERCASE", "lowercase", "Title Case", "No change"],
        index=0,
    )

with st.sidebar.expander("Missing Values", expanded=True):
    numeric_strategy = st.selectbox(
        "Numeric columns",
        ["Median", "Mean", "Mode", "Custom Value", "Leave as is"],
        index=0,
    )
    numeric_custom_value = 0.0
    if numeric_strategy == "Custom Value":
        numeric_custom_value = st.number_input("Custom numeric fill value", value=0.0)

    text_strategy = st.selectbox(
        "Text columns",
        ['"Unknown" placeholder', "Mode", "Custom Text", "Leave as is"],
        index=0,
    )
    text_custom_value = "Unknown"
    if text_strategy == "Custom Text":
        text_custom_value = st.text_input("Custom text fill value", value="Unknown")

with st.sidebar.expander("Outlier Removal", expanded=True):
    outlier_enabled = st.checkbox("Remove outliers (IQR method)", value=True)
    iqr_multiplier = 1.5
    if outlier_enabled:
        iqr_multiplier = st.slider(
            "Sensitivity (IQR multiplier)",
            0.5, 3.0, 1.5, 0.1,
            help="Lower = stricter (removes more rows). Higher = more lenient.",
        )

# Detect date-like columns on a lightly-cleaned probe copy so the sidebar
# can offer real column names (after stripping/lowercasing) before the
# full pipeline has run.
_probe_df = df.copy()
_probe_df.columns = _probe_df.columns.str.strip().str.lower()
candidate_date_cols = detect_date_columns(_probe_df)

with st.sidebar.expander("Date Conversion", expanded=bool(candidate_date_cols)):
    if candidate_date_cols:
        date_cols_to_convert = st.multiselect(
            "Columns to convert", candidate_date_cols, default=candidate_date_cols
        )
        date_output_format = st.selectbox("Output format", list(DATE_FORMATS.keys()), index=0)
    else:
        st.caption("No date-like columns were detected.")
        date_cols_to_convert = []
        date_output_format = next(iter(DATE_FORMATS))

# ----------------------------------------------------------------------
# CLEANING PIPELINE
# ----------------------------------------------------------------------
try:
    cleaned_df = df.copy()

    cleaned_df, duplicates_removed = remove_duplicates(cleaned_df, audit)
    cleaned_df = clean_column_names(cleaned_df, audit)

    date_converted_cols: list[str] = []
    if date_cols_to_convert:
        cleaned_df, date_converted_cols = convert_date_columns(
            cleaned_df, date_cols_to_convert, date_output_format, audit
        )

    cleaned_df = handle_missing_values(
        cleaned_df,
        audit,
        numeric_strategy,
        numeric_custom_value,
        text_strategy,
        text_custom_value,
    )

    cleaned_df = standardize_text(cleaned_df, audit, case_option, exclude_columns=date_converted_cols)

    cleaned_df = remove_outliers(cleaned_df, audit, outlier_enabled, iqr_multiplier)

    # Re-apply any derived columns confirmed in a previous interaction.
    for spec in st.session_state.applied_new_columns:
        if spec["col1"] in cleaned_df.columns and spec["col2"] in cleaned_df.columns:
            cleaned_df = apply_new_column(
                cleaned_df,
                spec["col1"],
                spec["col2"],
                spec["name"],
                spec["rules"],
                spec["else_value"],
                audit,
            )

except Exception as exc:  # noqa: BLE001 - surfaced to the user deliberately
    st.error(f"An error occurred while cleaning the data: {exc}")
    with st.expander("Show technical details"):
        st.code(traceback.format_exc())
    st.stop()

# ----------------------------------------------------------------------
# NEW COLUMN BUILDER (conditional / if-then logic on two columns)
# ----------------------------------------------------------------------
st.subheader("➕ Add a Derived Column (If-Then Rules)")
st.caption(
    "Pick two columns and write if-then rules to build a new column. Rules "
    "run top to bottom — the first match wins. Use **{COL1}** / **{COL2}** "
    "inside an output value to insert that row's actual value."
)

if cleaned_df.shape[1] < 2:
    st.info("Need at least two columns in the cleaned dataset to use this feature.")
else:
    column_options = list(cleaned_df.columns)
    pick_col1, pick_col2, pick_name = st.columns(3)
    with pick_col1:
        source_col1 = st.selectbox("Column 1", column_options, key="nc_col1_select")
    with pick_col2:
        remaining_cols = [c for c in column_options if c != source_col1]
        source_col2 = st.selectbox("Column 2", remaining_cols, key="nc_col2_select")
    with pick_name:
        new_col_name = st.text_input("New column name", value="derived_column", key="nc_name_input")

    delete_idx = None
    for idx, rule in enumerate(st.session_state.new_col_rules):
        rc1, rc2, rc3, rc4, rc5 = st.columns([1.3, 1, 1.3, 1.6, 0.5])
        with rc1:
            rule["source"] = st.selectbox(
                "If column",
                ["Column 1", "Column 2"],
                index=["Column 1", "Column 2"].index(rule["source"]),
                key=f"nc_source_{idx}",
            )
        with rc2:
            rule["operator"] = st.selectbox(
                "Operator",
                OPERATOR_LABELS,
                index=OPERATOR_LABELS.index(rule["operator"]),
                key=f"nc_op_{idx}",
            )
        with rc3:
            if rule["operator"] not in ("is null", "is not null"):
                rule["compare_value"] = st.text_input(
                    "Compare to", value=rule["compare_value"], key=f"nc_val_{idx}"
                )
            else:
                rule["compare_value"] = ""
                st.write("—")
        with rc4:
            rule["output_value"] = st.text_input(
                "Then output", value=rule["output_value"], key=f"nc_out_{idx}"
            )
        with rc5:
            st.write("")
            if st.button("Delete", key=f"nc_remove_{idx}", help="Remove this rule"):
                delete_idx = idx

    if delete_idx is not None:
        st.session_state.new_col_rules.pop(delete_idx)
        st.rerun()

    add_rule_col, _ = st.columns([1, 4])
    with add_rule_col:
        if st.button("+ Add rule"):
            st.session_state.new_col_rules.append(dict(DEFAULT_RULE))
            st.rerun()

    else_value = st.text_input("Else (default) value", value="Unknown", key="nc_else_input")

    if st.button("Apply New Column", type="primary"):
        is_valid, message = validate_rules(st.session_state.new_col_rules, else_value)
        if new_col_name.strip() == "":
            st.error("Please give the new column a name.")
        elif new_col_name in cleaned_df.columns:
            st.error(f"Column '{new_col_name}' already exists. Choose a different name.")
        elif not is_valid:
            st.error(message)
        else:
            st.session_state.applied_new_columns.append(
                {
                    "col1": source_col1,
                    "col2": source_col2,
                    "name": new_col_name,
                    "rules": copy.deepcopy(st.session_state.new_col_rules),
                    "else_value": else_value,
                }
            )
            st.session_state.new_col_rules = [dict(DEFAULT_RULE)]
            st.rerun()

if st.session_state.applied_new_columns:
    st.write("**Derived columns added:**")
    for i, spec in enumerate(st.session_state.applied_new_columns):
        row_left, row_right = st.columns([5, 1])
        row_left.write(
            f"`{spec['name']}` ← if-then on `{spec['col1']}` / `{spec['col2']}` "
            f"({len(spec['rules'])} rule(s))"
        )
        if row_right.button("Remove", key=f"applied_remove_{i}"):
            st.session_state.applied_new_columns.pop(i)
            st.rerun()

# ----------------------------------------------------------------------
# RESULTS
# ----------------------------------------------------------------------
st.subheader("Cleaned Dataset")
st.dataframe(cleaned_df, use_container_width=True)

st.subheader("Cleaning Report")
report_col1, report_col2 = st.columns(2)
report_col1.success(f"Duplicate rows removed: {duplicates_removed}")
report_col2.success(f"Final shape: {cleaned_df.shape[0]} rows × {cleaned_df.shape[1]} columns")

st.subheader("Dataset Statistics")
st.dataframe(cleaned_df.describe(include="all"), use_container_width=True)

# ----------------------------------------------------------------------
# DOWNLOADS
# ----------------------------------------------------------------------
st.subheader("Downloads")
download_col1, download_col2 = st.columns(2)

csv_bytes = cleaned_df.to_csv(index=False).encode("utf-8")
download_col1.download_button(
    label="Download Cleaned Dataset (CSV)",
    data=csv_bytes,
    file_name="cleaned_dataset.csv",
    mime="text/csv",
)

audit_report = audit.to_markdown(original_shape, cleaned_df.shape, filename=uploaded_file.name)
download_col2.download_button(
    label="Download Cleaning Audit Report (.md)",
    data=audit_report.encode("utf-8"),
    file_name="cleaning_audit_report.md",
    mime="text/markdown",
)

with st.expander("View Cleaning Audit Log"):
    st.markdown(audit_report)

# auto_data_cleaner
