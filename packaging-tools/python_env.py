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

import argparse
import os
import platform
import sys
from asyncio import get_event_loop
from shutil import rmtree
from typing import Dict, Tuple

from bld_python import build_python
from installer_utils import download_archive, is_valid_url_path
from logging_util import init_logger
from runner import async_exec_cmd, exec_cmd

log = init_logger(__name__, debug_mode=False)


class PythonEnvError(Exception):
    pass


def get_env(pythonInstallation: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    system = platform.system().lower()
    libDir = os.path.join(pythonInstallation, "lib")
    binDir = os.path.join(pythonInstallation, "bin")
    if "windows" in system:
        binDir = os.path.join(pythonInstallation, "PCbuild", "amd64")
        assert os.path.isdir(binDir), "The python binary directory did not exist: {0}".format(
            binDir
        )
        env["LIB_PATH"] = binDir
        env["PATH"] = binDir + ";" + os.environ.get("PATH", "")
        env["SYSTEMROOT"] = os.environ["SYSTEMROOT"]
        env["HOMEPATH"] = os.environ["HOMEPATH"]
    elif "darwin" in system:
        env["DYLD_LIBRARY_PATH"] = libDir
        env["PATH"] = binDir + ":" + os.environ.get("PATH", "")
    else:
        env["LD_LIBRARY_PATH"] = libDir
        env["PATH"] = binDir + ":" + os.environ.get("PATH", "")
    return env


def locate_venv(pipenv: str, env: Dict[str, str]) -> str:
    output = exec_cmd([pipenv, "--venv"], timeout=60, env=env)
    return output.splitlines()[0].strip()


async def install_pip(getPipFile: str, pythonInstallation: str) -> str:
    log.info("Installing pip...")
    if is_valid_url_path(getPipFile):
        pipTmpDir = os.path.join(os.getcwd(), "pip_install_tmp")
        rmtree(pipTmpDir, ignore_errors=True)
        os.makedirs(pipTmpDir)
        getPipFile = download_archive(getPipFile, pipTmpDir)
    elif not (getPipFile and os.path.isfile(getPipFile)):
        raise PythonEnvError("Could not install pip from: {0}".format(getPipFile))

    pythonExe = os.path.join(pythonInstallation, "PCBuild", "amd64", "python.exe")
    assert os.path.isfile(pythonExe), "The 'python' executable did not exist: {0}".format(
        pythonExe
    )
    installPipCmd = [pythonExe, getPipFile]
    await async_exec_cmd(installPipCmd)
    return os.path.join(pythonInstallation, "Scripts", "pip3.exe")


async def create_venv(pythonSrc: str, getPipFile: str) -> Tuple[str, str, Dict[str, str]]:
    log.info("Creating Python virtual env..")
    system = platform.system().lower()
    prefix = os.path.join(os.path.expanduser("~"), "_python_bld")
    await build_python(pythonSrc, prefix)
    env = get_env(prefix)
    if "windows" in system:
        pip3 = await install_pip(getPipFile, prefix)
    else:
        pip3 = os.path.join(prefix, "bin", "pip3")
    assert os.path.isfile(pip3), "The 'pip3' executable did not exist: {0}".format(pip3)
    log.info(f"Installing pipenv using: {pip3}")
    cmd = [pip3, "install", "pipenv"]
    await async_exec_cmd(cmd=cmd, timeout=60 * 15, env=env)  # give it 15 mins
    if "windows" in system:
        pipenv = os.path.join(prefix, "Scripts", "pipenv.exe")
    else:
        pipenv = os.path.join(prefix, "bin", "pipenv")
    assert os.path.isfile(pipenv), "The 'pipenv' executable did not exist: {0}".format(pipenv)
    cmd = [pipenv, "install"]
    log.info("Installing pipenv requirements into: %s", prefix)
    await async_exec_cmd(cmd=cmd, timeout=60 * 30, env=env)  # give it 30 mins
    venv_folder = locate_venv(pipenv, env)
    print(f"The pipenv virtualenv is created located in: {venv_folder}")
    return (venv_folder, pipenv, env)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Create Python virtual env")
    parser.add_argument(
        "--python-src",
        dest="python_src",
        type=str,
        default=os.getenv("PYTHON_SRC"),
        help="Path to local checkout or .zip/.7z/.tar.gz",
    )
    parser.add_argument(
        "--get-pip-file",
        dest="get_pip_file",
        type=str,
        default=os.getenv("GET_PIP_FILE"),
        help="Path to get-pip.py needed for installing pip on Windows",
    )
    args = parser.parse_args(sys.argv[1:])
    loop = get_event_loop()
    loop.run_until_complete(create_venv(args.python_src, args.get_pip_file))
