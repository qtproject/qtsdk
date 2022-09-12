#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
#
# Copyright (C) 2022 The Qt Company Ltd.
# Contact: https://www.qt.io/licensing/
#
# This file is part of the release tools of the Qt Toolkit.
#
# $QT_BEGIN_LICENSE:GPL-EXCEPT$
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
# $QT_END_LICENSE$
#
#############################################################################

import argparse
import os
import sys
from pathlib import Path
from typing import List

from installer_utils import ch_dir
from logging_util import init_logger

log = init_logger(__name__, debug_mode=False)


class CleanerError(Exception):
    pass


def expand_rules(rules: List[str]) -> List[str]:
    matches = []
    for mask in rules:
        # pathlib returns nothing with pattern ending "**"
        # append "/*" to the mask for such patterns
        mask = mask + "/*" if mask.endswith("**") else mask
        for file in Path(".").rglob(mask):
            matches.append(str(file))
    return matches


def remove_empty_directories(root_path: str) -> None:
    for root, dirs, _ in os.walk(root_path, topdown=True):
        for name in dirs:
            dir_path = os.path.join(root, name)
            if not os.listdir(dir_path):  # to check whether the dir is empty
                log.info("Removing empty directory: %s", dir_path)
                os.removedirs(dir_path)


def preserve_content(input_dir: str, preserve_rules: List[str]) -> None:
    log.info("Cleaning content from: '%s' - preserve_rules: %s", input_dir, preserve_rules)
    if not os.path.isdir(input_dir):
        raise CleanerError(f"Not a valid input directory: {input_dir}")
    split_preserve_rules = [word for line in preserve_rules for word in line.split()]
    with ch_dir(input_dir):
        files_to_keep = expand_rules(split_preserve_rules)
        for path in Path(".").rglob("*"):
            if str(path) in files_to_keep:
                continue
            if not os.path.islink(path) and os.path.isdir(path):
                continue
            log.info("Removing file: %s", path)
            os.remove(path)
    remove_empty_directories(input_dir)


def remove_content(input_dir: str, remove_rules: List[str]) -> None:
    log.info("Removing files from: '%s' - remove_rules: %s", input_dir, remove_rules)
    if not os.path.isdir(input_dir):
        raise CleanerError(f"Not a valid input directory: {input_dir}")
    split_remove_rules = [word for line in remove_rules for word in line.split()]
    with ch_dir(input_dir):
        files_to_remove = expand_rules(split_remove_rules)
        for path in Path(".").rglob("*"):
            if os.path.isdir(path):
                continue
            if str(path) in files_to_remove:
                log.info("Removing: %s", path)
                os.remove(path)
    remove_empty_directories(input_dir)


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(
        prog="Clean all files from the --input-dir directory except those defined by --glob-rule"
    )
    parser.add_argument("--input-dir", dest="input_dir", required=True, help="Directory to scan")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--preserve",
        dest="preserve_rules",
        action="append",
        help="One or multiple glob based rules which files to keep",
    )
    group.add_argument(
        "--remove",
        dest="remove_rules",
        action="append",
        help="One or multiple glob based rules which files to remove",
    )
    args = parser.parse_args(sys.argv[1:])
    if args.preserve_rules:
        preserve_content(args.input_dir, args.preserve_rules)
    elif args.remove_rules:
        remove_content(args.input_dir, args.remove_rules)
    else:
        raise SystemExit("--preserve or --remove rules need to be specified")


if __name__ == "__main__":
    main()
