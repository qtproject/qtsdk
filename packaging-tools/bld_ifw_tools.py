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
import re
import shlex
import shutil
import subprocess
import sys
from multiprocessing import cpu_count
from pathlib import Path
from typing import Dict, List

from bld_utils import is_linux, is_macos, is_windows
from bldinstallercommon import (
    clone_repository,
    extract_file,
    get_tag_from_branch,
    is_content_url_valid,
    locate_executable,
    locate_path,
    move_tree,
    remove_tree,
    retrieve_url,
)
from installer_utils import PackagingError, ch_dir
from logging_util import init_logger
from pkg_constants import IFW_BUILD_ARTIFACTS_DIR
from read_remote_config import get_pkg_value
from runner import run_cmd

log = init_logger(__name__, debug_mode=False)
ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
ARCH_EXT = '.zip' if is_windows() else '.tar.xz'
QT_VERSION = '5.12'
QT_VERSION_MINOR = '5.12.7'


ARCHIVE_PROGRAM = '7z'
if is_macos():
    try:
        log.info("Trying to use 7z from")
        subprocess.call(["where", "7z"])
    except OSError:
        log.warning("7z not found from path. Try to use 7z from /usr/local/bin")
        ARCHIVE_PROGRAM = "/usr/local/bin/7z"


##################################################################
# Get static Qt configure arguments. Platform is detected.
##################################################################
def get_static_qt_configure_options(openssl_dir: str) -> str:
    options = get_common_qt_configure_options() + '-static -no-sql-sqlite '
    if is_macos():
        options += '-no-securetransport '
    options += '-openssl-linked '
    if (is_linux() or is_macos()) and openssl_dir:
        options += f"-I {openssl_dir}/include -L {openssl_dir}/lib "
    if is_windows():
        options += '-static-runtime '
        if openssl_dir:
            options += 'OPENSSL_LIBS="-llibssl -llibcrypto -lUser32 -lWs2_32 -lAdvapi32 -lCrypt32" '
            options += f'-I {openssl_dir}\\include -L {openssl_dir}\\lib '
    return options


##################################################################
# Get common Qt configure arguments for all platforms
##################################################################
def get_common_allos_qt_configure_options() -> str:
    options = '-release -opensource -confirm-license '
    options += '-nomake examples -nomake tests '
    options += '-accessibility '
    return options


##################################################################
# Get common Qt configure arguments for unix platform
##################################################################
def get_common_unix_qt_configure_options() -> str:
    options = '-qt-zlib -qt-libpng -qt-libjpeg -no-cups -disable-vulkan '
    return options


##################################################################
# Get default Qt configure arguments. Platform is detected.
##################################################################
def get_common_qt_configure_options() -> str:
    # common
    options = get_common_allos_qt_configure_options()
    options += '-no-qml-debug '
    # Windows
    if is_windows():
        options += '-no-icu -mp '
    # Unix
    else:
        # OSX and Linux
        options += get_common_unix_qt_configure_options()
        # Linux
        if is_linux():
            options += '-qt-xcb -no-opengl -no-icu -no-libudev '
            options += '-qt-pcre -no-glib -no-egl '
            options += '-no-sm -qt-harfbuzz '
        if is_macos():
            options += '-no-freetype '
    return options


##################################################################
# Configure options for separate Qt build if doc build is needed.
##################################################################
def get_dynamic_qt_configure_options() -> str:
    options = get_common_qt_configure_options()
    options += '-qt-sqlite '
    options += '-no-dbus '
    return options


##################################################################
# Define OPENSSL_LIBS env if openssl_dir is defined
##################################################################
def get_build_env(openssl_dir: str) -> Dict[str, str]:
    tmp = dict(os.environ)
    if is_macos() and os.path.isdir(openssl_dir):
        tmp['OPENSSL_LIBS'] = f"-L{openssl_dir}/lib -lssl -lcrypto"
    if is_linux() and os.path.isdir(openssl_dir):
        tmp['OPENSSL_LIBS'] = f"-I{openssl_dir}/include -L{openssl_dir}/lib -ldl -lssl -lcrypto -lpthread"

    return tmp


