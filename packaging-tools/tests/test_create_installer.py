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

import unittest
from typing import Optional, Tuple

from ddt import data, ddt  # type: ignore
from temppathlib import TemporaryDirectory

from create_installer import CreateInstallerError, read_component_sha
from sdkcomponent import IfwSdkComponent


@ddt
class TestCommon(unittest.TestCase):
    @data(  # type: ignore
        ("8843d7f92416211de9ebb963ff4ce28125932878", "8843d7f92416211de9ebb963ff4ce28125932878"),
        ("8843d", "8843d"),
    )
    def test_read_component_sha(self, test_data: Tuple[str, Optional[str]]) -> None:
        sha, exp = test_data
        sdk_comp = IfwSdkComponent("", "", "", "", "", "", "", "", "", "", "", "")  # type: ignore
        with TemporaryDirectory() as tmpdir:
            test_sha = tmpdir.path / "test"
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
        sdk_comp = IfwSdkComponent("", "", "", "", "", "", "", "", "", "", "", "")  # type: ignore
        with TemporaryDirectory() as tmpdir:
            test_sha = tmpdir.path / "test"
            test_sha.write_text(test_sha1, encoding="utf-8")
            with self.assertRaises(CreateInstallerError):
                read_component_sha(sdk_comp, test_sha)

    def test_read_component_sha_invalid_path(self) -> None:
        sdk_comp = IfwSdkComponent("", "", "", "", "", "", "", "", "", "", "", "")  # type: ignore
        with TemporaryDirectory() as tmpdir:
            with self.assertRaises(CreateInstallerError):
                read_component_sha(sdk_comp, tmpdir.path / "invalid")


if __name__ == "__main__":
    unittest.main()
