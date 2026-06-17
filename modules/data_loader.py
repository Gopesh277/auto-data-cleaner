"""
data_loader.py
----------------
Handles reading the uploaded CSV file and validating it before it is
passed into the cleaning pipeline. Keeping this separate from app.py
means the file-reading rules (what counts as "bad input") live in one
place and can be unit tested independently of Streamlit.
"""

from __future__ import annotations

import pandas as pd


class DataValidationError(Exception):
    """Raised when an uploaded file fails a basic sanity check.

    Caught in app.py and shown to the user as a friendly st.error
    message instead of a raw traceback.
    """


def load_csv(uploaded_file) -> pd.DataFrame:
    """Read an uploaded CSV file into a DataFrame and validate it.

    Args:
        uploaded_file: A Streamlit UploadedFile object.

    Returns:
        A validated, non-empty pandas DataFrame.

    Raises:
        DataValidationError: If the file is empty, malformed, or has
            an encoding problem.
    """
    try:
        df = pd.read_csv(uploaded_file)
    except pd.errors.EmptyDataError as exc:
        raise DataValidationError("The uploaded CSV file has no data.") from exc
    except pd.errors.ParserError as exc:
        raise DataValidationError(
            "Could not parse the CSV file. Please check that it is a valid, "
            "comma-separated CSV."
        ) from exc
    except UnicodeDecodeError as exc:
        raise DataValidationError(
            "Encoding error while reading the file. Try re-saving the CSV as UTF-8."
        ) from exc

    if df.empty:
        raise DataValidationError("The uploaded CSV file is empty.")

    if df.shape[1] == 0:
        raise DataValidationError("No columns were detected in the uploaded file.")

    if df.shape[1] == 1 and df.columns[0].lower().startswith("unnamed"):
        # Common symptom of a delimiter mismatch (e.g. semicolon-separated file).
        raise DataValidationError(
            "Only one unnamed column was detected. The file may use a delimiter "
            "other than a comma."
        )

    return df
