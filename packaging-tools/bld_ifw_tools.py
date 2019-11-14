#!/usr/bin/env python
# -*- coding: utf-8 -*-
#############################################################################
##
## Copyright (C) 2018 The Qt Company Ltd.
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
import sys
import os
import re
import platform
import argparse
import multiprocessing
import bldinstallercommon
import pkg_constants
import shutil
import shlex
import traceback
import subprocess
from multiprocessing.connection import Listener

ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
ARCH_EXT = '.zip' if platform.system().lower().startswith('win') else '.tar.xz'
QT_VERSION = '5.12'
QT_VERSION_MINOR = '5.12.4'


ARCHIVE_PROGRAM = '7z'
if platform.system().lower().startswith('darwin'):
    try:
        print("Trying to use 7z from")
        subprocess.call(['where', '7z'])
    except OSError as e:
        print("7z not found from path. Try to use 7z from /usr/local/bin")
        ARCHIVE_PROGRAM = '/usr/local/bin/7z'


##################################################################
# Get default Qt configure arguments. Platform is detected.
##################################################################
def get_default_qt_configure_options(openssl_dir):
    return get_static_qt_configure_options(openssl_dir)


##################################################################
# Get static Qt configure arguments. Platform is detected.
##################################################################
def get_static_qt_configure_options(openssl_dir):
    options = get_common_qt_configure_options() + '-static -no-sql-sqlite '
    if bldinstallercommon.is_mac_platform():
        options += '-no-securetransport '
    options += '-openssl-linked '
    if (bldinstallercommon.is_linux_platform() or bldinstallercommon.is_mac_platform()) and openssl_dir:
        options += '-I {0}/include -L {0}/lib '.format(openssl_dir)
    if platform.system().lower().startswith('win'):
        options += '-static-runtime '
        if openssl_dir:
            options += 'OPENSSL_LIBS="-llibssl -llibcrypto -lUser32 -lWs2_32 -lAdvapi32 -lCrypt32" '
            options += '-I {0}\\include -L {0}\\lib '.format(openssl_dir)
    return options


##################################################################
# Get common Qt configure arguments for all platforms
##################################################################
def get_common_allos_qt_configure_options():
    options = '-release -opensource -confirm-license '
    options += '-nomake examples -nomake tests '
    options += '-accessibility '
    return options


##################################################################
# Get common Qt configure arguments for unix platform
##################################################################
def get_common_unix_qt_configure_options():
    options = '-qt-zlib -qt-libpng -qt-libjpeg -no-cups '
    return options


##################################################################
# Get default Qt configure arguments. Platform is detected.
##################################################################
def get_common_qt_configure_options():
    plat = platform.system().lower()
    # common
    options = get_common_allos_qt_configure_options()
    options += '-no-qml-debug '
    # Windows
    if plat.startswith('win'):
        options += '-no-icu -mp '
    # Unix
    else:
        # OSX and Linux
        options += get_common_unix_qt_configure_options()
        # Linux
        if plat.startswith('linux'):
            options += '-qt-xcb -no-opengl -no-icu -no-libudev '
            options += '-qt-pcre -no-glib -no-egl '
            options += '-no-sm -qt-harfbuzz '
        if bldinstallercommon.is_mac_platform():
            options += '-no-freetype '
    return options


##################################################################
# Configure options for separate Qt build if doc build is needed.
##################################################################
def get_dynamic_qt_configure_options():
    options = get_common_qt_configure_options()
    options += '-qt-sqlite '
    options += '-no-dbus '
    return options


##################################################################
# Define OPENSSL_LIBS env if openssl_dir is defined
##################################################################
def get_build_env(openssl_dir):
    tmp = dict(os.environ)
    if bldinstallercommon.is_mac_platform() and os.path.isdir(openssl_dir):
        tmp['OPENSSL_LIBS'] = "-L{0}/lib -lssl -lcrypto".format(openssl_dir)
    if bldinstallercommon.is_linux_platform() and os.path.isdir(openssl_dir):
        tmp['OPENSSL_LIBS'] = "-I{0}/include -L{0}/lib -ldl -lssl -lcrypto -lpthread".format(openssl_dir)

    return tmp


