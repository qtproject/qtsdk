#!/usr/bin/env python
#############################################################################
#
# Copyright (C) 2022 The Qt Company Ltd.
# Contact: http://www.qt-project.org/legal
#
# This file is part of the release tools of the Qt Toolkit.
#
# $QT_BEGIN_LICENSE:LGPL21$
# Commercial License Usage
# Licensees holding valid commercial Qt licenses may use this file in
# accordance with the commercial license agreement provided with the
# Software or, alternatively, in accordance with the terms contained in
# a written agreement between you and The Qt Company. For licensing terms
# and conditions see http://www.qt.io/terms-conditions. For further
# information use the contact form at http://www.qt.io/contact-us.
#
# GNU Lesser General Public License Usage
# Alternatively, this file may be used under the terms of the GNU Lesser
# General Public License version 2.1 or version 3 as published by the Free
# Software Foundation and appearing in the file LICENSE.LGPLv21 and
# LICENSE.LGPLv3 included in the packaging of this file. Please review the
# following information to ensure the GNU Lesser General Public License
# requirements will be met: https://www.gnu.org/licenses/lgpl.html and
# http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.
#
# As a special exception, The Qt Company gives you certain additional
# rights. These rights are described in The Qt Company LGPL Exception
# version 1.1, included in the file LGPL_EXCEPTION.txt in this package.
#
# $QT_END_LICENSE$
#
#############################################################################

import argparse
import os
import platform
import subprocess
import sys
from typing import List

from runner import do_execute_sub_process

ROOT_DIR = os.path.dirname(os.path.realpath(__file__))


def build(src_dir: str, install_dir: str, toolset: str) -> None:
    do_execute_sub_process(['perl', 'Configure', toolset, '--openssldir=' + install_dir], src_dir, True)
    if toolset == 'VC-WIN32':
        do_execute_sub_process([r'ms\do_nasm.bat'], src_dir, True)
    else:
        do_execute_sub_process([r'ms\do_win64a'], src_dir, True)
    do_execute_sub_process(['nmake', '-f', 'ms\\ntdll.mak'], src_dir, True)
    do_execute_sub_process(['nmake', '-f', 'ms\\ntdll.mak', 'install'], src_dir, True)


def archive(install_dir: str, archive_prefix: str) -> None:
    (directory, name) = os.path.split(install_dir)
    do_execute_sub_process(['7z', 'a', archive_prefix + '.7z', name], directory, True)
    do_execute_sub_process(['7z', 'a', archive_prefix + '-runtime.7z', '*.dll'], os.path.join(install_dir, 'bin'), True)


def check_environment() -> None:
    with open(os.devnull, 'w', encoding="utf-8") as fnull:

        def check_cmd(cmd: List[str]) -> None:
            if subprocess.call(cmd, stdout=fnull, stderr=fnull) != 0:
                raise SystemExit(f"Check environment fail: {cmd[0]}")
        check_cmd(['nasm', '-h'])
        check_cmd(['nmake', '/?'])
        check_cmd(['7z'])


def setup_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        add_help=True, description='Build openssl from sources',
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument('--sourcedir', help='Source directory', required=True)
    parser.add_argument('--installdir', help=r'Target directory (should be on C:\)', required=False, default=r'C:\usr\local\openssl')
    parser.add_argument('--toolset', help='Either VC-WIN32 or VC-WIN64', required=False, default='VC-WIN32')
    parser.add_argument('--archive_prefix', help='The start of the archive name to create', required=False, default=ROOT_DIR + '\\openssl')
    return parser


def main() -> None:
    """Main"""
    if not platform.system().lower().startswith('win'):
        raise SystemExit("Only Windows builds are supported.")

    check_environment()

    parser = setup_argument_parser()
    args = parser.parse_args()

    if args.toolset not in ('VC-WIN32', 'VC-WIN64A'):
        raise SystemExit("--toolset must be either VC-WIN32 or VC-WIN64A")

    build(args.sourcedir, args.installdir, args.toolset)
    archive(args.installdir, args.archive_prefix)


if __name__ == '__main__':
    main()
