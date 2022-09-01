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
import builtins
import itertools
import os
import sys
import threading
from multiprocessing import cpu_count
from queue import Queue
from time import sleep
from traceback import format_exc

# we are using RLock, because threadedPrint is using the same lock
output_lock = threading.RLock()
output_states = None
output_format_string = ''


# prepare our std output hooks
class StdOutHook:
    def write(self, text):
        # general print method sends line break just ignore that
        strippedText = text.strip()
        if strippedText == "":
            return
        global output_states
        global output_format_string
        localProgressIndicator = None
        if len(strippedText) > 6:
            localProgressIndicator = nextProgressIndicator()
        else:
            localProgressIndicator = strippedText

        newValue = f"{thread_data.taskNumber}: {localProgressIndicator}"
        with output_lock:
            if newValue != output_states[thread_data.workerThreadId]:
                oldOutput = "\r" + output_format_string.format(*output_states).strip()
                output_states[thread_data.workerThreadId] = newValue
                newOutput = "\r" + output_format_string.format(*output_states).strip()
                # cleanup old output if the new line is shorter
                cleanerString = ""
                if len(oldOutput) > len(newOutput):
                    cleanerString = " " * (len(oldOutput) - len(newOutput))

                sys.__stdout__.write(newOutput + cleanerString)

    def flush(self):
        sys.__stdout__.flush()


class StdErrHook:
    def write(self, text):
        with output_lock:
            sys.__stderr__.write(text)

    def flush(self):
        sys.__stderr__.flush()


# builtin print() isn't threadsafe, lets make it threadsafe
def threadedPrint(*a, **b):
    with output_lock:
        org_print(*a, **b)


# this is really a HACK or better only useful in this complicate situation
org_print = builtins.print
org_stdout = sys.stdout
org_sterr = sys.stderr


def enableThreadedPrint(enable=True, threadCount=cpu_count()):
    if enable:
        global output_states
        global output_format_string
        output_states = [""] * (threadCount)
        output_format_string = ""
        for x in range(threadCount):
            output_format_string = output_format_string + "{" + str(x) + ":10}"
        sys.stdout = StdOutHook()
        sys.stderr = StdErrHook()
        builtins.print = threadedPrint
    else:
        sys.stdout = org_stdout
        sys.stderr = org_sterr
        builtins.print = org_print


thread_data = threading.local()


def nextProgressIndicator():
    return next(thread_data.progressIndicator)


class TaskFunction():

    def __init__(self, function, *arguments):
        self.function = function
        self.arguments = arguments

    def __str__(self):
        return str(self.__dict__)


class Task():

    def __init__(self, description, function=None, *arguments):
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
        except Exception:
            print("FAIL")
            with output_lock:
                # there is no clean exit so we adding linesep here
                sys.__stdout__.write(os.linesep)
                sys.__stdout__.flush()
                sys.__stderr__.write(format(taskFunction))
                sys.__stderr__.write(os.linesep)
                sys.__stderr__.write(format_exc())
                sys.__stderr__.flush()
                self.exitFunction(*(self.exitFunctionArguments))
        print("Done")


class ThreadedWork():

    def __init__(self, description):
        self.description = os.linesep + f"##### {description} #####"
        self.queue = Queue()
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
        self.legend.append(("{:d}: " + os.linesep + "\t{}" + os.linesep).format(task.taskNumber, task.description))
        self.queue.put(task)
        self.taskNumber = self.taskNumber + 1

    def run(self, maxThreads=None):
        if not maxThreads:
            maxThreads = min(cpu_count(), self.taskNumber)
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
                    sleep(1)
                except KeyboardInterrupt:  # if ctrl-C is pressed within that second,
                    # catch the KeyboardInterrupt exception
                    sys.exit(0)
        # self.queue.join() <- this ignoring the KeyboardInterrupt
        if maxThreads > 1:
            enableThreadedPrint(False)
        print(f"\n{self.description} ... done")


class Consumer(threading.Thread):

    def __init__(self, queue, workerThreadId):
        self.queue = queue
        self.workerThreadId = workerThreadId
        threading.Thread.__init__(self)

    def run(self, stableRunIndicator=True):
        if stableRunIndicator:
            thread_data.progressIndicator = itertools.cycle(['..'])
        else:
            thread_data.progressIndicator = itertools.cycle(['|', '/', '-', '\\'])
        thread_data.workerThreadId = self.workerThreadId
        # run as long we have something in that queue
        while True:
            task = self.queue.get()
            if task is None:
                self.queue.task_done()
                break
            # we like to know which task get the progress -> see std handling
            thread_data.taskNumber = task.taskNumber
            task.do()
            self.queue.task_done()
