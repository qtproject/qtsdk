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
import argparse
import logging
import logging_util
from runner import exec_cmd
from python_env import create_venv, locate_venv


log = logging.getLogger("qtinstaller.createexec")


def locate_executable_from_venv(fileName: str) -> str:
    venvPath = locate_venv()
    filePath = os.path.join(venvPath, "bin", fileName)
    assert os.path.isfile(filePath), "Could not find given file '{0}' from: {1}".format(fileName, filePath)
    return filePath


async def generate_executable(pythonSrc: str, pyinstaller: str, fileName: str) -> str:
    env = await create_venv(pythonSrc)

    cmd = ['pipenv', 'run', 'pip', 'install', pyinstaller]
    await exec_cmd(cmd=cmd, timeout=60 * 15, env=env)  # give it 15 mins
    cmd = ['pipenv', 'run', 'pyinstaller', '--onefile', locate_executable_from_venv(fileName)]
    await exec_cmd(cmd=cmd, timeout=60 * 15, env=env)  # give it 15 mins

    destPath = os.path.join(os.getcwd(), "dist")
    generatedFiles = [os.path.join(destPath, x) for x in os.listdir(destPath)]
    assert generatedFiles, "No generated executables found from: {0}".format(destPath)
    log.info("Created executable: %s", generatedFiles)
    return destPath


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Create executable file from given Python file in virtualenv using pyinstaller.")
    parser.add_argument("--python-src", dest="python_src", type=str, default=os.getenv("PYTHON_SRC"), help="Path to local checkout or .zip/.7z/.tar.gz")
    parser.add_argument("--pyinstaller", dest="pyinstaller", type=str, default=os.getenv("PYINSTALLER_SRC"), help="Location of pyinstaller .zip/.7z/.tar.gz")
    parser.add_argument("--file", dest="file", type=str, required=True, help="Name of the Python file inside the virtual env which is transformed as executable")

    args = parser.parse_args(sys.argv[1:])
    loop = asyncio.get_event_loop()
    loop.run_until_complete(generate_executable(args.python_src, args.pyinstaller, args.file))