###############################
# Option class for ifw build
###############################
class IfwOptions:

    default_qt_src_pkg                          = 'http://download.qt.io/official_releases/qt/' + QT_VERSION + '/' + QT_VERSION_MINOR + '/single/qt-everywhere-src-' + QT_VERSION_MINOR + ARCH_EXT
    default_qt_installer_framework_url          = 'git://code.qt.io/installer-framework/installer-framework.git'
    default_qt_installer_framework_branch_qt    = '3.1'
    default_qt_installer_framework_qmake_args   = ['-r', '-config', 'release', '-config', 'static']

    def __init__(self,
                 qt_source_package_uri,
                 qt_configure_options,
                 qt_installer_framework_uri,
                 qt_installer_framework_branch,
                 qt_installer_framework_qmake_args,
                 openssl_dir,
                 product_key_checker_pri,
                 qt_binaries_static,
                 qt_binaries_dynamic,
                 signserver,
                 signpwd,
                 incremental_build = False,
                 squish_dir = "",
                 squish_src = "",
                 archive_qt = False
                 ):
        self.squish_dir                                 = squish_dir
        self.squish_src                                 = squish_src
        self.signserver                                 = signserver
        self.signpwd                                    = signpwd
        self.incremental_mode                           = incremental_build
        self.qt_source_dir                              = os.path.join(ROOT_DIR, 'qt-src')
        self.qt_build_dir                               = os.path.join(ROOT_DIR, 'qt-bld')
        self.qt_build_dir_dynamic                       = os.path.join(ROOT_DIR, 'qt-bld-dynamic')
        self.installer_framework_source_dir             = os.path.join(ROOT_DIR, 'ifw-src')
        self.installer_framework_build_dir              = os.path.join(ROOT_DIR, 'ifw-bld')
        self.installer_framework_build_dir_squish       = os.path.join(ROOT_DIR, 'ifw-bld_squish')
        self.installer_framework_pkg_dir                = os.path.join(ROOT_DIR, 'ifw-pkg')
        self.installer_framework_target_dir             = os.path.join(ROOT_DIR, 'ifw-target')
        self.qt_installer_framework_uri                 = qt_installer_framework_uri
        self.qt_installer_framework_uri_saveas          = os.path.join(ROOT_DIR, os.path.basename(self.qt_installer_framework_uri))
        self.qt_installer_framework_branch              = qt_installer_framework_branch
        self.qt_installer_framework_branch_pretty       = qt_installer_framework_branch.replace("/", "_")
        self.qt_installer_framework_qmake_args          = qt_installer_framework_qmake_args
        self.openssl_dir                                = openssl_dir
        self.qt_binaries_static                         = qt_binaries_static
        if self.qt_binaries_static:
            self.qt_binaries_static_saveas              = os.path.join(ROOT_DIR, os.path.basename(self.qt_binaries_static))
        self.qt_binaries_dynamic                        = qt_binaries_dynamic
        if self.qt_binaries_dynamic:
            self.qt_binaries_dynamic_saveas             = os.path.join(ROOT_DIR, os.path.basename(self.qt_binaries_dynamic))
        self.qt_build_modules                           = ["qtbase", "qtdeclarative", "qttools", "qttranslations"]
        self.qt_build_modules_docs                      = ["qtbase", "qttools"]
        if bldinstallercommon.is_win_platform():
            self.qt_build_modules.append("qtwinextras")
            self.make_cmd                               = 'jom.exe'
            self.make_doc_cmd                           = 'jom.exe'
            self.make_install_cmd                       = 'jom.exe install'
            self.qt_qmake_bin                           = 'qmake.exe'
            self.qt_configure_bin                       = self.qt_source_dir + os.sep + 'configure.bat'
        else:
            self.make_cmd                               = 'make -j' + str(multiprocessing.cpu_count() + 1)
            self.make_doc_cmd                           = 'make'
            self.make_install_cmd                       = 'make install'
            self.qt_qmake_bin                           = 'qmake'
            self.qt_configure_bin                       = self.qt_source_dir + os.sep + 'configure'

        self.build_artifacts_dir                        = os.path.join(ROOT_DIR, pkg_constants.IFW_BUILD_ARTIFACTS_DIR)
        self.mac_deploy_qt_archive_name                 = 'macdeployqt.7z'
        self.mac_qt_menu_nib_archive_name               = 'qt_menu.nib.7z'
        # determine filenames used later on
        self.architecture = ''
        # if this is cross-compilation attempt to parse the target architecture from the given -platform
        if '-platform' in qt_configure_options:
            temp = qt_configure_options.split(' ')
            plat = temp[temp.index('-platform') + 1]
            bits = ''.join(re.findall(r'\d+', plat))
            if bits == '32':
                self.architecture = 'x86'
            else:
                self.architecture = 'x64'
        if not self.architecture:
            self.architecture = bldinstallercommon.get_architecture()
        self.plat_suffix                                = bldinstallercommon.get_platform_suffix()
        self.installer_framework_archive_name           = 'installer-framework-build-' + self.qt_installer_framework_branch_pretty + "-" + self.plat_suffix + '-' + self.architecture + '.7z'
        self.installer_framework_with_squish_archive_name = 'installer-framework-build-squish-' + self.qt_installer_framework_branch_pretty + "-" + self.plat_suffix + '-' + self.architecture + '.7z'
        self.installer_base_archive_name                = 'installerbase-' + self.qt_installer_framework_branch_pretty + "-" + self.plat_suffix + '-' + self.architecture + '.7z'
        self.installer_framework_payload_arch           = 'installer-framework-build-stripped-' + self.qt_installer_framework_branch_pretty + "-" + self.plat_suffix + '-' + self.architecture + '.7z'
        self.qt_source_package_uri                      = qt_source_package_uri
        self.qt_source_package_uri_saveas               = os.path.join(ROOT_DIR, os.path.basename(self.qt_source_package_uri))
        # Set Qt build prefix
        qt_prefix                                       = ' -prefix ' + self.qt_build_dir + os.sep + 'qtbase'
        self.qt_configure_options                       = qt_configure_options + qt_prefix
        # Product key checker
        self.product_key_checker_pri                    = product_key_checker_pri
        if product_key_checker_pri:
            if os.path.isfile(product_key_checker_pri):
                self.qt_installer_framework_qmake_args += ['PRODUCTKEYCHECK_PRI_FILE=' + self.product_key_checker_pri]
        # macOS specific
        if bldinstallercommon.is_mac_platform():
            self.qt_installer_framework_qmake_args     += ['"LIBS+=-framework IOKit"']
        self.archive_qt                                 = archive_qt
        self.qt_static_binary_name                      = 'qt-bin-' + QT_VERSION + '-' + self.plat_suffix + '_static.7z'
        self.qt_shared_binary_name                      = 'qt-bin-' + QT_VERSION + '-' + self.plat_suffix + '_shared.7z'
        # sanity check
        self.sanity_check()

    def sanity_check(self):
        # check qt src package url
        res = bldinstallercommon.is_content_url_valid(self.qt_source_package_uri)
        if not(res):
            print('*** Qt src package uri is invalid: {0}'.format(self.qt_source_package_uri))
            sys.exit(-1)
        if self.product_key_checker_pri:
            if os.path.isfile(self.product_key_checker_pri):
                print('Using product key checker: {0}'.format(self.product_key_checker_pri))
            else:
                print('*** Error! Given product key checker is not a valid file: {0}'.format(self.product_key_checker_pri))
                sys.exit(-1)

    def print_data(self):
        print('-----------------------------------------')
        print('make cmd:                                {0}'.format(self.make_cmd))
        print('make doc_cmd:                            {0}'.format(self.make_doc_cmd))
        print('qt_source_package_uri:                   {0}'.format(self.qt_source_package_uri))
        print('qt_source_package_uri_saveas:            {0}'.format(self.qt_source_package_uri_saveas))
        print('qt_source_dir:                           {0}'.format(self.qt_source_dir))
        print('qt_build_dir:                            {0}'.format(self.qt_build_dir))
        print('qt_build_dir_dynamic:                    {0}'.format(self.qt_build_dir_dynamic))
        print('qt_configure_options:                    {0}'.format(self.qt_configure_options))
        print('qt_qmake_bin:                            {0}'.format(self.qt_qmake_bin))
        print('qt_configure_bin:                        {0}'.format(self.qt_configure_bin))
        print('qt_installer_framework_uri:              {0}'.format(self.qt_installer_framework_uri))
        print('qt_installer_framework_branch:           {0}'.format(self.qt_installer_framework_branch))
        print('qt_installer_framework_qmake_args:       {0}'.format(self.qt_installer_framework_qmake_args))
        print('openssl_dir:                             {0}'.format(self.openssl_dir))
        print('installer_framework_source_dir:          {0}'.format(self.installer_framework_source_dir))
        print('installer_framework_build_dir:           {0}'.format(self.installer_framework_build_dir))
        print('installer_framework_archive_name:        {0}'.format(self.installer_framework_archive_name))
        print('installer_framework_with_squish_archive_name: {0}'.format(self.installer_framework_with_squish_archive_name))
        print('installer_base_archive_name:             {0}'.format(self.installer_base_archive_name))
        print('installer_framework_pkg_dir:             {0}'.format(self.installer_framework_pkg_dir))
        print('installer_framework_target_dir:          {0}'.format(self.installer_framework_target_dir))
        print('installer_framework_payload_arch:        {0}'.format(self.installer_framework_payload_arch))
        print('product_key_checker:                     {0}'.format(self.product_key_checker_pri))
        print('qt_binaries_static:                      {0}'.format(self.qt_binaries_static))
        print('qt_binaries_dynamic:                     {0}'.format(self.qt_binaries_dynamic))
        print('squish_dir:                              {0}'.format(self.squish_dir))
        print('squish_src:                              {0}'.format(self.squish_src))
        print('-----------------------------------------')



