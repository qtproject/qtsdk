#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
#
# Copyright (C) 2023 The Qt Company Ltd.
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
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from subprocess import DEVNULL
from time import time
from typing import List

import pysftp  # type: ignore

from installer_utils import PackagingError
from logging_util import init_logger
from read_remote_config import download_remote_file_sftp, get_pkg_value

log = init_logger(__name__, debug_mode=False)
timestamp = datetime.fromtimestamp(time()).strftime('%Y-%m-%d--%H:%M:%S')


def _handle_signing(file_path: str, verify_signtool: str) -> None:
    """
    Sign executable from file_path using AzureSignTool with the configured options
    Verify the signing with the verify_signtool specified

    Args:
        file_path: A string path to the file to be signed
        verify_signtool: Name of the signtool executable used for verification

    Raises:
        PackagingError: When signing or verification is unsuccessful
    """
    remote_config = Path(os.environ["WINDOWS_SIGNKEYS_PATH"])
    kvu = get_pkg_value("kvu", "", remote_config)
    kvi = get_pkg_value("kvi", "", remote_config)
    kvs = get_pkg_value("kvs", "", remote_config)
    kvc = get_pkg_value("kvc", "", remote_config)
    tr_sect = get_pkg_value("tr", "", remote_config)
    cmd_args_sign = ["AzureSignTool.exe", "sign", "-kvu", kvu, "-kvi", kvi, "-kvs", kvs, "-kvc", kvc, "-tr", tr_sect, "-v", file_path]
    log_entry = cmd_args_sign[:]
    log_entry[3] = "****"
    log_entry[5] = "****"
    log_entry[7] = "****"
    log_entry[9] = "****"
    log_entry[11] = "****"
    log.info("Calling: %s", ' '.join(log_entry))
    sign_result = subprocess.run(cmd_args_sign, stdout=DEVNULL, stderr=DEVNULL, check=False)
    if sign_result.returncode != 0:
        raise PackagingError(f"Package {file_path} signing with error {sign_result.returncode}")
    log.info("Successfully signed: %s", file_path)
    cmd_args_verify: List[str] = [verify_signtool, "verify", "-pa", file_path]
    verify_result = subprocess.run(cmd_args_verify, stdout=DEVNULL, stderr=DEVNULL, check=False)
    if verify_result.returncode != 0:
        raise PackagingError(f"Failed to verify {file_path} with error {verify_result.returncode}")
    log.info("Successfully verified: %s", file_path)


def download_signing_tools(signtool: Path) -> None:
    try:
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None
        download_remote_file_sftp(remote_path=signtool)
    except PackagingError:
        raise PackagingError("Failed to download signing tools!") from None


def sign_executable(file_path: str) -> None:
    log.info("Signing: %s", file_path)
    try:
        signtool = os.environ["WINDOWS_SIGNTOOL_X64_PATH"]
    except KeyError as err:
        raise PackagingError("Signtool path not found from env") from err
    try:
        download_signing_tools(Path(signtool))
        path = Path(file_path)
        if path.is_dir():
            for subpath in path.rglob('*'):
                if subpath.is_file() and subpath.suffix in ['.exe', '.dll', '.pyd']:
                    _handle_signing(str(subpath), Path(signtool).name)
        else:
            _handle_signing(file_path, Path(signtool).name)
    finally:
        Path(Path.cwd() / Path(signtool).name).unlink()


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(prog="Codesign Windows executables and DLLs")
    parser.add_argument("--file", dest="file_to_sign", required=True, help="File or directory to sign")
    args = parser.parse_args(sys.argv[1:])
    sign_executable(args.file_to_sign)


if __name__ == "__main__":
    main()
