#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
##
## Copyright (C) 2022 The Qt Company Ltd.
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

from ddt import ddt, data
import os
import unittest
from tempfile import TemporaryDirectory
from bldinstallercommon import replace_in_files
from pathlib import Path


@ddt
class TestCommon(unittest.TestCase):
    @data(
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
    def test_replace_in_files(self, data):
        # unpack data
        file_contents, replacements, expected_file_content = data
        with TemporaryDirectory(dir=os.getcwd()) as tmp_base_dir:
            # run tag substitution with data
            tmp_file = Path(tmp_base_dir) / "test"
            with open(tmp_file, "a") as f:
                f.write(file_contents)
            for key, value in replacements:
                replace_in_files([tmp_file], key, value)
            with open(tmp_file, "r") as f:
                file_contents = f.read()
                # check that file contents match
                self.assertEqual(file_contents, expected_file_content)

    def test_replace_in_files_invalid_path(self):
        with TemporaryDirectory(dir=os.getcwd()) as tmp_base_dir:
            # invalid file path should raise FileNotFoundError
            invalid_path = Path(tmp_base_dir) / "invalid"
            with self.assertRaises(FileNotFoundError):
                replace_in_files([invalid_path], "foo", "bar")

    def test_replace_in_files_not_array(self):
        # non-array should raise TypeError
        with self.assertRaises(TypeError):
            replace_in_files(None, "foo", "bar")

    def test_replace_in_files_empty_array(self):
        # empty file array should not raise exception
        replace_in_files([], "foo", "bar")


if __name__ == "__main__":
    unittest.main()
