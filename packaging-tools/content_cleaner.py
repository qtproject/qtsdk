#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
##
## Copyright (C) 2021 The Qt Company Ltd.
## Contact: https://www.qt.io/licensing/
##
## This file is part of the release tools of the Qt Toolkit.
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

import os
import sys
import argparse
from pathlib import Path
from contextlib import contextmanager
from typing import List, Generator
from qt6_installer.logging_util import init_logger

log = init_logger(__name__, debug_mode=False)


class CleanerError(Exception):
    pass


@contextmanager
def cd(path: str) -> Generator:
    oldwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(oldwd)


def expand_rules(rules: List[str]) -> List[str]:
    matches = []
    for mask in rules:
        # pathlib returns nothing with pattern ending "**"
        # append "/*" to the mask for such patterns
        mask = mask + "/*" if mask.endswith("**") else mask
        for file in Path(".").rglob(mask):
            matches.append(str(file))
    return matches


def remove_empty_directories(root_path: str):
    for root, dirs, files in os.walk(root_path, topdown=True):
        for name in dirs:
            dirPath = os.path.join(root, name)
            if not os.listdir(dirPath):  # to check whether the dir is empty
                log.info(f"Removing empty directory: {dirPath}")
                os.removedirs(dirPath)


def preserve_content(input_dir: str, preserve_rules: List[str]) -> None:
    log.info(f"Cleaning content from: '{input_dir}' - preserve_rules: {preserve_rules}")
    if not os.path.isdir(input_dir):
        raise CleanerError(f"Not a valid input directory: {input_dir}")
    split_preserve_rules = [word for line in preserve_rules for word in line.split()]
    with cd(input_dir):
        files_to_keep = expand_rules(split_preserve_rules)
        for p in Path(".").rglob("*"):
            if str(p) in files_to_keep:
                continue
            if not os.path.islink(p) and os.path.isdir(p):
                continue
            log.info(f"Removing file: {p}")
            os.remove(p)
    remove_empty_directories(input_dir)


def remove_content(input_dir: str, remove_rules: List[str]) -> None:
    log.info(f"Removing files from: '{input_dir}' - remove_rules: {remove_rules}")
    if not os.path.isdir(input_dir):
        raise CleanerError(f"Not a valid input directory: {input_dir}")
    split_remove_rules = [word for line in remove_rules for word in line.split()]
    with cd(input_dir):
        files_to_remove = expand_rules(split_remove_rules)
        for p in Path(".").rglob("*"):
            if os.path.isdir(p):
                continue
            if str(p) in files_to_remove:
                log.info(f"Removing: {p}")
                os.remove(p)
    remove_empty_directories(input_dir)


if __name__ == "__main__":
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
        sys.exit(1)
