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
import ctypes
import time
import sys
import unittest
import argparse  # commandline argument parser
import os

if sys.platform.startswith("win"):
    # Don't display the Windows GPF dialog if the invoked program dies.
    # See comp.os.ms-windows.programmer.win32
    # How to suppress crash notification dialog?, Jan 14,2004 -
    # Raymond Chen's response [1]

    SEM_NOGPFAULTERRORBOX = 0x0002  # From MSDN
    ctypes.windll.kernel32.SetErrorMode(SEM_NOGPFAULTERRORBOX)
    subprocess_flags = 0x8000000  # win32con.CREATE_NO_WINDOW?


def baseCommand():
    return " ".join([sys.executable,os.path.abspath(__file__)])


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
        j


def printLines(count):
    for lineNumber in range(count):
        print("{0} printed line".format(lineNumber))


def useRunCommand(testArguments, *arguments):
    from bld_utils import runCommand
    return runCommand("{0} {1}".format(baseCommand(), testArguments), *arguments)


class TestRunCommand(unittest.TestCase):
    def test_ExitValue_0(self):
        self.assertEqual(useRunCommand("--printLines 10", os.getcwd()), 0)

    def test_Crash(self):
        with self.assertRaises(Exception) as contextManager:
            useRunCommand("--printLines 10 --crash", os.getcwd())

        self.assertIsNotNone(contextManager)
        self.assertIsNotNone(contextManager.exception)
        expectedMessageStart = "Different exit code then expected"
        messageStart = str(contextManager.exception)[:len(expectedMessageStart)]
        self.assertEqual(expectedMessageStart, messageStart)

    def test_Crash_onlyErrorCaseOutput(self):
        with self.assertRaises(Exception) as contextManager:
            useRunCommand("--printLines 10 --crash", os.getcwd(),
            # callerArguments=
            None,
            # extra_environment=
            None,
            # onlyErrorCaseOutput=
            True,
            # expectedExitCodes=
            [0])
        self.assertIsNotNone(contextManager)
        self.assertIsNotNone(contextManager.exception)
        expectedMessageStart = "Different exit code then expected"
        messageStart = str(contextManager.exception)[:len(expectedMessageStart)]
        self.assertEqual(expectedMessageStart, messageStart)
        expectedMessageEnd = "9 printed line"
        messageEnd = str(contextManager.exception).splitlines()[-1]
        self.assertTrue(messageEnd.__contains__(expectedMessageEnd))

    def test_differentExitCode_onlyErrorCaseOutput(self):
        self.assertEqual(useRunCommand("--printLines 10 --exitCode 5", os.getcwd(),
            # callerArguments=
            None,
            # extra_environment=
            None,
            # onlyErrorCaseOutput=
            True,
            # expectedExitCodes=
            [0,5]), 5)

    def test_withThreadedWork(self):
        currentMethodName = sys._getframe().f_code.co_name
        from threadedwork import ThreadedWork
        testWork = ThreadedWork("{} - run some command threaded".format(currentMethodName))
        taskStringList = []
        taskStringList.append("--sleep 1 --printLines 10")
        taskStringList.append("--sleep 2 --printLines 30")
        taskStringList.append("--sleep 1 --printLines 40")
        taskStringList.append("--sleep 2 --printLines 50")
        taskStringList.append("--sleep 1 --printLines 100")
        for taskString in taskStringList:
            testWork.addTask(taskString, useRunCommand, taskString, os.getcwd())
        testWork.run()

    def test_withThreadedWork_unexpected_exitCode(self):
        currentMethodName = sys._getframe().f_code.co_name
        from threadedwork import ThreadedWork
        testWork = ThreadedWork("{} - run some command threaded".format(currentMethodName))
        # this exchange the current os._exit(-1) implementation only for this testing case
        separatorLine = "{0}>>>>>>>>>>>>>>>>>>>>>>>>>>>>>{0}".format(os.linesep)
        separatorText = "the complete python application would stop here"
        testWork.setExitFailFunction(sys.__stdout__.write, ''.join([separatorLine, separatorText, separatorLine]))
        taskStringList = []
        taskStringList.append("--sleep 1 --printLines 10")
        taskStringList.append("--sleep 2 --printLines 30")
        taskStringList.append("--sleep 1 --printLines 40")
        taskStringList.append("--sleep 2 --printLines 3 --exitCode 5")
        taskStringList.append("--sleep 1 --printLines 100")
        for taskString in taskStringList:
            testWork.addTask(taskString, useRunCommand, taskString, os.getcwd())
        testWork.run()

    def test_withThreadedWork_crash(self):
        currentMethodName = sys._getframe().f_code.co_name
        from threadedwork import ThreadedWork
        testWork = ThreadedWork("{} - run some command threaded".format(currentMethodName))
        # this exchange the current os._exit(-1) implementation only for this testing case
        separatorLine = "{0}>>>>>>>>>>>>>>>>>>>>>>>>>>>>>{0}".format(os.linesep)
        separatorText = "the complete python application would stop here"
        testWork.setExitFailFunction(sys.__stdout__.write, ''.join([separatorLine, separatorText, separatorLine]))
        taskStringList = []
        taskStringList.append("--sleep 1 --printLines 10")
        taskStringList.append("--sleep 2 --printLines 30")
        taskStringList.append("--sleep 1 --printLines 40")
        taskStringList.append("--sleep 2 --printLines 3 --crash")
        taskStringList.append("--sleep 1 --printLines 100")
        for taskString in taskStringList:
            testWork.addTask(taskString, useRunCommand, taskString, os.getcwd())
        testWork.run()


if __name__ == '__main__':
    # no args means we are calling the tests
    if not sys.argv[1:]:
        unittest.main()
    else:
        parser = argparse.ArgumentParser(prog = os.path.basename(sys.argv[0]))
        parser.add_argument('--sleep', type=int)
        parser.add_argument('--printLines', type=int)
        parser.add_argument('--crash', action='store_true', default=False)
        parser.add_argument('--exitCode', type=int)
        parser.add_argument('--testMethod')
        callerArguments = parser.parse_args()
        if callerArguments.sleep:
            time.sleep(callerArguments.sleep)
        if callerArguments.printLines:
            printLines(callerArguments.printLines)
        if callerArguments.crash:
            sys.__stdout__.flush()
            sys.__stderr__.flush()
            crash()
        if callerArguments.exitCode:
            os._exit(callerArguments.exitCode)
        if callerArguments.testMethod:
            # python test_runCommand.py --testMethod test_Crash_onlyErrorCaseOutput
            TestRunCommand(methodName=callerArguments.testMethod).debug()
