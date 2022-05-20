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

import asyncio
import os
import unittest
from pathlib import Path
from subprocess import TimeoutExpired
from tempfile import TemporaryDirectory
from typing import Any, Dict, Tuple

from ddt import data, ddt  # type: ignore

from bld_utils import is_windows
from runner import run_cmd, run_cmd_async
from tests.testhelpers import asyncio_test


@ddt
class TestRunner(unittest.TestCase):

    @unittest.skipIf(is_windows(), "Windows not supported for this test yet")
    @asyncio_test
    async def test_async_exec_cmd(self) -> None:
        await run_cmd_async(cmd=["echo", "TEST"])
        await run_cmd_async(cmd="echo TEST")

        cmd = ['sleep', '2']
        with self.assertRaises(asyncio.TimeoutError):
            await run_cmd_async(cmd=cmd, timeout=1)

    def test_exec_cmd_timeout(self) -> None:
        cmd = ["sleep", "2"]
        with self.assertRaises(TimeoutExpired):
            run_cmd(cmd, timeout=1)

    @data(  # type: ignore
        (["echo TEST"], Exception if is_windows() else FileNotFoundError),
        ('"echo TEST"', Exception if is_windows() else FileNotFoundError),
        (None, TypeError),
        (1234, TypeError)
    )
    def test_exec_cmd_invalid_args(self, test_data: Tuple[Any, Any]) -> None:
        # Test with invalid args
        test_args, expected_exception = test_data
        with self.assertRaises(expected_exception):
            run_cmd(cmd=test_args, cwd=os.getcwd())

    def test_exec_cmd_execution_path(self) -> None:
        check_work_dir_args = ["cd"] if is_windows() else ["pwd"]
        # Test execution_path
        with TemporaryDirectory(dir=os.getcwd()) as tmp_base_dir:
            output = run_cmd(cmd=check_work_dir_args, cwd=tmp_base_dir)
            self.assertEqual(output, tmp_base_dir + "\n")

    def test_exec_cmd_log_to_file(self) -> None:
        # Test log_to_file
        with TemporaryDirectory(dir=os.getcwd()) as tmp_base_dir:
            log_file = Path(tmp_base_dir) / "log"
            log_file.touch()
            run_cmd(cmd=["echo", "TEST"], cwd=tmp_base_dir, redirect=str(log_file))
            with open(str(log_file), "r", encoding="utf-8") as handle:
                self.assertEqual(handle.read().strip(), "TEST")

    @data(  # type: ignore
        ({"EXTRA": "ENV"}, "ENV\n"),
        ({}, "%EXTRA%\n" if is_windows() else ""),
    )
    def test_exec_cmd_env(self, test_data: Tuple[Dict[str, str], str]) -> None:
        args = ["echo", "%EXTRA%"] if is_windows() else ["printenv", "EXTRA"]
        # Test extra_env
        extra_env, expected_value = test_data
        try:
            output = run_cmd(cmd=args, cwd=os.getcwd(), env=extra_env)
        except Exception:
            output = ""
        self.assertEqual(output, expected_value)


if __name__ == '__main__':
    unittest.main()
