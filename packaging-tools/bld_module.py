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
import shutil
import sys
from fileinput import FileInput
from functools import reduce
from multiprocessing import cpu_count
from pathlib import Path
from typing import List

from bld_utils import (
    is_linux,
    is_macos,
    is_windows,
    run_build_command,
    run_command,
    run_install_command,
    strip_vars,
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
from logging_util import init_logger
from runner import run_cmd
from threadedwork import ThreadedWork

log = init_logger(__name__, debug_mode=False)

SCRIPT_ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
MODULE_SRC_DIR_NAME = 'module_src'
MODULE_SRC_DIR = os.path.join(SCRIPT_ROOT_DIR, MODULE_SRC_DIR_NAME)


###############################
# function
###############################
def patch_archive(base_dir: str, search_strings: List[str], qt_install_prefix: str) -> None:
    erase_qmake_prl_build_dir(base_dir)
    patch_build_time_paths(base_dir, search_strings, qt_install_prefix)


###############################
# function
###############################
def get_qt_install_prefix(qt_path: str) -> str:
    cmd_args = [os.path.join(qt_path, 'bin', 'qmake'), '-query', 'QT_INSTALL_PREFIX']
    return run_cmd(cmd=cmd_args, cwd=qt_path).strip()


###############################
# function
###############################
def erase_qmake_prl_build_dir(search_path: str) -> None:
    log.info("--- Fix .prl files ---")
    # fetch all .prl files
    file_list = locate_paths(search_path, ['*.prl'], filters=[os.path.isfile])
    # erase lines starting with 'QMAKE_PRL_BUILD_DIR' from .prl files
    for item in file_list:
        found = False
        for line in FileInput(item, inplace=True):
            if line.startswith('QMAKE_PRL_BUILD_DIR'):
                found = True
                log.info("".rstrip("\n"))
            else:
                log.info(line.rstrip("\n"))
        if found:
            log.info("Erased 'QMAKE_PRL_BUILD_DIR' from: %s", item)


###############################
# function
###############################
def patch_build_time_paths(search_path: str, search_strings: List[str], qt_install_prefix: str) -> None:
    extension_list = ['*.prl', '*.pri', '*.pc', '*.la']
    search_regexp = '|'.join(search_strings)
    file_list = search_for_files(search_path, extension_list, search_regexp)

    for item in file_list:
        log.info("Replacing %s paths from file: %s", search_strings, item)
        for line in FileInput(item, inplace=True):
            patched_line = reduce(lambda accum, value: accum.replace(value, qt_install_prefix),
                                  search_strings,
                                  line)
            log.info(patched_line.rstrip("\n"))


def main() -> None:
    """Main"""
    # install an argument parser
    parser = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        add_help=True, description="build Qt 5 based Qt Module",
        formatter_class=argparse.RawTextHelpFormatter
    )
    if is_windows():
        parser.epilog = f"example on windows: {os.linesep}\tpython {Path(sys.argv[0]).name} --clean " \
            "--buildcommand C:\\bin\\ibjom.cmd" \
            "--qt5_module_url <uri to qt5_essentials.7z> " \
            "--qt5_module_url <uri to qt5_addons.7z> " \
            "--qt5_module_url <uri to qt5_webengine.7z> " \
            "--module_url <url into module repository>" \
            "--module_branch <module branch>" \
            "--module_dir <Local copy of module>"
    elif is_macos():
        parser.epilog = f"example: {os.linesep}\tpython {Path(sys.argv[0]).name} --clean " \
            "--qt5_module_url <uri to qt5_essentials.7z> " \
            "--qt5_module_url <uri to qt5_addons.7z> " \
            "--qt5_module_url <uri to qt5_webengine.7z> " \
            "--module_url <url into module repository>" \
            "--module_branch <module branch>" \
            "--module_dir <Local copy of module>"
    else:
        parser.epilog = f"example: {os.linesep}\tpython {Path(sys.argv[0]).name} --clean " \
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

    caller_arguments = parser.parse_args()

    # cleanup some values inside the caller_arguments object
    strip_vars(caller_arguments, "\"")
    if caller_arguments.qt5path != os.path.abspath(caller_arguments.qt5path):
        log.info(
            "Changing the value of --qt5path: %s -> %s",
            caller_arguments.qt5path, os.path.abspath(caller_arguments.qt5path)
        )
        caller_arguments.qt5path = os.path.abspath(caller_arguments.qt5path)

    if not caller_arguments.module_name:
        caller_arguments.module_name = os.environ['MODULE_NAME']

    temp_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'temp'))

    # clone module repo
    if caller_arguments.module_url != '':
        Path(MODULE_SRC_DIR).mkdir(parents=True, exist_ok=True)
        clone_repository(caller_arguments.module_url, caller_arguments.module_branch, os.path.join(os.path.dirname(__file__), MODULE_SRC_DIR_NAME))
        qt_module_source_directory = MODULE_SRC_DIR
    elif caller_arguments.module7z != '':
        Path(MODULE_SRC_DIR).mkdir(parents=True, exist_ok=True)
        my_get_qt_module = ThreadedWork("get and extract module src")
        my_get_qt_module.add_task_object(create_download_and_extract_tasks(caller_arguments.module7z, MODULE_SRC_DIR, temp_path))
        my_get_qt_module.run()
        qt_module_source_directory = MODULE_SRC_DIR
    else:
        log.info("Using local copy of %s", caller_arguments.module_name)
        qt_module_source_directory = caller_arguments.module_dir

    # install directory
    qt_module_install_directory = qt_module_source_directory + '_install'
    if is_windows():
        # rip out drive letter from path on Windows
        qt_module_install_directory = qt_module_install_directory[2:]
        # check whether this is a QNX build
        if any('qnx' in qt5_url.lower() for qt5_url in caller_arguments.qt5_module_urls):
            # apply the workaround from QTBUG-38555
            qt_module_install_directory = qt_module_install_directory.replace('\\', '/').replace('/', '\\', 1)

    # clean step
    if caller_arguments.clean:
        log.info("##### clean old builds #####")
        remove_tree(caller_arguments.qt5path)
        remove_tree(qt_module_install_directory)
        remove_tree(temp_path)

    if not os.path.lexists(caller_arguments.qt5path) and not caller_arguments.qt5_module_urls:
        parser.print_help()
        log.error(
            "The --qt5path %s does not exist, please add the missing --qt5_module_url arguments",
            caller_arguments.qt5path
        )
        raise RuntimeError()

    qmake_binary = os.path.abspath(os.path.join(caller_arguments.qt5path, 'bin', 'qmake'))

    if not os.path.lexists(caller_arguments.qt5path):
        # get Qt
        my_get_qt_binary_work = ThreadedWork("get and extract Qt 5 binary")
        my_get_qt_binary_work.add_task_object(
            create_qt_download_task(
                caller_arguments.qt5_module_urls,
                caller_arguments.qt5path, temp_path, caller_arguments
            )
        )
        my_get_qt_binary_work.run()

        # Save QT_INSTALL_PREFIX
        qt_install_prefix = get_qt_install_prefix(caller_arguments.qt5path)

        # "install" Qt
        patch_qt(caller_arguments.qt5path)

    # lets start building

    # prepare the environment for example setting LD_LIBRARY_PATH
    # or adding qmake path into the Path environment variable (Qt deployment step)
    path_key_list = []
    qt_bin_path = os.path.abspath(os.path.join(caller_arguments.qt5path, 'bin'))
    path_key_list.append(qt_bin_path)
    python_executable_path = os.path.dirname(sys.executable)
    path_key_list.append(python_executable_path)

    environment = {'PATH': os.pathsep.join(path_key_list)}

    if is_linux():
        environment["LD_LIBRARY_PATH"] = os.pathsep.join(
            [os.path.join(caller_arguments.qt5path, 'lib')]
            + os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep)
        )
        environment["QMAKESPEC"] = "linux-g++"

    if is_macos():
        environment["DYLD_FRAMEWORK_PATH"] = os.path.join(caller_arguments.qt5path, 'lib')

    if not is_windows():
        environment["MAKEFLAGS"] = "-j" + str(cpu_count() + 1)

    if caller_arguments.debug:
        build_type = 'debug'
    else:
        build_type = 'release'

    qt_module_build_directory = qt_module_source_directory + '_build'

    if caller_arguments.use_cmake:
        generate_command = ['cmake',
                            '-DCMAKE_VERBOSE_MAKEFILE=YES',
                            # TODO: should get QT_INSTALL_LIBS instead
                            '-DCMAKE_INSTALL_RPATH=' + ';'.join([qt_install_prefix, os.path.join(qt_install_prefix, 'lib')]),
                            '-DCMAKE_INSTALL_PREFIX=' + qt_module_install_directory,
                            '-DCMAKE_BUILD_TYPE=' + build_type.capitalize()]
        cmake_prefix_path = [caller_arguments.qt5path]
        for extra_arg in caller_arguments.additional_config_args:
            if extra_arg.startswith('-DCMAKE_PREFIX_PATH'):
                cmake_prefix_path.extend(extra_arg.split('=', 1)[1].split(';'))
            else:
                generate_command.append(extra_arg)
        generate_command.append('-DCMAKE_PREFIX_PATH=' + ';'.join(cmake_prefix_path))
        # for now assume that qt_module_source_directory contains CMakeLists.txt directly
        generate_command.append(qt_module_source_directory)
    else:  # --> qmake
        qt_module_pro_file = locate_path(qt_module_source_directory, ["*.pro"], filters=[os.path.isfile])
        if is_windows():
            # do not shadow-build with qmake on Windows
            qt_module_build_directory = os.path.dirname(qt_module_pro_file)
        generate_command = [qmake_binary]
        generate_command.extend(caller_arguments.additional_config_args)
        if os.environ.get('EXTRA_QMAKE_ARGS'):
            generate_command.append(os.environ["EXTRA_QMAKE_ARGS"])
        generate_command.append(qt_module_pro_file)

    run_command(generate_command, cwd=qt_module_build_directory, extra_environment=environment)

    ret = run_build_command(cwd=qt_module_build_directory, caller_arguments=caller_arguments)
    if ret:
        raise RuntimeError(f"Failure running the last command: {ret}")

    ret = run_install_command(
        ['install', 'INSTALL_ROOT=' + qt_module_install_directory],
        cwd=qt_module_build_directory,
        caller_arguments=caller_arguments, extra_environment=environment
    )
    if ret:
        raise RuntimeError(f"Failure running the last command: {ret}")

    # doc collection
    if caller_arguments.collectDocs:
        doc_list = locate_paths(qt_module_source_directory, ['*.qch'], filters=[os.path.isfile])
        doc_install_dir = os.path.join(qt_module_install_directory, 'doc')
        Path(doc_install_dir).mkdir(parents=True, exist_ok=True)
        for item in doc_list:
            shutil.copy(item, doc_install_dir)

    # enginio etc. docs creation
    if caller_arguments.makeDocs:
        # build docs first
        ret = run_install_command(
            'docs', cwd=qt_module_build_directory,
            caller_arguments=caller_arguments, extra_environment=environment
        )
        if ret:
            raise RuntimeError(f"Failure running the last command: {ret}")
        # then make install those
        ret = run_install_command(
            ['install_docs', 'INSTALL_ROOT=' + qt_module_install_directory],
            cwd=qt_module_build_directory,
            caller_arguments=caller_arguments, extra_environment=environment
        )
        if ret:
            raise RuntimeError(f"Failure running the last command: {ret}")
        # make separate "doc.7z" for later use if needed
        doc_dir = locate_path(qt_module_install_directory, ["doc"], filters=[os.path.isdir])
        archive_name = caller_arguments.module_name + '-' + os.environ['LICENSE'] + '-doc-' + os.environ['MODULE_VERSION'] + '.7z'
        ret = run_command(
            ['7z', 'a', os.path.join('doc_archives', archive_name), doc_dir],
            cwd=os.path.dirname(os.path.realpath(__file__))
        )
        if ret:
            raise RuntimeError(f"Failure running the last command: {ret}")

    # try to figure out where the actual exported content is
    qt5_install_basename = Path(caller_arguments.qt5path).name

    if caller_arguments.use_cmake:
        dir_to_archive = qt_module_install_directory
    else:
        dir_to_archive = locate_path(qt_module_install_directory, [qt5_install_basename], filters=[os.path.isdir])

    # if .tag file exists in the source package (sha1) then copy it into the binary archive
    try:
        tag_file = locate_path(qt_module_source_directory, [".tag"], filters=[os.path.isfile])
        shutil.copy2(tag_file, dir_to_archive)
    except PackagingError:
        pass

    # Pre-patch the package for IFW to patch it correctly during installation
    patch_archive(dir_to_archive, [caller_arguments.qt5path, dir_to_archive], qt_install_prefix)

    archive_cmd = ['7z', 'a', os.path.join('module_archives', 'qt5_' + caller_arguments.module_name + '.7z')]
    if caller_arguments.use_cmake:
        archive_cmd.append(os.path.join(dir_to_archive, '*'))
    else:
        archive_cmd.append(dir_to_archive)
    ret = run_command(archive_cmd, cwd=os.path.dirname(os.path.realpath(__file__)))
    if ret:
        raise RuntimeError(f"Failure running the last command: {ret}")


if __name__ == "__main__":
    main()
