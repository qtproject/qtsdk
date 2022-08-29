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
import shutil
import sys
from fileinput import FileInput
from functools import reduce
from multiprocessing import cpu_count
from pathlib import Path

from bld_utils import (
    is_linux,
    is_macos,
    is_windows,
    runBuildCommand,
    runCommand,
    runInstallCommand,
    stripVars,
)
from bldinstallercommon import (
    clone_repository,
    create_download_and_extract_tasks,
    create_qt_download_task,
    locate_path,
    locate_paths,
    patch_qt,
    remove_tree,
    search_for_files,
)
from installer_utils import PackagingError
from runner import do_execute_sub_process
from threadedwork import ThreadedWork

SCRIPT_ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
MODULE_SRC_DIR_NAME = 'module_src'
MODULE_SRC_DIR = os.path.join(SCRIPT_ROOT_DIR, MODULE_SRC_DIR_NAME)


###############################
# function
###############################
def patch_archive(base_dir, search_strings, qt_install_prefix):
    erase_qmake_prl_build_dir(base_dir)
    patch_build_time_paths(base_dir, search_strings, qt_install_prefix)


###############################
# function
###############################
def get_qt_install_prefix(qt_path):
    cmd_args = [os.path.join(qt_path, 'bin', 'qmake'), '-query', 'QT_INSTALL_PREFIX']
    _, qt_install_prefix = do_execute_sub_process(cmd_args, qt_path, get_output=True)
    return qt_install_prefix.strip()


###############################
# function
###############################
def erase_qmake_prl_build_dir(search_path):
    print('--- Fix .prl files ---')
    # fetch all .prl files
    file_list = locate_paths(search_path, ['*.prl'], filters=[os.path.isfile])
    # erase lines starting with 'QMAKE_PRL_BUILD_DIR' from .prl files
    for item in file_list:
        found = False
        for line in FileInput(item, inplace=1):
            if line.startswith('QMAKE_PRL_BUILD_DIR'):
                found = True
                print(''.rstrip('\n'))
            else:
                print(line.rstrip('\n'))
        if found:
            print(f"Erased 'QMAKE_PRL_BUILD_DIR' from: {item}")


###############################
# function
###############################
def patch_build_time_paths(search_path, search_strings, qt_install_prefix):
    extension_list = ['*.prl', '*.pri', '*.pc', '*.la']
    search_regexp = '|'.join(search_strings)
    file_list = search_for_files(search_path, extension_list, search_regexp)

    for item in file_list:
        print(f"Replacing {search_strings} paths from file: {item}")
        for line in FileInput(item, inplace=1):
            patched_line = reduce(lambda accum, value: accum.replace(value, qt_install_prefix),
                                  search_strings,
                                  line)
            print(patched_line.rstrip('\n'))


