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
import shlex
import subprocess
import sys
from asyncio import create_subprocess_exec, wait_for
from asyncio.subprocess import PIPE, STDOUT
from io import TextIOWrapper
from pathlib import Path
from typing import Dict, List, Optional, Union

from bld_utils import is_windows
from logging_util import init_logger, with_no_logging

log = init_logger(__name__, debug_mode=False)


if is_windows():

    class ProactorLoopPolicy36(asyncio.DefaultEventLoopPolicy):
        """Windows Proactor Event Loop Policy for Python 3.6"""

        _loop_factory = asyncio.ProactorEventLoop  # type: ignore

    # Set ProactorLoop as the default policy on Windows in Python versions <3.8
    if sys.version_info < (3, 7):
        asyncio.set_event_loop_policy(ProactorLoopPolicy36())
    elif sys.version_info < (3, 8):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def redirect_output(output: str, target: TextIOWrapper) -> None:
    """Write the given text to an instance of TextIOWrapper"""
    target.write(output or "")


def log_to_file(text: str, target: Union[str, Path]) -> None:
    """Log the given text to a file"""
    with open(target, "a" if Path(target).exists() else "w", encoding="utf-8") as file:
        file.write(text)


def handle_output(output: str, redirect: Optional[Union[str, Path, TextIOWrapper]] = None) -> str:
    """Log and return the given text, optionally redirect it to a file or a TextIOWrapper"""
    if not output.strip():
        log.info("No output from subprocess")
        return ""
    log.info("Output from subprocess:")
    log.info(output.strip())
    if isinstance(redirect, (str, Path)):
        log_to_file(output, redirect)
    if isinstance(redirect, TextIOWrapper):
        redirect_output(output, redirect)
    return output


def run_cmd(
    cmd: Union[List[str], str],
    cwd: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[int] = None,
    redirect: Optional[Union[str, Path, TextIOWrapper]] = None,
) -> str:
    """Execute a command with the given options and return its output"""
    if isinstance(cmd, str):
        args = shlex.split(cmd)
    else:
        args = cmd
    cwd = cwd or os.getcwd()
    env = env or os.environ.copy()
    log.info("Calling: %s", " ".join(args))
    try:
        output = subprocess.run(
            args,
            shell=is_windows(),
            cwd=cwd,
            env=env,
            timeout=timeout,
            universal_newlines=True,
            check=True,
            stdout=PIPE,
            stderr=STDOUT,  # combine stdout,stderr streams
        ).stdout
    except subprocess.CalledProcessError as err:
        handle_output(err.stdout, redirect)
        raise
    return handle_output(output, redirect)


async def run_cmd_async(
    cmd: Union[List[str], str],
    cwd: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[int] = None,
    redirect: Optional[Union[str, Path, TextIOWrapper]] = None,
) -> str:
    """Execute a command asynchronously with the given options and return its output"""
    if isinstance(cmd, str):
        args = shlex.split(cmd)
    else:
        args = cmd
    cwd = cwd or os.getcwd()
    env = env or os.environ.copy()
    log.info("Calling asynchronously: %s", " ".join(args))
    try:
        proc = await create_subprocess_exec(
            *args,
            stdout=PIPE,
            stderr=STDOUT,  # combine stdout,stderr streams
            cwd=cwd,
            env=env,
        )
        stdout, _ = await wait_for(proc.communicate(), timeout=timeout)
        await proc.wait()
    except subprocess.CalledProcessError as err:
        handle_output(err.stdout.decode("utf-8"), redirect)
        raise
    return handle_output(stdout.decode("utf-8"), redirect)


@with_no_logging
def run_cmd_silent(
    cmd: Union[List[str], str],
    cwd: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
    timeout: Optional[int] = None,
) -> bool:
    """Execute a command silently with the given options and return whether it succeeded or not"""
    try:
        run_cmd(cmd=cmd, cwd=cwd, env=env, timeout=timeout, redirect=None)
        return True
    except Exception:  # Do not raise here to prevent leaking sensitive data such as the cmd args
        return False
