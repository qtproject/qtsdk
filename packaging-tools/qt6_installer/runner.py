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
from logging_util import init_logger
from typing import List, Dict


log = init_logger(__name__, debug_mode=False)


if sys.platform == 'win32':
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)


def exec_cmd(cmd: List[str], timeout=60) -> str:
    log.info("Calling: %s", ' '.join(cmd))
    output = subprocess.check_output(' '.join(cmd), shell=True, timeout=timeout).decode("utf-8").strip()
    print(output)
    return output


async def async_exec_cmd(cmd: List[str], timeout: int=60 * 60, env: Dict[str, str]=os.environ.copy()) -> None:
    p = await asyncio.create_subprocess_exec(*cmd, stdout=None, stderr=subprocess.STDOUT, env=env)
    try:
        log.info("Calling: %s", cmd)
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
