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
    "--symlink_directory",
    "-l",
    default=None,
    type=str,
        help=(
        "Optional. Must be an absolute path if specified, creates a directory of sample sub-directories "
        "containing relative symlinks back to the original fastqs, and point the output sample sheet "
        "at those directories."
        "If omitted, no symlinks are made and the output sample sheet points at the "
        "original fastq directories."
    ),
)

args = parser.parse_args()

directory = args.directory
sample_sheet = args.sample_sheet
sheet_number = args.sheet_number
output_sheet = args.output_sheet
symlink_directory = args.symlink_directory


# Make sure we have a true, absolute path, not a symlink, and it exists
directory = str(Path(directory).resolve())
if not os.path.isdir(directory):
    sys.exit("\n=> ERROR: Specified directory does not exist.")


# check for single fastq_pass directory
pass_dirs = [p for p in Path(directory).rglob("fastq_pass") if p.is_dir()]

print(
    f"=> Found {len(pass_dirs)} 'fastq_pass' "
    f"director{'y' if len(pass_dirs) == 1 else 'ies'}"
    f"{':' if pass_dirs else ''}"
)
for p in pass_dirs:
    print(f"\t{p}")

if len(pass_dirs) != 1:
    sys.exit(
        "=> ERROR: expected exactly 1 'fastq_pass' directory in "
        f"'{directory}', found {len(pass_dirs)}. Please ensure the specified "
        "'directory' contains a single 'fastq_pass' sub-directory."
    )

# Set the fastq_pass directory within main directory
dir_pass = str(pass_dirs[0])


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
for c in ["barcode", "alias"]:
    if not c in df1.columns:
        sys.exit(f"=> ERROR: Sample sheet is missing column {c}")


# Validate sample IDs. They should start with 2-5 uppercase letters, then 2-5 numbers.
# Optionally, they may then have a "-" plus an alphanumeric suffix, but only lowercase
# letters. IDs should not contain any underscores or other special characters.
valid_id = re.compile("^[A-Z]{2,5}[0-9]{2,5}(?:-(?:[a-z]+|[0-9]+))?$")
bad_samples = []

for sample in df1["alias"]:
    if not valid_id.match(sample):
        bad_samples.append(sample)

if len(bad_samples) > 0:
    sys.exit(
        f"\n=> ERROR: found {len(bad_samples)} bad alias(es): {', '.join(bad_samples)}"
    )


# Only make symlinks if --symlink_directory was given.
# make the symlink parent directory (if necessary)
link_dir_parent = None
if symlink_directory is not None:
    link_dir_parent = os.path.abspath(symlink_directory)
    # link_dir_parent = Path(symlink_directory).resolve()
    os.makedirs(link_dir_parent, exist_ok=True)
    print(f"=> Will make symlinks in '{link_dir_parent}'")
else:
    print("=> No --symlink_directory specified: skipping symlinks")


print(f"=> Processing files for {len(df1)} samples")


# Directory holding each sample's fastqs, in the same order as the rows of df1.
# This is the symlink directory if linking, otherwise the original fastq directory.
data_paths = []

for sample, barcode in zip(df1["alias"], df1["barcode"]):
    # find all the fastqs within the original sample data directory
    # if data directory contains folder for alias, use it, otherwise, get the corresponding barcode
    alias_dir = os.path.join(dir_pass, sample)
    src_dir = alias_dir if os.path.isdir(alias_dir) else os.path.join(dir_pass, barcode)
    files = natsorted(glob.glob(os.path.join(src_dir, "*.fastq.gz")))
    print(f"Found {len(files)} files for {sample}: \n{files}")
    if not files:
        print(f"=> WARNING: no .fastq.gz files found for {sample} in {src_dir}")
 
    # not linking: the sample sheet will point straight at the original directory
    if link_dir_parent is None:
        data_paths.append(src_dir)
        continue
 
    # create the sample directory within the symlink parent directory (if necessary)
    link_dir_sample = os.path.join(link_dir_parent, sample)
    os.makedirs(link_dir_sample, exist_ok=True)
 
    # relative link targets are resolved from the link's own directory
    link_start = os.path.realpath(link_dir_sample)
    for file in files:
        try:
            os.symlink(
                src=os.path.relpath(os.path.abspath(file), start=link_start),
                dst=os.path.join(link_dir_sample, os.path.basename(file)),
            )
            print(f"Linked {os.path.basename(file)} for {sample}")
        except FileExistsError:
            continue
 
    data_paths.append(link_dir_sample)
 
if link_dir_parent is not None:
    print(f"Finished making symlink directories in {link_dir_parent}")


# Create new sample sheet for input to AssembLEE
print(f"=> Saving new sample sheet to '{output_sheet}'")
df2 = df1[["alias"]].copy()
df2["data_path"] = [p.rstrip("/") + "/" for p in data_paths]
df2 = df2.sort_values("alias", kind="stable")
df2.to_csv(os.path.join(output_sheet), header=False, index=False)
print("=> Done!")
