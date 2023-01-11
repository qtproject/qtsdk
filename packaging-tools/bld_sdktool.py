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
from collections import namedtuple
from io import TextIOWrapper
from pathlib import Path
from typing import List, Optional

from bld_utils import is_linux, is_windows
from bldinstallercommon import extract_file, retrieve_url, strip_dirs
from runner import run_cmd

BuildParams = namedtuple('BuildParams',
                         ['src_path', 'build_path', 'target_path',
                          'make_command', 'redirect_output'])


def qt_static_configure_options() -> List[str]:
    return ['-release', '-opensource', '-confirm-license', '-accessibility',
            '-no-gui',
            '-no-openssl',
            '-no-feature-sql',
            '-qt-zlib',
            '-nomake', 'examples',
            '-nomake', 'tests',
            '-static'] + qt_static_platform_configure_options()


def qt_static_platform_configure_options() -> List[str]:
    if is_windows():
        return ['-static-runtime', '-no-icu', '-mp']
    if is_linux():
        return ['-no-icu', '-no-glib', '-qt-zlib', '-qt-pcre', '-qt-doubleconversion']
    return []


def get_qt_src_path(qt_build_base: str) -> str:
    return os.path.join(qt_build_base, 'src')


def get_qt_build_path(qt_build_base: str) -> str:
    return os.path.join(qt_build_base, 'build')


def package_extension(url: str) -> str:
    url_path = Path(url)
    if url_path.suffixes[-2:] == [".tar", ".gz"]:
        return '.tar.gz'
    if url_path.suffixes[-2:] == [".tar", ".xz"]:
        return '.tar.xz'
    return Path(url).suffix


def get_and_extract_qt_src(url: str, temp: str, path: str) -> None:
    Path(temp).mkdir(parents=True, exist_ok=True)
    ext = package_extension(url)
    file_path = os.path.join(temp, 'qtsrc' + ext)
    retrieve_url(url, file_path)
    Path(path).mkdir(parents=True, exist_ok=True)
    extract_file(file_path, path)
    strip_dirs(Path(path))


def configure_qt(params: BuildParams, src: str, build: str) -> None:
    Path(build).mkdir(parents=True, exist_ok=True)
    configure = os.path.join(src, "configure")
    cmd = [configure, "-prefix", build] + qt_static_configure_options()
    run_cmd(cmd=cmd, cwd=build, redirect=params.redirect_output)


def build_qt(params: BuildParams, build: str) -> None:
    run_cmd(cmd=[params.make_command], cwd=build, redirect=params.redirect_output)


def build_sdktool_impl(params: BuildParams, qt_build_path: str) -> None:
    Path(params.build_path).mkdir(parents=True, exist_ok=True)
    cmake_args = ['cmake',
                  '-DCMAKE_PREFIX_PATH=' + qt_build_path,
                  '-DCMAKE_BUILD_TYPE=Release']
    # force MSVC on Windows, because it looks for GCC in the PATH first,
    # even if MSVC is first mentioned in the PATH...
    # TODO would be nicer if we only did this if cl.exe is indeed first in the PATH
    if is_windows():
        cmake_args += ['-DCMAKE_C_COMPILER=cl', '-DCMAKE_CXX_COMPILER=cl']

    cmd = cmake_args + ['-G', 'Ninja', params.src_path]
    run_cmd(cmd=cmd, cwd=params.build_path, redirect=params.redirect_output)
    run_cmd(cmd=['cmake', '--build', '.'], cwd=params.build_path, redirect=params.redirect_output)
    cmd = ['cmake', '--install', '.', '--prefix', params.target_path]
    run_cmd(cmd=cmd, cwd=params.build_path, redirect=params.redirect_output)


def build_sdktool(qt_src_url: str, qt_build_base: str, sdktool_src_path: str, sdktool_build_path: str, sdktool_target_path: str,
                  make_command: str, redirect_output: Optional[TextIOWrapper] = None) -> None:
    params = BuildParams(src_path=sdktool_src_path,
                         build_path=sdktool_build_path,
                         target_path=sdktool_target_path,
                         make_command=make_command,
                         redirect_output=redirect_output)
    qt_src = get_qt_src_path(qt_build_base)
    qt_build = get_qt_build_path(qt_build_base)
    get_and_extract_qt_src(qt_src_url, qt_build_base, qt_src)
    configure_qt(params, qt_src, qt_build)
    build_qt(params, qt_build)
    build_sdktool_impl(params, qt_build)


def zip_sdktool(sdktool_target_path: str, out_7zip: str, redirect_output: Optional[TextIOWrapper] = None) -> None:
    glob = "*.exe" if is_windows() else "*"
    run_cmd(cmd=["7z", "a", out_7zip, glob], cwd=sdktool_target_path, redirect=redirect_output)


def get_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Build sdktool')
    parser.add_argument('--qt-url', help='URL to Qt sources', required=True)
    parser.add_argument('--qt-build', help='Path that is used for building Qt',
                        required=True)
    parser.add_argument('--src', help='Path to sdktool sources', required=True)
    parser.add_argument('--build', help='Path that is used for building sdktool',
                        required=True)
    parser.add_argument('--install', help='Path that is used for installing sdktool',
                        required=True)
    parser.add_argument('--make-command', help='Make command to use for Qt',
                        required=True)
    return parser.parse_args()


def main() -> None:
    args = get_arguments()
    build_sdktool(args.qt_url, args.qt_build, args.src, args.build,
                  args.install, args.make_command)


if __name__ == '__main__':
    main()
