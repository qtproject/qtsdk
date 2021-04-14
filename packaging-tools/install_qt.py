#!/usr/bin/env python
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

# import the print function which is used in python 3.x
from __future__ import print_function

import argparse
import os

import bldinstallercommon
from threadedwork import ThreadedWork

def get_arguments():
    parser = argparse.ArgumentParser(description='Build Qt Creator')
    parser.add_argument('--qt-path', help='path to Qt', required=True)
    parser.add_argument('--qt-module', help='Qt module package url (.7z) needed for building',
                        action='append', dest='qt_modules')
    parser.add_argument('--temp-path', help='temporary path for downloads', required=True)

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
    parser.add_argument('--opengl32sw7z', help='a file or url where it get d3dcompiler lib')
    parser.add_argument('--openssl7z', help='a file or url where to get the openssl libs as 7z')

    args = parser.parse_args()
    args.qt_path = os.path.abspath(args.qt_path)
    args.temp_path = os.path.abspath(args.temp_path)

    if not args.qt_modules or args.base_url or args.module_name:
        if not args.base_url or not args.module_name:
            print('either --qt-module or --base-url and module_name(s) are required')
            exit(1)

    args.qt_modules = args.qt_modules if args.qt_modules else [] # ensure list
    args.qt_modules += [args.base_url + '/' + module + '/' + module + args.base_url_postfix
                        for module in args.module_name]

    return args

def install_qt(args):
    download_packages_work = ThreadedWork('get and extract Qt 5 binaries')
    need_to_install_qt = not os.path.lexists(args.qt_path)
    if need_to_install_qt:
        download_packages_work.addTaskObject(bldinstallercommon.create_qt_download_task(
            args.qt_modules, args.qt_path, args.temp_path, args))

    # run task if needed
    if download_packages_work.taskNumber != 0:
        download_packages_work.run()
        bldinstallercommon.patch_qt(args.qt_path)

def main():
    args = get_arguments()
    install_qt(args)

if __name__ == '__main__':
    main()
