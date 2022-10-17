#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
#
# Copyright (C) 2023 The Qt Company Ltd.
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
import shutil
import unittest
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from ddt import data, ddt, unpack  # type: ignore
from temppathlib import TemporaryDirectory

from bld_utils import is_linux, is_windows
from bldinstallercommon import (
    calculate_relpath,
    calculate_runpath,
    locate_executable,
    locate_path,
    locate_paths,
    read_file_rpath,
    replace_in_files,
    search_for_files,
    strip_dirs,
    update_file_rpath,
)
from installer_utils import PackagingError


@ddt
class TestCommon(unittest.TestCase):  # pylint: disable=R0904
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
            tmp_file = tmp_base_dir.path / "test"
            with tmp_file.open("a", encoding="utf-8") as handle:
                handle.write(file_contents)
            for key, value in replacements:
                replace_in_files([str(tmp_file)], key, value)
            with tmp_file.open("r", encoding="utf-8") as handle:
                file_contents = handle.read()
                # check that file contents match
                self.assertEqual(file_contents, expected_file_content)

    def test_replace_in_files_invalid_path(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            # invalid file path should raise FileNotFoundError
            invalid_path = tmp_base_dir.path / "invalid"
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
            tmp_file = tmp_base_dir.path / path
            tmp_file.parents[0].mkdir(parents=True, exist_ok=True)
            with tmp_file.open("a", encoding="utf-8") as handle:
                handle.write(content)
            extensions, rgx = params
            result = search_for_files(tmp_base_dir.path, extensions, rgx)
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
            test_folders = ["tempty", "d/n", ".d"]
            test_files = ["tst.t", "tst.y", "d/tst.t", ".t", ".d/.t"]
            for folder in test_folders:
                (tmp_base_dir.path / folder).mkdir(parents=True)
            for file in test_files:
                (tmp_base_dir.path / file).touch()
            result = locate_paths(tmp_base_dir.path, pattern, filters)
            result = [str(Path(p).relative_to(tmp_base_dir.path)) for p in result]
            self.assertCountEqual(expected_results, result)

    def test_locate_path(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            test_file = tmp_base_dir.path / "test"
            test_file.touch()
            self.assertEqual(str(test_file), locate_path(tmp_base_dir.path, ["test"], [os.path.isfile]))

    def test_locate_path_no_matches(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            with self.assertRaises(PackagingError):
                locate_path(tmp_base_dir.path, ["test"], [os.path.isfile])

    def test_locate_path_multiple_matches(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            (tmp_base_dir.path / "file").touch()
            (tmp_base_dir.path / "file2").touch()
            with self.assertRaises(PackagingError):
                locate_path(tmp_base_dir.path, ["file", "file2"])

    @unittest.skipIf(is_windows(), "Windows not supported for this test")
    def test_locate_executable(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            (tmp_base_dir.path / "test_file").touch()
            (tmp_base_dir.path / "test_file2").touch(0o755)
            # File with executable bit not set should throw an error
            with self.assertRaises(PackagingError):
                locate_executable(tmp_base_dir.path, ["test_file"])
            self.assertEqual(
                locate_executable(tmp_base_dir.path, ["test_file2"]),
                str(tmp_base_dir.path / "test_file2"))

    @data(  # type: ignore
        ("foo/bin", "", Path("../..")),
        ("foo/bin", ".", Path("../..")),
        ("foo/bin", "..", Path("../../..")),
        ("foo/bin", "foo/lib", Path("../lib")),
        ("foo/bin", "foo/bin", Path(".")),
        ("foo/bin", "foo/bin/lib", Path("lib")),
        ("foo/bin", "foo/bin/lib/foobar", Path("lib/foobar")),
        ("..", "lib", Path("test/lib")),
    )
    @unpack  # type: ignore
    def test_calculate_relpath(self, test_bin: str, lib_dir: str, expected: str) -> None:
        with TemporaryDirectory() as temp_dir:
            test_path = temp_dir.path / "test"
            lib_path = test_path / lib_dir
            lib_path.mkdir(parents=True, exist_ok=True)
            bin_path = test_path / test_bin
            bin_path.parent.mkdir(parents=True, exist_ok=True)
            bin_path.touch(exist_ok=True)
            result = calculate_relpath(lib_path, bin_path)
            self.assertEqual(result, expected)

    @data(  # type: ignore
        ("foo/bin/bar.elf", "", "$ORIGIN/../.."),
        ("foo/bin/bar.elf", ".", "$ORIGIN/../.."),
        ("foo/bin/bar.elf", "..", "$ORIGIN/../../.."),
        ("foo/bin/bar.elf", "foo/lib", "$ORIGIN/../lib"),
        ("foo/bin/bar.elf", "foo/bin", "$ORIGIN"),
        ("foo/bin/bar.elf", "foo/bin/lib", "$ORIGIN/lib"),
        ("foo/bin/bar.elf", "foo/bin/lib/foobar", "$ORIGIN/lib/foobar"),
    )
    @unpack  # type: ignore
    @unittest.skipUnless(is_linux(), reason="Skip RPATH/RUNPATH tests on non-Linux")
    def test_calculate_runpath(self, test_bin: str, lib_dir: str, expected: str) -> None:
        with TemporaryDirectory() as temp_dir:
            lib_path = temp_dir.path / lib_dir
            lib_path.mkdir(parents=True, exist_ok=True)
            bin_path = temp_dir.path / test_bin
            bin_path.parent.mkdir(parents=True, exist_ok=True)
            bin_path.touch(exist_ok=True)
            result = calculate_runpath(bin_path, lib_path)
            self.assertEqual(result, expected)

    @data(  # type: ignore
        ("testbin_empty_rpath", ""),
        ("testbin_no_rpath", None),
        ("testbin_exist_origin_rpath", "$ORIGIN/bin"),
        ("testbin_exist_rpath", "/home/qt/lib"),
        ("testbin_multiple_rpath", "$ORIGIN/bin:/home/qt"),
        ("testbin_origin_rpath", "$ORIGIN"),
    )
    @unpack  # type: ignore
    @unittest.skipUnless(is_linux(), reason="Skip RPATH/RUNPATH tests on non-Linux")
    @unittest.skipIf(shutil.which("chrpath") is None, reason="Skip tests requiring 'chrpath' tool")
    def test_read_file_rpath(self, test_file: str, expected: Optional[str]) -> None:
        test_asset_path = Path(__file__).parent / "assets" / "runpath"
        found_rpath = read_file_rpath(test_asset_path / test_file)
        self.assertEqual(found_rpath, expected)

    @data(  # type: ignore
        ("testbin_empty_rpath", "lib", "$ORIGIN/lib"),
        ("testbin_exist_origin_rpath", "", "$ORIGIN:$ORIGIN/bin"),
        ("testbin_exist_rpath", "lib", "$ORIGIN/lib"),
        ("testbin_multiple_rpath", "lib", "$ORIGIN/lib:$ORIGIN/bin"),
        ("testbin_origin_rpath", "lib", "$ORIGIN/lib:$ORIGIN"),
    )
    @unpack  # type: ignore
    @unittest.skipUnless(is_linux(), reason="Skip RPATH/RUNPATH tests on non-Linux")
    @unittest.skipIf(shutil.which("chrpath") is None, reason="Skip tests requiring 'chrpath' tool")
    def test_update_file_rpath(self, test_file: str, target_paths: str, expected: str) -> None:
        test_asset_path = Path(__file__).parent / "assets" / "runpath"
        with TemporaryDirectory() as temp_dir:
            temp_path = temp_dir.path
            for path in target_paths.split(':'):
                (temp_path / path).mkdir(parents=True, exist_ok=True)
            shutil.copy(test_asset_path / test_file, temp_path)
            update_file_rpath(temp_path / test_file, temp_path, target_paths)
            result_rpath = read_file_rpath(temp_path / test_file)
            self.assertEqual(result_rpath, expected)

    @unittest.skipUnless(is_linux(), reason="Skip RPATH/RUNPATH tests on non-Linux")
    @unittest.skipIf(shutil.which("chrpath") is None, reason="Skip tests requiring 'chrpath' tool")
    def test_update_file_rpath_too_large(self) -> None:
        test_asset_path = Path(__file__).parent / "assets" / "runpath"
        with TemporaryDirectory() as temp_dir:
            temp_path = temp_dir.path
            target_path = "too-long-path/foo-bar"
            (temp_path / target_path).mkdir(parents=True, exist_ok=True)
            test_bin = "testbin_multiple_rpath"
            shutil.copy(test_asset_path / test_bin, temp_path)
            with self.assertLogs() as logs:
                with self.assertRaises(PackagingError):
                    update_file_rpath(temp_path / test_bin, temp_path, target_path)
                # Last line in info logging output should contain the error message from process
                self.assertTrue("too large; maximum length" in logs.output.pop())

    def test_strip_dirs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_dir.path.joinpath("remove_dir", "sub_dir").mkdir(parents=True, exist_ok=True)
            strip_dirs(temp_dir.path)
            self.assertTrue(temp_dir.path.joinpath("sub_dir").exists())
            self.assertFalse(temp_dir.path.joinpath("remove_dir").exists())

    def test_strip_dirs_multiple_iterations(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_dir.path.joinpath("remove_dir", "remove_dir2", "sub_dir").mkdir(
                parents=True, exist_ok=True
            )
            strip_dirs(temp_dir.path, iterations=2)
            self.assertTrue(temp_dir.path.joinpath("sub_dir").exists())
            self.assertFalse(temp_dir.path.joinpath("remove_dir").exists())

    def test_strip_dirs_no_iterations(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_dir.path.joinpath("no_remove_dir", "sub_dir").mkdir(parents=True, exist_ok=True)
            strip_dirs(temp_dir.path, iterations=0)
            self.assertTrue(temp_dir.path.joinpath("no_remove_dir", "sub_dir").exists())

    def test_strip_dirs_identical_name(self) -> None:
        with TemporaryDirectory() as temp_dir:
            temp_dir.path.joinpath("dir_name", "dir_name").mkdir(parents=True, exist_ok=True)
            strip_dirs(temp_dir.path)
            self.assertTrue(temp_dir.path.joinpath("dir_name").exists())
            self.assertFalse(temp_dir.path.joinpath("dir_name", "dir_name").exists())

    def test_strip_dirs_invalid_subdir_count(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with self.assertRaises(IOError):
                temp_dir.path.joinpath("remove_dir").mkdir(parents=True, exist_ok=True)
                temp_dir.path.joinpath("another_dir").mkdir(parents=True, exist_ok=True)
                strip_dirs(temp_dir.path)

    def test_strip_dirs_not_a_dir(self) -> None:
        with TemporaryDirectory() as temp_dir:
            with self.assertRaises(IOError):
                temp_dir.path.joinpath("remove_dir").touch(exist_ok=True)
                strip_dirs(temp_dir.path)


if __name__ == "__main__":
    unittest.main()
