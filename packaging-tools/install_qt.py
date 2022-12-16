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
from tempfile import TemporaryDirectory
from typing import List, Optional

from bldinstallercommon import create_qt_download_task, patch_qt
from logging_util import init_logger
from threadedwork import ThreadedWork

log = init_logger(__name__, debug_mode=False)


def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build Qt Creator')
    parser.add_argument('--qt-path', help='path to Qt', required=True)
    parser.add_argument('--qt-module', help='Qt module package url (.7z) needed for building',
                        action='append', dest='qt_modules', default=[])

    parser.add_argument('--base-url', help='Base URL for given module_name(s)')
    parser.add_argument('module_name', help='Name of Qt module to install, based on --base-url and --base-url-postfix',
                        nargs='*')
    parser.add_argument('--base-url-postfix',
                        help='Postfix to add to URLs constructed from --base-url and given module_name(s)',
                        default='')

    # Linux
    parser.add_argument('--icu7z', help='a file or url where to get ICU libs as 7z')

    # Windows
    parser.add_argument('--d3dcompiler7z', help='a file or url where it get d3dcompiler lib')
    parser.add_argument('--opengl32sw7z', help='a file or url where it get opengl32sw lib')
    parser.add_argument('--openssl7z', help='a file or url where to get the openssl libs as 7z')

    args = parser.parse_args(sys.argv[1:])

    return args


def install_qt(
    qt_path: str,
    qt_modules: List[str],
    icu_url: Optional[str] = None,
    d3d_url: Optional[str] = None,
    opengl_url: Optional[str] = None,
    openssl_url: Optional[str] = None,
    temp_path: Optional[str] = None
) -> None:
    """
    Install Qt to directory qt_path with the specified module and library packages.

    Args:
        qt_path: File system path to Qt (target install directory)
        qt_modules: List of Qt module package URLs (.7z)
        icu_url: Local or remote URI to Linux ICU libraries (.7z)
        d3d_url: Local or remote URI to Windows d3dcompiler libraries (.7z)
        opengl_url: Local or remote URI to Windows OpenGL libraries (.7z)
        openssl_url: Local or remote URI to Windows OpenSSL libraries (.7z)
        temp_path: Temporary path used for saving downloaded archives

    Raises:
        SystemExit: When qt_modules list is empty

    """
    if not qt_modules:
        raise SystemExit("No modules specified in qt_modules")
    qt_path = os.path.abspath(qt_path)
    dl_pkgs_work = ThreadedWork("get and extract Qt 5 binaries")
    need_to_install_qt = not os.path.lexists(qt_path)
    if need_to_install_qt:
        opts = argparse.Namespace(
            icu7z=icu_url,
            d3dcompiler7z=d3d_url,
            opengl32sw7z=opengl_url,
            openssl7z=openssl_url,
        )
        if temp_path:
            dl_pkgs_work.add_task_object(
                create_qt_download_task(qt_modules, qt_path, temp_path, opts)
            )
        else:
            with TemporaryDirectory() as temporary_dir:
                dl_pkgs_work.add_task_object(
                    create_qt_download_task(qt_modules, qt_path, temporary_dir,
                                            opts)
                )

    # run task if needed
    if dl_pkgs_work.task_number != 0:
        dl_pkgs_work.run()
        patch_qt(qt_path)


def main() -> None:
    """Main"""
    args: argparse.Namespace = get_arguments()
    # Check that qt_module(s) or base-url/module_name(s) combo is specified
    if not args.qt_modules and not (args.base_url and args.module_name):
        raise SystemExit("'qt-module(s)' and/or 'base-url' with 'module_name(s)' required")
    # Create the list of modules from qt_modules + module_names with base_url and postfix
    qt_modules: List[str] = args.qt_modules
    if args.base_url and args.module_name:
        for module in args.module_name:
            qt_modules += [args.base_url + "/" + module + "/" + module + args.base_url_postfix]

    install_qt(
        qt_path=args.qt_path,
        qt_modules=qt_modules,
        icu_url=args.icu7z,
        d3d_url=args.d3dcompiler7z,
        opengl_url=args.opengl32sw7z,
        openssl_url=args.openssl7z,
    )


if __name__ == '__main__':
    main()