def main() -> None:
    """Main"""
    # install an argument parser
    parser = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        add_help=True, description="build Qt 5 based Qt Module",
        formatter_class=argparse.RawTextHelpFormatter
    )
    if is_windows():
        parser.epilog = f"example on windows: {os.linesep}\tpython {os.path.basename(sys.argv[0])} --clean " \
            "--buildcommand C:\\bin\\ibjom.cmd" \
            "--qt5_module_url <uri to qt5_essentials.7z> " \
            "--qt5_module_url <uri to qt5_addons.7z> " \
            "--qt5_module_url <uri to qt5_webengine.7z> " \
            "--module_url <url into module repository>" \
            "--module_branch <module branch>" \
            "--module_dir <Local copy of module>"
    elif is_macos():
        parser.epilog = f"example: {os.linesep}\tpython {os.path.basename(sys.argv[0])} --clean " \
            "--qt5_module_url <uri to qt5_essentials.7z> " \
            "--qt5_module_url <uri to qt5_addons.7z> " \
            "--qt5_module_url <uri to qt5_webengine.7z> " \
            "--module_url <url into module repository>" \
            "--module_branch <module branch>" \
            "--module_dir <Local copy of module>"
    else:
        parser.epilog = f"example: {os.linesep}\tpython {os.path.basename(sys.argv[0])} --clean " \
            "--qt5_module_url <uri to qt5_essentials.7z> " \
            "--qt5_module_url <uri to qt5_addons.7z> " \
            "--qt5_module_url <uri to qt5_webengine.7z> " \
            "--module_url <url into module repository>" \
            "--module_branch <module branch>" \
            "--module_dir <Local copy of module>"

    # general arguments
    parser.add_argument('--clean', help="clean up everything from old builds", action='store_true', default=False)
    parser.add_argument('--qt5path', help="here it expects a compiled Qt5", required=True)
    parser.add_argument('--use-cmake', help="use cmake instead of qmake for generating Makefiles", action='store_true', default=False)
    parser.add_argument('--add-config-arg', help='additional argument to use with qmake or cmake', action='append', default=[], dest='additional_config_args')
    parser.add_argument('--buildcommand', help="this means usually make", default="make")
    parser.add_argument('--installcommand', help="this means usually make", default="make")
    parser.add_argument('--debug', help="use debug builds", action='store_true', default=False)
    parser.add_argument('--qt5_module_url', help="a file or url where to get a qt5 module's binary content that is needed for the build as 7z",
                        dest='qt5_module_urls', action='append')
    parser.add_argument('--module-name', help='name of the module, used for the resulting 7zip file')
    parser.add_argument('--module_url', help="Git URL for Qt Module", required=False, default='')
    parser.add_argument('--module_branch', help="Git branch for Qt Module", required=False, default='')
    parser.add_argument('--module_dir', help="Local copy of Qt Module", required=False, default='')
    parser.add_argument('--module7z', help="a file or url where it get the module source", required=False, default='')
    parser.add_argument('--makeDocs', help="Should the docs be built for this component?", required=False, action='store_true', default=False)
    parser.add_argument('--collectDocs', help="Should the docs be collected for this component?", required=False, action='store_true', default=False)

    if not is_macos():
        parser.add_argument('--icu7z', help="a file or url where it get icu libs as 7z", required=False, default='')

    if is_windows():
        parser.add_argument('--environment_batch', help="batch file that sets up environment")
        parser.add_argument('--environment_batch_argument', help="if the batch file needs an argument just add it with this argument")

    callerArguments = parser.parse_args()

    # cleanup some values inside the callerArguments object
    stripVars(callerArguments, "\"")
    if callerArguments.qt5path != os.path.abspath(callerArguments.qt5path):
        print(f"changing the value of --qt5path from {callerArguments.qt5path} to {os.path.abspath(callerArguments.qt5path)}")
        callerArguments.qt5path = os.path.abspath(callerArguments.qt5path)

    if not callerArguments.module_name:
        callerArguments.module_name = os.environ['MODULE_NAME']

    tempPath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'temp'))

    # clone module repo
    if callerArguments.module_url != '':
        Path(MODULE_SRC_DIR).mkdir(parents=True, exist_ok=True)
        clone_repository(callerArguments.module_url, callerArguments.module_branch, os.path.join(os.path.dirname(__file__), MODULE_SRC_DIR_NAME))
        qtModuleSourceDirectory = MODULE_SRC_DIR
    elif callerArguments.module7z != '':
        Path(MODULE_SRC_DIR).mkdir(parents=True, exist_ok=True)
        myGetQtModule = ThreadedWork("get and extract module src")
        myGetQtModule.addTaskObject(create_download_and_extract_tasks(callerArguments.module7z, MODULE_SRC_DIR, tempPath))
        myGetQtModule.run()
        qtModuleSourceDirectory = MODULE_SRC_DIR
    else:
        print(f"Using local copy of {callerArguments.module_name}")
        qtModuleSourceDirectory = callerArguments.module_dir

    # install directory
    qtModuleInstallDirectory = qtModuleSourceDirectory + '_install'
    if is_windows():
        # rip out drive letter from path on Windows
        qtModuleInstallDirectory = qtModuleInstallDirectory[2:]
        # check whether this is a QNX build
        if any('qnx' in qt5_url.lower() for qt5_url in callerArguments.qt5_module_urls):
            # apply the workaround from QTBUG-38555
            qtModuleInstallDirectory = qtModuleInstallDirectory.replace('\\', '/').replace('/', '\\', 1)

    # clean step
    if callerArguments.clean:
        print("##### clean old builds #####")
        remove_tree(callerArguments.qt5path)
        remove_tree(qtModuleInstallDirectory)
        remove_tree(tempPath)

    if not os.path.lexists(callerArguments.qt5path) and not callerArguments.qt5_module_urls:
        parser.print_help()
        print(f"error: Please add the missing qt5_module_url arguments if the {callerArguments.qt5path} does not exist {os.linesep}{os.linesep}")
        raise RuntimeError()

    qmakeBinary = os.path.abspath(os.path.join(callerArguments.qt5path, 'bin', 'qmake'))

    if not os.path.lexists(callerArguments.qt5path):
        # get Qt
        myGetQtBinaryWork = ThreadedWork("get and extract Qt 5 binary")
        myGetQtBinaryWork.addTaskObject(
            create_qt_download_task(
                callerArguments.qt5_module_urls,
                callerArguments.qt5path, tempPath, callerArguments
            )
        )
        myGetQtBinaryWork.run()

        # Save QT_INSTALL_PREFIX
        qt_install_prefix = get_qt_install_prefix(callerArguments.qt5path)

        # "install" Qt
        patch_qt(callerArguments.qt5path)

    # lets start building

    # prepare the environment for example setting LD_LIBRARY_PATH
    # or adding qmake path into the Path environment variable (Qt deployment step)
    pathKeyList = []
    qtBinPath = os.path.abspath(os.path.join(callerArguments.qt5path, 'bin'))
    pathKeyList.append(qtBinPath)
    pythonExecutablePath = os.path.dirname(sys.executable)
    pathKeyList.append(pythonExecutablePath)

    environment = {'PATH': os.pathsep.join(pathKeyList)}

    if is_linux():
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(
            [os.path.join(callerArguments.qt5path, 'lib')]
            + os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep)
        )
        environment["QMAKESPEC"] = "linux-g++"

    if is_macos():
        environment["DYLD_FRAMEWORK_PATH"] = os.path.join(callerArguments.qt5path, 'lib')

    if not is_windows():
        environment["MAKEFLAGS"] = "-j" + str(cpu_count() + 1)

    if callerArguments.debug:
        buildType = 'debug'
    else:
        buildType = 'release'

    qtModuleBuildDirectory = qtModuleSourceDirectory + '_build'

    if callerArguments.use_cmake:
        generateCommand = ['cmake',
                           '-DCMAKE_VERBOSE_MAKEFILE=YES',
                           # TODO: should get QT_INSTALL_LIBS instead
                           '-DCMAKE_INSTALL_RPATH=' + ';'.join([qt_install_prefix, os.path.join(qt_install_prefix, 'lib')]),
                           '-DCMAKE_INSTALL_PREFIX=' + qtModuleInstallDirectory,
                           '-DCMAKE_BUILD_TYPE=' + buildType.capitalize()]
        cmake_prefix_path = [callerArguments.qt5path]
        for extra_arg in callerArguments.additional_config_args:
            if extra_arg.startswith('-DCMAKE_PREFIX_PATH'):
                cmake_prefix_path.extend(extra_arg.split('=', 1)[1].split(';'))
            else:
                generateCommand.append(extra_arg)
        generateCommand.append('-DCMAKE_PREFIX_PATH=' + ';'.join(cmake_prefix_path))
        # for now assume that qtModuleSourceDirectory contains CMakeLists.txt directly
        generateCommand.append(qtModuleSourceDirectory)
    else:  # --> qmake
        qtModuleProFile = locate_path(qtModuleSourceDirectory, ["*.pro"], filters=[os.path.isfile])
        if is_windows():
            # do not shadow-build with qmake on Windows
            qtModuleBuildDirectory = os.path.dirname(qtModuleProFile)
        generateCommand = [qmakeBinary]
        generateCommand.extend(callerArguments.additional_config_args)
        if os.environ.get('EXTRA_QMAKE_ARGS'):
            generateCommand.append(os.environ["EXTRA_QMAKE_ARGS"])
        generateCommand.append(qtModuleProFile)

    runCommand(generateCommand, currentWorkingDirectory=qtModuleBuildDirectory, extra_environment=environment)

    ret = runBuildCommand(currentWorkingDirectory=qtModuleBuildDirectory, callerArguments=callerArguments)
    if ret:
        raise RuntimeError(f"Failure running the last command: {ret}")

    ret = runInstallCommand(
        ['install', 'INSTALL_ROOT=' + qtModuleInstallDirectory],
        currentWorkingDirectory=qtModuleBuildDirectory,
        callerArguments=callerArguments, extra_environment=environment
    )
    if ret:
        raise RuntimeError(f"Failure running the last command: {ret}")

    # doc collection
    if callerArguments.collectDocs:
        doc_list = locate_paths(qtModuleSourceDirectory, ['*.qch'], filters=[os.path.isfile])
        doc_install_dir = os.path.join(qtModuleInstallDirectory, 'doc')
        Path(doc_install_dir).mkdir(parents=True, exist_ok=True)
        for item in doc_list:
            shutil.copy(item, doc_install_dir)

    # enginio etc. docs creation
    if callerArguments.makeDocs:
        # build docs first
        ret = runInstallCommand(
            'docs', currentWorkingDirectory=qtModuleBuildDirectory,
            callerArguments=callerArguments, extra_environment=environment
        )
        if ret:
            raise RuntimeError(f"Failure running the last command: {ret}")
        # then make install those
        ret = runInstallCommand(
            ['install_docs', 'INSTALL_ROOT=' + qtModuleInstallDirectory],
            currentWorkingDirectory=qtModuleBuildDirectory,
            callerArguments=callerArguments, extra_environment=environment
        )
        if ret:
            raise RuntimeError(f"Failure running the last command: {ret}")
        # make separate "doc.7z" for later use if needed
        doc_dir = locate_path(qtModuleInstallDirectory, ["doc"], filters=[os.path.isdir])
        archive_name = callerArguments.module_name + '-' + os.environ['LICENSE'] + '-doc-' + os.environ['MODULE_VERSION'] + '.7z'
        ret = runCommand(
            ['7z', 'a', os.path.join('doc_archives', archive_name), doc_dir],
            currentWorkingDirectory=os.path.dirname(os.path.realpath(__file__))
        )
        if ret:
            raise RuntimeError(f"Failure running the last command: {ret}")

    # try to figure out where the actual exported content is
    qt5_install_basename = os.path.basename(callerArguments.qt5path)

    if callerArguments.use_cmake:
        dir_to_archive = qtModuleInstallDirectory
    else:
        dir_to_archive = locate_path(qtModuleInstallDirectory, [qt5_install_basename], filters=[os.path.isdir])

    # if .tag file exists in the source package (sha1) then copy it into the binary archive
    try:
        tag_file = locate_path(qtModuleSourceDirectory, [".tag"], filters=[os.path.isfile])
        shutil.copy2(tag_file, dir_to_archive)
    except PackagingError:
        pass

    # Pre-patch the package for IFW to patch it correctly during installation
    patch_archive(dir_to_archive, [callerArguments.qt5path, dir_to_archive], qt_install_prefix)

    archive_cmd = ['7z', 'a', os.path.join('module_archives', 'qt5_' + callerArguments.module_name + '.7z')]
    if callerArguments.use_cmake:
        archive_cmd.append(os.path.join(dir_to_archive, '*'))
    else:
        archive_cmd.append(dir_to_archive)
    ret = runCommand(archive_cmd, currentWorkingDirectory=os.path.dirname(os.path.realpath(__file__)))
    if ret:
        raise RuntimeError(f"Failure running the last command: {ret}")


if __name__ == "__main__":
    main()
