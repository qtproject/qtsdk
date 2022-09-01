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
    subprocess_flags = 0x8000000  # win32con.CREATE_NO_WINDOW?


def base_command():
    return " ".join([sys.executable, os.path.abspath(__file__)])


def crash():
    '''\
    crash the Python interpreter...
    '''
    i = ctypes.c_char(b'a')
    j = ctypes.pointer(i)
    c = 0
    while True:
        j[c] = b'a'
        c += 1


def print_lines(count):
    for lineNumber in range(count):
        print(f"{lineNumber} printed line")


def use_run_command(testArguments, *arguments):
    return run_command(f"{base_command()} {testArguments}", *arguments)


class TestRunCommand(unittest.TestCase):
    def test_exit_value_0(self):
        self.assertEqual(use_run_command("--print_lines 10", os.getcwd()), 0)

    def test_crash(self):
        with self.assertRaises(Exception) as contextManager:
            use_run_command("--print_lines 10 --crash", os.getcwd())

        self.assertIsNotNone(contextManager)
        self.assertIsNotNone(contextManager.exception)
        expectedMessageStart = "Different exit code then expected"
        messageStart = str(contextManager.exception)[:len(expectedMessageStart)]
        self.assertEqual(expectedMessageStart, messageStart)

    def test_crash_only_error_case_output(self):
        with self.assertRaises(Exception) as contextManager:
            use_run_command(
                "--print_lines 10 --crash", os.getcwd(),
                # extra_environment=
                None,
                # onlyErrorCaseOutput=
                True,
                # expectedExitCodes=
                [0]
            )
        self.assertIsNotNone(contextManager)
        self.assertIsNotNone(contextManager.exception)
        expectedMessageStart = "Different exit code then expected"
        messageStart = str(contextManager.exception)[:len(expectedMessageStart)]
        self.assertEqual(expectedMessageStart, messageStart)
        expectedMessageEnd = "9 printed line"
        messageEnd = str(contextManager.exception).splitlines()[-1]
        self.assertTrue(messageEnd.__contains__(expectedMessageEnd))

    def test_different_exit_code_only_error_case_output(self):
        self.assertEqual(
            use_run_command(
                "--print_lines 10 --exitCode 5", os.getcwd(),
                # extra_environment=
                None,
                # onlyErrorCaseOutput=
                True,
                # expectedExitCodes=
                [0, 5]
            ), 5
        )

    def test_with_threadedwork(self):
        currentMethodName = sys._getframe().f_code.co_name
        testWork = ThreadedWork(f"{currentMethodName} - run some command threaded")
        taskStringList = []
        taskStringList.append("--sleep 1 --print_lines 10")
        taskStringList.append("--sleep 2 --print_lines 30")
        taskStringList.append("--sleep 1 --print_lines 40")
        taskStringList.append("--sleep 2 --print_lines 50")
        taskStringList.append("--sleep 1 --print_lines 100")
        for taskString in taskStringList:
            testWork.add_task(taskString, use_run_command, taskString, os.getcwd())
        testWork.run()

    def test_with_threadedwork_unexpected_exit_code(self):
        currentMethodName = sys._getframe().f_code.co_name
        testWork = ThreadedWork(f"{currentMethodName} - run some command threaded")
        # this exchange the current os._exit(-1) implementation only for this testing case
        separatorLine = f"{os.linesep}>>>>>>>>>>>>>>>>>>>>>>>>>>>>>{os.linesep}"
        separatorText = "the complete python application would stop here"
        testWork.set_exit_fail_function(sys.__stdout__.write, ''.join([separatorLine, separatorText, separatorLine]))
        taskStringList = []
        taskStringList.append("--sleep 1 --print_lines 10")
        taskStringList.append("--sleep 2 --print_lines 30")
        taskStringList.append("--sleep 1 --print_lines 40")
        taskStringList.append("--sleep 2 --print_lines 3 --exitCode 5")
        taskStringList.append("--sleep 1 --print_lines 100")
        for taskString in taskStringList:
            testWork.add_task(taskString, use_run_command, taskString, os.getcwd())
        testWork.run()

    def test_with_threadedwork_crash(self):
        currentMethodName = sys._getframe().f_code.co_name
        testWork = ThreadedWork(f"{currentMethodName} - run some command threaded")
        # this exchange the current os._exit(-1) implementation only for this testing case
        separatorLine = f"{os.linesep}>>>>>>>>>>>>>>>>>>>>>>>>>>>>>{os.linesep}"
        separatorText = "the complete python application would stop here"
        testWork.set_exit_fail_function(sys.__stdout__.write, ''.join([separatorLine, separatorText, separatorLine]))
        taskStringList = []
        taskStringList.append("--sleep 1 --print_lines 10")
        taskStringList.append("--sleep 2 --print_lines 30")
        taskStringList.append("--sleep 1 --print_lines 40")
        taskStringList.append("--sleep 2 --print_lines 3 --crash")
        taskStringList.append("--sleep 1 --print_lines 100")
        for taskString in taskStringList:
            testWork.add_task(taskString, use_run_command, taskString, os.getcwd())
        testWork.run()


if __name__ == '__main__':
    # no args means we are calling the tests
    if not sys.argv[1:]:
        unittest.main()
    else:
        parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]))
        parser.add_argument('--sleep', type=int)
        parser.add_argument('--print_lines', type=int)
        parser.add_argument('--crash', action='store_true', default=False)
        parser.add_argument('--exitCode', type=int)
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
        if caller_arguments.exitCode:
            os._exit(caller_arguments.exitCode)
        if caller_arguments.testMethod:
            # python test_runCommand.py --testMethod test_crash_only_error_case_output
            TestRunCommand(methodName=caller_arguments.testMethod).debug()
