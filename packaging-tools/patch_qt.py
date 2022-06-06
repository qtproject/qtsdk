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

import os
import re
from fileinput import FileInput
from typing import Any, Callable, Generator, List, Match


def _file_iterator(artifacts_dir: str) -> Generator[Any, Any, Any]:
    print(f"Patching build time paths from: {artifacts_dir}")
    for root, _, files in os.walk(artifacts_dir):
        for file_name in files:
            yield os.path.join(os.path.join(root, file_name))


def _get_patchers(product: str) -> List[Callable[[Any], Any]]:
    if product == 'qt_framework':
        return [patch_absolute_lib_paths_from_file, erase_qmake_prl_build_dir, patch_qconfig_pri]
    # default
    return [patch_absolute_lib_paths_from_file, erase_qmake_prl_build_dir]


def patch_files(artifacts_dir: str, product: str) -> None:
    print(f"Patching files from: {artifacts_dir}")
    patchers = _get_patchers(product)
    for file_path in _file_iterator(artifacts_dir):
        for patcher in patchers:
            patcher(file_path)


def patch_qt_edition(artifacts_dir: str, licheck_file_name: str, release_date: str) -> None:
    for root, _, files in os.walk(artifacts_dir):
        for file_name in files:
            if file_name == 'qconfig.pri':
                _patch_qt_edition(os.path.join(root, file_name), licheck_file_name, release_date)
                return


def _patch_qt_edition(file_path: str, licheck_file_name: str, release_date: str) -> None:
    for line in FileInput(file_path, inplace=True):
        if 'QT_EDITION' in line:
            edition_line = 'QT_EDITION = Enterprise'
            licheck_line = 'QT_LICHECK = ' + licheck_file_name
            release_line = 'QT_RELEASE_DATE = ' + release_date
            print(edition_line.rstrip('\n'))
            print(licheck_line.rstrip('\n'))
            print(release_line.rstrip('\n'))
        else:
            print(line.rstrip('\n'))


def patch_qconfig_pri(file_path: str) -> None:
    for line in FileInput(file_path, inplace=True):
        patched_line = patch_qconfig_pri_from_line(line)
        print(patched_line.rstrip('\n'))


def patch_qconfig_pri_from_line(line: str) -> str:
    if 'QMAKE_DEFAULT_LIBDIRS' in line:
        return line.split('=')[0].strip() + ' ='
    if 'QMAKE_DEFAULT_INCDIRS' in line:
        return line.split('=')[0].strip() + ' ='
    return line


def erase_qmake_prl_build_dir(file_path: str) -> None:
    # Erase lines starting with 'QMAKE_PRL_BUILD_DIR' from .prl files
    for line in FileInput(file_path, inplace=True):
        patched_line = patch_qmake_prl_build_dir_from_line(line)
        print(patched_line.rstrip('\n'))


def patch_qmake_prl_build_dir_from_line(line: str) -> str:
    return '' if line.startswith('QMAKE_PRL_BUILD_DIR') else line


def patch_absolute_lib_paths_from_file(file_path: str) -> None:
    for line in FileInput(file_path, inplace=True):
        patched_line = patch_absolute_lib_paths_from_line(line, file_path.split(".")[-1])
        print(patched_line.rstrip('\n'))


def patch_absolute_lib_paths_from_line(line: str, file_extension: str) -> str:
    r"""
    Captures XXX in e.g. /usr/lib/libXXX.so, /usr/lib64/libXXX.a, and C:\XXX.lib
    Paths are not allowed to contain whitespace though
      [^\s\"]+ - start of path
      "/lib", [\\/]
      ([a-zA-Z0-9\_\-\.\+]+) - capture group for the actual library name
      ".so", ".a", ".lib" suffix
      (\.[0-9]+)? - capture group for for versioned libraries
    """

    def _remove_whitespace(line: str) -> str:
        """Remove white space from paths if found inside quoted blocks."""
        erase_enabled = False
        result = ""
        for char in line:
            if char == "\"":
                # toggle on/off
                erase_enabled = not erase_enabled
            if erase_enabled and char == " ":
                continue
            result += char
        return result

    if file_extension == "cmake":
        # from cmake files patch only lines containing "find_extra_libs"
        cmake_find_extra_libs_search_regexp = re.compile(r'_*._find_extra_libs\(')
        if not re.search(cmake_find_extra_libs_search_regexp, line):
            return line

    expressions = [
        re.compile(r'[^\s\"]+/lib([a-zA-Z0-9\_\-\.\+]+)\.(so|a|tbd)(\.[0-9]+)?\b'),
        re.compile(r'[^\s\"]+[\\/]([a-zA-Z0-9\_\-\.\+]+)\.(lib)(\.[0-9]+)?\b')
    ]

    def _substitute_lib(match: Match[str]) -> str:
        if match.group(0).startswith("$$[QT_"):
            return match.group(0)
        result = "" if file_extension == "cmake" else "-l"  # .pri, .prl, .la, .pc
        result += match.group(1)
        return result

    for regex in expressions:
        # check if there are any matches?
        if re.search(regex, line):
            line = _remove_whitespace(line)
            line = regex.sub(_substitute_lib, line)
            break

    return line