###############################
# Option class for ifw build
###############################
class IfwOptions:

    default_qt_src_pkg = 'http://download.qt.io/official_releases/qt/' + QT_VERSION + '/' + QT_VERSION_MINOR + '/single/qt-everywhere-src-' + QT_VERSION_MINOR + ARCH_EXT
    default_qt_installer_framework_url = 'git://code.qt.io/installer-framework/installer-framework.git'
    default_qt_installer_framework_branch_qt = '3.2'
    default_qt_installer_framework_qmake_args = ['-r', '-config', 'release', '-config', 'static']

    def __init__(
        self,
        qt_source_package_uri: str,
        qt_configure_options: str,
        qt_installer_framework_uri: str,
        qt_installer_framework_branch: str,
        qt_installer_framework_qmake_args: List[str],
        openssl_dir: str,
        product_key_checker_pri: str,
        qt_binaries_static: str,
        qt_binaries_dynamic: str,
        signserver: str,
        signpwd: str,
        incremental_build: bool = False,
        archive_qt: bool = False,
    ) -> None:
        self.signserver = signserver
        self.signpwd = signpwd
        self.incremental_mode = incremental_build
        self.qt_source_dir = os.path.join(ROOT_DIR, 'qt-src')
        self.qt_build_dir = os.path.join(ROOT_DIR, 'qt-bld')
        self.qt_build_dir_dynamic = os.path.join(ROOT_DIR, 'qt-bld-dynamic')
        self.installer_framework_source_dir = os.path.join(ROOT_DIR, 'ifw-src')
        self.installer_framework_build_dir = os.path.join(ROOT_DIR, 'ifw-bld')
        self.installer_framework_pkg_dir = os.path.join(ROOT_DIR, 'ifw-pkg')
        self.installer_framework_target_dir = os.path.join(ROOT_DIR, 'ifw-target')
        self.qt_installer_framework_uri = qt_installer_framework_uri
        self.qt_installer_framework_uri_saveas = os.path.join(ROOT_DIR, os.path.basename(self.qt_installer_framework_uri))
        self.qt_installer_framework_branch = qt_installer_framework_branch
        self.qt_installer_framework_branch_pretty = qt_installer_framework_branch.replace("/", "_")
        self.qt_installer_framework_qmake_args = qt_installer_framework_qmake_args
        self.openssl_dir = openssl_dir
        self.qt_binaries_static = qt_binaries_static
        if self.qt_binaries_static:
            self.qt_binaries_static_saveas = os.path.join(ROOT_DIR, os.path.basename(self.qt_binaries_static))
        self.qt_binaries_dynamic = qt_binaries_dynamic
        if self.qt_binaries_dynamic:
            self.qt_binaries_dynamic_saveas = os.path.join(ROOT_DIR, os.path.basename(self.qt_binaries_dynamic))
        self.qt_build_modules = ["qtbase", "qtdeclarative", "qttools", "qttranslations"]
        self.qt_build_modules_docs = ["qtbase", "qttools"]
        if is_windows():
            self.qt_build_modules.append("qtwinextras")
            self.make_cmd = 'jom.exe'
            self.make_doc_cmd = 'jom.exe'
            self.make_install_cmd = 'jom.exe install'
            self.qt_qmake_bin = 'qmake.exe'
            self.qt_configure_bin = self.qt_source_dir + os.sep + 'configure.bat'
        else:
            self.make_cmd = 'make -j' + str(cpu_count() + 1)
            self.make_doc_cmd = 'make'
            self.make_install_cmd = 'make install'
            self.qt_qmake_bin = 'qmake'
            self.qt_configure_bin = self.qt_source_dir + os.sep + 'configure'

        self.build_artifacts_dir = os.path.join(ROOT_DIR, IFW_BUILD_ARTIFACTS_DIR)
        self.mac_deploy_qt_archive_name = 'macdeployqt.7z'
        self.mac_qt_menu_nib_archive_name = 'qt_menu.nib.7z'
        # determine filenames used later on
        self.architecture = 'x64'
        self.plat_suffix = get_platform_suffix()
        self.installer_framework_archive_name = 'installer-framework-build-' + self.qt_installer_framework_branch_pretty + "-" + self.plat_suffix + '-' + self.architecture + '.7z'
        self.installer_base_archive_name = 'installerbase-' + self.qt_installer_framework_branch_pretty + "-" + self.plat_suffix + '-' + self.architecture + '.7z'
        self.binarycreator_archive_name = 'binarycreator-' + self.qt_installer_framework_branch_pretty + "-" + self.plat_suffix + '-' + self.architecture + '.7z'
        self.installer_framework_payload_arch = 'installer-framework-build-stripped-' + self.qt_installer_framework_branch_pretty + "-" + self.plat_suffix + '-' + self.architecture + '.7z'
        self.qt_source_package_uri = qt_source_package_uri
        self.qt_source_package_uri_saveas = os.path.join(ROOT_DIR, os.path.basename(self.qt_source_package_uri))
        # Set Qt build prefix
        qt_prefix = ' -prefix ' + self.qt_build_dir + os.sep + 'qtbase'
        self.qt_configure_options = qt_configure_options + qt_prefix
        # Product key checker
        self.product_key_checker_pri = product_key_checker_pri
        if product_key_checker_pri:
            if os.path.isfile(product_key_checker_pri):
                self.qt_installer_framework_qmake_args += ['PRODUCTKEYCHECK_PRI_FILE=' + self.product_key_checker_pri]
        # macOS specific
        if is_macos():
            self.qt_installer_framework_qmake_args += ['"LIBS+=-framework IOKit"']
        self.archive_qt = archive_qt
        self.qt_static_binary_name = 'qt-bin-' + QT_VERSION + '-' + self.plat_suffix + '_static.7z'
        self.qt_shared_binary_name = 'qt-bin-' + QT_VERSION + '-' + self.plat_suffix + '_shared.7z'
        # sanity check
        self.sanity_check()

    def sanity_check(self) -> None:
        # check qt src package url
        res = is_content_url_valid(self.qt_source_package_uri)
        if not res:
            raise SystemExit(f"Qt src package uri is invalid: {self.qt_source_package_uri}")
        if self.product_key_checker_pri:
            if os.path.isfile(self.product_key_checker_pri):
                log.info("Using product key checker: %s", self.product_key_checker_pri)
            else:
                raise SystemExit(f"Invalid product key checker: {self.product_key_checker_pri}")

    def print_data(self) -> None:
        log.info("-----------------------------------------")
        log.info("make cmd: %s", self.make_cmd)
        log.info("make doc_cmd: %s", self.make_doc_cmd)
        log.info("qt_source_package_uri: %s", self.qt_source_package_uri)
        log.info("qt_source_package_uri_saveas: %s", self.qt_source_package_uri_saveas)
        log.info("qt_source_dir: %s", self.qt_source_dir)
        log.info("qt_build_dir: %s", self.qt_build_dir)
        log.info("qt_build_dir_dynamic: %s", self.qt_build_dir_dynamic)
        log.info("qt_configure_options: %s", self.qt_configure_options)
        log.info("qt_qmake_bin: %s", self.qt_qmake_bin)
        log.info("qt_configure_bin: %s", self.qt_configure_bin)
        log.info("qt_installer_framework_uri: %s", self.qt_installer_framework_uri)
        log.info("qt_installer_framework_branch: %s", self.qt_installer_framework_branch)
        log.info("qt_installer_framework_qmake_args: %s", self.qt_installer_framework_qmake_args)
        log.info("openssl_dir: %s", self.openssl_dir)
        log.info("installer_framework_source_dir: %s", self.installer_framework_source_dir)
        log.info("installer_framework_build_dir: %s", self.installer_framework_build_dir)
        log.info("installer_framework_archive_name: %s", self.installer_framework_archive_name)
        log.info("installer_base_archive_name: %s", self.installer_base_archive_name)
        log.info("binarycreator_archive_name: %s", self.binarycreator_archive_name)
        log.info("installer_framework_pkg_dir: %s", self.installer_framework_pkg_dir)
        log.info("installer_framework_target_dir: %s", self.installer_framework_target_dir)
        log.info("installer_framework_payload_arch: %s", self.installer_framework_payload_arch)
        log.info("product_key_checker_pri: %s", self.product_key_checker_pri)
        log.info("qt_binaries_static: %s", self.qt_binaries_static)
        log.info("qt_binaries_dynamic: %s", self.qt_binaries_dynamic)
        log.info("-----------------------------------------")