###############################
# Build IFW
###############################
def build_ifw(options, create_installer=False, build_ifw_examples=False):
    # verbose
    options.print_data()
    #clean environment first
    clean_build_environment(options)
    #checkout sources
    prepare_installer_framework(options)

    if options.qt_binaries_static:
        prepare_compressed_package(options.qt_binaries_static, options.qt_binaries_static_saveas, options.qt_build_dir)
    else:
        prepare_qt_sources(options)
        build_qt(options, options.qt_build_dir, options.qt_configure_options, options.qt_build_modules)

    if(options.squish_src):
        build_squish(options)
    # build installer framework
    build_installer_framework(options)
    if build_ifw_examples or options.squish_dir:
        build_installer_framework_examples(options)
    # steps when creating ifw installer
    if create_installer:
        if options.qt_binaries_dynamic:
            prepare_compressed_package(options.qt_binaries_dynamic, options.qt_binaries_dynamic_saveas, options.qt_build_dir_dynamic)
            if bldinstallercommon.is_win_platform():
                patch_win32_mkspecs(os.path.join(options.qt_build_dir_dynamic, "qtbase", "mkspecs"))
        else:
            configure_options = get_dynamic_qt_configure_options() + '-prefix ' + options.qt_build_dir_dynamic + os.sep + 'qtbase'
            # Although we have a shadow build qt sources are still taminated. Unpack sources again.
            if os.path.exists(options.qt_source_dir):
                bldinstallercommon.remove_tree(options.qt_source_dir)
            prepare_qt_sources(options)
            build_qt(options, options.qt_build_dir_dynamic, configure_options, options.qt_build_modules_docs)
        build_ifw_docs(options)
        create_installer_package(options)
    #archive
    archive_installerbase(options)
    archive_installer_framework(options.installer_framework_build_dir, options.installer_framework_archive_name, options, True)
    if (options.squish_dir):
        archive_installer_framework(options.installer_framework_build_dir_squish, options.installer_framework_with_squish_archive_name, options, False)
    return os.path.basename(options.installer_framework_build_dir)


###############################
# function
###############################
def prepare_qt_sources(options):
    if options.incremental_mode and os.path.exists(options.qt_source_dir):
        return
    print('--------------------------------------------------------------------')
    print('Prepare Qt src package: {0}'.format(options.qt_source_package_uri))
    prepare_compressed_package(options.qt_source_package_uri, options.qt_source_package_uri_saveas, options.qt_source_dir)

    if bldinstallercommon.is_win_platform():
        patch_win32_mkspecs(os.path.join(options.qt_source_dir, "qtbase", "mkspecs"))


