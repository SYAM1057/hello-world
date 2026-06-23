import pandas as pd
import glob
import os

# Load a single CSV and save to Excel
#csv_file = "path/to/your/file.csv"
csv_file = "D:\\SYAM\\Courses\\Practice_files\\part1_sample_data_10000_rows.csv"
df = pd.read_csv(csv_file)
df.to_excel("D:\\SYAM\\Courses\\Practice_files\\output_excel.xlsx", index=False, sheet_name="Data")

# Or load multiple CSVs into separate sheets in one Excel file
output_file = "D:\\SYAM\\Courses\\Practice_files\\combined_data.xlsx"
#csv_files = glob.glob("path/to/csv_files/*.csv")
csv_files = glob.glob("D:\\SYAM\\Courses\\Practice_files\\*.csv")

with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        sheet_name = os.path.basename(csv_file).replace('.csv', '')[:31]  # Excel sheet names limited to 31 chars
        df.to_excel(writer, sheet_name=sheet_name, index=False)

print(f"Data saved to {output_file}")