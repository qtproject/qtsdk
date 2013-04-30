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

tmp_txtpattern=$(mktemp)
tmp_filetypes=$(mktemp)

# Make sure intermediate files are removed on exit
trap "rm -f $tmp_txtpattern $tmp_filetypes >/dev/null 2>&1" 0
trap "exit 2" 1 2 3 13 15

echo ".*:.*ASCII
.*:.*directory
.*:.*empty
.*:.*POSIX
.*:.*html
.*:.*text" > $tmp_txtpattern || exit 1

# list all files and record file types
find $dir -exec file {} \; > $tmp_filetypes || exit 1
# zip text files and binary files separately
cat $tmp_filetypes | grep -f $tmp_txtpattern -v | cut -d: -f1 | zip -9 -q $zipfile -@
cat $tmp_filetypes | grep -f $tmp_txtpattern | cut -d: -f1 | zip -9 -q --to-crlf $zipfile -@ || exit 1
