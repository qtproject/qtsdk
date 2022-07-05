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

import argparse
import ctypes
import os
import sys
import unittest
from time import sleep

from bld_utils import run_command
from threadedwork import ThreadedWork

if sys.platform.startswith("win"):
    # Don't display the Windows GPF dialog if the invoked program dies.
    # See comp.os.ms-windows.programmer.win32
    # How to suppress crash notification dialog?, Jan 14,2004 -
    # Raymond Chen's response [1]

    SEM_NOGPFAULTERRORBOX = 0x0002  # From MSDN
    ctypes.windll.kernel32.SetErrorMode(SEM_NOGPFAULTERRORBOX)
    SUBPROCESS_FLAGS = 0x8000000  # win32con.CREATE_NO_WINDOW?


def base_command():
    return " ".join([sys.executable, os.path.abspath(__file__)])


def crash():
    '''\
    crash the Python interpreter...
    '''
    i = ctypes.c_char(b'a')
    j = ctypes.pointer(i)
    count = 0
    while True:
        j[count] = b'a'
        count += 1


def print_lines(count):
    for line_number in range(count):
        print(f"{line_number} printed line")


def use_run_command(test_arguments, *arguments):
    return run_command(f"{base_command()} {test_arguments}", *arguments)


class TestRunCommand(unittest.TestCase):
    def test_exit_value_0(self):
        self.assertEqual(use_run_command("--print_lines 10", os.getcwd()), 0)

    def test_crash(self):
        with self.assertRaises(Exception) as context_manager:
            use_run_command("--print_lines 10 --crash", os.getcwd())

        self.assertIsNotNone(context_manager)
        self.assertIsNotNone(context_manager.exception)
        expected_message_start = "Different exit code then expected"
        message_start = str(context_manager.exception)[:len(expected_message_start)]
        self.assertEqual(expected_message_start, message_start)

    def test_crash_only_error_case_output(self):
        with self.assertRaises(Exception) as context_manager:
            use_run_command(
                "--print_lines 10 --crash", os.getcwd(),
                # extra_environment=
                None,
                # only_error_case_output=
                True,
                # expected_exit_codes=
                [0]
            )
        self.assertIsNotNone(context_manager)
        self.assertIsNotNone(context_manager.exception)
        expected_message_start = "Different exit code then expected"
        message_start = str(context_manager.exception)[:len(expected_message_start)]
        self.assertEqual(expected_message_start, message_start)
        expected_message_end = "9 printed line"
        message_end = str(context_manager.exception).splitlines()[-1]
        self.assertTrue(expected_message_end in message_end)

    def test_different_exit_code_only_error_case_output(self):
        self.assertEqual(
            use_run_command(
                "--print_lines 10 --exit_code 5", os.getcwd(),
                # extra_environment=
                None,
                # only_error_case_output=
                True,
                # expected_exit_codes=
                [0, 5]
            ), 5
        )

    def test_with_threadedwork(self):
        current_method_name = sys._getframe().f_code.co_name  # pylint: disable=W0212
        test_work = ThreadedWork(f"{current_method_name} - run some command threaded")
        task_string_list = []
        task_string_list.append("--sleep 1 --print_lines 10")
        task_string_list.append("--sleep 2 --print_lines 30")
        task_string_list.append("--sleep 1 --print_lines 40")
        task_string_list.append("--sleep 2 --print_lines 50")
        task_string_list.append("--sleep 1 --print_lines 100")
        for task_string in task_string_list:
            test_work.add_task(task_string, use_run_command, task_string, os.getcwd())
        test_work.run()

    def test_with_threadedwork_unexpected_exit_code(self):
        current_method_name = sys._getframe().f_code.co_name  # pylint: disable=W0212
        test_work = ThreadedWork(f"{current_method_name} - run some command threaded")
        # this exchange the current os._exit(-1) implementation only for this testing case
        separator_line = f"{os.linesep}>>>>>>>>>>>>>>>>>>>>>>>>>>>>>{os.linesep}"
        separator_text = "the complete python application would stop here"
        test_work.set_exit_fail_function(sys.__stdout__.write, ''.join([separator_line, separator_text, separator_line]))
        task_string_list = []
        task_string_list.append("--sleep 1 --print_lines 10")
        task_string_list.append("--sleep 2 --print_lines 30")
        task_string_list.append("--sleep 1 --print_lines 40")
        task_string_list.append("--sleep 2 --print_lines 3 --exit_code 5")
        task_string_list.append("--sleep 1 --print_lines 100")
        for task_string in task_string_list:
            test_work.add_task(task_string, use_run_command, task_string, os.getcwd())
        test_work.run()

    def test_with_threadedwork_crash(self):
        current_method_name = sys._getframe().f_code.co_name  # pylint: disable=W0212
        test_work = ThreadedWork(f"{current_method_name} - run some command threaded")
        # this exchange the current os._exit(-1) implementation only for this testing case
        separator_line = f"{os.linesep}>>>>>>>>>>>>>>>>>>>>>>>>>>>>>{os.linesep}"
        separator_text = "the complete python application would stop here"
        test_work.set_exit_fail_function(sys.__stdout__.write, ''.join([separator_line, separator_text, separator_line]))
        task_string_list = []
        task_string_list.append("--sleep 1 --print_lines 10")
        task_string_list.append("--sleep 2 --print_lines 30")
        task_string_list.append("--sleep 1 --print_lines 40")
        task_string_list.append("--sleep 2 --print_lines 3 --crash")
        task_string_list.append("--sleep 1 --print_lines 100")
        for task_string in task_string_list:
            test_work.add_task(task_string, use_run_command, task_string, os.getcwd())
        test_work.run()


if __name__ == '__main__':
    # no args means we are calling the tests
    if not sys.argv[1:]:
        unittest.main()
    else:
        parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]))
        parser.add_argument('--sleep', type=int)
        parser.add_argument('--print_lines', type=int)
        parser.add_argument('--crash', action='store_true', default=False)
        parser.add_argument('--exit_code', type=int)
        parser.add_argument('--testMethod')
        caller_arguments = parser.parse_args()
        if caller_arguments.sleep:
            sleep(caller_arguments.sleep)
        if caller_arguments.print_lines:
            print_lines(caller_arguments.print_lines)
        if caller_arguments.crash:
            sys.__stdout__.flush()
            sys.__stderr__.flush()
            crash()
        if caller_arguments.exit_code:
            os._exit(caller_arguments.exit_code)  # pylint: disable=W0212
        if caller_arguments.testMethod:
            # python test_run_command.py --testMethod test_crash_only_error_case_output
            TestRunCommand(methodName=caller_arguments.testMethod).debug()
