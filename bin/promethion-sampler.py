#!/usr/bin/env python3
import argparse
import glob
import os
import re
import sys
from pathlib import Path

import pandas as pd
from natsort import natsorted

parser = argparse.ArgumentParser(
    description="Part of the NOVA pipeline: organize Nanopore data and create a sample sheet for genome assembly."
)

parser.add_argument(
    "--directory",
    "-d",
    type=str,
    required=True,
    help="Path to directory for the sequencing run. Must contain the sub-directories 'fastq_pass' and 'fastq_fail'.",
)

parser.add_argument(
    "--sample_sheet",
    "-s",
    type=str,
    required=True,
    help="Path and name for the sample sheet (CSV or XLSX).",
)

parser.add_argument(
    "--sheet_number",
    "-n",
    default=1,
    type=int,
    help="Sheet number for XLSX files (default: first sheet, 1).",
)

parser.add_argument(
    "--output_sheet",
    "-o",
    type=str,
    required=True,
    help="Path and name for the output CSV sample sheet.",
)

parser.add_argument(
    "--output_dir_pass",
    "-p",
    default="fastq_pass_link",
    type=str,
    help="Directory of links between sample IDs and corresponding barcode directories. Can be an absolute or relative path; in the latter case, it will start inside the provided run directory. Defaults to 'fastq_pass_link'.",
)

parser.add_argument(
    "--output_dir_fail",
    "-f",
    default="fastq_fail_link",
    type=str,
    help="Directory of links between sample IDs and corresponding barcode directories. Can be an absolute or relative path; in the latter case, it will start inside the provided run directory. Defaults to 'fastq_fail_link'.",
)

args = parser.parse_args()

directory = args.directory
sample_sheet = args.sample_sheet
sheet_number = args.sheet_number
output_sheet = args.output_sheet
output_dir_pass = args.output_dir_pass
output_dir_fail = args.output_dir_fail


# Make sure we have a true, absolute path, not a symlink, and it exists
directory = str(Path(directory).resolve())
if not os.path.isdir(directory):
    sys.exit("\n=> ERROR: Specified directory does not exist.")


# Setup input directories within main directory
dir_pass = os.path.abspath(os.path.join(directory, "fastq_pass"))
dir_fail = os.path.abspath(os.path.join(directory, "fastq_fail"))

if Path.is_absolute(Path(output_dir_pass)):
    dir_pass_link = Path(output_dir_pass)
else:
    dir_pass_link = os.path.abspath(os.path.join(directory, output_dir_pass))

if Path.is_absolute(Path(output_dir_fail)):
    dir_fail_link = Path(output_dir_fail)
else:
    dir_fail_link = os.path.abspath(os.path.join(directory, output_dir_fail))


# Check that target directory contains only one "fastq_pass" and one "fastq_fail" folder
target_dirs = ["fastq_pass", "fastq_fail"]
found_dirs = {name: list(Path(directory).rglob(name)) for name in target_dirs}
for name, paths in found_dirs.items():
    if len(paths) == 0:
        print(f"=> Found 0 '{name}' directories")
    else:
        print(
            f"=> Found {len(paths)} '{name}' director{'y' if len(paths) == 1 else 'ies'}:"
        )
        for p in paths:
            print(f"\t{p}")


# Check for presence of multiple fastq_fail and fastq_pass directories
multiples_found = any(len(paths) > 1 for paths in found_dirs.values())
if multiples_found:
    sys.exit(
        "=> ERROR: multiple 'fastq_fail' or 'fastq_pass' directories were found. ",
        "Please ensure specified 'directory' contains a single 'fastq_pass' and ",
        "'fastq_fail' sub-directory.",
    )


# Check file extension and read sample sheet
ext = sample_sheet.rsplit(".", 1)[-1].lower()
if ext == "xlsx":
    df1 = pd.read_excel(os.path.join(sample_sheet), sheet_name=sheet_number - 1)
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
    sys.exit(
        f"\n=> ERROR: found {len(bad_samples)} bad sample ID(s): {', '.join(bad_samples)}"
    )


# Create directories to hold the symlinks
unique_samples = df1["sample_id"].unique()
print(
    f"=> Processing files for {len(unique_samples)} samples and {len(df1['barcode'].unique())} barcodes"
)

# Use a dictionary to loop over the directories we want to process
dirs_to_process = {dir_pass: dir_pass_link, dir_fail: dir_fail_link}

for old_dir, new_dir in dirs_to_process.items():
    if os.path.isdir(old_dir):
        # Use os.makedirs() because it supports recursive creation
        # Only make the "link" directories if the corresponding original directory exists
        os.makedirs(new_dir, exist_ok=True)
        for sample in unique_samples:
            os.makedirs(os.path.join(new_dir, sample), exist_ok=True)
            barcodes = df1[df1["sample_id"] == sample]["barcode"]
            for barcode in barcodes:    
                files = natsorted(
                    glob.glob(os.path.join(old_dir, barcode, "*.fastq.gz"))
                )
                for file in files:
                    try:
                        os.symlink(
                            src=os.path.join(old_dir, file),
                            dst=os.path.join(
                                new_dir,
                                sample,
                                f"{sample}_{os.path.basename(file)}",
                            ),
                        )
                    except FileExistsError:
                        continue


# Create new sample sheet for input to Samnsero
print(f"=> Saving new sample sheet to '{output_sheet}'")
df2 = df1.copy()[["sample_id"]]
df2["data_path"] = dir_pass_link + "/" + df2["sample_id"] + "/"
df2.to_csv(os.path.join(output_sheet), header=False, index=False)
print("=> Done!")