###############################
# Build IFW
###############################
def build_ifw(options: IfwOptions, create_installer: bool = False, build_ifw_examples: bool = False) -> str:
    # verbose
    options.print_data()
    # clean environment first
    clean_build_environment(options)
    # checkout sources
    prepare_installer_framework(options)

    if options.qt_binaries_static:
        prepare_compressed_package(options.qt_binaries_static, options.qt_binaries_static_saveas, options.qt_build_dir)
    else:
        prepare_qt_sources(options)
        build_qt(options, options.qt_build_dir, options.qt_configure_options, options.qt_build_modules)
    # build installer framework
    build_installer_framework(options)
    if build_ifw_examples:
        build_installer_framework_examples(options)
    # steps when creating ifw installer
    if create_installer:
        if options.qt_binaries_dynamic:
            prepare_compressed_package(options.qt_binaries_dynamic, options.qt_binaries_dynamic_saveas, options.qt_build_dir_dynamic)
            if is_windows():
                patch_win32_mkspecs(os.path.join(options.qt_build_dir_dynamic, "qtbase", "mkspecs"))
        else:
            configure_options = get_dynamic_qt_configure_options() + '-prefix ' + options.qt_build_dir_dynamic + os.sep + 'qtbase'
            # Although we have a shadow build qt sources are still taminated. Unpack sources again.
            if os.path.exists(options.qt_source_dir):
                remove_tree(options.qt_source_dir)
            prepare_qt_sources(options)
            build_qt(options, options.qt_build_dir_dynamic, configure_options, options.qt_build_modules_docs)
        build_ifw_docs(options)
        create_installer_package(options)
    # archive
    archive_installerbase(options)
    archive_installer_framework(options.installer_framework_build_dir, options.installer_framework_archive_name, options, True)
    archive_binarycreator(options)
    return os.path.basename(options.installer_framework_build_dir)


###############################
# function
###############################
def prepare_qt_sources(options: IfwOptions) -> None:
    if options.incremental_mode and os.path.exists(options.qt_source_dir):
        return
    log.info("--------------------------------------------------------------------")
    log.info("Prepare Qt src package: %s", options.qt_source_package_uri)
    prepare_compressed_package(options.qt_source_package_uri, options.qt_source_package_uri_saveas, options.qt_source_dir)

    if is_windows():
        patch_win32_mkspecs(os.path.join(options.qt_source_dir, "qtbase", "mkspecs"))


