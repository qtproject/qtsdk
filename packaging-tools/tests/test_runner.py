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
import sys
import unittest
from asyncio import TimeoutError
from pathlib import Path
from tempfile import TemporaryDirectory

from ddt import data, ddt  # type: ignore

from bld_utils import is_windows
from runner import async_exec_cmd, do_execute_sub_process, exec_cmd
from tests.testhelpers import asyncio_test


@ddt
class TestRunner(unittest.TestCase):

    @unittest.skipIf(is_windows(), "Windows not supported for this test yet")
    @asyncio_test
    async def test_async_exec_cmd(self) -> None:
        await async_exec_cmd(['echo', "TEST"])

        cmd = ['sleep', '2']
        with self.assertRaises(TimeoutError):
            await async_exec_cmd(cmd, timeout=1)

    @unittest.skipIf(is_windows(), "Windows not supported for this test yet")
    @asyncio_test
    async def test_exec_cmd(self) -> None:
        output = exec_cmd(['echo', "TEST"])
        self.assertEqual(output, "TEST")

        cmd = ['sleep', '2']
        with self.assertRaises(TimeoutError):
            await async_exec_cmd(cmd, timeout=1)

    @data(
        (["echo", "TEST"], "TEST", True),
        (["echo", "TEST"], '', False),
    )
    def test_do_execute_sub_process_get_output(self, data):
        # Test get_output
        args, expected_output, get_output = data
        _, output = do_execute_sub_process(args, os.getcwd(), get_output=get_output)
        self.assertEqual(output.strip(), expected_output)

    @data(
        (["echo TEST"], Exception if is_windows() else FileNotFoundError),
        ('"echo TEST"', Exception if is_windows() else FileNotFoundError),
        (None, TypeError),
        (1234, TypeError)
    )
    def test_do_execute_sub_process_invalid_args(self, data):
        # Test with invalid args
        test_args, expected_exception = data
        with self.assertRaises(expected_exception):
            do_execute_sub_process(test_args, os.getcwd())

    def test_do_execute_sub_process_execution_path(self):
        args = ["cd"] if is_windows() else ["pwd"]
        # Test execution_path
        with TemporaryDirectory(dir=os.getcwd()) as tmp_base_dir:
            _, output = do_execute_sub_process(args, tmp_base_dir, get_output=True)
            self.assertEqual(output.strip(), tmp_base_dir)

    def test_do_execute_sub_process_abort_on_fail(self):
        # Throw exception in subprocess with error code 1
        args = [sys.executable, "-c", "exit(1)"]
        # abort_on_fail=True should throw an exception (default)
        with self.assertRaises(Exception):
            do_execute_sub_process(args, os.getcwd())
        # abort_on_fail=False should not throw an exception and continue
        return_code, _ = do_execute_sub_process(args, os.getcwd(), abort_on_fail=False)
        self.assertEqual(return_code, 1)

    def test_do_execute_sub_process_redirect_output(self):
        # Test redirect_output
        with TemporaryDirectory(dir=os.getcwd()) as tmp_base_dir:
            log_file = Path(tmp_base_dir) / "log"
            log_file.touch()
            with open(log_file, 'w') as f:
                do_execute_sub_process(["echo", "TEST"], tmp_base_dir, redirect_output=f)
            with open(log_file, 'r') as f:
                self.assertEqual(f.read().strip(), "TEST")

    @data(
        ({"EXTRA": "ENV"}, "ENV"),
        ({}, "%EXTRA%" if is_windows() else ""),
    )
    def test_do_execute_sub_process_extra_env(self, data):
        args = ["echo", "%EXTRA%"] if is_windows() else ["printenv", "EXTRA"]
        # Test extra_env
        extra_env, expected_value = data
        _, output = do_execute_sub_process(args, os.getcwd(), False, True, extra_env)
        self.assertEqual(output.strip(), expected_value)


if __name__ == '__main__':
    unittest.main()
