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
from shutil import rmtree

import environmentfrombatchfile
from bld_utils import is_linux, is_macos, is_windows, runCommand
from bldinstallercommon import create_download_extract_task, create_qt_download_task
from read_remote_config import get_pkg_value
from runner import do_execute_sub_process
from threadedwork import ThreadedWork


def git_clone_and_checkout(base_path, remote_repository_url, directory, revision):
    runCommand(['git', 'clone',
                '--depth', '1',
                '--config', 'core.eol=lf',
                '--config', 'core.autocrlf=input',
                '--branch', revision,
                '--recursive',
                remote_repository_url, directory], base_path)


def get_clang(base_path, llvm_repository_url, llvm_revision):
    git_clone_and_checkout(base_path, llvm_repository_url, 'llvm', llvm_revision)


def msvc_version():
    msvc_ver = os.environ.get('MSVC_VERSION')
    if not msvc_ver:
        msvc_ver = '14.1'
    return msvc_ver


def msvc_year_version():
    return {
        '12.0': 'MSVC2013',
        '14.0': 'MSVC2015',
        '14.1': 'MSVC2017',
        '14.2': 'MSVC2019'
    }.get(os.environ.get('MSVC_VERSION'), 'MSVC2017')


def msvc_year():
    return {
        '12.0': '2013',
        '14.0': '2015',
        '14.1': '2017',
        '14.2': '2019'
    }.get(os.environ.get('MSVC_VERSION'), 'MSVC2017')


def msvc_year_version_libclang():
    return {
        '12.0': 'vs2013',
        '14.0': 'vs2015',
        '14.1': 'vs2017',
        '14.2': 'vs2019'
    }.get(os.environ.get('MSVC_VERSION'), 'vs2017')


def cmake_version():
    cmake_ver = os.environ.get('CMAKE_VERSION')
    if not cmake_ver:
        cmake_ver = '3.18.3'
    return cmake_ver


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
        else:
            environment = msvc_environment(bitness)
            environment['CC'] = 'cl'
            environment['CXX'] = 'cl'
            return environment
    else:
        return None  # == process environment


def training_qt_version():
    qt_ver = os.environ.get('TRAINING_QT_VERSION')
    if not qt_ver:
        qt_ver = '6.2'
    return qt_ver


def training_qt_long_version():
    qt_ver = os.environ.get('TRAINING_QT_LONG_VERSION')
    if not qt_ver:
        qt_ver = '6.2.3'
    return qt_ver


def training_qtcreator_version():
    qtcreator_ver = os.environ.get('TRAINING_QTCREATOR_VERSION')
    if not qtcreator_ver:
        qtcreator_ver = '4.5'
    return qtcreator_ver


