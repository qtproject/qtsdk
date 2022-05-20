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
import platform as plat  # import as plat to not shadow the "import platform"
import re
import shutil
import sys
import tarfile
from glob import glob
from pathlib import Path
from shutil import which
from subprocess import CalledProcessError
from time import gmtime, strftime
from typing import List, Tuple
from urllib.parse import urlparse
from urllib.request import urlretrieve

from bld_utils import is_windows
from logging_util import init_logger
from read_remote_config import get_pkg_value
from remote_uploader import RemoteUploader
from runner import run_cmd

log = init_logger(__name__, debug_mode=False)


def find_file(search_path: str, file_name: str) -> str:
    for root, _, files in os.walk(search_path):
        if file_name in files:
            return os.path.join(root, file_name)
    assert False, f"Unable to find: {file_name} from: {search_path}"


def collect_libs(search_path: str) -> List[str]:
    for root, dirs, _ in os.walk(search_path):
        for dir_name in dirs:
            if dir_name == "lib":
                return [str(Path(root, dir_name, x)) for x in os.listdir(Path(root, dir_name))]
    assert False, f"Unable to find: 'lib' from: {search_path}"


def parse_qt_version(download_url_path: str) -> str:
    regex = re.compile(r'([\d.]+)')
    for item in download_url_path.split("/"):
        matches = regex.search(item)
        if matches:
            return matches.groups()[0]
    assert False, f"Could not parse Qt version number from: {download_url_path}"


def download_qt_pkg(args: argparse.Namespace, current_dir: str) -> Tuple[str, str]:
    url_res = urlparse(args.qtpkg)
    assert url_res.scheme and url_res.netloc and url_res.path, f"Invalid URL: {args.qtpkg}"
    qt_version = parse_qt_version(url_res.path)

    save_as = os.path.join(current_dir, os.path.basename(url_res.path))
    if os.path.exists(save_as):
        log.info("Using existing: %s", save_as)
    else:
        log.info("Downloading: %s into: %s", args.qtpkg, save_as)
        urlretrieve(args.qtpkg, save_as)

    return save_as, qt_version


def extract_archive(save_as: str, current_dir: str) -> str:
    qt_dest_dir = os.path.join(current_dir, "qt_pkg")
    if not os.path.exists(qt_dest_dir):
        os.makedirs(qt_dest_dir)
        log.info("Extracting to: %s", qt_dest_dir)
        if save_as.endswith("tar.gz"):
            with tarfile.open(save_as, "r:gz") as tar:
                tar.extractall(qt_dest_dir)
        elif save_as.endswith(".7z"):
            try:
                run_cmd(cmd=["7z", "x", save_as], cwd=qt_dest_dir)
            except CalledProcessError as error:
                log.error("Extracting 7z file failed: %s", str(error))
                raise
    return qt_dest_dir


def build(args: argparse.Namespace, qt_dest_dir: str, current_dir: str) -> str:
    if is_windows():
        qmake_tool_name = "qmake.exe"
        make_tool_name = "nmake"
    else:
        qmake_tool_name = "qmake"
        make_tool_name = "make"

    qmake_tool = find_file(qt_dest_dir, qmake_tool_name)
    assert qmake_tool, f"Could not find: {qmake_tool_name} from: {qt_dest_dir}"

    # patch
    with open(os.path.join(os.path.dirname(qmake_tool), "qt.conf"), "w+", encoding="utf-8") as handle:
        handle.write("[Paths]\n")
        handle.write("Prefix=..\n")

    pro_files_list = glob(os.path.join(args.src_path, "*.pro"))
    assert pro_files_list, f"Could not find .pro file(s) from: {args.src_path}"
    pro_file = pro_files_list[0]
    log.info("Using .pro file: %s", pro_file)

    install_root_dir = os.path.join(current_dir, "lib_install_root")
    shutil.rmtree(install_root_dir, ignore_errors=True)
    os.makedirs(install_root_dir)

    bld_dir = os.path.join(current_dir, "lib_bld")
    shutil.rmtree(bld_dir, ignore_errors=True)  # ignore if path did not exist
    os.makedirs(bld_dir)

    try:
        run_cmd(cmd=[qmake_tool, pro_file], cwd=bld_dir)
        run_cmd(cmd=[make_tool_name], cwd=bld_dir)
        # on Windows chop out the drive letter (e.g. 'C:')
        install_root = install_root_dir[2:] if is_windows() else install_root_dir
        run_cmd(cmd=[make_tool_name, "install", "INSTALL_ROOT=" + install_root], cwd=bld_dir)
    except CalledProcessError as build_error:
        log.error("Failed to build the project: %s", str(build_error))
        raise
    except Exception as error:
        log.error("Something bad happened: %s", str(error))
        raise

    return install_root_dir