###############################
# function
###############################
def prepare_compressed_package(src_pkg_uri, src_pkg_saveas, destination_dir):
    print('Fetching package from: {0}'.format(src_pkg_uri))
    if not os.path.isfile(src_pkg_saveas):
        if not bldinstallercommon.is_content_url_valid(src_pkg_uri):
            print('*** Src package uri is invalid! Abort!')
            sys.exit(-1)
        bldinstallercommon.retrieve_url(src_pkg_uri, src_pkg_saveas)
    else:
        print('Found old local package, using that: {0}'.format(src_pkg_saveas))
    print('Done')
    print('--------------------------------------------------------------------')
    bldinstallercommon.create_dirs(destination_dir)
    bldinstallercommon.extract_file(src_pkg_saveas, destination_dir)
    l = os.listdir(destination_dir)
    items = len(l)
    if items == 1:
        dir_name = l[0]
        full_dir_name = destination_dir + os.sep + dir_name
        bldinstallercommon.move_tree(full_dir_name, destination_dir)
        bldinstallercommon.remove_tree(full_dir_name)
    else:
        print('*** Invalid dir structure encountered?!')
        sys.exit(-1)


###############################
# function
###############################
def build_qt(options, qt_build_dir, qt_configure_options, qt_modules):
    if options.incremental_mode:
        qmake_bin = os.path.join(options.qt_build_dir, 'qtbase', 'bin', options.qt_qmake_bin)
        qt_lib_dir = bldinstallercommon.locate_directory(qt_build_dir, 'lib')
        if os.path.isfile(qmake_bin) and os.path.isdir(qt_lib_dir):
            return

    bldinstallercommon.create_dirs(qt_build_dir)
    # configure first
    print('--------------------------------------------------------------------')
    print('Configuring Qt')
    configure_options = re.sub(' +', ' ', qt_configure_options)
    cmd_args = options.qt_configure_bin + ' ' + configure_options
    # shlex does not like backslashes
    cmd_args = cmd_args.replace('\\', '/')
    bldinstallercommon.do_execute_sub_process(shlex.split(cmd_args), options.qt_source_dir, True, False, get_build_env(options.openssl_dir))
    print('--------------------------------------------------------------------')
    print('Building Qt')
    cmd_args = options.make_cmd
    for module in qt_modules:
        cmd_args += " module-"+module
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), options.qt_source_dir, True, False, get_build_env(options.openssl_dir))
    print('--------------------------------------------------------------------')
    print('Installing Qt')
    cmd_args = options.make_install_cmd
    for module in qt_modules:
        moduleDir = os.path.join(options.qt_source_dir, module)
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), moduleDir)


###############################
# function
###############################
def build_squish(options):

    print('--------------------------------------------------------------------')
    print('Configuring Squish')
    qmake_bin = os.path.join(options.qt_build_dir, 'qtbase', 'bin', options.qt_qmake_bin)
    print ('qmake path ' + qmake_bin)

    if bldinstallercommon.is_win_platform():
        cmd_args = "configure --with-qmake=" + qmake_bin + " --enable-qmake-config --disable-all --enable-idl --enable-qt"
        print("command args " + cmd_args)
        bldinstallercommon.do_execute_sub_process(cmd_args, options.squish_src)
    else:
        cmd_args = os.path.join(options.squish_src, "configure") + " --with-qmake=" + qmake_bin + " --enable-qmake-config --disable-all --enable-idl --enable-qt"
        print("command args " + cmd_args)
        bldinstallercommon.do_execute_sub_process(shlex.split(cmd_args), options.squish_src)

    print('--------------------------------------------------------------------')
    print("building form source " + options.squish_src)
    print('Building Squish')

    if bldinstallercommon.is_win_platform():
        bldinstallercommon.do_execute_sub_process('build', options.squish_src)
        bldinstallercommon.do_execute_sub_process('build install DESTDIR=' + options.squish_dir, options.squish_src)
    else:
        bldinstallercommon.do_execute_sub_process(shlex.split(os.path.join(options.squish_src, 'build')), options.squish_src)
        bldinstallercommon.do_execute_sub_process(shlex.split(os.path.join(options.squish_src,'build install DESTDIR=') + options.squish_dir), options.squish_src)

###############################
# function
###############################
def prepare_installer_framework(options):
    if options.incremental_mode and os.path.exists(options.installer_framework_source_dir):
        return
    print('--------------------------------------------------------------------')
    print('Prepare Installer Framework source')
    #create dirs
    bldinstallercommon.create_dirs(options.installer_framework_build_dir)
    if (options.squish_dir):
        bldinstallercommon.create_dirs(options.installer_framework_build_dir_squish)
    if options.qt_installer_framework_uri.endswith('.git'):
        # clone repos
        bldinstallercommon.clone_repository(options.qt_installer_framework_uri, options.qt_installer_framework_branch, options.installer_framework_source_dir, True)

    else:
        # fetch src package
        prepare_compressed_package(options.qt_installer_framework_uri, options.qt_installer_framework_uri_saveas, options.installer_framework_source_dir)


def start_IFW_build(options, cmd_args, installer_framework_build_dir):
    print("cmd_args: " + bldinstallercommon.list_as_string(cmd_args))
    bldinstallercommon.do_execute_sub_process(cmd_args, installer_framework_build_dir)
    cmd_args = options.make_cmd
    print("cmd_args: " + bldinstallercommon.list_as_string(cmd_args))
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), installer_framework_build_dir)

