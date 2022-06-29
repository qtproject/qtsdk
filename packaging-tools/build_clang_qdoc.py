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

import os

import environmentfrombatchfile
from bld_utils import is_linux, is_windows, runCommand
from read_remote_config import get_pkg_value
from runner import do_execute_sub_process


def git_clone_and_checkout(base_path, remote_repository_url, directory, revision):
    runCommand(['git', 'clone',
                '--config', 'core.eol=lf',
                '--config', 'core.autocrlf=input',
                '--branch', revision,
                '--recursive',
                remote_repository_url, directory], base_path)


def get_clang(base_path, llvm_revision):
    git_clone_and_checkout(base_path, 'git://code.qt.io/clang/llvm-project.git', 'llvm', llvm_revision)


def msvc_version():
    msvc_ver = os.environ.get('MSVC_VERSION')
    if not msvc_ver:
        msvc_ver = '14.2'
    return msvc_ver


def msvc_year_version():
    return {
        '12.0': 'MSVC2013',
        '14.0': 'MSVC2015',
        '14.1': 'MSVC2017',
        '14.2': 'MSVC2019'
    }.get(os.environ.get('MSVC_VERSION'), 'MSVC2019')


def msvc_year():
    return {
        '12.0': '2013',
        '14.0': '2015',
        '14.1': '2017',
        '14.2': '2019'
    }.get(os.environ.get('MSVC_VERSION'), 'MSVC2019')


def msvc_year_version_libclang():
    return {
        '12.0': 'vs2013',
        '14.0': 'vs2015',
        '14.1': 'vs2017',
        '14.2': 'vs2019'
    }.get(os.environ.get('MSVC_VERSION'), 'vs2019')


def msvc_environment(bitness):
    program_files = os.path.join('C:', '/Program Files (x86)')
    if not os.path.exists(program_files):
        program_files = os.path.join('C:', '/Program Files')
    msvc_ver = msvc_version()
    if msvc_ver == '14.1' or msvc_ver == '14.2':
        vcvarsall = os.path.join(program_files, 'Microsoft Visual Studio', msvc_year(), 'Professional', 'VC', 'Auxiliary', 'Build', 'vcvarsall.bat')
        arg = 'x64' if bitness == 64 else 'x86'
    else:
        vcvarsall = os.path.join(program_files, 'Microsoft Visual Studio ' + msvc_ver, 'VC', 'vcvarsall.bat')
        arg = 'amd64' if bitness == 64 else 'x86'
    return environmentfrombatchfile.get(vcvarsall, arguments=arg)


def paths_with_sh_exe_removed(path_value):
    items = path_value.split(os.pathsep)
    items = [i for i in items if not os.path.exists(os.path.join(i, 'sh.exe'))]
    return os.pathsep.join(items)


def build_environment(toolchain, bitness):
    if is_windows():
        if is_mingw_toolchain(toolchain):
            environment = dict(os.environ)
            # cmake says "For MinGW make to work correctly sh.exe must NOT be in your path."
            environment['PATH'] = paths_with_sh_exe_removed(environment['PATH'])
            environment['CC'] = 'gcc'
            environment['CXX'] = 'g++'
            return environment
        environment = msvc_environment(bitness)
        environment['CC'] = 'cl'
        environment['CXX'] = 'cl'
        return environment
    return None  # == process environment


def is_msvc_toolchain(toolchain):
    return 'msvc' in toolchain


def is_mingw_toolchain(toolchain):
    return 'mingw' in toolchain


def is_gcc_toolchain(toolchain):
    return 'g++' in toolchain


def cmake_generator():
    if is_windows():
        return 'Ninja'
    return 'Unix Makefiles'


def static_flags(toolchain):
    if is_mingw_toolchain(toolchain):
        linker_flags = '-static-libgcc -static-libstdc++ -static'
        return [
            '-DCMAKE_SHARED_LINKER_FLAGS=' + linker_flags,
            '-DCMAKE_EXE_LINKER_FLAGS=' + linker_flags,
        ]
    return []


def bitness_flags(bitness):
    if bitness == 32 and is_linux():
        return ['-DLLVM_BUILD_32_BITS=ON']
    return []


def rtti_flags(toolchain):
    if is_mingw_toolchain(toolchain):
        return ['-DLLVM_ENABLE_RTTI:BOOL=OFF']
    return ['-DLLVM_ENABLE_RTTI:BOOL=ON']


def build_command():
    if is_windows():
        command = ['ninja']
    else:
        command = ['make']
    return command


def install_command():
    if is_windows():
        command = ['ninja']
    else:
        command = ['make', '-j1']
    return command


# For instrumented build we now use the same targets because clazy
# requires the llvm installation to properly build
def build_and_install(build_path, environment, build_targets, install_targets):
    build_cmd = build_command()
    do_execute_sub_process(build_cmd + build_targets, build_path, extra_env=environment)
    install_cmd = install_command()
    do_execute_sub_process(install_cmd + install_targets, build_path, extra_env=environment)