###############################
# function
###############################
def prepare_compressed_package(src_pkg_uri: str, src_pkg_saveas: str, destination_dir: str) -> None:
    log.info("Fetching package from: %s", src_pkg_uri)
    if not os.path.isfile(src_pkg_saveas):
        if not is_content_url_valid(src_pkg_uri):
            raise SystemExit("Src package uri is invalid! Abort!")
        retrieve_url(src_pkg_uri, src_pkg_saveas)
    else:
        log.info("Found old local package, using that: %s", src_pkg_saveas)
    log.info("Done")
    log.info("--------------------------------------------------------------------")
    Path(destination_dir).mkdir(parents=True, exist_ok=True)
    extract_file(src_pkg_saveas, destination_dir)
    dir_contents = os.listdir(destination_dir)
    items = len(dir_contents)
    if items == 1:
        dir_name = dir_contents[0]
        full_dir_name = destination_dir + os.sep + dir_name
        move_tree(full_dir_name, destination_dir)
        remove_tree(full_dir_name)
    else:
        raise SystemExit("Invalid dir structure encountered?!")


###############################
# function
###############################
def build_qt(options: IfwOptions, qt_build_dir: str, qt_configure_options: str, qt_modules: List[str]) -> None:
    if options.incremental_mode:
        try:
            locate_path(qt_build_dir, ["lib"], filters=[os.path.isdir])
            qmake_bin = os.path.join(options.qt_build_dir, 'qtbase', 'bin', options.qt_qmake_bin)
            if os.path.isfile(qmake_bin):
                return
        except PackagingError:
            pass
    Path(qt_build_dir).mkdir(parents=True, exist_ok=True)
    # configure first
    log.info("--------------------------------------------------------------------")
    log.info("Configuring Qt")
    configure_options = re.sub(' +', ' ', qt_configure_options)
    cmd_args = options.qt_configure_bin + ' ' + configure_options
    # shlex does not like backslashes
    cmd_args = cmd_args.replace("\\", "/")
    extra_env = get_build_env(options.openssl_dir)
    run_cmd(cmd=shlex.split(cmd_args), cwd=options.qt_source_dir, env=extra_env)
    log.info("--------------------------------------------------------------------")
    log.info("Building Qt")
    cmd_args = options.make_cmd
    for module in qt_modules:
        cmd_args += " module-" + module
    run_cmd(cmd=cmd_args, cwd=options.qt_source_dir, env=extra_env)
    log.info("--------------------------------------------------------------------")
    log.info("Installing Qt")
    cmd_args = options.make_install_cmd
    for module in qt_modules:
        module_dir = os.path.join(options.qt_source_dir, module)
        run_cmd(cmd=cmd_args, cwd=module_dir)


###############################
# function
###############################
def prepare_installer_framework(options: IfwOptions) -> None:
    if options.incremental_mode and os.path.exists(options.installer_framework_source_dir):
        return
    log.info("--------------------------------------------------------------------")
    log.info("Prepare Installer Framework source")
    # create dirs
    Path(options.installer_framework_build_dir).mkdir(parents=True, exist_ok=True)
    if options.qt_installer_framework_uri.endswith('.git'):
        # clone repos
        clone_repository(options.qt_installer_framework_uri, options.qt_installer_framework_branch, options.installer_framework_source_dir, True)

    else:
        # fetch src package
        prepare_compressed_package(options.qt_installer_framework_uri, options.qt_installer_framework_uri_saveas, options.installer_framework_source_dir)


def start_ifw_build(options: IfwOptions, cmd_args: List[str], installer_framework_build_dir: str) -> None:
    run_cmd(cmd=cmd_args, cwd=installer_framework_build_dir)
    cmd_args = options.make_cmd.split(" ")
    run_cmd(cmd=cmd_args, cwd=installer_framework_build_dir)


###############################
# function
###############################
def build_installer_framework(options: IfwOptions) -> None:
    if options.incremental_mode:
        file_to_check = os.path.join(options.installer_framework_build_dir, 'bin', 'installerbase')
        if is_windows():
            file_to_check += '.exe'
        if os.path.exists(file_to_check):
            return

    log.info("--------------------------------------------------------------------")
    log.info("Building Installer Framework")
    qmake_bin = os.path.join(options.qt_build_dir, 'qtbase', 'bin', options.qt_qmake_bin)
    if not os.path.isfile(qmake_bin):
        raise SystemExit(f"Unable to find qmake from {qmake_bin}, aborting!")
    Path(options.installer_framework_build_dir).mkdir(parents=True, exist_ok=True)
    cmd_args = [qmake_bin]
    cmd_args += options.qt_installer_framework_qmake_args
    cmd_args += [options.installer_framework_source_dir]
    start_ifw_build(options, cmd_args, options.installer_framework_build_dir)