def mingw_training(base_path, qtcreator_path, environment, bitness):
    # Checkout qt-creator, download libclang for build, qt installer and DebugView

    git_clone_and_checkout(base_path, 'git://code.qt.io/qt-creator/qt-creator.git', qtcreator_path, training_qtcreator_version())

    # Set up paths
    script_dir = os.path.dirname(os.path.realpath(__file__))
    debugview_dir = os.path.join(base_path, 'debugview')
    cmake_dir = os.path.join(base_path, 'cmake')
    creator_build_dir = os.path.join(base_path, 'qtcreator_build')
    creator_install_dir = os.path.join(base_path, 'qtcreator_install')
    creator_settings_dir = os.path.join(base_path, 'qtc-settings')
    creator_logs_dir = os.path.join(base_path, 'logs')
    training_dir = os.path.join(script_dir, 'libclang_training')
    qt_dir = os.path.join(base_path, 'qt')
    qt_mingw_dir = os.path.join(base_path, 'qt_mingw')

    # Create some paths
    os.makedirs(creator_settings_dir)
    os.makedirs(creator_logs_dir)

    pkg_server = get_pkg_value("PACKAGE_STORAGE_SERVER")

    # Install Qt
    qt_modules = ['qtbase', 'qtdeclarative', 'qtimageformats', 'qt5compat', 'qtshadertools', 'qtsvg', 'qttools']

    qt_base_url = 'http://' + pkg_server + '/packages/jenkins/archive/qt/' \
        + training_qt_version() + '/' + training_qt_long_version() + '-final-released/Qt' + training_qt_long_version()
    msvc_year_ver = msvc_year_version()
    if bitness == 64:
        qt_mingw_postfix = '-Windows-Windows_10-Mingw-Windows-Windows_10-X86_64.7z'
        qt_postfix = '-Windows-Windows_10-' + msvc_year_ver + '-Windows-Windows_10-X86_64.7z'

    qt_module_urls = [qt_base_url + '/' + module + '/' + module + qt_postfix for module in qt_modules]
    qt_mingw_module_urls = [qt_base_url + '/' + module + '/' + module + qt_mingw_postfix for module in qt_modules]
    qt_temp = os.path.join(base_path, 'qt_download')
    qt_mingw_temp = os.path.join(base_path, 'qt_download_mingw')
    download_packages_work = ThreadedWork("get and extract Qt")
    download_packages_work.addTaskObject(create_qt_download_task(qt_module_urls, qt_dir, qt_temp, None))
    download_packages_work.addTaskObject(create_qt_download_task(qt_mingw_module_urls, qt_mingw_dir, qt_mingw_temp, None))

    download_packages_work.addTaskObject(create_download_extract_task(
        'https://download.sysinternals.com/files/DebugView.zip',
        debugview_dir,
        base_path,
        None))

    # Install CMake
    cmake_arch_suffix = 'win64-x64' if bitness == 64 else 'win32-x86'
    cmake_base_url = 'http://' + pkg_server + '/packages/jenkins/cmake/' \
        + cmake_version() + '/cmake-' + cmake_version() + '-' + cmake_arch_suffix + '.zip'
    download_packages_work.addTaskObject(create_download_extract_task(
        cmake_base_url, cmake_dir, base_path, None))

    download_packages_work.run()

    # Build QtCreator with installed libclang and qt
    # WITH_TESTS is required for QtCreator to support running .batch files
    cmake_command = os.path.join(cmake_dir, 'cmake-' + cmake_version() + '-' + cmake_arch_suffix, 'bin', 'cmake')
    qtc_cmake = [cmake_command,
                 '-GNinja',
                 '-DCMAKE_BUILD_TYPE=Release',
                 '-DWITH_TESTS=ON',
                 '-DBUILD_WITH_PCH=OFF',

                 '-DBUILD_QBS=OFF',

                 '-DBUILD_PLUGINS_BY_DEFAULT=OFF',
                 '-DBUILD_EXECUTABLES_BY_DEFAULT=OFF',

                 '-DBUILD_PLUGIN_CORE=ON',
                 '-DBUILD_PLUGIN_TEXTEDITOR=ON',
                 '-DBUILD_PLUGIN_PROJECTEXPLORER=ON',
                 '-DBUILD_PLUGIN_CPPEDITOR=ON',
                 '-DBUILD_PLUGIN_QMAKEPROJECTMANAGER=ON',
                 '-DBUILD_PLUGIN_CLANGCODEMODEL=ON',
                 '-DBUILD_PLUGIN_CLANGTOOLS=ON',
                 '-DBUILD_PLUGIN_DEBUGGER=ON',
                 '-DBUILD_PLUGIN_DESIGNER=ON',
                 '-DBUILD_PLUGIN_LANGUAGECLIENT=ON',
                 '-DBUILD_PLUGIN_QTSUPPORT=ON',
                 '-DBUILD_PLUGIN_RESOURCEEDITOR=ON',

                 '-DBUILD_EXECUTABLE_QTCREATOR=ON',
                 '-DBUILD_EXECUTABLE_ECHO=ON',
                 '-DBUILD_EXECUTABLE_CLANGBACKEND=ON',
                 '-DBUILD_EXECUTABLE_QTCREATOR_PROCESSLAUNCHER=ON',

                 '-DCMAKE_PREFIX_PATH=' + qt_mingw_dir + ';' + os.path.join(base_path, 'libclang'),
                 '-S' + qtcreator_path,
                 '-B' + creator_build_dir]

    runCommand(qtc_cmake, creator_build_dir, None, environment)
    runCommand([cmake_command, '--build', creator_build_dir], creator_build_dir, None, environment)
    runCommand([cmake_command, '--install', creator_build_dir, '--prefix', creator_install_dir], creator_build_dir, None, environment)
    runCommand([cmake_command, '--install', creator_build_dir, '--prefix', creator_install_dir, '--component', 'Dependencies'], creator_build_dir, None, environment)

    # Remove the regular libclang.dll which got deployed via 'Dependencies' qtcreator install target
    os.remove(os.path.join(creator_install_dir, 'bin', 'libclang.dll'))

    # Train mingw libclang library with build QtCreator
    # First time open the project, then close it. This will generate initial settings and .user files. Second time do the actual training.
    for batchFile in ['qtc.openProject.batch', 'qtc.fileTextEditorCpp.batch']:
        runCommand(
            [os.path.join(training_dir, 'runBatchFiles.bat'), msvc_version(), 'x64' if bitness == 64 else 'x86', batchFile],
            base_path, callerArguments=None, extra_environment=None, onlyErrorCaseOutput=False, expectedExitCodes=[0, 1]
        )


