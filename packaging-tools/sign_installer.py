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
import sys
from shutil import rmtree

from logging_util import init_logger
from read_remote_config import get_pkg_value
from runner import run_cmd, run_cmd_silent

log = init_logger(__name__, debug_mode=False)


def sign_mac_app(app_path: str, signing_identity: str) -> None:
    assert app_path.endswith(".app"), f"Not a valid path to .app bundle: {app_path}"
    # we need to unlock the keychain first
    unlock_script = "/Users/qt/unlock-keychain.sh"
    run_cmd(cmd=[unlock_script])
    # "-o runtime" is required for notarization
    cmd_args = ['codesign', '-o', 'runtime', '--verbose=3', '-r', get_pkg_value("SIGNING_FLAGS")]
    cmd_args += ['-s', signing_identity, app_path]
    run_cmd(cmd=cmd_args)
    log.info("Successfully signed: %s", app_path)


def create_mac_dmg(app_path: str) -> None:
    assert app_path.endswith(".app"), f"Not a valid path to .app bundle: {app_path}"
    installer_name_base = os.path.basename(app_path).split(".app")[0]
    destination_dmg_path = app_path.split(".app")[0] + '.dmg'
    cmd_args = ['hdiutil', 'create', '-srcfolder', app_path, '-volname', installer_name_base]
    cmd_args += ['-format', 'UDBZ', destination_dmg_path, '-ov', '-scrub', '-size', '4g']
    run_cmd(cmd=cmd_args)
    log.info("Successfully created: %s", destination_dmg_path)


def sign_windows_executable(file_path: str) -> None:
    sign_tools = ["signtool32.exe", "keys.pfx", "capicom.dll"]
    sign_tools_temp_dir = r'C:\Utils\sign_tools_temp'
    for item in sign_tools:
        dest = os.path.join(sign_tools_temp_dir, item)
        curl_cmd = ['curl', "--fail", "-L", "--retry", "5", "--retry-delay", "30", "-o", dest]
        curl_cmd += ['--create-dirs', get_pkg_value("SIGN_TOOLS_ADDR") + item]
        run_cmd(cmd=curl_cmd)
    sign_tool_executable = os.path.join(sign_tools_temp_dir, 'signtool32.exe')
    keys_path = os.path.join(sign_tools_temp_dir, 'keys.pfx')
    signing_server = get_pkg_value("SIGNING_SERVER")
    timestamp_server = get_pkg_value("TIMESTAMP_SERVER")
    signing_password = get_pkg_value("SIGNING_PASSWORD")
    cmd = [sign_tool_executable, 'sign', '/v', '/du', signing_server, '/p', signing_password]
    cmd += ['/tr', timestamp_server, '/f', keys_path, '/td', "sha256", '/fd', "sha256", file_path]
    # redact sensitive data from logging
    log_entry = cmd[:]
    log_entry[4] = "****"
    log_entry[6] = "****"
    log.info("Calling: %s", " ".join(log_entry))
    sign_success = run_cmd_silent(cmd=cmd)
    rmtree(sign_tools_temp_dir)
    if sign_success:
        log.info("Successfully signed: %s", file_path)
    else:
        log.info("Error signing: %s", file_path)


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
