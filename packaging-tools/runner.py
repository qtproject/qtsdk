#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
##
## Copyright (C) 2020 The Qt Company Ltd.
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

import os
import sys
import asyncio
import subprocess
from subprocess import PIPE, STDOUT, Popen
from traceback import print_exc
from typing import List, Dict

from logging_util import init_logger


log = init_logger(__name__, debug_mode=False)

MAX_DEBUG_PRINT_LENGTH = 10000

if sys.platform == 'win32':
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)


def exec_cmd(cmd: List[str], timeout=60, env: Dict[str, str]=None) -> str:
    env = env if env else os.environ.copy()
    log.info("Calling: %s", ' '.join(cmd))
    output = subprocess.check_output(' '.join(cmd), shell=True, env=env, timeout=timeout).decode("utf-8").strip()
    print(output)
    return output


async def async_exec_cmd(cmd: List[str], timeout: int=60 * 60, env: Dict[str, str]=None) -> None:
    env = env if env else os.environ.copy()
    p = await asyncio.create_subprocess_exec(*cmd, stdout=None, stderr=STDOUT, env=env)
    try:
        log.info("Calling: %s", ' '.join(cmd))
        await asyncio.wait_for(p.communicate(), timeout=timeout)
    except (asyncio.TimeoutError, subprocess.TimeoutExpired):
        log.error("Timeout (%ss) for: %s", str(timeout), cmd)
        raise
    except subprocess.CalledProcessError as commandErr:
        log.error("Failed to run command: %s", str(commandErr))
        raise
    except Exception as e:
        log.error("Something failed: %s", str(e))
        raise


def do_execute_sub_process(args, execution_path, abort_on_fail=True, get_output=False,
                           extra_env=dict(os.environ), redirect_output=None, args_log=None):
    # Temporarily adding imports here, to prevent circular import
    from bld_utils import is_windows
    from bldinstallercommon import list_as_string
    _args_log = args_log or list_as_string(args)
    print('      --------------------------------------------------------------------')
    print('      Executing:      [' + _args_log + ']')
    print('      Execution path: [' + execution_path + ']')
    print('      Abort on fail:  [' + str(abort_on_fail) + ']')
    sys.stdout.flush()
    theproc = None
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
                theproc = Popen(args, env=extra_env, cwd=execution_path, universal_newlines=True)
                theproc.communicate()

        if theproc.returncode:
            return_code = theproc.returncode
            if output:
                output = output[len(output) - MAX_DEBUG_PRINT_LENGTH:] if len(output) > MAX_DEBUG_PRINT_LENGTH else output
                print(output)
            else:
                print('Note, no output from the sub process!')
                sys.stdout.flush()
            raise Exception('*** Execution failed with code: {0}'.format(theproc.returncode))
        print('      --------------------------------------------------------------------')
        sys.stdout.flush()
    except Exception:
        sys.stderr.write('      ERROR - ERROR - ERROR - ERROR - ERROR - ERROR !!!' + os.linesep)
        sys.stderr.write('      Executing:      [' + list_as_string(args) + ']' + os.linesep)
        sys.stderr.write('      Execution path: [' + execution_path + ']' + os.linesep)
        print_exc()
        sys.stderr.flush()
        sys.stdout.flush()
        if abort_on_fail:
            raise
        else:
            pass

    return return_code, output