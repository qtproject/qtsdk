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
import subprocess
import sys
from subprocess import PIPE
from typing import Any, Callable

from bld_utils import is_windows
from installer_utils import PackagingError
from read_remote_config import get_pkg_value

if sys.version_info < (3, 7):
    from asyncio_backport import run as asyncio_run
else:
    from asyncio import run as asyncio_run

if not is_windows():
    import sh  # type: ignore


def asyncio_test(func: Any) -> Any:
    assert asyncio.iscoroutinefunction(func)
    return lambda *args, **kwargs: asyncio_run(func(*args, **kwargs))


def asyncio_test_parallel_data(*data_args, unpack: bool = True) -> Any:  # type: ignore
    # then double pack so we can unpack anyway
    data_args = ((d,) for d in data_args) if not unpack else data_args  # type: ignore

    def decorator(func: Callable[..., Any]) -> Callable[[Any], Any]:
        assert asyncio.iscoroutinefunction(func)

        async def wrapped(*args, **kwargs):  # type: ignore
            calls = (func(*args, *d, **kwargs) for d in data_args)
            await asyncio.gather(*calls)

        return wrapped
    return decorator


def is_internal_file_server_reachable() -> bool:
    try:
        package_server = get_pkg_value("PACKAGE_STORAGE_SERVER")
        ping = sh.which("ping")
        ret = subprocess.run(args=[ping, "-c", "1", package_server], timeout=5, stdout=PIPE, stderr=PIPE, check=False)
        return ret.returncode == 0
    except (sh.ErrorReturnCode, PackagingError):
        return False
