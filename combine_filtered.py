import pandas as pd

def read_csv_list(filename):
    with open(filename, "r") as f:
        return [line.strip() for line in f if line.strip()]

townnames = read_csv_list("townnames.csv")

frames = []
for town in townnames:
    input_file = f"Data/{town}_filtered.csv"
    try:
        df = pd.read_csv(input_file)
        df['Town'] = town  # Optionally add a column to identify the town
        frames.append(df)
    except FileNotFoundError:
        print(f"File not found: {input_file}")
        continue

if frames:
    combined = pd.concat(frames, ignore_index=True)
    combined.to_csv("Data/all_towns_combined.csv", index=False)
    print("Combined file saved as all_towns_combined.csv")
else:
    print("No files to combine.")
