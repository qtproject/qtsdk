#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
##
## Copyright (C) 2022 The Qt Company Ltd.
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
import time
import pysftp
import paramiko
import argparse
import datetime
import subprocess
import configparser
from cryptography.fernet import Fernet
sys.path.insert(1, "qt6_installer")
from installer_utils import PackagingError
from logging_util import init_logger
log = init_logger(__name__, debug_mode=False)
timestamp = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d--%H:%M:%S')


def _get_home_dir() -> str:
    home_dir = os.getenv("HOME") or os.getenv("USERPROFILE")
    if not home_dir:
        raise PackagingError(f"Failed to determine home directory.")
    return home_dir


def _get_private_key() -> bytes:
    log.info("Return the private key in the build agent")
    private_key_path = os.path.join(_get_home_dir(), "sshkeys", os.getenv("ID_RSA_FILE"))
    assert os.path.isfile(private_key_path), f"File not found: {private_key_path}"
    with open(private_key_path, "rb") as private_key:
        return private_key.read()


def _get_decrypt_key() -> bytes:
    log.info("Return the pre-generated Fernet key")
    key_file_path = os.path.join(os.getenv("PKG_NODE_ROOT"), os.getenv("FILES_SHARE_PATH"))
    assert os.path.isfile(key_file_path), f"File not found: {key_file_path}"
    with open(key_file_path, "rb") as decrypt_key:
        return decrypt_key.read()


def _handle_signing(file_path: str):
    config = configparser.ConfigParser()
    config.read(os.path.basename(os.getenv("WINDOWS_SIGNKEYS_PATH")))
    section = config.sections()[0]
    if section in config:
        kvu = config[section]['kvu']
        kvi = config[section]['kvi']
        kvs = config[section]['kvs']
        kvc = config[section]['kvc']
        tr = config[section]['tr']
    cmd_args_sign = ["AzureSignTool.exe", "sign", "-kvu", kvu, "-kvi", kvi, "-kvs", kvs, "-kvc", kvc, "-tr", tr, "-v", file_path]
    log_entry = cmd_args_sign[:]
    log_entry[3] = "****"
    log_entry[5] = "****"
    log_entry[7] = "****"
    log_entry[9] = "****"
    log_entry[11] = "****"
    log.info(f"Calling: {' '.join(log_entry)}")
    sign_result = subprocess.run(cmd_args_sign, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if sign_result.returncode != 0:
        raise PackagingError(f"Package {file_path} signing  with error {sign_result.returncode}")
    log.info(f"Successfully signed: {file_path}")
    cmd_args_verify = [os.path.basename(os.getenv("WINDOWS_SIGNTOOL_X64_PATH")), "verify", "-pa", file_path]
    verify_result = subprocess.run(cmd_args_verify, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if verify_result.returncode != 0:
        raise PackagingError(f"Failed to verify {file_path} with error {verify_result.returncode}")
    log.info(f"Successfully verified: {file_path}")


def decrypt_private_key() -> str:
    log.info("decrypt private key using pre-generated Fernet key")
    key = _get_decrypt_key()
    f = Fernet(key)
    decrypted_key = f.decrypt(_get_private_key())
    temp_key_path = os.getenv("PKG_NODE_ROOT")
    temp_file = os.path.join(temp_key_path, "temp_keyfile")
    with open(temp_file, 'wb') as outfile:
        outfile.write(decrypted_key)
    return temp_file


def download_signing_tools(path_to_key: str):
    try:
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None
        with pysftp.Connection(os.getenv("SFTP_ADDRESS"), username=os.getenv("SFTP_USER"), private_key=path_to_key, cnopts=cnopts) as sftp:
            sftp.get(os.getenv("WINDOWS_SIGNKEYS_PATH"))
            sftp.get(os.getenv("WINDOWS_SIGNTOOL_X64_PATH"))
    except paramiko.SSHException:
        raise PackagingError("FTP authentication failed!") from None


def sign_executable(file_path: str):
    log.info(f"Signing: {file_path}")
    try:
        key_path = decrypt_private_key()
        download_signing_tools(key_path)
        _handle_signing(file_path)
    finally:
        # cleanup temporary files
        if "key_path" in locals():
            os.remove(key_path)
        os.remove(os.path.basename(os.getenv("WINDOWS_SIGNKEYS_PATH")))
        os.remove(os.path.basename(os.getenv("WINDOWS_SIGNTOOL_X64_PATH")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Codesign Windows executables")
    parser.add_argument("--file", dest="file_to_sign", required=True, help="File to sign")
    args = parser.parse_args(sys.argv[1:])
    sign_executable(args.file_to_sign)
