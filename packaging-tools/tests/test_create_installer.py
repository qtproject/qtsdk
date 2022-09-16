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
from typing import Optional, Tuple

from ddt import data, ddt  # type: ignore

from bld_utils import is_macos, is_windows
from bldinstallercommon import locate_paths
from create_installer import CreateInstallerError, read_component_sha, remove_all_debug_libraries
from sdkcomponent import IfwSdkComponent


@ddt
class TestCommon(unittest.TestCase):
    @data((  # type: ignore
        ("/bin/", "/lib/", "/qml/", "/plugins/", "/unrelated/"),
        (
            "Foo.lib", "Food.lib", "dd.qml", "Bar.exe", "Bard.exe", "Qt3d.dll", "Qt3dd.dll"
        ) if is_windows() else (
            "foo_debug.bar", ".foo_debug.bar", "_debug.bar", "foo_debug.", "foodebugbar"
        ),
        [
            'Foo.lib', 'dd.qml', 'Bard.exe', 'Qt3d.dll', 'Bar.exe'
        ] if is_windows() else ["foodebugbar"]
    ))
    @unittest.skipIf(not(is_windows() or is_macos()), "This test is only for Windows and macOS")
    def test_remove_all_debug_libraries_win(self, test_data: Tuple[str, str, str]) -> None:
        dirs, files, remaining_files = test_data
        with TemporaryDirectory(dir=str(Path.cwd())) as tmpdir:
            for directory in dirs:
                Path(tmpdir + directory).mkdir()
                for file in files:
                    Path(tmpdir + directory + file).touch()
            remove_all_debug_libraries(tmpdir)
            for directory in dirs:
                result_paths = locate_paths(tmpdir + directory, ["*"], [os.path.isfile])
                result_rel = [str(Path(p).relative_to(tmpdir + directory)) for p in result_paths]
                if directory == "/unrelated/":
                    self.assertCountEqual(result_rel, files)
                else:
                    self.assertCountEqual(result_rel, remaining_files)

    @data(  # type: ignore
        ("8843d7f92416211de9ebb963ff4ce28125932878", "8843d7f92416211de9ebb963ff4ce28125932878"),
        ("8843d", "8843d"),
    )
    def test_read_component_sha(self, test_data: Tuple[str, Optional[str]]) -> None:
        sha, exp = test_data
        sdk_comp = IfwSdkComponent("", "", "", "", "", "", "", "", "", "", "")  # type: ignore
        with TemporaryDirectory(dir=Path.cwd()) as tmpdir:
            test_sha = Path(tmpdir) / "test"
            test_sha.write_text(sha, encoding="utf-8")
            read_component_sha(sdk_comp, test_sha)
            self.assertEqual(sdk_comp.component_sha1, exp)

    @data(  # type: ignore
        ("foobar"),
        ("8843"),
        ("8843d7f92416211de9ebb963ff4ce2812593287g"),
        (""),
    )
    def test_read_component_sha_invalid_content(self, test_sha1: str) -> None:
        sdk_comp = IfwSdkComponent("", "", "", "", "", "", "", "", "", "", "")  # type: ignore
        with TemporaryDirectory(dir=Path.cwd()) as tmpdir:
            test_sha = Path(tmpdir) / "test"
            test_sha.write_text(test_sha1, encoding="utf-8")
            with self.assertRaises(CreateInstallerError):
                read_component_sha(sdk_comp, test_sha)

    def test_read_component_sha_invalid_path(self) -> None:
        sdk_comp = IfwSdkComponent("", "", "", "", "", "", "", "", "", "", "")  # type: ignore
        with TemporaryDirectory(dir=Path.cwd()) as tmpdir:
            with self.assertRaises(CreateInstallerError):
                read_component_sha(sdk_comp, Path(tmpdir) / "invalid")


if __name__ == "__main__":
    unittest.main()