def build_installer_framework_examples(options: IfwOptions) -> None:
    log.info("--------------------------------------------------------------------")
    log.info("Building Installer Framework Examples")
    file_binarycreator = os.path.join(options.installer_framework_build_dir, 'bin', 'binarycreator')
    if is_windows():
        file_binarycreator += '.exe'
    if not os.path.exists(file_binarycreator):
        raise SystemExit(f"Unable to find binarycreator from {file_binarycreator}, aborting!")

    ifw_examples = os.path.join(options.installer_framework_source_dir, 'examples')
    ifw_example_binaries = []

    for root, dirs, _ in os.walk(ifw_examples):
        if 'doc' in dirs:
            dirs.remove('doc')  # don't visit doc dir
        if 'translations' in dirs:
            dirs.remove('translations')  # for now don't visit translation example as qm files needs to be generated first
        for directory in dirs:
            log.info("Building example %s", directory)
            config_file = os.path.join(root, directory, 'config', 'config.xml')
            package_dir = os.path.join(root, directory, 'packages')
            target_filename = os.path.join(root, directory, 'installer')
            args = ["--offline-only", "-c", config_file, "-p", package_dir, target_filename]
            run_cmd(cmd=[file_binarycreator] + args, cwd=package_dir)
            if is_windows():
                target_filename += '.exe'
            ifw_example_binaries.append(target_filename)
        # Breaking here as we don't want to go through sub directories
        break


###############################
# function
###############################
def build_ifw_docs(options: IfwOptions) -> None:
    log.info("--------------------------------------------------------------------")
    log.info("Building Qt Installer Framework Documentation")
    qmake_bin = os.path.join(options.qt_build_dir_dynamic, 'qtbase', 'bin', options.qt_qmake_bin)
    if not os.path.isfile(qmake_bin):
        raise SystemExit(f"Aborting doc build, qmake not found in: {options.qt_build_dir_dynamic}")
    cmd_args = qmake_bin + ' -r ' + options.installer_framework_source_dir
    run_cmd(cmd=cmd_args, cwd=options.installer_framework_build_dir)
    cmd_args = options.make_doc_cmd + ' docs'
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = os.path.normpath(os.path.join(os.path.dirname(qmake_bin), '..', 'lib'))
    run_cmd(cmd=cmd_args, cwd=options.installer_framework_build_dir, env=env)


################################################################
# Create installer containing the Qt Installer Framework itself
################################################################
def create_installer_package(options: IfwOptions) -> None:
    log.info("--------------------------------------------------------------------")
    log.info("Creating installer for Qt Installer Framework")
    # Temporary dir for creating installer containing the Qt Installer Framework itself
    package_dir = options.installer_framework_pkg_dir
    os.makedirs(package_dir)
    # Final directory for the installer containing the Qt Installer Framework itself
    os.makedirs(options.installer_framework_target_dir)
    target_dir = os.path.join(options.installer_framework_target_dir, 'QtInstallerFramework' + '-' + options.plat_suffix + '-' + options.architecture)
    with ch_dir(package_dir):
        shutil.copytree(os.path.join(options.installer_framework_build_dir, 'bin'), os.path.join(package_dir, 'bin'), ignore=shutil.ignore_patterns("*.exe.manifest", "*.exp", "*.lib"))
        if is_linux():
            run_cmd(cmd=['strip', os.path.join(package_dir, 'bin/archivegen')], cwd=package_dir)
            run_cmd(cmd=['strip', os.path.join(package_dir, 'bin/binarycreator')], cwd=package_dir)
            run_cmd(cmd=['strip', os.path.join(package_dir, 'bin/devtool')], cwd=package_dir)
            run_cmd(cmd=['strip', os.path.join(package_dir, 'bin/installerbase')], cwd=package_dir)
            run_cmd(cmd=['strip', os.path.join(package_dir, 'bin/repogen')], cwd=package_dir)
        shutil.copytree(os.path.join(options.installer_framework_build_dir, 'doc'), os.path.join(package_dir, 'doc'))
        shutil.copytree(os.path.join(options.installer_framework_source_dir, 'examples'), os.path.join(package_dir, 'examples'))
        shutil.copy(os.path.join(options.installer_framework_source_dir, 'README'), package_dir)
        # pack payload into separate .7z archive for later usage
        cmd_args = [ARCHIVE_PROGRAM, 'a', options.installer_framework_payload_arch, package_dir]
        run_cmd(cmd=cmd_args, cwd=ROOT_DIR)
        shutil.move(os.path.join(ROOT_DIR, options.installer_framework_payload_arch), options.build_artifacts_dir)
        # create 7z
        archive_file = os.path.join(options.installer_framework_source_dir, 'dist', 'packages', 'org.qtproject.ifw.binaries', 'data', 'data.7z')
        if not os.path.exists(os.path.dirname(archive_file)):
            os.makedirs(os.path.dirname(archive_file))
        archivegen = os.path.join(package_dir, 'bin', 'archivegen')
        run_cmd(cmd=[archivegen, archive_file, '*'], cwd=package_dir)
        # run installer
        binary_creator = os.path.join(options.installer_framework_build_dir, 'bin', 'binarycreator')
        config_file = os.path.join(options.installer_framework_source_dir, 'dist', 'config', 'config.xml')
        package_dir = os.path.join(options.installer_framework_source_dir, 'dist', 'packages')
        args = ['--offline-only', '-c', config_file, '-p', package_dir, target_dir]
        run_cmd(cmd=[binary_creator] + args, cwd=package_dir)
        log.info("Installer package is at: %s", target_dir)
        artifacts = os.listdir(options.installer_framework_target_dir)
        for artifact in artifacts:
            dest_file_name = os.path.join(options.build_artifacts_dir, artifact)
            if is_linux():
                dest_file_name += '.run'
            shutil.move(os.path.join(options.installer_framework_target_dir, artifact), dest_file_name)


