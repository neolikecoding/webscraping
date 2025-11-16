#!/usr/bin/env python3
"""
Combine all `WheelingMtProspect` split .xlsx files in `Data/` into a single workbook.

Behavior:
- Scans `Data/` for filenames containing `WheelingMtProspect` and `__` (e.g. `WheelingMtProspectPocket__MP-01.xlsx`).
- For each file, reads sheet named `sheet1` (falls back to `Sheet1` if necessary).
- Extracts the text between `__` and `.xlsx` and writes it into a new column `Folder Name` for each row.
- Also adds `Source File` column with the original filename.
- Concatenates all rows and writes `Data/WheelingMtProspect_combined.xlsx` with sheet name `combined`.

Usage: python3 scripts/combine_wheeling.py

Requires: pandas, openpyxl
"""
from pathlib import Path
import re
import sys

try:
    import pandas as pd
except Exception:
    print("Missing dependency: pandas (and openpyxl). Install with: pip install pandas openpyxl")
    raise

DATA_DIR = Path('Data')


def default_out_file(base: str) -> Path:
    return DATA_DIR / f"{base}_combined.xlsx"

def find_files(base: str = 'WheelingMtProspect'):
    if not DATA_DIR.exists():
        print('Data directory not found:', DATA_DIR)
        return []
    # Prioritize files in the `Data/<base>/` subfolder if it exists
    subdir = DATA_DIR / base
    if subdir.exists() and subdir.is_dir():
        files = [p for p in subdir.iterdir() if p.is_file() and '__' in p.name and p.suffix.lower() in ('.xlsx', '.xlsm', '.xltx')]
        files.sort()
        return files

    # fallback: look in Data/ for files containing the base name
    files = [p for p in DATA_DIR.iterdir() if p.is_file() and base in p.name and '__' in p.name and p.suffix.lower() in ('.xlsx', '.xlsm', '.xltx')]
    files.sort()
    return files


def extract_folder_token(fname: str) -> str:
    m = re.search(r'__(.+?)\.', fname)
    if m:
        return m.group(1)
    # fallback: last token after first '__'
    parts = fname.split('__', 1)
    return parts[1].rsplit('.',1)[0] if len(parts) > 1 else ''


def read_sheet(p: Path):
    # try lower-case sheet name first, then Title-case
    for sname in ('sheet1', 'Sheet1'):
        try:
            df = pd.read_excel(p, sheet_name=sname, engine='openpyxl')
            return df
        except Exception:
            continue
    # fallback: read first sheet
    try:
        df = pd.read_excel(p, engine='openpyxl')
        return df
    except Exception as e:
        raise


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description='Combine split Excel files for a given base name')
    parser.add_argument('--base', '-b', default='WheelingMtProspect', help='Base name to match (default: WheelingMtProspect)')
    parser.add_argument('--out', '-o', help='Output file path (optional). If not set, uses Data/<base>_combined.xlsx')
    args = parser.parse_args(argv)

    base = args.base
    out_file = Path(args.out) if args.out else default_out_file(base)

    files = find_files(base)
    if not files:
        print(f'No matching files found for base "{base}" in {DATA_DIR} or {DATA_DIR / base}')
        return 2

    frames = []
    summary = []
    for p in files:
        try:
            df = read_sheet(p)
        except Exception as e:
            print(f'Failed to read {p}: {e}')
            continue
        # Identify columns whose header is a date (e.g. '2025-10-11' or '2025-10-11 00:00:00')
        date_cols = []
        for col in df.columns:
            try:
                # pandas.to_datetime will return NaT for non-date-like strings
                parsed = pd.to_datetime(col, errors='coerce')
                if not pd.isna(parsed):
                    date_cols.append(col)
            except Exception:
                continue

        if date_cols:
            # consolidate non-empty values from all date columns into one 'Activity' column
            def consolidate_activity(row):
                parts = []
                for c in date_cols:
                    v = row.get(c)
                    if pd.isna(v):
                        continue
                    s = str(v).strip()
                    if s == '' or s.lower() in ('nan', 'none'):
                        continue
                    parts.append(s)
                return '; '.join(parts) if parts else ''

            df['Activity'] = df.apply(consolidate_activity, axis=1)
            # drop the original date columns
            df = df.drop(columns=date_cols, errors='ignore')
            print(f'  Consolidated date columns {date_cols} into Activity')
        token = extract_folder_token(p.name)
        df['Folder Name'] = token
        df['Source File'] = p.name
        frames.append(df)
        summary.append((p.name, token, len(df)))
        print(f'Read {p.name}: sheet rows={len(df)}, folder={token}')

    if not frames:
        print('No data frames read successfully.')
        return 1

    combined = pd.concat(frames, ignore_index=True, sort=False)

    # write to excel
    try:
        combined.to_excel(out_file, index=False, sheet_name='combined', engine='openpyxl')
        print(f'Wrote combined file: {out_file} ({len(combined)} rows)')
    except Exception as e:
        print('Failed to write combined file:', e)
        return 1

    # print preview
    with pd.option_context('display.max_rows', 10, 'display.max_columns', 8, 'display.width', 160):
        print('\nPreview:')
        print(combined.head(10).to_string(index=False))

    # small manifest
    print('\nManifest:')
    for name, token, rows in summary:
        print(f'  {name} -> {token} ({rows} rows)')

    return 0


if __name__ == '__main__':
    import sys
    raise SystemExit(main(sys.argv[1:]))
