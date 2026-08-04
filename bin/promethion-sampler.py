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
    help="Name of the sample sheet, inside the specified 'directory'",
)

parser.add_argument(
    "--sheet_name",
    "-n",
    default=0,
    help="Sheet name or index for XLSX files (default: first sheet)",
)

parser.add_argument(
    "--rename_files",
    "-r",
    action="store_true",
    help="If added/enabled, rename the fastq files to match sample names (default: disabled)",
)

args = parser.parse_args()

directory = args.directory
sample_sheet = args.sample_sheet
sheet_name = args.sheet_name
rename_files = args.rename_files

dir_pass = os.path.join(directory, "fastq_pass")
dir_fail = os.path.join(directory, "fastq_fail")


# Check if specified directory exists
if not os.path.isdir(directory):
    sys.exit("Specified directory does not exist.")

if not os.path.isdir(dir_pass):
    sys.exit("Specified directory does not contain sub-directory 'fastq_pass'.")


# Check that target directory contains only one "fastq_pass" and one "fastq_fail" folder
target_dirs = ["fastq_pass", "fastq_fail"]
found_dirs = {name: list(Path(directory).rglob(name)) for name in target_dirs}
for name, paths in found_dirs.items():
    print(f"Found {len(paths)} '{name}' director{'y' if len(paths) == 1 else 'ies'}:")
    for p in paths:
        print(f"\t{p}")

# Check for presence of multiple fastq_fail and fastq_pass directories
multiples_found = any(len(paths) > 1 for paths in found_dirs.values())
if multiples_found:
    sys.exit(
        "Aborting: multiple 'fastq_fail' or 'fastq_pass' directories were found. ",
        "Please ensure specified 'directory' contains only one 'fastq_pass' and one 'fastq_fail' directory.",
    )


# Check file extension and read sample sheet
ext = sample_sheet.rsplit(".", 1)[-1].lower()
if ext == "xlsx":
    df1 = pd.read_excel(os.path.join(directory, sample_sheet), sheet_name=sheet_name)
elif ext == "csv":
    df1 = pd.read_csv(os.path.join(directory, sample_sheet))
else:
    sys.exit(
        f"Unsupported file format: '.{ext}'. Please provide a '.csv' or '.xlsx' file."
    )


# Check for column names
for c in ["sample_id", "barcode"]:
    if not c in df1.columns:
        sys.exit(f"Sample sheet is missing column {c}")


# Validate sample IDs. They should start with 2-5 uppercase letters, then 2-5 numbers.
# Optionally, they may then have a "-" plus an alphanumeric suffix, but only lowercase
# letters. IDs should not contain any underscores or other special characters.
valid_id = re.compile("^[A-Z]{2,5}[0-9]{2,5}(?:-(?:[a-z]+|[0-9]+))?$")
bad_samples = []

for sample in df1["sample_id"]:
    if not valid_id.match(sample):
        bad_samples.append(sample)

# if len(bad_samples) > 0:
#     sys.exit(f"Found {len(bad_samples)} bad sample ID(s): {', '.join(bad_samples)}")


# Rename directories and files
print(f"Renaming {df1.shape[0]} sample directories")
for index, row in df1.iterrows():
    # Rename the directory containing the fastq files for each sample
    # print(f"\t{row['sample_id']}")

    try:
        os.rename(
            src=os.path.join(dir_pass, row["barcode"]),
            dst=os.path.join(dir_pass, row["sample_id"]),
        )
    except FileNotFoundError:
        print(f"No directory '{row['barcode']}' was found in {dir_pass}, skipping")
    except OSError:
        print(f"Directory '{row['sample_id']}' already exists in {dir_pass} and is non-empty, skipping")

    try:
        os.rename(
            src=os.path.join(dir_fail, row["barcode"]),
            dst=os.path.join(dir_fail, row["sample_id"]),
        )
    except FileNotFoundError:
        print(f"No directory '{row['barcode']}' was found in {dir_fail}, skipping")
    except OSError:
        print(f"Directory '{row['sample_id']}' already exists in {dir_fail} and is non-empty, skipping")

    # Find and rename the files within each directory
    if rename_files:
        files_pass = natsorted(
            glob.glob(os.path.join(dir_pass, row["sample_id"], "*.fastq.gz"))
        )
        for index, file in enumerate(files_pass):
            os.rename(
                src=os.path.join(dir_pass, file),
                dst=os.path.join(
                    dir_pass,
                    row["sample_id"],
                    "".join([row["sample_id"], "_", str(index), ".fastq.gz"]),
                ),
            )

        files_fail = natsorted(
            glob.glob(os.path.join(dir_fail, row["sample_id"], "*.fastq.gz"))
        )
        for index, file in enumerate(files_fail):
            os.rename(
                src=os.path.join(dir_fail, file),
                dst=os.path.join(
                    dir_fail,
                    row["sample_id"],
                    "".join([row["sample_id"], "_", str(index), ".fastq.gz"]),
                ),
            )


# Create new sample sheet for input to Samnsero
new_name = sample_sheet.replace("." + ext, "_samnsero.csv")
print(f"\nSaving new sample sheet to '{new_name}'")
df2 = df1[["sample_id"]]
df2["data_path"] = dir_pass + "/" + df2["sample_id"] + "/"
df2.to_csv(os.path.join(directory, new_name), header=False, index=False)