################################################################
# Build and archive Qt for IFW builds
################################################################
def build_and_archive_qt(options: IfwOptions) -> None:
    log.info("--------------------------------------------------------------------")
    log.info("Build static Qt")
    prepare_qt_sources(options)
    build_qt(options, options.qt_build_dir, options.qt_configure_options, options.qt_build_modules)

    log.info("--------------------------------------------------------------------")
    log.info("Archive static Qt binaries")
    cmd_args_archive = [ARCHIVE_PROGRAM, 'a', options.qt_static_binary_name, options.qt_build_dir]
    run_cmd(cmd=cmd_args_archive, cwd=ROOT_DIR)

    log.info("--------------------------------------------------------------------")
    log.info("Build shared Qt")
    configure_options = get_dynamic_qt_configure_options() + '-prefix ' + options.qt_build_dir_dynamic + os.sep + 'qtbase'
    # Although we have a shadow build qt sources are still contaminated. Unpack sources again.
    if os.path.exists(options.qt_source_dir):
        remove_tree(options.qt_source_dir)
    prepare_qt_sources(options)
    build_qt(options, options.qt_build_dir_dynamic, configure_options, options.qt_build_modules_docs)

    log.info("--------------------------------------------------------------------")
    log.info("Archive shared Qt binaries")
    cmd_args = [ARCHIVE_PROGRAM, 'a', options.qt_shared_binary_name, options.qt_build_dir_dynamic]
    run_cmd(cmd=cmd_args, cwd=ROOT_DIR)


###############################
# function
###############################
def clean_build_environment(options: IfwOptions) -> None:
    if os.path.isfile(options.installer_framework_archive_name):
        os.remove(options.installer_framework_archive_name)
    if os.path.isfile(options.installer_framework_payload_arch):
        os.remove(options.installer_framework_payload_arch)
    if os.path.exists(options.build_artifacts_dir):
        remove_tree(options.build_artifacts_dir)
    Path(options.build_artifacts_dir).mkdir(parents=True, exist_ok=True)
    if os.path.exists(options.installer_framework_build_dir):
        remove_tree(options.installer_framework_build_dir)

    if os.path.exists(options.installer_framework_pkg_dir):
        shutil.rmtree(options.installer_framework_pkg_dir)
    if os.path.exists(options.installer_framework_target_dir):
        shutil.rmtree(options.installer_framework_target_dir)

    if options.incremental_mode:
        return

    if os.path.exists(options.installer_framework_source_dir):
        remove_tree(options.installer_framework_source_dir)
    if os.path.exists(options.qt_source_dir):
        remove_tree(options.qt_source_dir)
    if os.path.exists(options.qt_build_dir):
        remove_tree(options.qt_source_dir)
    if os.path.isfile(options.qt_source_package_uri_saveas):
        os.remove(options.qt_source_package_uri_saveas)
    if os.path.isfile(options.qt_installer_framework_uri_saveas):
        os.remove(options.qt_installer_framework_uri_saveas)


###############################
# function
###############################
def archive_installer_framework(installer_framework_build_dir: str, installer_framework_archive_name: str, options: IfwOptions, create_tagged_package: bool) -> None:
    log.info("--------------------------------------------------------------------")
    log.info("Archive Installer Framework")
    # first strip out all unnecessary files
    for root, dummy, files in os.walk(installer_framework_build_dir):
        for filename in files:
            if filename.endswith(('.moc', 'Makefile', '.cpp', '.h', '.o')) or filename == 'Makefile':
                os.remove(os.path.join(root, filename))
    cmd_args = [ARCHIVE_PROGRAM, 'a', installer_framework_archive_name, os.path.basename(installer_framework_build_dir)]
    run_cmd(cmd=cmd_args, cwd=ROOT_DIR)
    shutil.move(installer_framework_archive_name, options.build_artifacts_dir)
    # Check if installer framework is created from branch. If so, check if the branch is tagged and
    # create a package with a tagged name.
    # Package with the tagged name is needed for creating e.g. offline installers from stable builds
    if options.qt_installer_framework_uri.endswith('.git') and create_tagged_package:
        tag = get_tag_from_branch(options.installer_framework_source_dir)
        if tag:
            log.info("Create archive from tag %s", tag)
            installer_framework_tagged_archive = 'installer-framework-build-' + tag + "-" + options.plat_suffix + '-' + options.architecture + '.7z'
            log.info("Create archive %s", installer_framework_tagged_archive)
            shutil.copy(os.path.join(options.build_artifacts_dir, installer_framework_archive_name), os.path.join(options.build_artifacts_dir, installer_framework_tagged_archive))


