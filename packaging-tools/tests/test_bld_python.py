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

from temppathlib import TemporaryDirectory

from bld_python import BldPythonError, locate_source_root
from tests.testhelpers import asyncio_test


class TestBldPython(unittest.TestCase):

    @asyncio_test
    async def test_locate_source_root(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            base_dir_path = tmp_base_dir.path
            temp_dir = base_dir_path / "foo" / "bar" / "test" / "dir"
            temp_dir.mkdir(parents=True)
            temp_file_path = temp_dir / "configure"
            with temp_file_path.open('w+', encoding="utf-8") as handle:
                handle.write("\n")

            found_dir = locate_source_root(str(base_dir_path))
            self.assertEqual(found_dir, str(temp_dir))

            invalid_dir = base_dir_path / "foo2" / "bar" / "test" / "dir"
            invalid_dir.mkdir(parents=True)
            with self.assertRaises(BldPythonError):
                locate_source_root(str(base_dir_path / "foo2"))


if __name__ == '__main__':
    unittest.main()
