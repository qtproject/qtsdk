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
import sys
from io import TextIOWrapper
from subprocess import PIPE, STDOUT, CalledProcessError, Popen, TimeoutExpired, check_output
from traceback import print_exc
from typing import Any, Dict, List, Optional, Tuple

from bld_utils import is_windows
from logging_util import init_logger

log = init_logger(__name__, debug_mode=False)

MAX_DEBUG_PRINT_LENGTH = 10000

if sys.platform == 'win32':
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)


def exec_cmd(
    cmd: List[str], timeout: float = 60.0, env: Optional[Dict[str, str]] = None
) -> str:
    env = env if env else os.environ.copy()
    log.info("Calling: %s", ' '.join(cmd))
    output = check_output(' '.join(cmd), shell=True, env=env, timeout=timeout).decode("utf-8").strip()
    print(output)
    return output


async def async_exec_cmd(
    cmd: List[str], timeout: int = 60 * 60, env: Optional[Dict[str, str]] = None
) -> None:
    env = env if env else os.environ.copy()
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=None, stderr=STDOUT, env=env)
    try:
        log.info("Calling: %s", ' '.join(cmd))
        await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except (asyncio.TimeoutError, TimeoutExpired):
        log.error("Timeout (%ss) for: %s", str(timeout), cmd)
        raise
    except CalledProcessError as command_err:
        log.error("Failed to run command: %s", str(command_err))
        raise
    except Exception as error:
        log.error("Something failed: %s", str(error))
        raise


def do_execute_sub_process(
    args: List[str],
    execution_path: str,
    abort_on_fail: bool = True,
    get_output: bool = False,
    extra_env: Optional[Dict[str, str]] = None,
    redirect_output: Optional[TextIOWrapper] = None,
    args_log: Optional[str] = None,
) -> Tuple[int, str]:
    extra_env = extra_env or os.environ.copy()
    _args_log = args_log or ' '.join([str(i) for i in args])
    print('      --------------------------------------------------------------------')
    print(f'      Executing:      [{_args_log}]')
    print(f'      Execution path: [{execution_path}]')
    print(f'      Abort on fail:  [{str(abort_on_fail)}]')
    sys.stdout.flush()
    theproc: Any
    return_code = -1
    output = ''

    try:
        if is_windows():
            if get_output:
                theproc = Popen(args, shell=True, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=False, env=extra_env, cwd=execution_path, universal_newlines=True)
                output = theproc.communicate()[0]
            elif redirect_output:
                theproc = Popen(args, shell=True, stdout=redirect_output, stderr=STDOUT, close_fds=False, env=extra_env, cwd=execution_path, universal_newlines=True)
                theproc.communicate()
            else:
                theproc = Popen(args, shell=True, close_fds=False, env=extra_env, cwd=execution_path, universal_newlines=True)
                theproc.communicate()

        else:
            if get_output:
                theproc = Popen(args, shell=False, stdin=PIPE, stdout=PIPE, stderr=STDOUT, close_fds=True, env=extra_env, cwd=execution_path, universal_newlines=True)
                output = theproc.communicate()[0]
            elif redirect_output:
                theproc = Popen(args, shell=False, stdout=redirect_output, stderr=STDOUT, close_fds=False, env=extra_env, cwd=execution_path, universal_newlines=True)
                theproc.communicate()
            else:
                theproc = Popen(  # pylint: disable=R1732
                    args, env=extra_env, cwd=execution_path, universal_newlines=True
                )
                theproc.communicate()

        if theproc.returncode:
            return_code = theproc.returncode
            if output:
                output = output[len(output) - MAX_DEBUG_PRINT_LENGTH:] if len(output) > MAX_DEBUG_PRINT_LENGTH else output
                print(output)
            else:
                print('Note, no output from the sub process!')
                sys.stdout.flush()
            raise Exception(f"*** Execution failed with code: {theproc.returncode}")
        print('      --------------------------------------------------------------------')
        sys.stdout.flush()
    except Exception:
        sys.stderr.write('      ERROR - ERROR - ERROR - ERROR - ERROR - ERROR !!!' + os.linesep)
        sys.stderr.write('      Executing:      [' + _args_log + ']' + os.linesep)
        sys.stderr.write('      Execution path: [' + execution_path + ']' + os.linesep)
        print_exc()
        sys.stderr.flush()
        sys.stdout.flush()
        if abort_on_fail:
            raise

    return return_code, output
