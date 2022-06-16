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
import itertools
# to get the cpu number
import multiprocessing
import os
import threading
import traceback
import time
import sys
import queue
import builtins as __builtin__

# we are using RLock, because threadedPrint is using the same lock
outputLock = threading.RLock()
outputStates = None
outputFormatString = ''

# prepare our std output hooks
class StdOutHook:
    def write(self, text):
        # general print method sends line break just ignore that
        strippedText = text.strip()
        if strippedText == "":
            return
        global outputStates
        global outputFormatString
        localProgressIndicator = None
        if len(strippedText) > 6:
            localProgressIndicator = nextProgressIndicator()
        else:
            localProgressIndicator = strippedText

        newValue = "{:d}: {}".format(threadData.taskNumber, localProgressIndicator)
        with outputLock:
            if newValue != outputStates[threadData.workerThreadId]:
                oldOutput = "\r" + outputFormatString.format(*outputStates).strip()
                outputStates[threadData.workerThreadId] = newValue
                newOutput = "\r" + outputFormatString.format(*outputStates).strip()
                # cleanup old output if the new line is shorter
                cleanerString = ""
                if len(oldOutput) > len(newOutput):
                    cleanerString = " " * (len(oldOutput) - len(newOutput))

                sys.__stdout__.write(newOutput + cleanerString)

    def flush(self):
        sys.__stdout__.flush()

class StdErrHook:
    def write(self, text):
        with outputLock:
            sys.__stderr__.write(text)

    def flush(self):
        sys.__stderr__.flush()

# builtin print() isn't threadsafe, lets make it threadsafe
def threadedPrint(*a, **b):
    with outputLock:
        __builtin__.org_print(*a, **b)

# this is really a HACK or better only useful in this complicate situation
__builtin__.org_print = __builtin__.print
__builtin__.org_stdout = sys.stdout
__builtin__.org_sterr = sys.stderr

def enableThreadedPrint(enable = True, threadCount = multiprocessing.cpu_count()):
    if enable:
        global outputStates
        global outputFormatString
        outputStates = [""] * (threadCount)
        outputFormatString = ""
        for x in range(threadCount):
            outputFormatString = outputFormatString + "{" + str(x) + ":10}"
        sys.stdout = StdOutHook()
        sys.stderr = StdErrHook()
        __builtin__.print = threadedPrint
    else:
        sys.stdout = __builtin__.org_stdout
        sys.stderr = __builtin__.org_sterr
        __builtin__.print = __builtin__.org_print

threadData = threading.local()

def nextProgressIndicator():
    return next(threadData.progressIndicator)

class TaskFunction():
    def __init__(self, function, *arguments):
        self.function = function
        self.arguments = arguments
    def __str__(self):
        return str(self.__dict__)

class Task():
    def __init__(self, description, function = None, *arguments):
        self.taskNumber = 0  # will be set from outside
        self.description = description
        self.listOfFunctions = []
        if function:
            firstFunction = TaskFunction(function, *arguments)
            self.listOfFunctions.append(firstFunction)
        # exit the complete program with code -1, sys.exit would just close the thread
        self.exitFunction = os._exit
        self.exitFunctionArguments = [-1]

    def addFunction(self, function, *arguments):
        aFunction = TaskFunction(function, *arguments)
        self.listOfFunctions.append(aFunction)

    def do(self):
        try:
            for taskFunction in self.listOfFunctions:
                taskFunction.function(*(taskFunction.arguments))
        except Exception as e:
            print("FAIL")
            with outputLock:
                # there is no clean exit so we adding linesep here
                sys.__stdout__.write(os.linesep)
                sys.__stdout__.flush()
                sys.__stderr__.write(format(taskFunction))
                sys.__stderr__.write(os.linesep)
                sys.__stderr__.write(traceback.format_exc())
                sys.__stderr__.flush()
                self.exitFunction(*(self.exitFunctionArguments))
        print("Done")

class ThreadedWork():
    def __init__(self, description):
        self.description = os.linesep + "##### {} #####".format(description)
        self.queue = queue.Queue()
        self.legend = []
        self.taskNumber = 0
        self.exitFunction = None
    def setExitFailFunction(self, function, *arguments):
        self.exitFunction = function
        self.exitFunctionArguments = arguments

    def addTask(self, description, function, *arguments):
        self.addTaskObject(Task(description, function, *arguments))

    def addTaskObject(self, task):
        task.taskNumber = self.taskNumber
        if self.exitFunction:
            task.exitFunction = self.exitFunction
            task.exitFunctionArguments = self.exitFunctionArguments
        self.legend.append(("{:d}: " + os.linesep +"\t{}" + os.linesep).format(task.taskNumber, task.description))
        self.queue.put(task)
        self.taskNumber = self.taskNumber + 1

    def run(self, maxThreads=None):
        if not maxThreads:
            maxThreads = min(multiprocessing.cpu_count(), self.taskNumber)
        print(self.description)
        print(os.linesep.join(self.legend))

        if maxThreads > 1:
            enableThreadedPrint(True, maxThreads)
        listOfConsumers = []
        for i in range(maxThreads):
            # every Consumer needs a stop/none item
            self.queue.put(None)
            newConsumer = Consumer(self.queue, i)
            listOfConsumers.append(newConsumer)
            newConsumer.daemon = True
            newConsumer.start()

        # block until everything is done
        for consumer in listOfConsumers:
            while consumer.is_alive():
                try:
                    # wait 1 second, then go back and ask if thread is still alive
                    time.sleep(1)
                except KeyboardInterrupt:  # if ctrl-C is pressed within that second,
                    # catch the KeyboardInterrupt exception
                    sys.exit(0)
        # self.queue.join() <- this ignoring the KeyboardInterrupt
        if maxThreads > 1:
            enableThreadedPrint(False)
        print(os.linesep + self.description + ' ... done')

class Consumer(threading.Thread):
    def __init__(self, queue, workerThreadId):
        self.queue = queue
        self.workerThreadId = workerThreadId
        threading.Thread.__init__(self)
    def run(self, stableRunIndicator = True):
        if stableRunIndicator:
            threadData.progressIndicator = itertools.cycle(['..'])
        else:
            threadData.progressIndicator = itertools.cycle(['|', '/', '-', '\\'])
        threadData.workerThreadId = self.workerThreadId
        # run as long we have something in that queue
        while True:
            task = self.queue.get()
            if task is None:
                self.queue.task_done()
                break
            else:
                # we like to know which task get the progress -> see std handling
                threadData.taskNumber = task.taskNumber
                task.do()
                self.queue.task_done()
