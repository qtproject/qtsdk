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
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Callable, List, Optional, Tuple

from ddt import data, ddt  # type: ignore

from bld_utils import is_windows
from bldinstallercommon import (
    calculate_relpath,
    locate_executable,
    locate_path,
    locate_paths,
    replace_in_files,
    search_for_files,
)
from installer_utils import PackagingError


@ddt
class TestCommon(unittest.TestCase):
    @data(  # type: ignore
        (
            "%TAG_VERSION%%TAG_EDITION%",
            [("%TAG_VERSION%", "6.3.0"), ("%TAG_EDITION%", "opensource"), ("foo", "bar")],
            "6.3.0opensource",
        ),
        (
            "QT_VERSION=%TAG_VERSION%\n%TAG_EDITION%=QT_EDITION",
            [("%TAG_VERSION%", "6.3.0"), ("%TAG_EDITION%", "opensource")],
            "QT_VERSION=6.3.0\nopensource=QT_EDITION",
        ),
        (
            "%foo%",
            [("%foo%", "%bar%"), ("%bar%", "foo"), ("", "bar"), ("barfbarobarobar", "foo")],
            "foo",
        ),
        (
            "%=%foo%foo%foo%foo%%\n",
            [("%foo%", "%foo"), ("%foo%", "foo%"), ("%%", "foo%")],
            "%=%foofoo%foofoofoo%\n",
        ),
        ("%foo\nbar%foo", [("%foobar%", "foobar"), ("%foo%", "")], "%foo\nbar%foo"),
    )
    def test_replace_in_files(self, test_data: Tuple[str, List[Tuple[str, str]], str]) -> None:
        # unpack data
        file_contents, replacements, expected_file_content = test_data
        with TemporaryDirectory() as tmp_base_dir:
            # run tag substitution with data
            tmp_file = Path(tmp_base_dir) / "test"
            with open(tmp_file, "a", encoding="utf-8") as handle:
                handle.write(file_contents)
            for key, value in replacements:
                replace_in_files([str(tmp_file)], key, value)
            with open(tmp_file, "r", encoding="utf-8") as handle:
                file_contents = handle.read()
                # check that file contents match
                self.assertEqual(file_contents, expected_file_content)

    def test_replace_in_files_invalid_path(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            # invalid file path should raise FileNotFoundError
            invalid_path = Path(tmp_base_dir) / "invalid"
            with self.assertRaises(FileNotFoundError):
                replace_in_files([str(invalid_path)], "foo", "bar")

    def test_replace_in_files_not_array(self) -> None:
        # non-array should raise TypeError
        with self.assertRaises(TypeError):
            replace_in_files(None, "foo", "bar")  # type: ignore

    def test_replace_in_files_empty_array(self) -> None:
        # empty file array should not raise exception
        replace_in_files([], "foo", "bar")

    @data(  # type: ignore
        (
            ("script.py", "content\n foo bar\n"),
            (["*.prl", ".pri"], "foo"),
            [],
        ),
        (
            ("file.pc", "content\n foo bar\n"),
            (["*.pc"], "foo"),
            ["file.pc"],
        ),
        (
            ("file.la", "content\n foo bar\n"),
            (["*.la"], "foobar"),
            [],
        ),
        (
            ("file.x", "foobar"),
            (["*.x"], ""),
            ["file.x"],
        ),
        (
            ("file.x", "foobar"),
            ([], "foobar"),
            ["file.x"],
        ),
        (
            ("subfolder/file.x", "foobar"),
            (["*.x"], "foobar"),
            ["file.x"],
        ),
    )
    def test_search_for_files(self, test_data: Tuple[Tuple[str, str], Tuple[List[str], str], List[str]]) -> None:
        file, params, expected_files = test_data
        with TemporaryDirectory() as tmp_base_dir:
            path, content = file
            tmp_file = Path(tmp_base_dir) / path
            tmp_file.parents[0].mkdir(parents=True, exist_ok=True)
            with open(tmp_file, "a", encoding="utf-8") as handle:
                handle.write(content)
            extensions, rgx = params
            result = search_for_files(tmp_base_dir, extensions, rgx)
            self.assertEqual(len(result), len(expected_files))
            for result_path, expected_path in zip(result, expected_files):
                self.assertEqual(Path(result_path).name, expected_path)

    @data(  # type: ignore
        (([], [], ['d', '.d', 'tst.y', '.t', 'tst.t', 'tempty', 'd/tst.t', 'd/n', '.d/.t'])),
        ((["*"], [], ['d', '.d', 'tst.y', '.t', 'tst.t', 'tempty', 'd/tst.t', 'd/n', '.d/.t'])),
        ((["tst*"], [os.path.isfile], ['tst.y', 'tst.t', 'd/tst.t'])),
        ((["*"], [os.path.isdir], ['d', '.d', 'tempty', 'd/n'])),
        ((["*y"], [], ['tst.y', 'tempty'])),
        ((["tst.t"], [], ['tst.t', 'd/tst.t'])),
        ((["wontmatch"], [], [])),
        ((["*.t", "*.y"], [], ["tst.y", ".t", "tst.t", "d/tst.t", ".d/.t"])),
        (([".t", ".d"], [], [".d", ".t", ".d/.t"]))
    )
    def test_locate_paths(self, test_data: Tuple[List[str], Optional[List[Callable[[Path], bool]]], List[str]]) -> None:
        pattern, filters, expected_results = test_data
        with TemporaryDirectory() as tmp_base_dir:
            # Create files and folders
            test_folders = ["/tempty", "/d/n", "/.d"]
            test_files = ["/tst.t", "/tst.y", "/d/tst.t", "/.t", "/.d/.t"]
            for folder in test_folders:
                Path(tmp_base_dir + folder).mkdir(parents=True)
            for file in test_files:
                Path(tmp_base_dir + file).touch()
            result = locate_paths(tmp_base_dir, pattern, filters)
            result = [str(Path(p).relative_to(tmp_base_dir)) for p in result]
            self.assertCountEqual(expected_results, result)

    def test_locate_path(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            test_file = tmp_base_dir + "/test"
            Path(test_file).touch()
            self.assertEqual(test_file, locate_path(tmp_base_dir, ["test"], [os.path.isfile]))

    def test_locate_path_no_matches(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            with self.assertRaises(PackagingError):
                locate_path(tmp_base_dir, ["test"], [os.path.isfile])

    def test_locate_path_multiple_matches(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            Path(tmp_base_dir + "/file").touch()
            Path(tmp_base_dir + "/file2").touch()
            with self.assertRaises(PackagingError):
                locate_path(tmp_base_dir, ["file", "file2"])

    @unittest.skipIf(is_windows(), "Windows not supported for this test")
    def test_locate_executable(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            Path(tmp_base_dir + "/test_file").touch()
            Path(tmp_base_dir + "/test_file2").touch(0o755)
            # File with executable bit not set should throw an error
            with self.assertRaises(PackagingError):
                locate_executable(tmp_base_dir, ["test_file"])
            self.assertEqual(
                locate_executable(tmp_base_dir, ["test_file2"]),
                tmp_base_dir + "/test_file2")

    @data(  # type: ignore
        ("/home/qt/bin/foo/bar", "/home/qt/lib", "../../../lib"),
        ("/home/qt/bin/foo/", "/home/qt/lib", "/home/qt/lib"),
        ("/home/qt/bin", "/home/qt/lib", "../lib"),
        ("/home/qt/bin", "lib", "../../../../lib"),
        ("/home/qt/bin", "/lib", "../../../lib"),
        ("/home/qt", "./lib", "../../.././lib"),
        ("bin", "/home/qt/lib", "/home/qt/lib"),
        ("/home/qt/", "/home/qt", "/home/qt"),
        ("/home/qt", "/home/qt/", "/home/qt"),
        ("/home/qt", "/home/qt/", "/home/qt"),
        ("/", "/home/qt", "home/qt"),
        ("/home/qt", "", "../../../"),
        ("", "/home/qt", "/home/qt"),
    )
    def test_calculate_relpath(self, test_data: Tuple[str, str, str]) -> None:
        path1, path2, expected = test_data
        result = calculate_relpath(path1, path2)
        self.assertEqual(result, expected)

    @data(  # type: ignore
        ("/home/qt", "/home/qt"),
        ("/", "/"),
        ("lib", "lib"),
        ("", ""),
    )
    def test_calculate_relpath_invalid(self, test_data: Tuple[str, str]) -> None:
        path1, path2 = test_data
        with self.assertRaises(TypeError):
            calculate_relpath(path1, path2)


if __name__ == "__main__":
    unittest.main()