###############################
# function
###############################
def build_installer_framework(options):
    if options.incremental_mode:
        file_to_check = os.path.join(options.installer_framework_build_dir, 'bin', 'installerbase')
        if bldinstallercommon.is_win_platform():
            file_to_check += '.exe'
        if os.path.exists(file_to_check):
            return

    print('--------------------------------------------------------------------')
    print('Building Installer Framework')
    qmake_bin = os.path.join(options.qt_build_dir, 'qtbase', 'bin', options.qt_qmake_bin)
    if not os.path.isfile(qmake_bin):
        print('*** Unable to find qmake, aborting!')
        print('qmake: {0}'.format(qmake_bin))
        sys.exit(-1)
    if not os.path.exists(options.installer_framework_build_dir):
        bldinstallercommon.create_dirs(options.installer_framework_build_dir)
    cmd_args = [qmake_bin]
    cmd_args += options.qt_installer_framework_qmake_args
    cmd_args += [options.installer_framework_source_dir]
    start_IFW_build(options, cmd_args, options.installer_framework_build_dir)
    if options.squish_dir:
        print('--------------------------------------------------------------------')
        print('Build Installer Framework with squish support')
        if not os.path.exists(options.installer_framework_build_dir_squish):
            bldinstallercommon.create_dirs(options.installer_framework_build_dir_squish)
        cmd_args = [qmake_bin]
        cmd_args += options.qt_installer_framework_qmake_args
        cmd_args += ['SQUISH_PATH=' + options.squish_dir]
        cmd_args += [options.installer_framework_source_dir]
        start_IFW_build(options, cmd_args, options.installer_framework_build_dir_squish)

def build_installer_framework_examples(options):
    print('--------------------------------------------------------------------')
    print('Building Installer Framework Examples')
    if options.squish_dir:
        file_binarycreator = os.path.join(options.installer_framework_build_dir_squish, 'bin', 'binarycreator')
    else:
        file_binarycreator = os.path.join(options.installer_framework_build_dir, 'bin', 'binarycreator')
    if bldinstallercommon.is_win_platform():
        file_binarycreator += '.exe'
    if not os.path.exists(file_binarycreator):
        print('*** Unable to find binarycreator: {0}, aborting!'.format(file_binarycreator))
        sys.exit(-1)

    ifw_examples = os.path.join(options.installer_framework_source_dir, 'examples')
    ifw_example_binaries = []

    for root, dirs, files in os.walk(ifw_examples):
        if 'doc' in dirs:
            dirs.remove('doc')  # don't visit doc dir
        if 'translations' in dirs:
            dirs.remove('translations')  # for now don't visit translation example as qm files needs to be generated first
        for directory in dirs:
            print("********** building example " + directory)
            config_file =  os.path.join(root, directory, 'config', 'config.xml')
            package_dir = os.path.join(root, directory, 'packages')
            target_filename = os.path.join(root, directory, 'installer')
            bldinstallercommon.do_execute_sub_process(args=(file_binarycreator, '--offline-only', '-c', config_file, '-p', package_dir, target_filename), execution_path=package_dir)
            if bldinstallercommon.is_win_platform:
                target_filename += '.exe'
            ifw_example_binaries.append(target_filename)
        #Breaking here as we don't want to go through sub directories
        break
    file_squishDir = options.squish_dir
    if os.path.exists(file_squishDir):
        print('--------------------------------------------------------------------')
        print('Running squish tests')
        # Windows
        if sys.platform.startswith('win'):
            squishserver_handle = subprocess.Popen(os.path.join(file_squishDir, 'bin', 'squishserver.exe'))
            bldinstallercommon.do_execute_sub_process(args=('squishrunner.exe --testsuite ' + os.path.join(os.getcwd(), 'squish_suites', 'suite_IFW_examples')), execution_path=os.path.join(file_squishDir, 'bin'))
            squishserver_handle.kill() # this will not kill squishserver most likely
            subprocess.Popen("TASKKILL /IM _squishserver.exe /F") #this should kill squish server
        # Unix
        else:
            squishserver_handle = subprocess.Popen(shlex.split(os.path.join(file_squishDir, "bin", "squishserver")), shell=False)
            bldinstallercommon.do_execute_sub_process(args=shlex.split(os.path.join(file_squishDir, "bin", "squishrunner") + ' --testsuite ' +os.path.join(os.getcwd(), "squish_suites", "suite_IFW_examples")), execution_path=os.path.join(file_squishDir, "bin"))
            squishserver_handle.kill() #kills squish server

        # Delete the example executables we have created for Squish
        for example in ifw_example_binaries:
            print("Removing " + example)
            os.remove(example)

###############################
# function
###############################
def build_ifw_docs(options):
    print('--------------------------------------------------------------------')
    print('Building Qt Installer Framework Documentation')
    qmake_bin = os.path.join(options.qt_build_dir_dynamic, 'qtbase', 'bin', options.qt_qmake_bin)
    if not os.path.isfile(qmake_bin):
        print('*** Aborting doc build, unable to find qmake from: {0}'.format(options.qt_build_dir_dynamic))
        sys.exit(-1)
    cmd_args = qmake_bin + ' ' + options.installer_framework_source_dir
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), options.installer_framework_build_dir)
    cmd_args = options.make_doc_cmd + ' docs'
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = os.path.normpath(os.path.join(os.path.dirname(qmake_bin), '..', 'lib'))
    bldinstallercommon.do_execute_sub_process(args=cmd_args.split(' '), execution_path=options.installer_framework_build_dir,
                                              abort_on_fail=True, get_output=False, extra_env=env)