def cmake_command(toolchain, src_path, install_path, bitness, build_type):
    command = ['cmake',
               '-DCMAKE_INSTALL_PREFIX=' + install_path,
               '-G',
               cmake_generator(),
               '-DCMAKE_BUILD_TYPE=' + build_type,
               '-DLLVM_ENABLE_PROJECTS=clang',
               '-DLLVM_TARGETS_TO_BUILD=X86',
               '-DLLVM_ENABLE_LIBXML2=OFF',
               '-DLLVM_ENABLE_ZLIB=OFF',
               '-DLLVM_ENABLE_TERMINFO=OFF',
               '-DLIBCLANG_BUILD_STATIC=ON',
               '-DLLVM_TEMPORARILY_ALLOW_OLD_TOOLCHAIN=ON',
               '-DLLVM_ENABLE_PIC=OFF',
               "-DLLVM_LIT_ARGS='-v'"]
    if is_msvc_toolchain(toolchain):
        command.append('-DLLVM_EXPORT_SYMBOLS_FOR_PLUGINS=1')
    command.extend(bitness_flags(bitness))
    command.extend(rtti_flags(toolchain))
    command.extend(static_flags(toolchain))
    command.append(src_path)

    return command


def build_clang(toolchain, src_path, build_path, install_path, bitness=64, environment=None, build_type='Release'):
    if build_path and not os.path.lexists(build_path):
        os.makedirs(build_path)

    cmake_cmd = cmake_command(toolchain, src_path, install_path, bitness, build_type)

    do_execute_sub_process(cmake_cmd, build_path, extra_env=environment)
    build_targets = ['install/strip']
    if is_msvc_toolchain(toolchain):
        build_targets = ['install']  # There is no 'install/strip' for nmake.
    build_and_install(build_path, environment, ['libclang', 'clang', 'llvm-config'], build_targets)


def check_clang(toolchain, build_path, environment):
    if is_msvc_toolchain(toolchain) or is_mingw_toolchain(toolchain):
        tools_path = os.environ.get('WINDOWS_UNIX_TOOLS_PATH')
        if tools_path:
            path_key = 'Path' if 'Path' in environment else 'PATH'
            environment[path_key] += ';' + tools_path

    build_cmd = build_command()
    do_execute_sub_process(build_cmd + ['check-clang'], build_path, extra_env=environment)


def package_clang(install_path, result_file_path):
    (basepath, dirname) = os.path.split(install_path)
    zip_command = ['cmake', '-E', 'tar', 'cvf', result_file_path, '--format=7zip', dirname]
    runCommand(zip_command, basepath)


def upload_clang(file_path, remote_path):
    (path, filename) = os.path.split(file_path)
    scp_bin = '%SCP%' if is_windows() else 'scp'
    scp_command = [scp_bin, filename, remote_path]
    runCommand(scp_command, path)


def main():
    # Used Environment variables:
    #
    # PKG_NODE_ROOT
    # Absolute path of a working directory for this script.
    # It checks out LLVM and Clang in "$PKG_NODE_ROOT/llvm",
    # builds it in "$PKG_NODE_ROOT/build", and installs it to
    # "$PKG_NODE_ROOT/libclang"
    #
    # CLANG_BRANCH
    # "Branch" identifier for the resulting package name
    #
    # cfg
    # Configuration containing of platform and bitness information
    # like "linux-g++-Rhel7.2-x64", "mac-clang-10.11-x64",
    # "win-MinGW5.3.0-Windows10-x64", "win-MinGW5.3.0-Windows10-x86",
    # "win-msvc2015-Windows10-x64", "win-msvc2015-Windows10-x86"
    #
    # GENERATE_INSTRUMENTED_BINARIES
    # Set this to 1 if you want to build MinGW libraries with information
    # suitable for creating profile optimized builds
    #
    # PACKAGE_STORAGE_SERVER_USER
    # PACKAGE_STORAGE_SERVER
    # PACKAGE_STORAGE_SERVER_BASE_DIR
    # CLANG_UPLOAD_SERVER_PATH
    # Define a remote path where to upload the resulting package
    # "PACKAGE_STORAGE_SERVER_USER@PACKAGE_STORAGE_SERVER:PACKAGE_STORAGE_SERVER_BASE_DIR/CLANG_UPLOAD_SERVER_PATH"
    #
    # LLVM_REVISION
    # Git revision, branch or tag for LLVM/Clang check out

    base_path = os.path.join(os.environ['PKG_NODE_ROOT'])
    branch = os.environ['CLANG_BRANCH']
    src_path = os.path.join(base_path, 'llvm/llvm')
    build_path = os.path.join(base_path, 'build')
    install_path = os.path.join(base_path, 'libclang')
    bitness = 64 if '64' in os.environ['cfg'] else 32
    toolchain = os.environ['cfg'].split('-')[1].lower()
    environment = build_environment(toolchain, bitness)
    result_file_path = os.path.join(base_path, 'libclang-' + branch + '-' + os.environ['CLANG_PLATFORM'] + '.7z')
    remote_path = (get_pkg_value("PACKAGE_STORAGE_SERVER_USER") + '@' + get_pkg_value("PACKAGE_STORAGE_SERVER") + ':'
                   + os.environ['PACKAGE_STORAGE_SERVER_BASE_DIR'] + '/' + os.environ['CLANG_UPLOAD_SERVER_PATH'])

    get_clang(base_path, os.environ['LLVM_REVISION'])

    # TODO: put args in some struct to improve readability, add error checks
    build_clang(toolchain, src_path, build_path, install_path, bitness, environment, build_type='Release')

    check_clang(toolchain, build_path, environment)

    package_clang(install_path, result_file_path)
    upload_clang(result_file_path, remote_path)


if __name__ == "__main__":
    main()
