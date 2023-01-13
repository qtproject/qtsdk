#!/usr/bin/env python3
# -*- coding: utf-8 -*-

############################################################################
#
# Copyright (C) 2023 The Qt Company Ltd.
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

"""Convert the output of libclang when running with LIBCLANG_TIMING=1 to csv data.

Only the wall clock time value is extracted.

Use this converter together with /usr/bin/paste to create whole csv tables.

Usage: ./$0 <log-file of libclang output>"""

import getopt
import re
import sys
from pathlib import Path
from typing import List, Pattern


def construct_record_matcher() -> Pattern[str]:
    regex = (
        '( Parsing)'
        + '|( Precompiling preamble)'
        + '|( Reparsing)'
        + '|( Cache global code completions)'
        + '|( Code completion)'
    )

    return re.compile(regex)


def construct_time_needed_matcher() -> Pattern[str]:
    # An output line looks like:
    #   :   2.5625 (100.0%)   0.1563 (100.0%)   2.7188 (100.0%)   2.7813 (100.0%)
    # Note: There is always at least the wall clock time at the utmost right,
    #       the others in front (up to 3) are optional.
    start_indicator = r'\s*:'
    not_relevant_parts = r'(\s*\d+\.\d+ \(\d+\.\d+\%\)){0,3}'
    wall_clock_time = r'\s*(\d+\.\d+) \(\d+\.\d+\%\)'

    regex = start_indicator + not_relevant_parts + wall_clock_time

    return re.compile(regex)


def csv_line(values: List[str]) -> str:
    return ",".join(values) + "\n"


def extract_records(file_content: str) -> List[List[str]]:
    record_matcher = construct_record_matcher()
    time_needed_matcher = construct_time_needed_matcher()

    records: List[List[str]] = []
    previous_time_match_end = -1

    for record_start_match in record_matcher.finditer(file_content):
        time_needed_in_ms = ""
        if previous_time_match_end >= record_start_match.start():
            # Ops, we've detected a missing time record.
            previous_record = records[-1]
            records[-1] = [previous_record[0], '-1']
            time_needed_in_ms = previous_record[1]

        if not time_needed_in_ms:
            time_match = next(time_needed_matcher.finditer(file_content, record_start_match.end()))
            previous_time_match_end = time_match.end()
            time_needed_in_ms = time_match.group(2)

        record_id = record_start_match.group().strip()
        record = [record_id, time_needed_in_ms]
        records.append(record)

    # for record in records: print record
    return records


def records_to_string(records: List[List[str]]) -> str:
    string = ""
    for record in records:
        string += csv_line(record)

    return string


def convert(input_file: str, column_label: str = "") -> str:
    if not column_label:
        column_label = Path(input_file).name
    with open(input_file, 'r', encoding="utf-8") as file_content:
        records = [[column_label, column_label]] + extract_records(file_content.read())

    return records_to_string(records)


def print_usage_and_exit() -> None:
    print(__doc__)
    raise SystemExit(0)


def main() -> None:
    # parse command line options
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])
    except getopt.error as msg:
        raise SystemExit("for help use --help") from msg

    # process options
    for opt, _ in opts:
        if opt in ("-h", "--help"):
            print_usage_and_exit()

    # process arguments
    if not args:
        print_usage_and_exit()
    for arg in args:
        print(convert(arg))


if __name__ == "__main__":
    main()
