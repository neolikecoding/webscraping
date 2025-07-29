import pandas as pd


def read_csv_list(filename):
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip()]

townnames = read_csv_list("townnames.csv")

for town in townnames:
    input_file = f"{town}.csv"
    output_file = f"{town}_grouped.csv"
    try:
        df = pd.read_csv(input_file)
    except FileNotFoundError:
        print(f"File not found: {input_file}")
        continue
    # Remove leading/trailing whitespace from column names
    df.columns = df.columns.str.strip()
    # Remove rows where 'View Doc' == 'View Doc' and 'Doc Number' == 'Doc Number'
    df = df[~((df['View Doc'] == 'View Doc') & (df['Doc Number'] == 'Doc Number'))]
    # Ensure 'Doc Recorded' is parsed as datetime
    df['Doc Recorded'] = pd.to_datetime(df['Doc Recorded'], errors='coerce')
    # Group by '1st PIN' and get the index of the max 'Doc Recorded' in each group
    idx = df.groupby('1st PIN')['Doc Recorded'].idxmax()
    # Select those rows
    result = df.loc[idx]
    # Write to a new CSV file
    result.to_csv(output_file, index=False)
    print(f"Processed and saved: {output_file}")