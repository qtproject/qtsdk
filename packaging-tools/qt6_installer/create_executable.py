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
import shutil
from logging_util import init_logger
from typing import Dict, List
from runner import async_exec_cmd
from python_env import create_venv, locate_venv
from installer_utils import is_valid_url_path


log = init_logger(__name__, debug_mode=False)


def locate_executable_from_venv(pythonInstallDir: str, fileName: str, env: Dict[str, str]) -> str:
    venvPath = locate_venv(pythonInstallDir, env)
    filePath = os.path.join(venvPath, "bin", fileName)
    assert os.path.isfile(filePath), "Could not find given file '{0}' from: {1}".format(fileName, filePath)
    return filePath


async def clone_repo(url: str, destinationDir: str, env: Dict[str, str]) -> None:
    assert not os.path.isdir(destinationDir), "Destination dir already exists: {0}".format(destinationDir)
    os.makedirs(os.path.dirname(destinationDir), exist_ok=True)
    log.info("Cloning repo: %s -> %s", url, destinationDir)
    cmd = ['git', 'clone', url, destinationDir]
    await async_exec_cmd(cmd=cmd, timeout=60 * 15, env=env)  # give it 15 mins


async def pip_install_from_checkout(pipenv: str, checkoutDir: str, env: Dict[str, str]) -> None:
    log.info("Installing pip package from git checkout: %s", checkoutDir)
    cmd = [pipenv, 'run', 'pip', 'install', '-e', checkoutDir]
    await async_exec_cmd(cmd=cmd, timeout=60 * 60, env=env)  # give it 60 mins


async def generate_executable(pythonSrc: str, pyinstaller: str, fileNameList: List[str], pipPackages: List[str]) -> str:
    pythonInstallDir, env = await create_venv(pythonSrc)
    pipenv = os.path.join(pythonInstallDir, "bin", "pipenv")
    assert os.path.isfile(pipenv), "Could not find pipenv: '{0}'".format(pipenv)

    _pipPackages = []  # type: List[str]
    for pkg in pipPackages or []:
        if is_valid_url_path(pkg):
            destinationDir = os.path.join(os.getcwd(), "_git_tmp", pkg.split("/")[-1])
            shutil.rmtree(destinationDir, ignore_errors=True)
            await clone_repo(pkg, destinationDir, env)
            _pipPackages.append(destinationDir)
        else:
            _pipPackages.append(pkg)

    for package in _pipPackages:
        await pip_install_from_checkout(pipenv, package, env)

    cmd = [pipenv, 'run', 'pip', 'install', pyinstaller]
    await async_exec_cmd(cmd=cmd, timeout=60 * 15, env=env)  # give it 15 mins
    for fileName in fileNameList:
        # if the path does not point to actual file then we assume it exists under the virtualenv
        _fileName = fileName if os.path.isfile(fileName) else locate_executable_from_venv(pythonInstallDir, fileName, env)
        cmd = [pipenv, 'run', 'pyinstaller', '--console', '--hidden-import=glob', '--onefile', _fileName]
        await async_exec_cmd(cmd=cmd, timeout=60 * 15, env=env)  # give it 15 mins

    destPath = os.path.join(os.getcwd(), "dist")
    generatedFiles = [os.path.join(destPath, x) for x in os.listdir(destPath)]
    assert generatedFiles, "No generated executables found from: {0}".format(destPath)
    log.info("Created executable: %s", generatedFiles)
    return destPath


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Create executable file from given Python file in virtualenv using pyinstaller.")
    parser.add_argument("--python-src", dest="python_src", type=str, default=os.getenv("PYTHON_SRC"), help="Path to local checkout or .zip/.7z/.tar.gz")
    parser.add_argument("--pyinstaller", dest="pyinstaller", type=str, default=os.getenv("PYINSTALLER_SRC"), help="Location of pyinstaller .zip/.7z/.tar.gz")
    parser.add_argument("--add-pip-package", dest="pip_packages", action='append', help="Install Python packages from git url or local checkout")
    parser.add_argument("--file", dest="file_list", action='append', required=True, help="Absolute path to the file which needs to be transformed as executable")

    args = parser.parse_args(sys.argv[1:])
    loop = asyncio.get_event_loop()
    loop.run_until_complete(generate_executable(args.python_src, args.pyinstaller, args.file_list, args.pip_packages))
