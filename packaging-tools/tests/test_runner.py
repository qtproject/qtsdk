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

import testhelpers
import asyncio
import unittest
from runner import exec_cmd, async_exec_cmd


class TestRunner(unittest.TestCase):

    @testhelpers.asyncio_test
    async def test_async_exec_cmd(self) -> None:
        await async_exec_cmd(['echo', "TEST"])

        cmd = ['sleep', '2']
        with self.assertRaises(asyncio.TimeoutError):
            await async_exec_cmd(cmd, timeout=1)

    @testhelpers.asyncio_test
    async def test_exec_cmd(self) -> None:
        output = exec_cmd(['echo', "TEST"])
        self.assertEqual(output, "TEST")

        cmd = ['sleep', '2']
        with self.assertRaises(asyncio.TimeoutError):
            await async_exec_cmd(cmd, timeout=1)


if __name__ == '__main__':
    unittest.main()
