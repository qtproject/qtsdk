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
import sh
import sys
import inspect
import asyncio
import typing
import subprocess
current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)


_asyncio_test_loop = asyncio.get_event_loop()


def asyncio_test(f):
    assert asyncio.iscoroutinefunction(f)
    return lambda *args, **kwargs: _asyncio_test_loop.run_until_complete(f(*args, **kwargs))


def asyncio_test_parallel_data(*data_args, unpack=True):
    if not unpack:
        # then double pack so we can unpack anyway
        data_args = ((d,) for d in data_args)

    def decorator(f: typing.Callable[..., typing.Any]):
        assert asyncio.iscoroutinefunction(f)

        def wrapped(*args, **kwargs):
            calls = (f(*args, *d, **kwargs) for d in data_args)
            _asyncio_test_loop.run_until_complete(asyncio.gather(*calls))
        return wrapped
    return decorator

def isInternalFileServerReachable() -> bool:
        packageServer = "ci-files02-hki.intra.qt.io"
        ping = sh.which("ping")
        try:
            ret = subprocess.run([ping, "-c", "1", packageServer], timeout=5, capture_output=True)
            return ret.returncode == 0
        except subprocess.TimeoutExpired:
            pass
        return False
