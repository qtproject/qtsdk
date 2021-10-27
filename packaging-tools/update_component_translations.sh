#! /bin/bash
#############################################################################
##
## Copyright (C) 2021 The Qt Company Ltd.
## Contact: https://www.qt.io/licensing/
##
## This file is part of the FOO module of the Qt Toolkit.
##
## $QT_BEGIN_LICENSE:GPL-EXCEPT$
## Commercial License Usage
## Licensees holding valid commercial Qt licenses may use this file in
## accordance with the commercial license agreement provided with the
## Software or, alternatively, in accordance with the terms contained in
## a written agreement between you and The Qt Company. For licensing terms
## and conditions see https://www.qt.io/terms-conditions. For further
## information use the contact form at https://www.qt.io/contact-us.
##
## GNU General Public License Usage
## Alternatively, this file may be used under the terms of the GNU
## General Public License version 3 as published by the Free Software
## Foundation with exceptions as appearing in the file LICENSE.GPL3-EXCEPT
## included in the packaging of this file. Please review the following
## information to ensure the GNU General Public License requirements will
## be met: https://www.gnu.org/licenses/gpl-3.0.html.
##
## $QT_END_LICENSE$
##
#############################################################################

set -o errexit
set -o nounset
set -o pipefail

pkgroot=""
lupdate=""
lrelease=""

usage() {
    echo "Usage: $0 [OPTION]... [PKG_DIR]"
    echo "Performs linguist operations for component translations."
    echo
    echo "This script takes only one positional argument [PKG_DIR] which"
    echo "is a path for the package templates directory to work in."
    echo
    echo "  -u <path to lupdate>   Updates source strings in existing TS files"
    echo "  -r <path to lrelease>  Produces QM files out of TS files"
    echo
}

update() {
    readarray -d '' files < <(find "$pkgroot" -name "*.ts" -print0)
    for i in "${files[@]}"
    do
        filepath="${i%/*}/"
        cd "$filepath"
        "$lupdate" -locations none -no-ui-lines -no-sort -no-obsolete "$filepath" -ts "$i"
    done
    echo "Done"
}

release() {
    readarray -d '' files < <(find "$pkgroot" -name "*.ts" -print0)
    for i in "${files[@]}"
    do
        filepath="${i%/*}/"
        cd "$filepath"
        "$lrelease" "$i"
    done
    echo "Done"
}

while getopts hu:r: flag
do
    case "$flag" in
        h) usage && exit 0;;
        u) lupdate="$OPTARG";;
        r) lrelease="$OPTARG";;
    esac
done

shift $((OPTIND - 1))
if [ "$#" -gt 0 ]; then
    pkgroot="$1"
fi

if [ -z "$pkgroot" ]; then
    usage
    exit 1
else
    pkgroot=$(realpath "$pkgroot")
fi

if [ "$lupdate" ]; then
    lupdate=$(realpath "$lupdate")
    update
elif [ "$lrelease" ]; then
    lrelease=$(realpath "$lrelease")
    release
else
    usage
    exit 1
fi
