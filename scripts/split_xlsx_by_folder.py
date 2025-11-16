#!/usr/bin/env python3
"""
Split Excel files by the "Folder Name" column.

Usage:
  python scripts/split_xlsx_by_folder.py [files...]

If no files are passed, the script will look for PalatinePocket.xlsx and WheelingMtProspectPocket.xlsx
in the current directory and in the Data/ directory.

Outputs files named: <original_stem>_<sanitized_folder_name>.xlsx

Requires: pandas, openpyxl
"""
import sys
from pathlib import Path
import re

DEFAULT_FILES = ['DesplainesPocket.xlsx']


def sanitize_name(name: str) -> str:
    if name is None:
        return 'UNKNOWN'
    s = str(name)
    s = s.strip()
    if s == '':
        return 'EMPTY'
    # replace any filesystem-unfriendly chars
    s = re.sub(r"[\\/\:\*\?\"<>\|]", "_", s)
    s = re.sub(r"\s+", "_", s)
    # limit length
    return s[:120]


def find_files(candidates):
    found = []
    cwd = Path.cwd()
    data_dir = cwd / 'Data'
    for c in candidates:
        p = cwd / c
        if p.exists():
            found.append(p)
            continue
        p2 = data_dir / c
        if p2.exists():
            found.append(p2)
            continue
    return found


def split_file(path: Path):
    print(f"Processing {path}")
    try:
        import pandas as pd
    except Exception as e:
        print("Missing dependency: pandas (and openpyxl). Install with: pip install pandas openpyxl")
        return False

    try:
        df = pd.read_excel(path, engine='openpyxl')
    except Exception as e:
        print(f"Failed to read {path}: {e}")
        return False

    # locate the actual 'Folder Name' column case-insensitively
    folder_col = None
    for c in df.columns:
        if str(c).strip().lower() == 'folder name':
            folder_col = c
            break
    if folder_col is None:
        print(f"No 'Folder Name' column found in {path}; available columns: {list(df.columns)}")
        return False

    # find address component columns (case-insensitive candidates)
    def find_col(candidates):
        for c in df.columns:
            if str(c).strip().lower() in candidates:
                return c
        return None

    addr_col = find_col({'address line 1', 'address1', 'address'})
    city_col = find_col({'city'})
    state_col = find_col({'state', 'st'})
    zip_col = find_col({'zip', 'zipcode', 'postalcode', 'postal'})

    # create combined Address column (skip empty parts)
    def make_address(row):
        parts = []
        for c in (addr_col, city_col, state_col, zip_col):
            if c is None:
                continue
            v = row.get(c)
            if pd.isna(v):
                continue
            s = str(v).strip()
            if s:
                parts.append(s)
        return ', '.join(parts)

    # build output columns order: keep original order but replace individual address cols with single 'Address', and drop Folder Name
    out_columns = []
    seen_addr_replaced = False
    for c in df.columns:
        if c == folder_col:
            continue
        if c in (addr_col, city_col, state_col, zip_col):
            # only add 'Address' once where the first address component appeared
            if not seen_addr_replaced:
                out_columns.append('Address')
                seen_addr_replaced = True
            # skip adding the individual component columns
            continue
        out_columns.append(c)

    # if none of the address component columns existed, still add Address as empty string
    if not seen_addr_replaced:
        out_columns = ['Address'] + list(out_columns)

    out_dir = path.parent
    stem = path.stem

    groups = df.groupby(df[folder_col].fillna('______NONE__'))
    created = 0
    for key, group in groups:
        folder_value = None if key == '______NONE__' else key
        safe = sanitize_name(folder_value) if folder_value is not None else 'NONE'
        out_name = f"{stem}_{safe}.xlsx"
        out_path = out_dir / out_name

        # prepare output DataFrame with combined Address and without Folder Name
        out_df = group.copy()
        try:
            out_df['Address'] = out_df.apply(make_address, axis=1)
        except Exception:
            # fallback: create Address column from available columns without apply
            out_df['Address'] = ''
            for idx, row in out_df.iterrows():
                out_df.at[idx, 'Address'] = make_address(row)

        # drop the now-unneeded address components and the folder column
        drop_cols = [c for c in (addr_col, city_col, state_col, zip_col) if c is not None]
        drop_cols = [c for c in drop_cols if c in out_df.columns]
        if folder_col in out_df.columns:
            drop_cols.append(folder_col)
        out_df = out_df.drop(columns=drop_cols, errors='ignore')

        # reorder columns to out_columns (but ensure all present)
        final_cols = [c for c in out_columns if c in out_df.columns]
        # if Address wasn't in final_cols (rare), prepend it
        if 'Address' not in final_cols:
            final_cols = ['Address'] + final_cols

        try:
            out_df.to_excel(out_path, index=False, columns=final_cols, engine='openpyxl')
            print(f"  Wrote {out_path} ({len(out_df)} rows)")
            created += 1
        except Exception as e:
            print(f"  Failed to write {out_path}: {e}")
    if created == 0:
        print(f"No groups created for {path}")
    return True


def main(argv):
    files = argv[1:]
    if not files:
        candidates = DEFAULT_FILES
    else:
        candidates = files

    found = find_files(candidates)
    if not found:
        print("No files found. Looked for:")
        for c in candidates:
            print(' ', c)
        print("Place the files in the current directory or the Data/ directory, or pass paths as arguments.")
        return 2

    ok = True
    for f in found:
        res = split_file(f)
        ok = ok and res

    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