def archive(args: argparse.Namespace, install_root_dir: str, current_dir: str) -> str:
    # strip out drive letter on Windows e.g. 'C:'
    src_path = args.src_path[2:] if is_windows() else args.src_path
    archive_path = os.path.join(install_root_dir, src_path.lstrip(os.path.sep))
    log.info("Archiving from: %s", archive_path)

    libs = collect_libs(install_root_dir)
    for lib in libs:
        shutil.copy2(lib, archive_path)

    arch = "x86_64" if sys.maxsize > 2**32 else "x86"
    artifacts_file_name = "artifacts-" + plat.system().lower() + "-" + arch + ".7z"
    artifacts_file_path = os.path.join(current_dir, artifacts_file_name)
    try:
        run_cmd(["7z", "a", "-m0=lzma2", "-mmt=16", artifacts_file_path, "*"], cwd=archive_path)
    except CalledProcessError as error:
        log.error(str(error))
        raise

    log.info("Created artifact: %s", artifacts_file_path)
    return artifacts_file_path


def handle_build(args: argparse.Namespace) -> None:
    current_dir = os.getcwd()

    save_as, qt_version = download_qt_pkg(args, current_dir)
    qt_dest_dir = extract_archive(save_as, current_dir)
    install_root_dir = build(args, qt_dest_dir, current_dir)
    artifacts_file_path = archive(args, install_root_dir, current_dir)

    remote_uploader = RemoteUploader(False, args.remote_server, args.username, args.remote_base_path)
    remote_uploader.init_snapshot_upload_path(args.project_name, qt_version, args.build_id)
    remote_uploader.copy_to_remote(artifacts_file_path)
    remote_uploader.update_latest_symlink()


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(prog="Helper script to build a lib against qtbase artifact.")
    parser.add_argument("--qtpkg", dest="qtpkg", type=str, default=os.getenv("QT_PKG_URL"), help="URL pointing to pre-built Qt bin package.")
    parser.add_argument("--src-path", dest="src_path", type=str, default=os.getenv("SRC_PATH"), help="Path to sources")
    parser.add_argument("--remote-server", dest="remote_server", type=str, default=get_pkg_value("PACKAGE_STORAGE_SERVER"), help="Output server for build artifacts")
    parser.add_argument("--username", dest="username", type=str, default=get_pkg_value("PACKAGE_STORAGE_SERVER_USER"), help="Username for the output server")
    parser.add_argument("--remote-base-path", dest="remote_base_path", type=str, default=os.getenv("PACKAGE_STORAGE_SERVER_BASE_DIR"), help="Base path for output")
    parser.add_argument("--project-name", dest="project_name", type=str, default=os.getenv("PROJECT_NAME"), help="Base path for output")
    parser.add_argument("--build-id", dest="build_id", type=str, default=strftime('%Y%m%d%H%M%S', gmtime()), help="Base path for output")
    args = parser.parse_args(sys.argv[1:])

    assert args.qtpkg, "You must define '--qtpkg'!"
    assert args.src_path, "You must define '--src-path'!"
    assert args.remote_server, "You must define '--remote-server'!"
    assert args.username, "You must define '--username'!"
    assert args.remote_base_path, "You must define '--remote-base-path'!"
    assert args.project_name, "You must define '--project-name'!"
    if not which("7z"):
        raise SystemExit("Could not find '7z' from the system for notarization. Aborting..")

    handle_build(args)


if __name__ == "__main__":
    main()