################################################################
# Create installer containing the Qt Installer Framework itself
################################################################
def create_installer_package(options):
    print('--------------------------------------------------------------------')
    print('Creating installer for Qt Installer Framework')
    # Temporary dir for creating installer containing the Qt Installer Framework itself
    package_dir = options.installer_framework_pkg_dir
    os.makedirs(package_dir)
    # Final directory for the installer containing the Qt Installer Framework itself
    os.makedirs(options.installer_framework_target_dir)
    target_dir = os.path.join(options.installer_framework_target_dir, 'QtInstallerFramework' + '-' + options.plat_suffix + '-' + options.architecture)

    current_dir = os.getcwd()
    os.chdir(package_dir)
    shutil.copytree(os.path.join(options.installer_framework_build_dir, 'bin'), os.path.join(package_dir, 'bin'), ignore = shutil.ignore_patterns("*.exe.manifest","*.exp","*.lib"))
    if sys.platform == 'linux2':
        bldinstallercommon.do_execute_sub_process(args=('strip', os.path.join(package_dir, 'bin/archivegen')), execution_path=package_dir)
        bldinstallercommon.do_execute_sub_process(args=('strip', os.path.join(package_dir, 'bin/binarycreator')), execution_path=package_dir)
        bldinstallercommon.do_execute_sub_process(args=('strip', os.path.join(package_dir, 'bin/devtool')), execution_path=package_dir)
        bldinstallercommon.do_execute_sub_process(args=('strip', os.path.join(package_dir, 'bin/installerbase')), execution_path=package_dir)
        bldinstallercommon.do_execute_sub_process(args=('strip', os.path.join(package_dir, 'bin/repogen')), execution_path=package_dir)
    shutil.copytree(os.path.join(options.installer_framework_build_dir, 'doc'), os.path.join(package_dir, 'doc'))
    shutil.copytree(os.path.join(options.installer_framework_source_dir, 'examples'), os.path.join(package_dir, 'examples'))
    shutil.copy(os.path.join(options.installer_framework_source_dir, 'README'), package_dir)
    # pack payload into separate .7z archive for later usage
    cmd_args = [ARCHIVE_PROGRAM, 'a', options.installer_framework_payload_arch, package_dir]
    bldinstallercommon.do_execute_sub_process(cmd_args, ROOT_DIR)
    shutil.move(os.path.join(ROOT_DIR, options.installer_framework_payload_arch), options.build_artifacts_dir)
    # create 7z
    archive_file = os.path.join(options.installer_framework_source_dir, 'dist', 'packages', 'org.qtproject.ifw.binaries', 'data', 'data.7z')
    if not os.path.exists(os.path.dirname(archive_file)):
        os.makedirs(os.path.dirname(archive_file))
    bldinstallercommon.do_execute_sub_process(args=(os.path.join(package_dir, 'bin', 'archivegen'), archive_file, '*'), execution_path=package_dir)
    # run installer
    binary_creator = os.path.join(options.installer_framework_build_dir, 'bin', 'binarycreator')
    config_file = os.path.join(options.installer_framework_source_dir, 'dist', 'config', 'config.xml')
    package_dir = os.path.join(options.installer_framework_source_dir, 'dist', 'packages')
    bldinstallercommon.do_execute_sub_process(args=(binary_creator, '--offline-only', '-c', config_file, '-p', package_dir, target_dir), execution_path=package_dir)
    print('Installer package is at: {0}'.format(target_dir))
    artifacts = os.listdir(options.installer_framework_target_dir)
    for artifact in artifacts:
        destFileName = os.path.join(options.build_artifacts_dir, artifact)
        if bldinstallercommon.is_linux_platform():
            destFileName += '.run'
        shutil.move(os.path.join(options.installer_framework_target_dir, artifact), destFileName)
    os.chdir(current_dir)

################################################################
# Build and archive Qt for IFW builds
################################################################
def build_and_archive_qt(options):
    print('--------------------------------------------------------------------')
    print('Build static Qt')
    prepare_qt_sources(options)
    build_qt(options, options.qt_build_dir, options.qt_configure_options, options.qt_build_modules)

    print('--------------------------------------------------------------------')
    print('Archive static Qt binaries')
    cmd_args_archive = [ARCHIVE_PROGRAM, 'a', options.qt_static_binary_name, options.qt_build_dir]
    bldinstallercommon.do_execute_sub_process(cmd_args_archive, ROOT_DIR)

    print('--------------------------------------------------------------------')
    print('Build shared Qt')
    configure_options = get_dynamic_qt_configure_options() + '-prefix ' + options.qt_build_dir_dynamic + os.sep + 'qtbase'
    # Although we have a shadow build qt sources are still contaminated. Unpack sources again.
    if os.path.exists(options.qt_source_dir):
        bldinstallercommon.remove_tree(options.qt_source_dir)
    prepare_qt_sources(options)
    build_qt(options, options.qt_build_dir_dynamic, configure_options, options.qt_build_modules_docs)

    print('--------------------------------------------------------------------')
    print('Archive shared Qt binaries')
    cmd_args_archive = [ARCHIVE_PROGRAM, 'a', options.qt_shared_binary_name, options.qt_build_dir_dynamic]
    bldinstallercommon.do_execute_sub_process(cmd_args_archive, ROOT_DIR)


