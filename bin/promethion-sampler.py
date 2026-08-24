#!/usr/bin/env python3
import argparse
import glob
import os
import re
import sys
from pathlib import Path

import pandas as pd
from natsort import natsorted

parser = argparse.ArgumentParser(description="Parameters")

parser.add_argument(
    "--directory",
    "-d",
    type=str,
    required=True,
    help="Path to directory for the sequencing run. Must contain the sub-directory 'fastq_pass'.",
)

parser.add_argument(
    "--sample_sheet",
    "-s",
    type=str,
    required=True,
    help="Path and name for the sample sheet (CSV or XLSX)",
)

parser.add_argument(
    "--sheet_number",
    "-n",
    default=1,
    type=int,
    help="Sheet number for XLSX files (default: first sheet, 1)",
)

parser.add_argument(
    "--output_sheet",
    "-o",
    type=str,
    required=True,
    help="Path and name for the output CSV sample sheet",
)

args = parser.parse_args()

directory = args.directory
sample_sheet = args.sample_sheet
sheet_number = args.sheet_number
output_sheet = args.output_sheet


# Make sure we have a true, absolute path, not a symlink
directory = str(Path(directory).resolve())

dir_pass = os.path.abspath(os.path.join(directory, "fastq_pass"))
dir_pass_link = os.path.abspath(os.path.join(directory, "fastq_pass_link"))

dir_fail = os.path.abspath(os.path.join(directory, "fastq_fail"))
dir_fail_link = os.path.abspath(os.path.join(directory, "fastq_fail_link"))


# Check if specified directory exists
if not os.path.isdir(directory):
    sys.exit("\n=> ERROR: Specified directory does not exist.")


# Check that target directory contains only one "fastq_pass" and one "fastq_fail" folder
target_dirs = ["fastq_pass", "fastq_fail"]
found_dirs = {name: list(Path(directory).rglob(name)) for name in target_dirs}
for name, paths in found_dirs.items():
    print(f"=> Found {len(paths)} '{name}' director{'y' if len(paths) == 1 else 'ies'}:")
    for p in paths:
        print(f"\t{p}")


# Check for presence of multiple fastq_fail and fastq_pass directories
multiples_found = any(len(paths) > 1 for paths in found_dirs.values())
if multiples_found:
    sys.exit(
        "=> ERROR: multiple 'fastq_fail' or 'fastq_pass' directories were found. ",
        "Please ensure specified 'directory' contains a single 'fastq_pass' and ",
        "'fastq_fail' sub-directory."
    )


# Check file extension and read sample sheet
ext = sample_sheet.rsplit(".", 1)[-1].lower()
if ext == "xlsx":
    df1 = pd.read_excel(os.path.join(sample_sheet), sheet_name=sheet_number-1)
elif ext == "csv":
    df1 = pd.read_csv(os.path.join(sample_sheet))
else:
    sys.exit(
        f"=> ERROR: Unsupported file format '.{ext}'. Please provide a '.csv' or '.xlsx' file."
    )


# Check for column names
for c in ["sample_id", "barcode"]:
    if not c in df1.columns:
        sys.exit(f"=> ERROR: Sample sheet is missing column {c}")


# Validate sample IDs. They should start with 2-5 uppercase letters, then 2-5 numbers.
# Optionally, they may then have a "-" plus an alphanumeric suffix, but only lowercase
# letters. IDs should not contain any underscores or other special characters.
valid_id = re.compile("^[A-Z]{2,5}[0-9]{2,5}(?:-(?:[a-z]+|[0-9]+))?$")
bad_samples = []

for sample in df1["sample_id"]:
    if not valid_id.match(sample):
        bad_samples.append(sample)

if len(bad_samples) > 0:
    sys.exit(f"\n=> ERROR: found {len(bad_samples)} bad sample ID(s): {', '.join(bad_samples)}")


# Rename directories and files
print(f"=> Creating {df1.shape[0]} linked directories")

os.mkdir(dir_pass_link)
os.mkdir(dir_fail_link)

for index, row in df1.iterrows():
    try:
        os.symlink(
            src=os.path.join(dir_pass, row["barcode"]),
            dst=os.path.join(dir_pass_link, row["sample_id"]),
        )
    except FileNotFoundError:
        print(f"=> ERROR: No directory '{row['barcode']}' was found in {dir_pass}, skipping")
    except OSError:
        print(f"=> ERROR: Link '{row['sample_id']}' already exists in {dir_pass}, skipping")

    try:
        os.symlink(
            src=os.path.join(dir_fail, row["barcode"]),
            dst=os.path.join(dir_fail_link, row["sample_id"]),
        )
    except FileNotFoundError:
        print(f"=> ERROR: No directory '{row['barcode']}' was found in {dir_fail}, skipping")
    except OSError:
        print(f"=> ERROR: Link '{row['sample_id']}' already exists in {dir_fail}, skipping")


# Create new sample sheet for input to Samnsero
print(f"=> Saving new sample sheet to '{output_sheet}'")
df2 = df1[["sample_id"]]
df2["data_path"] = dir_pass + "/" + df2["sample_id"] + "/"
df2.to_csv(os.path.join(output_sheet), header=False, index=False)
