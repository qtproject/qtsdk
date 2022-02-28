#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2017 The Qt Company Ltd.
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

import bldinstallercommon
import collections

BuildParams = collections.namedtuple('BuildParams',
                                     ['src_path', 'build_path', 'target_path',
                                      'make_command', 'redirect_output'])

def qt_static_configure_options():
    return ['-release', '-opensource', '-confirm-license', '-accessibility',
            '-no-gui',
            '-no-openssl',
            '-no-feature-sql',
            '-qt-zlib',
            '-nomake', 'examples',
            '-nomake', 'tests',
            '-static'] + qt_static_platform_configure_options()

def qt_static_platform_configure_options():
    if bldinstallercommon.is_win_platform():
        return ['-static-runtime', '-no-icu', '-mp']
    elif bldinstallercommon.is_linux_platform():
        return ['-no-icu', '-no-glib', '-qt-zlib', '-qt-pcre', '-qt-doubleconversion']
    return []

def qt_src_path(qt_build_base):
    return os.path.join(qt_build_base, 'src')

def qt_build_path(qt_build_base):
    return os.path.join(qt_build_base, 'build')

def package_extension(url):
    if url.endswith('.tar.gz'):
        return '.tar.gz'
    elif url.endswith('.zip'):
        return '.zip'
    elif url.endswith('.tar.xz'):
        return '.tar.xz'
    else:
        (_, ext) = os.path.splitext(url)
        return ext

def get_and_extract_qt_src(url, temp, path):
    bldinstallercommon.create_dirs(temp)
    ext = package_extension(url)
    file_path = os.path.join(temp, 'qtsrc' + ext)
    bldinstallercommon.retrieve_url(url, file_path)
    bldinstallercommon.create_dirs(path)
    bldinstallercommon.extract_file(file_path, path)
    bldinstallercommon.remove_one_tree_level(path)

def configure_qt(params, src, build):
    bldinstallercommon.create_dirs(build)
    configure = os.path.join(src, 'configure')
    bldinstallercommon.do_execute_sub_process([configure, '-prefix', build] + qt_static_configure_options(),
                                              build, redirect_output=params.redirect_output)

def build_qt(params, build):
    bldinstallercommon.do_execute_sub_process([params.make_command], build, redirect_output=params.redirect_output)

def build_sdktool_impl(params, qt_build_path):
    bldinstallercommon.create_dirs(params.build_path)
    cmake_args = ['cmake',
                  '-DCMAKE_PREFIX_PATH=' + qt_build_path,
                  '-DCMAKE_BUILD_TYPE=Release']
    # force MSVC on Windows, because it looks for GCC in the PATH first,
    # even if MSVC is first mentioned in the PATH...
    # TODO would be nicer if we only did this if cl.exe is indeed first in the PATH
    if bldinstallercommon.is_win_platform():
        cmake_args += ['-DCMAKE_C_COMPILER=cl', '-DCMAKE_CXX_COMPILER=cl']

    bldinstallercommon.do_execute_sub_process(cmake_args +
                                              ['-G', 'Ninja', params.src_path],
                                              params.build_path,
                                              redirect_output=params.redirect_output)
    bldinstallercommon.do_execute_sub_process(['cmake', '--build', '.'], params.build_path,
                                              redirect_output=params.redirect_output)
    bldinstallercommon.do_execute_sub_process(['cmake',
                                               '--install', '.',
                                               '--prefix', params.target_path],
                                              params.build_path,
                                              redirect_output=params.redirect_output)

def build_sdktool(qt_src_url, qt_build_base, sdktool_src_path, sdktool_build_path, sdktool_target_path,
                  make_command, redirect_output=None):
    params = BuildParams(src_path=sdktool_src_path,
                         build_path=sdktool_build_path,
                         target_path=sdktool_target_path,
                         make_command=make_command,
                         redirect_output=redirect_output)
    qt_src = qt_src_path(qt_build_base)
    qt_build = qt_build_path(qt_build_base)
    get_and_extract_qt_src(qt_src_url, qt_build_base, qt_src)
    configure_qt(params, qt_src, qt_build)
    build_qt(params, qt_build)
    build_sdktool_impl(params, qt_build)

def zip_sdktool(sdktool_target_path, out_7zip, redirect_output=None):
    glob = "*.exe" if bldinstallercommon.is_win_platform() else "*"
    bldinstallercommon.do_execute_sub_process(['7z', 'a', out_7zip, glob],
                                              sdktool_target_path, redirect_output=redirect_output)