###############################
# function
###############################
def clean_build_environment(options):
    if os.path.isfile(options.installer_framework_archive_name):
        os.remove(options.installer_framework_archive_name)
    if os.path.isfile(options.installer_framework_with_squish_archive_name):
        os.remove(options.installer_framework_with_squish_archive_name)
    if os.path.isfile(options.installer_framework_payload_arch):
        os.remove(options.installer_framework_payload_arch)
    if os.path.exists(options.build_artifacts_dir):
        bldinstallercommon.remove_tree(options.build_artifacts_dir)
    bldinstallercommon.create_dirs(options.build_artifacts_dir)
    if os.path.exists(options.installer_framework_build_dir):
        bldinstallercommon.remove_tree(options.installer_framework_build_dir)
    if os.path.exists(options.installer_framework_build_dir_squish):
        bldinstallercommon.remove_tree(options.installer_framework_build_dir_squish)

    if os.path.exists(options.installer_framework_pkg_dir):
        shutil.rmtree(options.installer_framework_pkg_dir)
    if os.path.exists(options.installer_framework_target_dir):
        shutil.rmtree(options.installer_framework_target_dir)

    if options.incremental_mode:
        return

    if os.path.exists(options.installer_framework_source_dir):
        bldinstallercommon.remove_tree(options.installer_framework_source_dir)
    if os.path.exists(options.qt_source_dir):
        bldinstallercommon.remove_tree(options.qt_source_dir)
    if os.path.exists(options.qt_build_dir):
        bldinstallercommon.remove_tree(options.qt_source_dir)
    if os.path.isfile(options.qt_source_package_uri_saveas):
        os.remove(options.qt_source_package_uri_saveas)
    if os.path.isfile(options.qt_installer_framework_uri_saveas):
        os.remove(options.qt_installer_framework_uri_saveas)


###############################
# function
###############################
def archive_installer_framework(installer_framework_build_dir, installer_framework_archive_name, options, create_tagged_package):
    print('--------------------------------------------------------------------')
    print('Archive Installer Framework')
    # first strip out all unnecessary files
    for root, dummy, files in os.walk(installer_framework_build_dir):
        for filename in files:
            if filename.endswith(('.moc', 'Makefile', '.cpp', '.h', '.o')) or filename == 'Makefile':
                os.remove(os.path.join(root, filename))
    cmd_args = [ARCHIVE_PROGRAM, 'a', installer_framework_archive_name, os.path.basename(installer_framework_build_dir)]
    bldinstallercommon.do_execute_sub_process(cmd_args, ROOT_DIR)
    shutil.move(installer_framework_archive_name, options.build_artifacts_dir)
    # Check if installer framework is created from branch. If so, check if the branch is tagged and
    # create a package with a tagged name.
    # Package with the tagged name is needed for creating e.g. offline installers from stable builds
    if options.qt_installer_framework_uri.endswith('.git') and create_tagged_package:
        tag = bldinstallercommon.get_tag_from_branch(options.installer_framework_source_dir, options.qt_installer_framework_branch)
        if tag:
            print('Create archive from tag {0}'.format(tag))
            installer_framework_tagged_archive = 'installer-framework-build-' + tag + "-" + options.plat_suffix + '-' + options.architecture + '.7z'
            print('Create archive {0}'.format(installer_framework_tagged_archive))
            shutil.copy(os.path.join(options.build_artifacts_dir, installer_framework_archive_name), os.path.join(options.build_artifacts_dir, installer_framework_tagged_archive))

###############################
# function
###############################
def archive_installerbase(options):
    print('--------------------------------------------------------------------')
    print('Archive Installerbase')
    cmd_args_archive = []
    cmd_args_clean = []
    bin_temp = ''
    if bldinstallercommon.is_linux_platform() or bldinstallercommon.is_mac_platform():
        bin_path = bldinstallercommon.locate_executable(options.installer_framework_build_dir, 'installerbase')
        bin_temp = ROOT_DIR + os.sep + '.tempSDKMaintenanceTool'
        shutil.copy(bin_path, bin_temp)
        cmd_args_archive = [ARCHIVE_PROGRAM, 'a', options.installer_base_archive_name, bin_temp]
        cmd_args_clean = ['rm', bin_temp]
    if bldinstallercommon.is_win_platform():
        bin_path = bldinstallercommon.locate_executable(options.installer_framework_build_dir, 'installerbase.exe')
        bin_temp = ROOT_DIR + os.sep + 'tempSDKMaintenanceToolBase.exe'
        shutil.copy(bin_path, bin_temp)
        if options.signserver and options.signpwd:
            sign_windows_installerbase('tempSDKMaintenanceToolBase.exe', ROOT_DIR + os.sep, True, options)
        cmd_args_archive = [ARCHIVE_PROGRAM, 'a', options.installer_base_archive_name, bin_temp]
        cmd_args_clean = ['del', bin_temp]
    bldinstallercommon.do_execute_sub_process(cmd_args_archive, ROOT_DIR)
    bldinstallercommon.do_execute_sub_process(cmd_args_clean, ROOT_DIR)
    if not os.path.isfile(options.installer_base_archive_name):
        print('*** Failed to generate archive: {0}'.format(options.installer_base_archive_name))
        sys.exit(-1)
    shutil.move(options.installer_base_archive_name, options.build_artifacts_dir)

###############################
# sign windows installerbase
###############################
def sign_windows_installerbase(file_name, working_dir, abort_on_fail, options):
    print('--------------------------------------------------------------------')
    print('Sign Windows Installerbase')
    cmd_args = [r'C:\Utils\sign\signtool.exe', 'sign', '/v', '/du', options.signserver, '/p', options.signpwd,
                '/t', 'http://timestamp.verisign.com/scripts/timestamp.dll', '/f', r'C:\utils\sign\keys.pfx', file_name]
    bldinstallercommon.do_execute_sub_process(cmd_args, working_dir, abort_on_fail)