###############################
# function
###############################
def archive_installerbase(options: IfwOptions) -> None:
    log.info("--------------------------------------------------------------------")
    log.info("Archive Installerbase")
    cmd_args_archive = []
    cmd_args_clean = []
    bin_temp = ''
    if is_linux() or is_macos():
        bin_path = locate_executable(options.installer_framework_build_dir, ['installerbase'])
        bin_temp = ROOT_DIR + os.sep + '.tempSDKMaintenanceTool'
        shutil.copy(bin_path, bin_temp)
        cmd_args_archive = [ARCHIVE_PROGRAM, 'a', options.installer_base_archive_name, bin_temp]
        cmd_args_clean = ['rm', bin_temp]
    if is_windows():
        bin_path = locate_executable(options.installer_framework_build_dir, ['installerbase.exe'])
        bin_temp = ROOT_DIR + os.sep + 'tempSDKMaintenanceToolBase.exe'
        shutil.copy(bin_path, bin_temp)
        if options.signserver and options.signpwd:
            sign_windows_installerbase('tempSDKMaintenanceToolBase.exe')
        cmd_args_archive = [ARCHIVE_PROGRAM, 'a', options.installer_base_archive_name, bin_temp]
        cmd_args_clean = ['del', bin_temp]
    run_cmd(cmd=cmd_args_archive, cwd=ROOT_DIR)
    run_cmd(cmd=cmd_args_clean, cwd=ROOT_DIR)
    if not os.path.isfile(options.installer_base_archive_name):
        raise SystemExit(f"Failed to generate archive: {options.installer_base_archive_name}")
    shutil.move(options.installer_base_archive_name, options.build_artifacts_dir)


###############################
# function
###############################
def archive_binarycreator(options: IfwOptions) -> None:
    log.info("--------------------------------------------------------------------")
    log.info("Archive Installerbase and Binarycreator")
    cmd_args_archive = []
    if is_linux() or is_macos():
        bin_path = locate_executable(options.installer_framework_build_dir, ['installerbase'])
        binarycreator_path = locate_executable(options.installer_framework_build_dir, ['binarycreator'])
    elif is_windows():
        bin_path = locate_executable(options.installer_framework_build_dir, ['installerbase.exe'])
        binarycreator_path = locate_executable(options.installer_framework_build_dir, ['binarycreator.exe'])
    else:
        raise Exception("Not a supported platform")
    cmd_args_archive = ['7z', 'a', options.binarycreator_archive_name, bin_path, binarycreator_path]
    run_cmd(cmd=cmd_args_archive, cwd=ROOT_DIR)
    if not os.path.isfile(options.binarycreator_archive_name):
        raise Exception(f"*** Failed to generate archive: {options.binarycreator_archive_name}")
    shutil.move(options.binarycreator_archive_name, options.build_artifacts_dir)


###############################
# sign windows installerbase
###############################
def sign_windows_installerbase(file_name: str) -> None:
    log.info("--------------------------------------------------------------------")
    log.info("Sign Windows Installerbase")
    sign_tools_temp_dir = r'C:\Utils\sign_tools_temp'
    for item in ["signtool32.exe", "keys.pfx", "capicom.dll"]:
        dst = os.path.join(sign_tools_temp_dir, item)
        curl_cmd_args = ['curl', "--fail", "-L", "--retry", "5", "--retry-delay", "30", "-o", dst]
        curl_cmd_args += ['--create-dirs', get_pkg_value("SIGN_TOOLS_ADDR") + item]
        run_cmd(cmd=curl_cmd_args)

    signing_server = get_pkg_value("SIGNING_SERVER")
    signing_pass = get_pkg_value("SIGNING_PASSWORD")
    cmd_args = [os.path.join(sign_tools_temp_dir, 'signtool32.exe'), 'sign', '/v', '/du', signing_server, '/p', signing_pass]
    cmd_args += ['/tr', "http://timestamp.digicert.com", '/f', os.path.join(sign_tools_temp_dir, 'keys.pfx')]
    cmd_args += ['/td', "sha256", '/fd', "sha256", file_name]

    log_entry = cmd_args[:]
    log_entry[4] = "****"
    log_entry[6] = "****"
    log.info("Calling: %s", " ".join(log_entry))
    run_cmd(cmd=cmd_args)
    shutil.rmtree(sign_tools_temp_dir)
    log.info("Successfully signed: %s", file_name)


