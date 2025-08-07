import pandas as pd


def read_csv_list(filename):
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip()]

lastname_filter = set(read_csv_list("lastnames_new.csv"))

townnames = read_csv_list("townnames.csv")

for town in townnames:
    input_file = f"Data/{town}.csv"
    output_file = f"Data/{town}_filtered.csv"
    try:
        df = pd.read_csv(input_file)
    except FileNotFoundError:
        print(f"File not found: {input_file}")
        continue
    # Remove leading/trailing whitespace from column names
    df.columns = df.columns.str.strip()
    # Remove rows where 'View Doc' == 'View Doc' and 'Doc Number' == 'Doc Number'
    df = df[~((df['View Doc'] == 'View Doc') & (df['Doc Number'] == 'Doc Number'))]
    # Filter rows where any part of lastname_filter is in 1st Grantor or 1st Grantee
    def get_matching_name(row):
        grantor = str(row['1st Grantor']).lower()
        grantee = str(row['1st Grantee']).lower()
        for name in lastname_filter:
            lname = name.lower()
            if lname in grantor or lname in grantee:
                return name
        return ''

    mask = (
        df['1st Grantor'].apply(lambda x: any(name.lower() in str(x).lower() for name in lastname_filter)) |
        df['1st Grantee'].apply(lambda x: any(name.lower() in str(x).lower() for name in lastname_filter))
    )
    filtered = df[mask].copy()
    filtered['Matched Lastname'] = filtered.apply(get_matching_name, axis=1)
    filtered.to_csv(output_file, index=False)
    print(f"Filtered and saved: {output_file}")