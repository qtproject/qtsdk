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
import sys
from shutil import rmtree
from subprocess import DEVNULL, check_call

from read_remote_config import get_pkg_value

log = logging.getLogger("Sign-utility")
logging.basicConfig(level=logging.INFO, format='%(message)s')


def sign_mac_app(app_path: str, signing_identity: str) -> None:
    assert app_path.endswith(".app"), f"Not a valid path to .app bundle: {app_path}"
    # we need to unlock the keychain first
    unlock_script = "/Users/qt/unlock-keychain.sh"
    check_call([unlock_script])
    # "-o runtime" is required for notarization
    cmd_args = ['codesign', '-o', 'runtime', '--verbose=3', '-r', get_pkg_value("SIGNING_FLAGS"), '-s', signing_identity, app_path]
    check_call(cmd_args)
    log.info("Successfully signed: %s", app_path)


def create_mac_dmg(app_path: str) -> None:
    assert app_path.endswith(".app"), f"Not a valid path to .app bundle: {app_path}"
    installer_name_base = os.path.basename(app_path).split(".app")[0]
    destination_dmg_path = app_path.split(".app")[0] + '.dmg'
    cmd_args = ['hdiutil', 'create', '-srcfolder', app_path, '-volname', installer_name_base]
    cmd_args += ['-format', 'UDBZ', destination_dmg_path, '-ov', '-scrub', '-size', '4g']
    check_call(cmd_args)
    log.info("Successfully created: %s", destination_dmg_path)


def sign_windows_executable(file_path: str):
    sign_tools = ["signtool32.exe", "keys.pfx", "capicom.dll"]
    sign_tools_temp_dir = r'C:\Utils\sign_tools_temp'
    for item in sign_tools:
        dst = os.path.join(sign_tools_temp_dir, item)
        curl_cmd_args = ['curl', "--fail", "-L", "--retry", "5", "--retry-delay", "30", "-o", dst,
                         '--create-dirs', get_pkg_value("SIGN_TOOLS_ADDR") + item]
        check_call(curl_cmd_args)
    cmd_args = [os.path.join(sign_tools_temp_dir, 'signtool32.exe'), 'sign', '/v', '/du', get_pkg_value("SIGNING_SERVER"), '/p', get_pkg_value("SIGNING_PASSWORD")]
    cmd_args += ['/tr', get_pkg_value("TIMESTAMP_SERVER"), '/f', os.path.join(sign_tools_temp_dir, 'keys.pfx'), '/td', "sha256", '/fd', "sha256", file_path]
    log_entry = cmd_args[:]
    log_entry[4] = "****"
    log_entry[6] = "****"
    log.info("Calling: %s", " ".join(log_entry))
    check_call(cmd_args, stdout=DEVNULL, stderr=DEVNULL)
    rmtree(sign_tools_temp_dir)
    log.info("Successfully signed: %s", file_path)


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(prog="Helper script to sign macOS .app bundle and create .dmg from it or sign a Windows .exe")
    subparsers = parser.add_subparsers(dest='command')

    app_parser = subparsers.add_parser("mac")
    exe_parser = subparsers.add_parser("win")

    app_parser.add_argument("--file", dest="file_path", required=True, help="Full path to .app file")
    app_parser.add_argument("--signing-identity", default=get_pkg_value("SIGNING_IDENTITY"))

    exe_parser.add_argument("--file", dest="file_path", required=True, help="Full path to .exe file")
    exe_parser.add_argument("--signing-server", required=False, default=get_pkg_value("SIGNING_SERVER"))
    exe_parser.add_argument("--signing-pass", required=False, default=get_pkg_value("SIGNING_PASSWORD"))
    exe_parser.add_argument("--timestamp", required=False, default="http://timestamp.digicert.com")

    args = parser.parse_args(sys.argv[1:])
    if args.command == 'mac':
        sign_mac_app(args.file_path, args.signing_identity)
        create_mac_dmg(args.file_path)
    if args.command == 'win':
        sign_windows_executable(args.file_path)


if __name__ == "__main__":
    main()