def is_msvc_toolchain(toolchain):
    return 'msvc' in toolchain


def is_mingw_toolchain(toolchain):
    return 'mingw' in toolchain


def is_gcc_toolchain(toolchain):
    return 'g++' in toolchain


def cmake_generator(toolchain):
    if is_windows():
        return 'Ninja'
    else:
        return 'Unix Makefiles'


# We need '-fprofile-correction -Wno-error=coverage-mismatch' to deal with possible conflicts
# in the initial build while using profiler data from the build with plugins
def profile_data_flags(toolchain, profile_data_path, first_run):
    if profile_data_path and is_mingw_toolchain(toolchain):
        profile_flag = '-fprofile-generate' if first_run else '-fprofile-correction -Wno-error=coverage-mismatch -fprofile-use'
        compiler_flags = profile_flag + '=' + profile_data_path
        linker_flags = compiler_flags + ' -static-libgcc -static-libstdc++ -static'

        cmake_flags = [
            '-DCMAKE_C_FLAGS=' + compiler_flags,
            '-DCMAKE_CXX_FLAGS=' + compiler_flags,
            '-DCMAKE_SHARED_LINKER_FLAGS=' + linker_flags,
            '-DCMAKE_EXE_LINKER_FLAGS=' + linker_flags,
        ]
        if first_run:
            stage1path = os.path.join(profile_data_path, '../build/bin')
            cmake_flags.append('-DCLANG_TABLEGEN=' + os.path.join(stage1path, "clang-tblgen.exe"))
            cmake_flags.append('-DLLVM_TABLEGEN=' + os.path.join(stage1path, "llvm-tblgen.exe"))
            cmake_flags.append('-DLLVM_BUILD_RUNTIME=No')

        return cmake_flags
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


def build_command(toolchain):
    if is_windows():
        command = ['ninja']
    else:
        command = ['make']
    return command


def install_command(toolchain):
    if is_windows():
        command = ['ninja']
    else:
        command = ['make', '-j1']
    return command


# For instrumented build we now use the same targets because clazy
# requires the llvm installation to properly build
def build_and_install(toolchain, build_path, environment, build_targets, install_targets):
    build_cmd = build_command(toolchain)
    do_execute_sub_process(build_cmd + build_targets, build_path, extra_env=environment)
    install_cmd = install_command(toolchain)
    do_execute_sub_process(install_cmd + install_targets, build_path, extra_env=environment)


