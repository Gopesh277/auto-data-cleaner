import streamlit as st
import pandas as pd
import numpy as np

# --------------------------------
# PAGE CONFIG
# --------------------------------

st.set_page_config(
    page_title="Automatic Data Cleaning System",
    layout="wide"
)

# --------------------------------
# PAGE TITLE
# --------------------------------

st.title("Automatic Data Cleaning System")

st.write("Upload a CSV dataset and clean it automatically.")

# --------------------------------
# FILE UPLOAD
# --------------------------------

uploaded_file = st.file_uploader(
    "Upload CSV File",
    type=["csv"]
)

# --------------------------------
# PROCESS FILE
# --------------------------------

if uploaded_file is not None:

    # --------------------------------
    # ERROR HANDLING
    # --------------------------------

    try:

        # Load dataset
        df = pd.read_csv(uploaded_file)

        # --------------------------------
        # CHECK EMPTY DATASET
        # --------------------------------

        if df.empty:
            st.warning("Uploaded CSV file is empty.")
            st.stop()

        # --------------------------------
        # ORIGINAL DATA
        # --------------------------------

        st.subheader("Original Dataset")
        st.dataframe(df)

        # --------------------------------
        # DATASET INFO
        # --------------------------------

        st.subheader("Dataset Information")

        col1, col2 = st.columns(2)

        col1.metric("Rows", df.shape[0])
        col2.metric("Columns", df.shape[1])

        st.write("### Column Names")
        st.write(df.columns.tolist())

        # --------------------------------
        # MISSING VALUES
        # --------------------------------

        st.subheader("Missing Values")

        missing_values = df.isnull().sum()

        st.dataframe(missing_values)

        # --------------------------------
        # CLEANING PROCESS
        # --------------------------------

        cleaned_df = df.copy()

        # -----------------------------
        # 1. Remove Duplicates
        # -----------------------------

        duplicates = cleaned_df.duplicated().sum()

        cleaned_df = cleaned_df.drop_duplicates()

        # -----------------------------
        # 2. Clean Column Names
        # -----------------------------

        cleaned_df.columns = (
            cleaned_df.columns
            .str.strip()
            .str.lower()
        )

        # -----------------------------
        # 3. Handle Missing Values
        # -----------------------------

        for column in cleaned_df.columns:

            # Numeric columns
            if pd.api.types.is_numeric_dtype(
                cleaned_df[column]
            ):

                cleaned_df[column] = cleaned_df[column].fillna(
                    cleaned_df[column].median()
                )

            # Text columns
            else:

                cleaned_df[column] = cleaned_df[column].fillna(
                    "Unknown"
                )

        # -----------------------------
        # 4. Standardize Text Columns
        # -----------------------------

        text_cols = cleaned_df.select_dtypes(
            include='object'
        ).columns

        for col in text_cols:

            cleaned_df[col] = (
                cleaned_df[col]
                .astype(str)
                .str.strip()
                .str.upper()
            )

        # -----------------------------
        # 5. Remove Outliers (IQR)
        # -----------------------------

        numeric_cols = cleaned_df.select_dtypes(
            include=np.number
        ).columns

        for col in numeric_cols:

            Q1 = cleaned_df[col].quantile(0.25)
            Q3 = cleaned_df[col].quantile(0.75)

            IQR = Q3 - Q1

            lower = Q1 - 1.5 * IQR
            upper = Q3 + 1.5 * IQR

            cleaned_df = cleaned_df[
                (cleaned_df[col] >= lower) &
                (cleaned_df[col] <= upper)
            ]

        # --------------------------------
        # CLEANED DATA
        # --------------------------------

        st.subheader("Cleaned Dataset")

        st.dataframe(cleaned_df)

        # --------------------------------
        # CLEANING REPORT
        # --------------------------------

        st.subheader("Cleaning Report")

        st.success(
            f"Removed Duplicates: {duplicates}"
        )

        st.success(
            f"Final Rows After Cleaning: {cleaned_df.shape[0]}"
        )

        # --------------------------------
        # DATA STATISTICS
        # --------------------------------

        st.subheader("Dataset Statistics")

        st.dataframe(cleaned_df.describe())

        # --------------------------------
        # DOWNLOAD CLEANED DATA
        # --------------------------------

        csv = cleaned_df.to_csv(
            index=False
        ).encode('utf-8')

        st.download_button(
            label="Download Cleaned Dataset",
            data=csv,
            file_name="cleaned_dataset.csv",
            mime="text/csv"
        )

    # --------------------------------
    # ERROR MESSAGES
    # --------------------------------

    except pd.errors.EmptyDataError:

        st.error(
            "The uploaded CSV file is empty."
        )

    except pd.errors.ParserError:

        st.error(
            "Error parsing CSV file. "
            "Please upload a valid CSV."
        )

    except UnicodeDecodeError:

        st.error(
            "Encoding error. "
            "Try saving the CSV as UTF-8."
        )

    except Exception as e:

        st.error(
            f"Unexpected Error: {e}"
        )
