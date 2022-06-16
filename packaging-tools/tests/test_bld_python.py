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

from tests import testhelpers
import os
import unittest
import tempfile
from bld_python import BldPythonError, locate_source_root


class TestBldPython(unittest.TestCase):

    @testhelpers.asyncio_test
    async def test_locate_source_root(self) -> None:
        with tempfile.TemporaryDirectory(dir=os.getcwd()) as tmpBaseDir:
            tempDir = os.path.join(tmpBaseDir, "foo", "bar", "test", "dir")
            os.makedirs(tempDir)
            tempFilePath = os.path.join(tempDir, "configure")
            with open(tempFilePath, 'w+') as f:
                f.write("\n")

            foundDir = locate_source_root(tmpBaseDir)
            self.assertEqual(foundDir, tempDir)

            invalidDir = os.path.join(tmpBaseDir, "foo2", "bar", "test", "dir")
            os.makedirs(invalidDir)
            with self.assertRaises(BldPythonError):
                locate_source_root(os.path.join(tmpBaseDir, "foo2"))


if __name__ == '__main__':
    unittest.main()
