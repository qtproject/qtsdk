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
from typing import List

from ddt import data, ddt, unpack  # type: ignore

from content_cleaner import preserve_content, remove_content, remove_empty_directories


@ddt
class TestContentCleaner(unittest.TestCase):
    def generate_test_content(self, test_base_dir: str, test_content_paths: List[str]) -> None:
        for test_content_path in test_content_paths:
            test_path = os.path.join(test_base_dir, test_content_path)
            os.makedirs(os.path.dirname(test_path), exist_ok=True)
            if not test_path.endswith("/"):
                with open(test_path, "w+", encoding="utf-8") as handle:
                    handle.write("")

    @data(  # type: ignore
        (
            [
                "libexec/codegen/preserve-file.ext",
                "libexec/codegen/test-file1",
                "libexec/codegen/test-file2",
            ],  # test content
            ["libexec/codegen/preserve-file.ext"],  # expected result
            ["preserve-file.ext"],  # preserve rule
        ),
        (
            [
                "libexec/codegen/test-file1",
                "libexec/codegen/test-file2",
                "libexec/codegen/test-file3",
                "remove/this/path/",
                "remove/this/path/test-file1",
            ],
            [
                "libexec/codegen/test-file1",
                "libexec/codegen/test-file1",
                "libexec/codegen/test-file2",
                "libexec/codegen/test-file3",
            ],
            ["libexec/codegen/**"],
        ),
        (
            ["bin/test-file1", "bin/test-file2", "bin/test-file3", "remove/this/path/.test-file1"],
            ["bin/test-file1", "bin/test-file2", "bin/test-file3"],
            ["bin/*"],
        ),
        (
            [
                "libexec/codegen/preserve-file.ext",
                "libexec/codegen/.preserve-file",
                "libexec/codegen/remove-file",
                "remove/this/path/",
                "bin/codegen/.preserve-file",
            ],
            [
                "libexec/codegen/preserve-file.ext",
                "libexec/codegen/.preserve-file",
                "bin/codegen/.preserve-file",
            ],
            ["**/*preserve-file*"],
        ),
    )
    @unpack  # type: ignore
    def test_preserve_content(
        self,
        test_content: List[str],
        expected_result: List[str],
        preserve_rules: List[str],
    ) -> None:
        with TemporaryDirectory(dir=str(Path.cwd())) as tmp_base_dir:
            test_base_dir = os.path.join(tmp_base_dir, "test-base-dir")
            self.generate_test_content(test_base_dir, test_content)
            preserve_content(test_base_dir, preserve_rules)
            for item in expected_result:
                self.assertTrue(os.path.isfile(os.path.join(test_base_dir, item)))

    @data(  # type: ignore
        (
            [
                "testA/path1/path2/path3/testfile1.ext",
                "testA/path1/path2/path3/.testfile2",
                "testA/path1/path2/path3/testfile3",
                "testB/path3/path4/testfile1.ext",
                "testB/path3/path4/.testfile2",
                "testB/path5/path5/testfile3",
            ],
            [
                "**/path1/path2/**/testfile1.ext",
                "**/path1/path2/path3/.testfile2",
                "**/path3/path4/testfile1.ext",
                "**/path3/path4/.testfile2",
            ],
            ["testfile1.ext", ".testfile2"],
        ),
        (
            [
                "testA/path1/path2/path3/testfile1.ext",
                "testA/path1/path2/path3/.testfile2",
                "testA/path1/path2/path3/testfile3",
            ],
            ["**/*testfile*"],
            ["testfile1.ext", ".testfile2", "testfile3"],
        ),
    )
    @unpack  # type: ignore
    def test_remove_content(
        self,
        test_content: List[str],
        remove_rules: List[str],
        verify_removed_files: List[str],
    ) -> None:
        try:
            with TemporaryDirectory(dir=str(Path.cwd())) as tmp_base_dir:
                test_base_dir = os.path.join(tmp_base_dir, "test-base-dir")
                self.generate_test_content(test_base_dir, test_content)
                remove_content(test_base_dir, remove_rules)
                for file_path in verify_removed_files:
                    for path in test_content:
                        if file_path in os.path.join(test_base_dir, path):
                            self.assertFalse(os.path.isfile(os.path.join(test_base_dir, path)))
        # Python 3.7 and below will throw FileNotFoundError on cleanup when exiting context
        # if the TemporaryDirectory was removed.
        except FileNotFoundError:
            pass

    @data(  # type: ignore
        (["test/path/test-file", "test/path/.test-file"], False),
        (["test/path/to/remove/", "test/.path/to/remove/"], True),
    )
    @unpack  # type: ignore
    def test_remove_empty_directories(self, test_content: List[str], remove_dir: bool) -> None:
        try:
            with TemporaryDirectory(dir=str(Path.cwd())) as tmp_base_dir:
                test_base_dir = os.path.join(tmp_base_dir, "test-base-dir")
                self.generate_test_content(test_base_dir, test_content)
                remove_empty_directories(test_base_dir)
                for path in test_content:
                    verify_path = os.path.join(test_base_dir, path)
                    if remove_dir:
                        self.assertFalse(os.path.exists(verify_path))
                    else:
                        self.assertTrue(os.path.exists(verify_path))
        # Python 3.7 and below will throw FileNotFoundError on cleanup when exiting context
        # if the temporary directory was removed.
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    unittest.main()
