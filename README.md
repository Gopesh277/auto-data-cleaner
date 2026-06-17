# Automatic Data Cleaning System (`#auto_data_cleaner`)

A Streamlit app that cleans a CSV file automatically, lets the user
control *how* it gets cleaned, lets them derive a new column with
if-then logic, and exports a full audit trail of every change made.

## Running it

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Project structure

```
auto_data_cleaner/
├── app.py                  # Streamlit UI + pipeline orchestration
├── requirements.txt
├── README.md
└── modules/
    ├── data_loader.py      # CSV reading + input validation
    ├── cleaning.py         # Duplicate removal, missing values, text case,
    │                        # date conversion, outlier removal
    ├── new_column.py       # If-then rule engine for derived columns
    └── audit_logger.py     # Records every step for the audit report
```

Keeping each concern in its own module means the cleaning logic can be
tested or reused without Streamlit, and a bug in one feature (say, the
rule engine) can't break unrelated code.

## Features

**Always-on cleaning**
- Removes fully duplicated rows
- Strips and lowercases column names

**User-configurable formatting** (sidebar)
- Text case for all text columns: UPPERCASE / lowercase / Title Case / no change
- Missing-value strategy, set independently for numeric and text columns
  (median, mean, mode, a custom value, or leave untouched)
- Outlier removal via the IQR method, toggle on/off with an adjustable
  sensitivity multiplier
- Automatic date-column detection with a user-selected output format
  (e.g. `YYYY-MM-DD`, `DD/MM/YYYY`, `Month DD, YYYY`)

**Derived column builder**
- Pick any two columns from the cleaned data
- Add any number of if-then rules (`=`, `!=`, `>`, `<`, `>=`, `<=`,
  `contains`, `is null`, `is not null`) evaluated top-to-bottom,
  first match wins
- Output values can reference `{COL1}` / `{COL2}` to insert the row's
  actual values
- A default ("else") value covers rows that match no rule
- Rules persist across reruns and can be removed individually

**Industry-ready touches**
- Friendly, specific error messages for empty files, parser errors,
  encoding issues, and wrong delimiters — with a collapsible
  "technical details" traceback for debugging
- A downloadable Markdown audit report listing every transformation,
  with timestamps and row/column counts before and after
- A "Reset App" button to clear all settings and start over

## Notes on the rule engine

Comparisons try numeric parsing first (so `"10" > "9"` behaves like a
number comparison rather than a string comparison) and fall back to
case-insensitive string comparison otherwise. A rule that fails to
evaluate on a given row (e.g. a type mismatch) is treated as "no
match" rather than crashing the whole pipeline.
