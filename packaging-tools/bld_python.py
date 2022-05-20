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
import re
import sys
from multiprocessing import cpu_count
from shutil import copytree, rmtree, which
from subprocess import check_output

from installer_utils import ch_dir, download_archive, extract_archive, is_valid_url_path
from logging_util import init_logger
from runner import run_cmd, run_cmd_async

if sys.version_info < (3, 7):
    import asyncio_backport as asyncio
else:
    import asyncio

log = init_logger(__name__, debug_mode=False)


class BldPythonError(Exception):
    pass


async def prepare_sources(src: str, tmp_base_dir: str) -> str:
    log.info("Preparing sources: %s", src)
    src_tmp_dir = os.path.join(tmp_base_dir, "src_dir")
    rmtree(src_tmp_dir, ignore_errors=True)
    if os.path.isdir(src):
        if "windows" in platform.system().lower():
            copytree(src, src_tmp_dir)
        else:
            return src
    elif os.path.isfile(src):
        os.makedirs(src_tmp_dir)
        await extract_archive(src, src_tmp_dir)
    elif is_valid_url_path(src):
        os.makedirs(src_tmp_dir)
        dest_file = download_archive(src, tmp_base_dir)
        await extract_archive(dest_file, src_tmp_dir)
    else:
        raise BldPythonError(f"Could not prepare sources from: {src}")
    return src_tmp_dir


def locate_source_root(search_dir: str) -> str:
    for root, _, files in os.walk(search_dir):
        if "configure" in files and os.path.isfile(os.path.join(root, "configure")):
            return root
    raise BldPythonError(f"Could not find source root directory from: {search_dir}")


async def create_symlink(python_dir: str) -> None:
    python_exe = os.path.join(python_dir, 'python.exe')
    assert os.path.isfile(python_exe), f"The 'python' executable did not exist: {python_exe}"
    version_cmd = [python_exe, '--version']
    version_output = check_output(version_cmd, shell=True).decode("utf-8")
    match = re.search(r'(\d+)\.(\d+)\.(\d+)', version_output)
    if match:
        destination = os.path.join(python_dir, 'python' + match.group(1) + match.group(2) + '.exe')
        os.symlink(python_exe, destination)
        log.info("Symbolic link created from %s to %s", python_exe, destination)
    else:
        raise BldPythonError(f"Could not parse version output: {version_output}")


async def _build_python_win(src_dir: str) -> str:
    log.info("Building..")
    log.info("Source dir: %s", src_dir)
    build_bat = os.path.join(src_dir, 'PCbuild', 'build.bat')
    assert os.path.isfile(build_bat), f"The 'build.bat' batch file did not exist: {build_bat}"
    await run_cmd_async(cmd=[build_bat])
    dest_dir = os.path.join(src_dir, 'PCbuild', 'amd64')
    assert os.path.isdir(dest_dir), f"The build destination directory did not exist: {dest_dir}"
    await create_symlink(dest_dir)
    log.info("Python built successfully and installed to: %s", dest_dir)
    return src_dir


async def build_python_win(src: str) -> str:
    base_dir = os.path.join(os.getcwd(), "python_bld_tmp")
    os.makedirs(base_dir, exist_ok=True)
    src_dir = await prepare_sources(src, base_dir)
    source_root_dir = locate_source_root(src_dir)
    return await _build_python_win(source_root_dir)


async def _build_python(src_dir: str, bld_dir: str, prefix: str) -> str:
    log.info("Building..")
    log.info("  Source dir: %s", src_dir)
    log.info("  Build dir: %s", bld_dir)
    log.info("  Prefix: %s", prefix)
    system = platform.system().lower()
    thread_count = str(cpu_count())
    if "darwin" in system:
        openssl_query_cmd = ["brew", "--prefix", "openssl"]
        openssl_path = run_cmd(cmd=openssl_query_cmd)
        if not os.path.exists(openssl_path):
            raise BldPythonError(
                "Could not find OpenSSL path. Please check that the required brew formula is installed."
            )
        configure_cmd = [
            os.path.join(src_dir, 'configure'),
            '--enable-framework',
            '--with-openssl=' + openssl_path,
            '--prefix=' + prefix
        ]
        make_cmd = ['make', '-j' + thread_count]
        make_install_cmd = ['make', 'install']
    else:
        configure_cmd = [
            os.path.join(src_dir, 'configure'),
            '--enable-shared',
            '--prefix=' + prefix
        ]
        make_cmd = ['make', '-j' + thread_count]
        make_install_cmd = ['make', 'install']

    rmtree(bld_dir, ignore_errors=True)
    os.makedirs(bld_dir)

    with ch_dir(bld_dir):
        await run_cmd_async(cmd=configure_cmd)
        await run_cmd_async(cmd=make_cmd)
        await run_cmd_async(cmd=make_install_cmd)
    log.info("Python built successfully and installed to: %s", prefix)
    return prefix


async def build_python(src: str, prefix: str) -> str:
    if "windows" in platform.system().lower():
        return await build_python_win(src)
    if os.path.isdir(prefix):
        log.info("Deleting existing Python build from: %s", prefix)
        rmtree(prefix, ignore_errors=True)
    base_dir = os.path.join(os.getcwd(), "python_bld_tmp")
    os.makedirs(base_dir, exist_ok=True)
    src_dir = await prepare_sources(src, base_dir)
    bld_dir = os.path.join(base_dir, "build_dir")
    source_root_dir = locate_source_root(src_dir)
    return await _build_python(source_root_dir, bld_dir, prefix)


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(prog="Script to build Python from sources")
    parser.add_argument("--src", dest="src", type=str, default=os.getenv("PYTHON_SRC"), help="Path to local checkout or .zip/.7z/.tar.gz")
    parser.add_argument("--prefix", dest="prefix", type=str, default=os.path.join(os.path.expanduser("~"), "_python_bld"))
    args = parser.parse_args(sys.argv[1:])

    for tool in ["7z", "tar"]:
        if not which(tool):
            raise SystemExit(f"Could not find required tool '{tool}' from the system. Aborting..")

    asyncio.run(build_python(args.src, args.prefix))


if __name__ == "__main__":
    main()
