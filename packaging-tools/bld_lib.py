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
import logging
import os
import platform as plat  # import as plat to not shadow the "import platform"
import re
import shutil
import sys
import tarfile
from glob import glob
from shutil import which
from subprocess import CalledProcessError, check_call
from time import gmtime, strftime
from typing import List, Tuple
from urllib.parse import urlparse
from urllib.request import urlretrieve

from rainbow_logging_handler import RainbowLoggingHandler  # type: ignore

from bld_utils import is_windows
from read_remote_config import get_pkg_value
from remote_uploader import RemoteUploader

LOG_FMT_CI = "%(asctime)s %(levelname)s:%(filename)s:%(lineno)d(%(process)d): %(message)s"
log = logging.getLogger("Bld")
log.setLevel(logging.INFO)
# Unify format of all messages
handler = RainbowLoggingHandler(sys.stderr, color_asctime=(None, None, False))

formatter = logging.Formatter(LOG_FMT_CI)
handler.setFormatter(formatter)
log.addHandler(handler)


def findFile(searchPath: str, fileName: str) -> str:
    for root, dirs, files in os.walk(searchPath):
        if fileName in files:
            return os.path.join(root, fileName)
    assert False, f"Unable to find: {fileName} from: {searchPath}"


def collectLibs(searchPath: str) -> List[str]:
    for root, dirs, files in os.walk(searchPath):
        for dir in dirs:
            if dir == "lib":
                return [os.path.join(root, dir, x) for x in os.listdir(os.path.join(root, dir))]
    assert False, f"Unable to find: 'lib' from: {searchPath}"


def parseQtVersion(downloadUrlPath: str) -> str:
    regex = re.compile(r'([\d.]+)')
    for item in downloadUrlPath.split("/"):
        m = regex.search(item)
        if m:
            return m.groups()[0]
    assert False, f"Could not parse Qt version number from: {downloadUrlPath}"


def downloadQtPkg(args: argparse.Namespace, currentDir: str) -> Tuple[str, str]:
    urlRes = urlparse(args.qtpkg)
    assert urlRes.scheme and urlRes.netloc and urlRes.path, f"Invalid URL: {args.qtpkg}"
    qtVersion = parseQtVersion(urlRes.path)

    saveAs = os.path.join(currentDir, os.path.basename(urlRes.path))
    if os.path.exists(saveAs):
        log.info("Using existing: %s", saveAs)
    else:
        log.info("Downloading: %s into: %s", args.qtpkg, saveAs)
        urlretrieve(args.qtpkg, saveAs)

    return saveAs, qtVersion


def extractArchive(saveAs: str, currentDir: str) -> str:
    qtDestDir = os.path.join(currentDir, "qt_pkg")
    if not os.path.exists(qtDestDir):
        os.makedirs(qtDestDir)
        log.info("Extracting to: %s", qtDestDir)
        if saveAs.endswith("tar.gz"):
            with tarfile.open(saveAs, "r:gz") as tar:
                tar.extractall(qtDestDir)
        elif saveAs.endswith(".7z"):
            try:
                os.chdir(qtDestDir)
                check_call(['7z', 'x', saveAs])
            except Exception as e:
                log.error("Extracting 7z file failed: %s", str(e))
                raise
            finally:
                os.chdir(currentDir)
    return qtDestDir


def build(qtDestDir: str, currentDir: str) -> str:
    if is_windows():
        qmakeToolName = "qmake.exe"
        makeToolName = "nmake"
    else:
        qmakeToolName = "qmake"
        makeToolName = "make"

    qmakeTool = findFile(qtDestDir, qmakeToolName)
    assert qmakeTool, f"Could not find: {qmakeToolName} from: {qtDestDir}"

    # patch
    with open(os.path.join(os.path.dirname(qmakeTool), "qt.conf"), "w+") as f:
        f.write("[Paths]\n")
        f.write("Prefix=..\n")

    pro_files_list = glob(os.path.join(args.src_path, "*.pro"))
    assert pro_files_list, f"Could not find .pro file(s) from: {args.src_path}"
    proFile = pro_files_list[0]
    log.info("Using .pro file: %s", proFile)

    installRootDir = os.path.join(currentDir, "lib_install_root")
    shutil.rmtree(installRootDir, ignore_errors=True)
    os.makedirs(installRootDir)

    bldDir = os.path.join(currentDir, "lib_bld")
    shutil.rmtree(bldDir, ignore_errors=True)  # ignore if path did not exist
    os.makedirs(bldDir)

    try:
        os.chdir(bldDir)
        check_call([qmakeTool, proFile])
        check_call([makeToolName])
        # on windows chhop out the drive letter (e.g. 'C:'"
        installRoot = installRootDir[2:] if is_windows() else installRootDir
        check_call([makeToolName, 'install', 'INSTALL_ROOT=' + installRoot])
    except CalledProcessError as buildError:
        log.error("Failed to build the project: %s", str(buildError))
        raise
    except Exception as e:
        log.error("Something bad happened: %s", str(e))
        raise
    finally:
        os.chdir(currentDir)

    return installRootDir


def archive(args: argparse.Namespace, installRootDir: str, currentDir: str) -> str:
    # strip out drive letter on Windows e.g. 'C:'
    srcPath = args.src_path[2:] if is_windows() else args.src_path
    archivePath = os.path.join(installRootDir, srcPath.lstrip(os.path.sep))
    log.info("Archiving from: %s", archivePath)

    libs = collectLibs(installRootDir)
    for lib in libs:
        shutil.copy2(lib, archivePath)

    arch = "x86_64" if sys.maxsize > 2**32 else "x86"
    artifactsFileName = "artifacts-" + plat.system().lower() + "-" + arch + ".7z"
    artifactsFilePath = os.path.join(currentDir, artifactsFileName)
    try:
        os.chdir(archivePath)
        check_call(['7z', 'a', '-m0=lzma2', '-mmt=16', artifactsFilePath, '*'])
    except Exception as e:
        print(str(e))
        raise
    finally:
        os.chdir(currentDir)

    log.info("Created artifact: %s", artifactsFilePath)
    return artifactsFilePath


def handleBuild(args: argparse.Namespace) -> None:
    currentDir = os.getcwd()

    saveAs, qtVersion = downloadQtPkg(args, currentDir)
    qtDestDir = extractArchive(saveAs, currentDir)
    installRootDir = build(qtDestDir, currentDir)
    artifactsFilePath = archive(args, installRootDir, currentDir)

    remoteUploader = RemoteUploader(False, args.remote_server, args.username, args.remote_base_path)
    remoteUploader.init_snapshot_upload_path(args.project_name, qtVersion, args.build_id)
    remoteUploader.copyToRemote(artifactsFilePath)
    remoteUploader.updateLatestSymlink()


if __name__ == "__main__":
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
        log.error("Could not find '7z' from the system. This tool is needed for notarization. Aborting..")
        sys.exit(1)

    handleBuild(args)
