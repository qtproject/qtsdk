#!/usr/bin/env python3
# -*- coding: utf-8 -*-

############################################################################
#
# Copyright (C) 2022 The Qt Company Ltd.
# Contact: https://www.qt.io/licensing/
#
# This file is part of Qt Creator.
#
# Commercial License Usage
# Licensees holding valid commercial Qt licenses may use this file in
# accordance with the commercial license agreement provided with the
# Software or, alternatively, in accordance with the terms contained in
# a written agreement between you and The Qt Company. For licensing terms
# and conditions see https://www.qt.io/terms-conditions. For further
# information use the contact form at https://www.qt.io/contact-us.
#
# GNU General Public License Usage
# Alternatively, this file may be used under the terms of the GNU
# General Public License version 3 as published by the Free Software
# Foundation with exceptions as appearing in the file LICENSE.GPL3-EXCEPT
# included in the packaging of this file. Please review the following
# information to ensure the GNU General Public License requirements will
# be met: https://www.gnu.org/licenses/gpl-3.0.html.
#
############################################################################


"""Merge given *.csv files

Usage: ./$0 <mergedFileName> <csvFile1> <csvFile2> ..."""

import csv
import getopt
import sys
from typing import List, Tuple


class Global:
    Delimiter = ','


class FileWithValues:
    def __init__(self, file_path: str, tag: str, values: List[List[str]]) -> None:
        self.file_path = file_path
        self.tag = tag
        self.values = values


def read_csv(file_path: str, delimiter: str) -> List[Tuple[str, str]]:
    lines = []
    with open(file_path, 'rt', encoding="utf-8") as handle:
        lines = handle.readlines()

    records = []
    for line in lines:
        identifier, value = line.split(delimiter)
        identifier = identifier.strip()
        value = value.strip()
        records.append((identifier, value))

    return records


def read_csv_files(file_paths: List[str]) -> List[FileWithValues]:
    files = []

    for file_path in file_paths:
        with open(file_path, 'rt', encoding="utf-8") as handle:
            reader = csv.reader(handle, delimiter=Global.Delimiter, quoting=csv.QUOTE_NONE)

        values = []
        for row in reader:
            values.append(row)

        tag = values[0][0]  # remember column label
        values = values[1:]  # skip header

        my_file = FileWithValues(file_path, tag, values)
        files.append(my_file)

    return files


def check_consistency(files: List[FileWithValues]) -> List[str]:
    reference_entry = files[0]
    reference_entry_size = len(reference_entry.values)
    reference_entry_identifiers = [v[0] for v in reference_entry.values]

    # Ensure same size of records
    for file in files:
        if not len(file.values) == reference_entry_size:
            raise SystemExit(f"Entry count mismatch: {reference_entry.file_path}, {file.file_path}")

    # Ensure same identifier on the left
    for file in files:
        identifiers = [v[0] for v in file.values]
        if not identifiers == reference_entry_identifiers:
            raise SystemExit(f"Column 1 id mismatch: {reference_entry.file_path}, {file.file_path}")

    return reference_entry_identifiers


def merge_files_helper(
    output_file_path: str, reference_identifiers: List[str], files: List[FileWithValues]
) -> None:
    with open(output_file_path, "wt", encoding="utf-8") as csvfile:
        delimiter = Global.Delimiter
        writer = csv.writer(csvfile, delimiter=delimiter, quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Write header row
        headers = ['action'] + [f.tag for f in files]
        writer.writerow(headers)

        # Write values
        columns = [[v[1] for v in f.values] for f in files]
        rows = list(zip(reference_identifiers, *columns))
        for row in rows:
            writer.writerow(row)


def merge_files(output_file_path: str, files_to_merge: List[str]) -> None:
    files = read_csv_files(files_to_merge)
    reference_identifiers = check_consistency(files)
    merge_files_helper(output_file_path, reference_identifiers, files)


def print_help_and_exit() -> None:
    print(__doc__)
    raise SystemExit(0)


def main() -> None:
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])
    except getopt.error as msg:
        raise SystemExit("for help use --help") from msg

    for opt, _ in opts:
        if opt in ("-h", "--help"):
            print_help_and_exit()
    if len(args) <= 2:
        print_help_and_exit()

    output_file = args[0]
    files_to_merge = args[1:]
    merge_files(output_file, files_to_merge)


if __name__ == "__main__":
    main()