###############################
# Replace all dict keys with values in file
###############################
def patch(file: str, replacements: Dict[str, str]) -> None:
    filedata = None
    log.info("Patching %s ...", file)
    with open(file, 'r', encoding="utf-8") as handle:
        filedata = handle.read()

    for key in replacements:
        filedata = filedata.replace(key, replacements[key])

    with open(file, 'w', encoding="utf-8") as handle:
        handle.write(filedata)


###############################
# Patch win32 mkspecs
###############################
def patch_win32_mkspecs(mkspecsdir: str) -> None:
    log.info("--------------------------------------------------------------------")
    log.info("Patching win32 mkspecs in %s ...", mkspecsdir)
    for root, dummy, files in os.walk(mkspecsdir):
        for file in files:
            if "win32" in root and file == "qmake.conf":
                patch(os.path.join(root, file), {"-MD" : "-MT", "embed_manifest_dll" : "", "embed_manifest_exe" : ""})


def get_platform_suffix() -> str:
    if is_windows():
        return 'win'
    if is_linux():
        return 'linux'
    if is_macos():
        return 'mac'
    raise EnvironmentError('*** Unsupported platform, abort!')


###############################
# Setup argument parser
###############################
def setup_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]),
        add_help=True, description="Build Qt Installer-Framework",
        epilog="Builds Qt Installer Framework against static Qt libraries and archives the build artifacts for further usage. \n"
        "To create an installer which installs the built Installer Framework libraries and tools use \"--create_installer\" option.",
        formatter_class=argparse.RawTextHelpFormatter
    )

    parser.add_argument('--qt_archive_uri', help="Qt source package for Qt Installer-Framework", required=False)
    parser.add_argument('--qt_configure_options', help="Configure options for (static) Qt build", required=False)
    parser.add_argument('--ifw_uri', help="URI for Qt Installer-Framework", required=False, default=IfwOptions.default_qt_installer_framework_url)
    parser.add_argument('--ifw_branch', help="Git branch for Qt Installer-Framework", required=False)
    parser.add_argument('--ifw_qmake_args', help="Qmake arguments for Installer-Framework build ", required=False, default=IfwOptions.default_qt_installer_framework_qmake_args)
    parser.add_argument('--product_key_checker_pri', help="Custom product key checker (.pri file)", required=False)
    parser.add_argument('--openssl_dir', help="Path where it can find the openssl installation(libs, includes) on windows.", required=False, default='C:\\OpenSSL')
    parser.add_argument('--debug', help="Build the ifw in debug mode", action='store_true', required=False, default=False)
    parser.add_argument('--create_installer', help="Build the ifw and wrap it in the installer", action='store_true', required=False, default=False)
    parser.add_argument('--incremental', help="Build the ifw in incremental mode", action='store_true', required=False, default=False)
    parser.add_argument('--build_ifw_examples', help="Build the IFW examples", action='store_true', required=False, default=False)
    parser.add_argument('--qt_binaries_static', help="Use prebuilt Qt package instead of building from scratch", required=False)
    parser.add_argument('--qt_binaries_dynamic', help="Use prebuilt Qt package instead of building from scratch", required=False)
    parser.add_argument('--sign_server', help="Signing server address", required=False)
    parser.add_argument('--sign_server_pwd', help="Signing server parssword", required=False)
    parser.add_argument('--archive_qt', help="Build and archive both static and shared Qt binaries for IFW", action='store_true', required=False, default=False)
    return parser


def main() -> None:
    """Main"""
    # init things
    parser = setup_argument_parser()
    # parse args
    cargs = parser.parse_args()
    qt_src = IfwOptions.default_qt_src_pkg if not cargs.qt_archive_uri else cargs.qt_archive_uri
    qt_configure_options = get_static_qt_configure_options(cargs.openssl_dir) if not cargs.qt_configure_options else cargs.qt_configure_options
    ifw_branch = IfwOptions.default_qt_installer_framework_branch_qt if not cargs.ifw_branch else cargs.ifw_branch
    signserver = '' if not cargs.sign_server else cargs.sign_server
    signpwd = '' if not cargs.sign_server_pwd else cargs.sign_server_pwd

    qt_conf_args = cargs.qt_configure_options
    ifw_qmake_args = cargs.ifw_qmake_args
    if cargs.debug:
        qt_conf_args = qt_conf_args.replace('-release', '-debug')
        ifw_qmake_args = ifw_qmake_args.replace('-config release', '-config debug')
    # create options object
    options = IfwOptions(
        qt_src,
        qt_configure_options,
        cargs.ifw_uri,
        ifw_branch,
        ifw_qmake_args,
        cargs.openssl_dir,
        cargs.product_key_checker_pri,
        cargs.qt_binaries_static,
        cargs.qt_binaries_dynamic,
        signserver,
        signpwd,
        cargs.incremental,
        cargs.archive_qt
    )
    # build ifw tools
    if cargs.archive_qt:
        build_and_archive_qt(options)
    else:
        build_ifw(options, cargs.create_installer, cargs.build_ifw_examples)


if __name__ == "__main__":
    main()
