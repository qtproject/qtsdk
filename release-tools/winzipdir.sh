#!/bin/sh
# Copyright (C) 2013 Digia Plc and/or its subsidiary(-ies).
# Contact: http://www.qt-project.org/legal
#
# You may use this file under the terms of the 3-clause BSD license.
# See the file LICENSE from this package for details.
#
#
#
# Script for generating a zip file with windows line endings for text file
#

USAGE="Usage: `basename $0` zipfile dir"

if [ $# -ne 2 ]; then
    echo $USAGE >&2
    exit 1
fi

zipfile=$1
dir=$2

# Make sure intermediate files are removed on exit
trap "rm -f __txtpattern __packagedfiles __filetypes >/dev/null 2>&1" 0
trap "exit 2" 1 2  3 13 15

echo ".*:.*ASCII
.*:.*directory
.*:.*empty
.*:.*POSIX
.*:.*html
.*:.*text" > __txtpattern || exit 1

# list all files
find $dir > __packagedfiles || exit 1
# record file types
file -f __packagedfiles > __filetypes || exit 1
# zip text files and binary files separately
cat __filetypes | grep -f __txtpattern -v | cut -d: -f1 | zip -9 -q $zipfile -@ || exit 1
cat __filetypes | grep -f __txtpattern | cut -d: -f1 | zip -9 -q --to-crlf $zipfile -@ || exit 1