###############################
# function
###############################
def archive_nib(options):
    print('--------------------------------------------------------------------')
    print('Archive qt_menu.nib')
    content_parent_path = options.qt_source_dir + os.sep + 'src/gui/mac'
    content_root_path = content_parent_path + os.sep + 'qt_menu.nib'
    content_parent_path = os.path.normpath(content_parent_path)
    content_root_path = os.path.normpath(content_root_path)
    cmd_args = [ARCHIVE_PROGRAM, 'a', options.mac_qt_menu_nib_archive_name, content_root_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, ROOT_DIR)
    if not os.path.isfile(options.mac_qt_menu_nib_archive_name):
        print('*** Failed to generate archive: {0}'.format(options.mac_qt_menu_nib_archive_name))
        sys.exit(-1)
    shutil.move(options.mac_qt_menu_nib_archive_name, options.build_artifacts_dir)


###############################
# function
###############################
def archive_macdeployqt(options):
    print('--------------------------------------------------------------------')
    print('Archive macdeployqt')
    content_path = options.qt_build_dir + os.sep + 'tools/macdeployqt/macchangeqt/macchangeqt'
    cmd_args_archive = [ARCHIVE_PROGRAM, 'a', options.mac_deploy_qt_archive_name, content_path]
    bldinstallercommon.do_execute_sub_process(cmd_args_archive, ROOT_DIR)
    if not os.path.isfile(options.mac_deploy_qt_archive_name):
        print('*** Failed to generate archive: {0}'.format( options.mac_deploy_qt_archive_name))
        sys.exit(-1)
    shutil.move(options.mac_deploy_qt_archive_name, options.build_artifacts_dir)

###############################
# Replace all dict keys with values in file
###############################
def patch(file, dict):
    filedata = None
    print("Patching {0} ...".format(file))
    with open(file, 'r') as f:
        filedata = f.read()

    for key in dict:
        filedata = filedata.replace(key, dict[key])

    with open(file, 'w') as f:
        f.write(filedata)

###############################
# Patch win32 mkspecs
###############################
def patch_win32_mkspecs(mkspecsdir):
    print('--------------------------------------------------------------------')
    print('Patching win32 mkspecs in {0} ...'.format(mkspecsdir))
    for root, dummy, files in os.walk(mkspecsdir):
        for file in files:
            if "win32" in root and file == "qmake.conf":
                patch(os.path.join(root, file), {"-MD" : "-MT", "embed_manifest_dll" : "", "embed_manifest_exe" : "" })

###############################
# Setup argument parser
###############################
def setup_argument_parser():
    parser = argparse.ArgumentParser(prog = os.path.basename(sys.argv[0]),
              add_help=True, description="Build Qt Installer-Framework",
              epilog="Builds Qt Installer Framework against static Qt libraries and archives the build artifacts for further usage. \n"
                     "To create an installer which installs the built Installer Framework libraries and tools use \"--create_installer\" option.",
               formatter_class=argparse.RawTextHelpFormatter)

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
    parser.add_argument('--squish_dir', help="Path to Squish. If set, runs squish tests to IFW examples", required=False, default='')
    parser.add_argument('--squish_src', help="Path to Squish sources. If set, Squish is built", required=False, default='')
    parser.add_argument('--archive_qt', help="Build and archive both static and shared Qt binaries for IFW", action='store_true', required=False, default=False)
    return parser

###############################
# Main
###############################
if __name__ == "__main__":
    # init things
    bldinstallercommon.init_common_module(ROOT_DIR)
    PARSER = setup_argument_parser()
    # parse args
    CARGS = PARSER.parse_args()
    qt_src               = IfwOptions.default_qt_src_pkg if not CARGS.qt_archive_uri else CARGS.qt_archive_uri
    qt_configure_options = get_static_qt_configure_options(CARGS.openssl_dir) if not CARGS.qt_configure_options else CARGS.qt_configure_options
    ifw_branch           = IfwOptions.default_qt_installer_framework_branch_qt if not CARGS.ifw_branch else CARGS.ifw_branch
    signserver           = '' if not CARGS.sign_server else CARGS.sign_server
    signpwd              = '' if not CARGS.sign_server_pwd else CARGS.sign_server_pwd

    qt_conf_args = CARGS.qt_configure_options
    ifw_qmake_args = CARGS.ifw_qmake_args
    if CARGS.debug:
        qt_conf_args = qt_conf_args.replace('-release', '-debug')
        ifw_qmake_args = ifw_qmake_args.replace('-config release', '-config debug')
    # create options object
    OPTIONS = IfwOptions(qt_src,
                         qt_configure_options,
                         CARGS.ifw_uri,
                         ifw_branch,
                         ifw_qmake_args,
                         CARGS.openssl_dir,
                         CARGS.product_key_checker_pri,
                         CARGS.qt_binaries_static,
                         CARGS.qt_binaries_dynamic,
                         signserver,
                         signpwd,
                         CARGS.incremental,
                         CARGS.squish_dir,
                         CARGS.squish_src,
                         CARGS.archive_qt
                        )
    # build ifw tools
    if CARGS.archive_qt:
        build_and_archive_qt(OPTIONS)
    else:
        build_ifw(OPTIONS, CARGS.create_installer, CARGS.build_ifw_examples)


