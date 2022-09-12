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
from typing import Any, List, Optional

# we are using RLock, because threaded_print is using the same lock
output_lock = threading.RLock()  # pylint: disable=invalid-name
output_states = []  # pylint: disable=invalid-name
output_format_string = ''  # pylint: disable=invalid-name


# prepare our std output hooks
class StdOutHook:
    def write(self, text: str) -> None:
        # general print method sends line break just ignore that
        stripped_text = text.strip()
        if stripped_text == "":
            return
        local_progress_indicator = None
        if len(stripped_text) > 6:
            local_progress_indicator = next_progress_indicator()
        else:
            local_progress_indicator = stripped_text

        new_value = f"{thread_data.task_number}: {local_progress_indicator}"
        with output_lock:
            if new_value != output_states[thread_data.worker_thread_id]:
                old_output = "\r" + output_format_string.format(*output_states).strip()
                output_states[thread_data.worker_thread_id] = new_value
                new_output = "\r" + output_format_string.format(*output_states).strip()
                # cleanup old output if the new line is shorter
                cleaner_string = ""
                if len(old_output) > len(new_output):
                    cleaner_string = " " * (len(old_output) - len(new_output))

                sys.__stdout__.write(new_output + cleaner_string)

    def flush(self) -> None:
        sys.__stdout__.flush()


class StdErrHook:
    def write(self, text: str) -> None:
        with output_lock:
            sys.__stderr__.write(text)

    def flush(self) -> None:
        sys.__stderr__.flush()


# builtin print() isn't threadsafe, lets make it threadsafe
def threaded_print(*a: Any, **b: Any) -> None:
    with output_lock:
        org_print(*a, **b)


# this is really a HACK or better only useful in this complicate situation
org_print = builtins.print
org_stdout = sys.stdout
org_sterr = sys.stderr


def enable_threaded_print(enable: bool = True, thread_count: int = cpu_count()) -> None:
    if enable:
        global output_states  # pylint: disable=W0603,C0103
        global output_format_string  # pylint: disable=W0603,C0103
        output_states = [""] * (thread_count)
        output_format_string = ""
        for xthread in range(thread_count):
            output_format_string = output_format_string + "{" + str(xthread) + ":10}"
        sys.stdout = StdOutHook()  # type: ignore
        sys.stderr = StdErrHook()  # type: ignore
        builtins.print = threaded_print
    else:
        sys.stdout = org_stdout
        sys.stderr = org_sterr
        builtins.print = org_print


thread_data = threading.local()


def next_progress_indicator() -> Any:
    return next(thread_data.progress_indicator)


class TaskFunction:

    def __init__(self, function: Any, *arguments) -> None:  # type: ignore
        self.function = function
        self.arguments = arguments

    def __str__(self) -> str:
        return str(self.__dict__)


class Task:

    def __init__(self, description: str, function: Any, *arguments) -> None:  # type: ignore
        self.task_number = 0  # will be set from outside
        self.description = description
        self.list_of_functions = []
        if function:
            first_function = TaskFunction(function, *arguments)
            self.list_of_functions.append(first_function)
        # exit the complete program with code -1, sys.exit would just close the thread
        self.exit_function = os._exit
        self.exit_function_arguments = [-1]

    def add_function(self, function: Any, *arguments) -> None:  # type: ignore
        a_function = TaskFunction(function, *arguments)
        self.list_of_functions.append(a_function)

    def do_task(self) -> None:
        try:
            for task_function in self.list_of_functions:
                task_function.function(*(task_function.arguments))
        except Exception:
            print("FAIL")
            with output_lock:
                # there is no clean exit so we adding linesep here
                sys.__stdout__.write(os.linesep)
                sys.__stdout__.flush()
                sys.__stderr__.write(format(task_function))
                sys.__stderr__.write(os.linesep)
                sys.__stderr__.write(format_exc())
                sys.__stderr__.flush()
                self.exit_function(*(self.exit_function_arguments))
        print("Done")


class ThreadedWork:

    def __init__(self, description: str) -> None:
        self.description = os.linesep + f"##### {description} #####"
        self.queue = Queue()  # type: ignore
        self.legend: List[str] = []
        self.task_number = 0
        self.exit_function: Any = None
        self.exit_function_arguments: Any = None

    def set_exit_fail_function(self, function: Any, *arguments) -> None:  # type: ignore
        self.exit_function = function
        self.exit_function_arguments = arguments

    def add_task(self, description: str, function: Any, *arguments) -> None:  # type: ignore
        self.add_task_object(Task(description, function, *arguments))

    def add_task_object(self, task: Any) -> None:
        task.task_number = self.task_number
        if self.exit_function:
            task.exit_function = self.exit_function
            task.exit_function_arguments = self.exit_function_arguments
        self.legend.append(("{:d}: " + os.linesep + "\t{}" + os.linesep).format(task.task_number, task.description))
        self.queue.put(task)
        self.task_number = self.task_number + 1

    def run(self, max_threads: Optional[int] = None) -> None:
        if max_threads is None:
            max_threads = min(cpu_count(), self.task_number)
        print(self.description)
        print(os.linesep.join(self.legend))

        if max_threads > 1:
            enable_threaded_print(True, max_threads)
        list_of_consumers = []
        for i in range(max_threads):
            # every Consumer needs a stop/none item
            self.queue.put(None)
            new_consumer = Consumer(self.queue, i)
            list_of_consumers.append(new_consumer)
            new_consumer.daemon = True
            new_consumer.start()

        # block until everything is done
        for consumer in list_of_consumers:
            while consumer.is_alive():
                try:
                    # wait 1 second, then go back and ask if thread is still alive
                    sleep(1)
                except KeyboardInterrupt:  # if ctrl-C is pressed within that second,
                    # catch the KeyboardInterrupt exception
                    raise SystemExit(0) from KeyboardInterrupt
        # self.queue.join() <- this ignoring the KeyboardInterrupt
        if max_threads > 1:
            enable_threaded_print(False)
        print(f"\n{self.description} ... done")


class Consumer(threading.Thread):

    def __init__(self, queue: Any, worker_thread_id: Any) -> None:
        self.queue = queue
        self.worker_thread_id = worker_thread_id
        threading.Thread.__init__(self)

    def run(self, stable_run_indicator: bool = True) -> None:  # pylint: disable=W0221
        if stable_run_indicator:
            thread_data.progress_indicator = itertools.cycle(['..'])
        else:
            thread_data.progress_indicator = itertools.cycle(['|', '/', '-', '\\'])
        thread_data.worker_thread_id = self.worker_thread_id
        # run as long we have something in that queue
        while True:
            task = self.queue.get()
            if task is None:
                self.queue.task_done()
                break
            # we like to know which task get the progress -> see std handling
            thread_data.task_number = task.task_number
            task.do_task()
            self.queue.task_done()
