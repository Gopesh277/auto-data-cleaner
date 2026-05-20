# 📊 Automatic Data Cleaning System

A Streamlit-based web application that automatically cleans uploaded CSV datasets by handling missing values, removing duplicates, standardizing text, and detecting outliers. It also provides dataset insights and allows users to download the cleaned data.

---

## 🚀 Features

- 📁 Upload CSV files easily
- 🧹 Automatic data cleaning pipeline:
  - Remove duplicate rows
  - Handle missing values (median for numeric, "Unknown" for text)
  - Standardize column names (lowercase & trimmed)
  - Clean and format text columns
  - Detect and remove outliers using IQR method
- 📊 Dataset overview:
  - Shape (rows & columns)
  - Column names
  - Missing values report
  - Statistical summary
- 📥 Download cleaned dataset as CSV
- ⚠️ Error handling for invalid or corrupted files

---

## 🧠 Tech Stack

- Streamlit – Web application framework  
- Pandas – Data manipulation and analysis  
- NumPy – Numerical computations  

---

## 📂 Project Structure
auto-data-cleaner/
|
|-----app.py
|-----datasets/
      |------.csv
|-----README.md
 
