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
from pathlib import Path
from shutil import rmtree
from typing import Dict, List

from installer_utils import cd, is_valid_url_path
from logging_util import init_logger
from python_env import create_venv
from runner import async_exec_cmd

log = init_logger(__name__, debug_mode=False)


def locate_file_from_venv(venv_folder: str, file_name: str) -> str:
    log.info("Locating file '%s' from: %s", file_name, venv_folder)
    matches = list(Path(venv_folder).resolve(strict=True).rglob(file_name))
    assert len(matches) == 1, f"Found != 1 matches: {matches}"
    return str(matches.pop())


async def clone_repo(url: str, destination_dir: str, env: Dict[str, str]) -> None:
    assert not os.path.isdir(destination_dir), f"Destination dir already exists: {destination_dir}"
    os.makedirs(os.path.dirname(destination_dir), exist_ok=True)
    log.info("Cloning repo: %s -> %s", url, destination_dir)
    cmd = ["git", "clone", url, destination_dir]
    await async_exec_cmd(cmd=cmd, timeout=60 * 15, env=env)  # give it 15 mins


async def pip_install_from_checkout(pipenv: str, checkout_dir: str, env: Dict[str, str]) -> None:
    log.info("Installing pip package from git checkout: %s", checkout_dir)
    cmd = [pipenv, "run", "pip", "install", "-e", checkout_dir]
    await async_exec_cmd(cmd=cmd, timeout=60 * 60, env=env)  # give it 60 mins


async def pip_install_url(pipenv: str, pip_packages: List[str], env: Dict[str, str]) -> None:
    chekout_folders: List[str] = []
    for pkg in pip_packages or []:
        if is_valid_url_path(pkg):
            destination_dir = os.path.join(os.getcwd(), "_git_tmp", pkg.split("/")[-1])
            rmtree(destination_dir, ignore_errors=True)
            await clone_repo(pkg, destination_dir, env)
            chekout_folders.append(destination_dir)
        else:
            chekout_folders.append(pkg)

    for package in chekout_folders:
        await pip_install_from_checkout(pipenv, package, env)


async def pip_install_pkg(pipenv: str, pip_packages: List[str], env: Dict[str, str]) -> None:
    for pkg in pip_packages:
        cmd = [pipenv, "install", pkg]
        await async_exec_cmd(cmd=cmd, timeout=60 * 15, env=env)  # give it 15 mins


async def generate_executable(
    pipenv: str, env: Dict[str, str], venv_folder: str, source_file: str, hidden_imports: List[str]
) -> str:
    # if the path does not point to actual file then we assume it exists under the virtualenv
    _file_name = (
        source_file
        if os.path.isfile(source_file)
        else locate_file_from_venv(venv_folder, source_file)
    )
    cmd = [
        pipenv,
        "run",
        "pyinstaller",
        "-p",
        venv_folder,
        "--onefile",
        "--console",
        _file_name,
        " ".join([f"--hidden-import={s}" for s in hidden_imports]),
    ]
    # give it 15 mins
    await async_exec_cmd(cmd=cmd, timeout=60 * 15, env=env)

    dest_path = os.path.join(os.getcwd(), "dist")
    generated_files = [os.path.join(dest_path, x) for x in os.listdir(dest_path)]
    assert generated_files, f"No generated executables found from: {dest_path}"
    log.info("Created executable: %s", generated_files)
    return dest_path


async def run(
    python_src: str,
    source_file: str,
    hidden_imports: List[str],
    url_pip_packages: List[str],
    pip_packages: List[str],
    get_pip_file: str,
) -> str:
    work_dir = Path().home() / "_tmp_work_dir_"
    if work_dir.exists():
        rmtree(work_dir)
    work_dir.mkdir(parents=True)

    with cd(str(work_dir)):
        venv_folder, pipenv, env = await create_venv(python_src, get_pip_file)
        await pip_install_url(pipenv, url_pip_packages, env)
        await pip_install_pkg(pipenv, pip_packages, env)
        return await generate_executable(pipenv, env, venv_folder, source_file, hidden_imports)


def get_known_hidden_imports() -> List[str]:
    hidden_imports = [
        "glob",
        "conan.tools.microsoft",
        "conan.tools.gnu",
        "conan.tools.cmake",
        "conan.tools.meson",
    ]
    if platform.system() != "Windows":
        hidden_imports.append("setuptools.msvc")
    return hidden_imports


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(
        prog="Create executable file from given Python file in virtualenv using pyinstaller."
    )
    parser.add_argument(
        "--python-src",
        dest="python_src",
        type=str,
        default=os.getenv("PYTHON_SRC"),
        help="Path to local checkout or .zip/.7z/.tar.gz",
    )
    parser.add_argument(
        "--add-pip-package-url",
        dest="url_pip_packages",
        action="append",
        help="Install Python packages from git url or local checkout",
    )
    parser.add_argument(
        "--add-pip-package",
        dest="pip_packages",
        action="append",
        default=[
            "pyinstaller==4.7",
            "conan==1.42.0",
            "colorama",
            "distro",
            "fasteners",
            "pygments",
            "PyJWT",
            "python-dateutil",
            "PyYAML",
            "requests",
        ],
        help="Install Python packages from PyPI, use syntax: <pkg>==<version>",
    )
    parser.add_argument(
        "--file",
        dest="source_file",
        type=str,
        default="conans" + os.path.sep + "conan.py",
        help="Absolute path to file which needs to be transformed as executable",
    )
    parser.add_argument(
        "--get-pip-file",
        dest="get_pip_file",
        type=str,
        default=os.getenv("GET_PIP_FILE"),
        help="Path to get-pip.py needed for installing pip on Windows",
    )
    parser.add_argument(
        "--hidden-import",
        dest="hidden_imports",
        action="append",
        default=[],
        help="Add hidden Python import to be passed to pyinstaller tool.",
    )

    args = parser.parse_args(sys.argv[1:])
    hidden_imports = get_known_hidden_imports() + args.hidden_imports
    loop = get_event_loop()
    loop.run_until_complete(
        run(
            args.python_src,
            args.source_file,
            hidden_imports,
            args.url_pip_packages,
            args.pip_packages,
            args.get_pip_file,
        )
    )


if __name__ == "__main__":
    main()