def cmake_command(toolchain, src_path, build_path, install_path, profile_data_path, first_run, bitness, build_type):
    enabled_projects = 'clang;clang-tools-extra'
    if profile_data_path and first_run:
        enabled_projects = 'clang'

    command = ['cmake',
               '-DCMAKE_INSTALL_PREFIX=' + install_path,
               '-G',
               cmake_generator(toolchain),
               '-DCMAKE_BUILD_TYPE=' + build_type,
               '-DLLVM_TEMPORARILY_ALLOW_OLD_TOOLCHAIN=ON',
               '-DLLVM_ENABLE_LIBXML2=OFF',
               '-DLLVM_ENABLE_ZLIB=OFF',
               '-DLLVM_ENABLE_TERMINFO=OFF',
               '-DLLVM_TARGETS_TO_BUILD=X86;AArch64',
               '-DLLVM_ENABLE_PROJECTS=' + enabled_projects,
               "-DLLVM_LIT_ARGS='-v'"]
    if is_msvc_toolchain(toolchain):
        command.append('-DLLVM_EXPORT_SYMBOLS_FOR_PLUGINS=1')
    command.extend(bitness_flags(bitness))
    command.extend(rtti_flags(toolchain))
    command.extend(profile_data_flags(toolchain, profile_data_path, first_run))
    command.append(src_path)

    return command


def build_clang(toolchain, src_path, build_path, install_path, profile_data_path, first_run, bitness=64, environment=None, build_type='Release'):
    if build_path and not os.path.lexists(build_path):
        os.makedirs(build_path)

    cmake_cmd = cmake_command(toolchain, src_path, build_path, install_path, profile_data_path, first_run, bitness, build_type)

    do_execute_sub_process(cmake_cmd, build_path, extra_env=environment)

    build_targets = ['libclang', 'clang', 'llvm-config']
    install_targets = ['install/strip']

    if is_msvc_toolchain(toolchain):
        install_targets = ['install']  # There is no 'install/strip' for nmake.

    if profile_data_path and first_run:
        build_targets = ['libclang']
        install_targets = ['tools/clang/tools/libclang/install/strip']  # we only want to build / install libclang

    build_and_install(toolchain, build_path, environment, build_targets, install_targets)


def build_clazy(toolchain, src_path, build_path, install_path, bitness=64, environment=None):
    if build_path and not os.path.lexists(build_path):
        os.makedirs(build_path)

    cmake_cmd = ['cmake',
                 '-G', cmake_generator(toolchain),
                 '-DCMAKE_INSTALL_PREFIX=' + install_path,
                 '-DCMAKE_BUILD_TYPE=Release',
                 '-DCLAZY_LINK_CLANG_DYLIB=OFF',
                 '-DCMAKE_PREFIX_PATH=' + install_path]

    if is_msvc_toolchain(toolchain):
        cmake_cmd.append('-DCLANG_LIBRARY_IMPORT=' + build_path + '/../build/lib/clang.lib')

    if is_macos():
        cmake_cmd.append('-DREADLINK_CMD=greadlink')

    cmake_cmd.extend(bitness_flags(bitness))
    cmake_cmd.append(src_path)
    do_execute_sub_process(cmake_cmd, build_path, extra_env=environment)

    install_targets = ['install/strip']
    if is_msvc_toolchain(toolchain):
        install_targets = ['install']  # There is no 'install/strip' for nmake.
    build_and_install(toolchain, build_path, environment, [], install_targets)


def check_clang(toolchain, build_path, environment):
    if is_msvc_toolchain(toolchain) or is_mingw_toolchain(toolchain):
        tools_path = os.environ.get('WINDOWS_UNIX_TOOLS_PATH')
        if tools_path:
            path_key = 'Path' if 'Path' in environment else 'PATH'
            environment[path_key] += ';' + tools_path

    build_cmd = build_command(toolchain)
    do_execute_sub_process(build_cmd + ['check-clang'], build_path, abort_on_fail=False, extra_env=environment)


def package_clang(install_path, result_file_path):
    (basepath, dirname) = os.path.split(install_path)
    zip_command = ['7z', 'a', '-mmt4', result_file_path, dirname]
    runCommand(zip_command, basepath)


def upload_clang(file_path, remote_path):
    (path, filename) = os.path.split(file_path)
    scp_bin = '%SCP%' if is_windows() else 'scp'
    scp_command = [scp_bin, filename, remote_path]
    runCommand(scp_command, path)


