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
import argparse
import subprocess
import logging

log = logging.getLogger("Sign-utility")
logging.basicConfig(level=logging.INFO, format='%(message)s')


def sign_mac_app(app_path: str, codesign_identity_key: str) -> None:
    assert app_path.endswith(".app"), f"Not a valid path to .app bundle: {app_path}"
    # we need to unlock the keychain first
    unlock_script = "/Users/qt/unlock-keychain.sh"
    subprocess.check_call([unlock_script])
    s_arg = f'Developer ID Application: The Qt Company Oy ({codesign_identity_key})'
    # "-o runtime" is required for notarization
    cmd_args = ['codesign', '-o', 'runtime', '--verbose=3', '-r', '/Users/qt/csreq_qt_company.txt', '-s', s_arg, app_path]
    subprocess.check_call(cmd_args)
    log.info(f"Successfully signed: {app_path}")


def create_mac_dmg(app_path: str) -> None:
    assert app_path.endswith(".app"), f"Not a valid path to .app bundle: {app_path}"
    installer_name_base = os.path.basename(app_path).split(".")[0]
    destination_dmg_path = app_path.split(".")[0] + '.dmg'
    cmd_args = ['hdiutil', 'create', '-srcfolder', app_path, '-volname', installer_name_base]
    cmd_args += ['-format', 'UDBZ', destination_dmg_path, '-ov', '-scrub', '-size', '4g']
    subprocess.check_call(cmd_args)
    log.info(f"Successfully created: {destination_dmg_path}")


def sign_windows_executable(file_path: str, signing_server: str, signing_pass: str, timestamp: str):
    cmd_args = [r'C:\Utils\sign\signtool.exe', 'sign', '/v', '/du', signing_server, '/p', signing_pass]
    cmd_args += ['/t', timestamp, '/f', r'C:\utils\sign\keys.pfx', file_path]
    subprocess.check_call(cmd_args)
    log.info(f"Successfully signed: {file_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Helper script to sign macOS .app bundle and create .dmg from it or sign a Windows .exe")
    subparsers = parser.add_subparsers(dest='command')

    app_parser = subparsers.add_parser("mac")
    exe_parser = subparsers.add_parser("win")

    app_parser.add_argument("--file", dest="file_path", required=True, help="Full path to .app file")
    app_parser.add_argument("--codesign-identity-key", default=os.environ.get('QT_CODESIGN_IDENTITY_KEY'))

    exe_parser.add_argument("--file", dest="file_path", required=True, help="Full path to .exe file")
    exe_parser.add_argument("--signing-server", required=True, default=os.environ.get('SIGNING_SERVER'))
    exe_parser.add_argument("--signing-pass", required=True, default=os.environ.get('SIGNING_PASSWORD'))
    exe_parser.add_argument("--timestamp", required=True, default="http://timestamp.verisign.com/scripts/timestamp.dll")

    args = parser.parse_args(sys.argv[1:])
    if args.command == 'mac':
        sign_mac_app(args.file_path, args.codesign_identity_key)
        create_mac_dmg(args.file_path)
    if args.command == 'win':
        sign_windows_executable(args.file_path, args.signing_server, args.signing_pass, args.timestamp)
