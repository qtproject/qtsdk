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


class Global:
    Delimiter = ','


class FileWithValues:
    def __init__(self, filePath, tag, values):
        self.filePath = filePath
        self.tag = tag
        self.values = values


def readCsv(filePath, delimiter):
    lines = []
    with open(filePath, 'rt') as f:
        lines = f.readlines()

    records = []
    for line in lines:
        identifier, value = line.split(delimiter)
        identifier = identifier.strip()
        value = value.strip()
        records.append((identifier, value))

    return records


def readCsvFiles(filePaths):
    files = []

    for filePath in filePaths:
        f = open(filePath, 'rt')
        reader = csv.reader(f, delimiter=Global.Delimiter, quoting=csv.QUOTE_NONE)

        values = []
        for row in reader:
            values.append(row)

        tag = values[0][0]  # remember column label
        values = values[1:]  # skip header

        myFile = FileWithValues(filePath, tag, values)
        files.append(myFile)

    return files


def checkConsistency(files):
    referenceEntry = files[0]
    referenceEntrySize = len(referenceEntry.values)
    referenceEntryIdentifiers = [v[0] for v in referenceEntry.values]

    # Ensure same size of records
    for f in files:
        if not len(f.values) == referenceEntrySize:
            print(f"error: number of entries mismatch between '{referenceEntry.filePath}' and '{f.filePath}'.", file=sys.stderr)
            sys.exit(1)

    # Ensure same identifier on the left
    for f in files:
        identifiers = [v[0] for v in f.values]
        if not identifiers == referenceEntryIdentifiers:
            print(f"error: mismatch between identifers in first column between '{referenceEntry.filePath}' and '{f.filePath}'.", file=sys.stderr)
            sys.exit(1)

    return referenceEntryIdentifiers


def mergeFilesHelper(outputFilePath, referenceIdentifiers, files):
    with open(outputFilePath, 'wt') as csvfile:
        writer = csv.writer(csvfile, delimiter=Global.Delimiter, quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Write header row
        headers = ['action'] + [f.tag for f in files]
        writer.writerow(headers)

        # Write values
        columns = [[v[1] for v in f.values] for f in files]
        rows = list(zip(referenceIdentifiers, *columns))
        for row in rows:
            writer.writerow(row)


def mergeFiles(outputFilePath, filesToMerge):
    files = readCsvFiles(filesToMerge)
    referenceIdentifiers = checkConsistency(files)
    mergeFilesHelper(outputFilePath, referenceIdentifiers, files)


def printHelpAndExit():
    print(__doc__)
    sys.exit(0)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h", ["help"])
    except getopt.error as msg:
        print(msg)
        print("for help use --help")
        sys.exit(2)

    for o, _ in opts:
        if o in ("-h", "--help"):
            printHelpAndExit()
    if len(args) <= 2:
        printHelpAndExit()

    outputFile = args[0]
    filesToMerge = args[1:]
    mergeFiles(outputFile, filesToMerge)


if __name__ == "__main__":
    main()