def profile_data(toolchain):
    if is_windows() and is_mingw_toolchain(toolchain):
        return os.getenv('PROFILE_DATA_URL')


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
    # PACKAGE_STORAGE_SERVER_USER
    # PACKAGE_STORAGE_SERVER
    # PACKAGE_STORAGE_SERVER_BASE_DIR
    # CLANG_UPLOAD_SERVER_PATH
    # Define a remote path where to upload the resulting package
    # "PACKAGE_STORAGE_SERVER_USER@PACKAGE_STORAGE_SERVER:PACKAGE_STORAGE_SERVER_BASE_DIR/CLANG_UPLOAD_SERVER_PATH"
    #
    # LLVM_REPOSITORY_URL
    # URL to the remote llvm-project repository.
    #
    # LLVM_REVISION
    # Git revision, branch or tag for LLVM/Clang check out
    #
    # CLAZY_REPOSITORY_URL
    # URL to the remote clazy repository
    #
    # CLAZY_REVISION
    # Git revision, branch or tag for clazy check out

    base_path = os.path.join(os.environ['PKG_NODE_ROOT'])
    branch = os.environ['CLANG_BRANCH']
    src_path = os.path.join(base_path, 'llvm/llvm')
    build_path = os.path.join(base_path, 'build')
    install_path = os.path.join(base_path, 'libclang')
    bitness = 64 if '64' in os.environ['cfg'] else 32
    toolchain = os.environ['cfg'].split('-')[1].lower()
    environment = build_environment(toolchain, bitness)
    profile_data_path = os.path.join(base_path, 'profile_data')

    remote_path = (get_pkg_value("PACKAGE_STORAGE_SERVER_USER") + '@' + get_pkg_value("PACKAGE_STORAGE_SERVER") + ':'
                   + os.environ['PACKAGE_STORAGE_SERVER_BASE_DIR'] + '/' + os.environ['CLANG_UPLOAD_SERVER_PATH'])

    # Get, build and install LLVM/Clang
    get_clang(base_path, os.environ['LLVM_REPOSITORY_URL'], os.environ['LLVM_REVISION'])

    # TODO: put args in some struct to improve readability, add error checks
    build_clang(toolchain, src_path, build_path, install_path, profile_data_path, False, bitness, environment, build_type='Release')
    check_clang(toolchain, build_path, environment)

    if is_mingw_toolchain(toolchain):
        # We need to build libclang three times.
        # First time as a regular build, which would be used by a Qt Creator build to link to libclang/llvm.
        # Second time a PGO build, which would be trained with Qt Creator itself
        # Third time will use the training data collected and produce the optimized output

        if os.path.exists(profile_data_path):
            rmtree(profile_data_path)
        os.makedirs(profile_data_path)

        # Update the regular build, so that we can see the differences
        result_file_path = os.path.join(base_path, 'libclang-' + branch + '-' + os.environ['CLANG_PLATFORM'] + '-regular.7z')
        package_clang(install_path, result_file_path)
        upload_clang(result_file_path, remote_path)

        build_path_training = os.path.join(base_path, 'build-training')
        install_path_training = os.path.join(base_path, 'libclang-training')
        build_clang(toolchain, src_path, build_path_training, install_path_training, profile_data_path, True, bitness, environment, build_type='Release')
        mingw_training(base_path, os.path.join(base_path, 'qt-creator'), environment, bitness)
        build_clang(toolchain, src_path, build_path_training, install_path, profile_data_path, False, bitness, environment, build_type='Release')

    # Get, build and install clazy
    git_clone_and_checkout(base_path,
                           os.environ['CLAZY_REPOSITORY_URL'],
                           'clazy',
                           os.environ['CLAZY_REVISION'])
    build_clazy(toolchain,
                os.path.join(base_path, 'clazy'),
                os.path.join(base_path, 'clazy-build'),
                install_path,
                bitness,
                environment)

    # Package and upload
    result_file_path = os.path.join(base_path, 'libclang-' + branch + '-' + os.environ['CLANG_PLATFORM'] + '.7z')
    package_clang(install_path, result_file_path)
    upload_clang(result_file_path, remote_path)


if __name__ == "__main__":
    main()
