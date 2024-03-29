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

import io
import os
from itertools import takewhile
from subprocess import PIPE, Popen
from typing import IO, Any, Dict, Optional

# http://stackoverflow.com/questions/1214496/how-to-get-environment-from-a-subprocess-in-python
# def validate_pair(ob):
#     try:
#         if not (len(ob) == 2):
#             print("Unexpected result:", ob, file = sys.stderr)
#             raise ValueError
#     except:
#         return False
#     return True


def consume(iterator: Any) -> None:
    try:
        while True:
            next(iterator)
    except StopIteration:
        pass


class PackagingError(Exception):
    pass


def sanity_check_env(env_cmd: str, env_dict: Dict[str, str]) -> None:
    # throw error if 'Path' exists in environment dictionary
    if "Path" in env_dict:
        raise PackagingError(
            f"Configuration error, possible duplicate path 'Path' found in {env_cmd}"
        )


def get(
    env_cmd: str, initial: Optional[Dict[str, str]] = None, arguments: Any = None
) -> Dict[str, str]:
    """
    Take a command (either a single command or list of arguments)
    and return the environment created after running that command.
    Note that if the command must be a batch file or .cmd file, or the
    changes to the environment will not be captured.

    If initial is supplied, it is used as the initial environment passed
    to the child process.
    """
    if not os.path.lexists(env_cmd):
        raise Exception(f"Can not find {env_cmd} to get an environment from it.")

    # if not isinstance(env_cmd, (list, tuple)):
    #     env_cmd = [env_cmd]
    # construct the command that will alter the environment
    # env_cmd = list2cmdline(env_cmd)

    # create a tag so we can tell in the output when the proc is done
    tag = 'Done running command'
    # construct a cmd.exe command to do accomplish this
    cmd = f'cmd.exe /s /c ""{env_cmd}" {arguments}&& echo "{tag}" && set"'

    # launch the process
    with Popen(cmd, stdout=PIPE, env=initial, universal_newlines=True) as proc:
        # parse the output sent to stdout
        lines: IO[str] = proc.stdout or io.StringIO("")
        # consume whatever output occurs until the tag is reached
        consume(takewhile(lambda line: tag not in line, lines))
        # parse key/values into pairs
        pairs = (line.rstrip().split('=', 1) for line in lines)
        # make sure the pairs are valid
        valid_pairs = (pair for pair in pairs if len(pair) == 2)
        # construct a dictionary of the pairs
        result = dict(valid_pairs)
        # let the process finish
        proc.communicate()
    # check resulting env for duplicate path
    sanity_check_env(env_cmd, result)
    return result
