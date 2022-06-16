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

"""Convert the output of libclang when running with LIBCLANG_TIMING=1 to csv data.

Only the wall clock time value is extracted.

Use this converter together with /usr/bin/paste to create whole csv tables.

Usage: ./$0 <log-file of libclang output>"""

import getopt
import os
import re
import sys

def constructRecordMatcher():
    regex = '( Parsing)' \
          + '|( Precompiling preamble)' \
          + '|( Reparsing)' \
          + '|( Cache global code completions)' \
          + '|( Code completion)'

    return re.compile(regex)

def constructTimeNeededMatcher():
    # An output line looks like:
    #   :   2.5625 (100.0%)   0.1563 (100.0%)   2.7188 (100.0%)   2.7813 (100.0%)
    # Note: There is always at least the wall clock time at the utmost right,
    #       the others in front (up to 3) are optional.
    startIndicator = r'\s*:'
    notRelevantParts =  r'(\s*\d+\.\d+ \(\d+\.\d+\%\)){0,3}'
    wallClockTime = r'\s*(\d+\.\d+) \(\d+\.\d+\%\)'

    regex = startIndicator \
          + notRelevantParts \
          + wallClockTime

    return re.compile(regex)

def csvLine(values):
    return ','.join(values) + '\n'

def extractRecords(fileContent):
    recordMatcher = constructRecordMatcher()
    timeNeededMatcher = constructTimeNeededMatcher()

    records = []
    previousTimeMatchEnd = -1

    for recordStartMatch in recordMatcher.finditer(fileContent):
        timeNeededInMs = False
        if previousTimeMatchEnd >= recordStartMatch.start():
            # Ops, we've detected a missing time record.
            previousRecord = records[-1]
            records[-1] = [previousRecord[0], '-1']
            timeNeededInMs = previousRecord[1]

        if not timeNeededInMs:
            timeMatch = next(timeNeededMatcher.finditer(fileContent, recordStartMatch.end()))
            previousTimeMatchEnd = timeMatch.end()
            timeNeededInMs = timeMatch.group(2)

        recordId = recordStartMatch.group().strip()
        record = [recordId, timeNeededInMs]
        records.append(record)

    # for record in records: print record
    return records

def recordsToString(records):
    string = ""
    for record in records:
        string += csvLine(record)

    return string

def convert(inputFile, columnLabel = None):
    if not columnLabel:
        columnLabel = os.path.basename(inputFile)
    fileContent = open(inputFile, 'r').read()

    records = [[columnLabel, columnLabel]] + extractRecords(fileContent)

    return recordsToString(records)

def printUsageAndExit():
    print(__doc__)
    sys.exit(0)

def main():
    # parse command line options
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])
    except getopt.error as msg:
        print(msg)
        print("for help use --help")
        sys.exit(2)

    # process options
    for o, a in opts:
        if o in ("-h", "--help"):
            printUsageAndExit()

    # process arguments
    if not args:
        printUsageAndExit()
    for arg in args:
        print(convert(arg))

if __name__ == "__main__":
    main()

