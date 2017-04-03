#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2016 The Qt Company Ltd.
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

ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
ARCH_EXT = '.zip' if platform.system().lower().startswith('win') else '.tar.gz'



##################################################################
# Get default Qt configure arguments. Platform is detected.
##################################################################
def get_default_qt_configure_options(openssl_dir):
    return get_static_qt_configure_options(openssl_dir)


##################################################################
# Get static Qt configure arguments. Platform is detected.
##################################################################
def get_static_qt_configure_options(openssl_dir):
    options = get_common_qt_configure_options() + '-static '
    if bldinstallercommon.is_mac_platform():
        options += '-no-securetransport '
    options += '-openssl-linked '
    if (bldinstallercommon.is_linux_platform() or bldinstallercommon.is_mac_platform()) and openssl_dir:
        options += '-I {0}/include -L {0}/lib '.format(openssl_dir)
    if platform.system().lower().startswith('win'):
        options += '-static-runtime '
        if openssl_dir:
            options += 'OPENSSL_LIBS="-lssleay32MT -llibeay32MT -lcrypt32 -lgdi32" '
            options += '-I {0}\\include -L {0}\\lib\\VC\\static '.format(openssl_dir)
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
    options += '-no-sql-sqlite -no-qml-debug '
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
            options += '-no-xinput2 -no-sm '
        if bldinstallercommon.is_mac_platform():
            options += '-no-freetype '
    return options


##################################################################
# Configure options for separate Qt build if doc build is needed.
##################################################################
def get_dynamic_qt_configure_options():
    options = get_common_qt_configure_options()
    options += '-qt-sql-sqlite '
    options += '-no-dbus '
    return options


##################################################################
# Define OPENSSL_LIBS env if openssl_dir is defined
##################################################################
def get_build_env(openssl_dir):
    tmp = dict(os.environ)
    if bldinstallercommon.is_mac_platform() and os.path.isdir(openssl_dir):
        tmp['OPENSSL_LIBS'] = "-L{0}/lib -lssl -lcrypto".format(openssl_dir)
    return tmp


###############################
# Option class for ifw build
###############################
class IfwOptions:

    default_qt_src_pkg                          = 'http://download.qt.io/official_releases/qt/5.7/5.7.0/single/qt-everywhere-opensource-src-5.7.0' + ARCH_EXT
    default_qt_installer_framework_url          = 'git://code.qt.io/installer-framework/installer-framework.git'
    default_qt_installer_framework_branch_qt    = '2.0'
    default_qt_installer_framework_qmake_args   = ['-config', 'release', '-config', 'static']

    def __init__(self,
                 qt_source_package_uri,
                 qt_configure_options,
                 qt_installer_framework_uri,
                 qt_installer_framework_branch,
                 qt_installer_framework_qmake_args,
                 openssl_dir,
                 product_key_checker_pri,
                 incremental_build = False):
        self.incremental_mode                           = incremental_build
        self.qt_source_dir                              = os.path.join(ROOT_DIR, 'qt-src')
        self.qt_build_dir                               = os.path.join(ROOT_DIR, 'qt-bld')
        self.qt_build_dir_dynamic                       = os.path.join(ROOT_DIR, 'qt-bld-dynamic')
        self.installer_framework_source_dir             = os.path.join(ROOT_DIR, 'ifw-src')
        self.installer_framework_build_dir              = os.path.join(ROOT_DIR, 'ifw-bld')
        self.installer_framework_pkg_dir                = os.path.join(ROOT_DIR, 'ifw-pkg')
        self.installer_framework_target_dir             = os.path.join(ROOT_DIR, 'ifw-target')
        self.qt_installer_framework_uri                 = qt_installer_framework_uri
        self.qt_installer_framework_uri_saveas          = os.path.join(ROOT_DIR, os.path.basename(self.qt_installer_framework_uri))
        self.qt_installer_framework_branch              = qt_installer_framework_branch
        self.qt_installer_framework_qmake_args          = qt_installer_framework_qmake_args
        self.openssl_dir                                = openssl_dir
        self.qt_build_modules                           = " module-qtbase module-qtdeclarative module-qttools module-qttranslations"
        self.qt_build_modules_docs                      = " module-qttools"
        if bldinstallercommon.is_win_platform():
            self.qt_build_modules                       += " module-qtwinextras"
            self.make_cmd                               = 'nmake'
            self.make_doc_cmd                           = 'nmake'
            self.make_install_cmd                       = 'nmake install'
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
        self.installer_framework_archive_name           = 'installer-framework-build-' + self.plat_suffix + '-' + self.architecture + '.7z'
        self.installer_base_archive_name                = 'installerbase-' + self.plat_suffix + '-' + self.architecture + '.7z'
        self.installer_framework_payload_arch           = 'installer-framework-build-stripped-' + self.plat_suffix + '-' + self.architecture + '.7z'
        self.qt_source_package_uri                      = qt_source_package_uri
        self.qt_source_package_uri_saveas               = os.path.join(ROOT_DIR, os.path.basename(self.qt_source_package_uri))
        # Set Qt build prefix
        qt_prefix = ' -prefix ' + self.qt_build_dir + os.sep + 'qtbase'
        self.qt_configure_options = qt_configure_options + qt_prefix
        # Product key checker
        self.product_key_checker_pri                    = product_key_checker_pri
        if product_key_checker_pri:
            if os.path.isfile(product_key_checker_pri):
                self.qt_installer_framework_qmake_args      += ['-r', 'PRODUCTKEYCHECK_PRI_FILE=' + self.product_key_checker_pri]
        # macOS specific
        if bldinstallercommon.is_mac_platform():
            self.qt_installer_framework_qmake_args += ['-r', '"LIBS+=-framework IOKit"']
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
                print('Using product key checker: '.format(self.product_key_checker_pri))
            else:
                print('*** Error! Given product key checker is not a valid file: '.format(self.product_key_checker_pri))
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
        print('installer_base_archive_name:             {0}'.format(self.installer_base_archive_name))
        print('installer_framework_pkg_dir:             {0}'.format(self.installer_framework_pkg_dir))
        print('installer_framework_target_dir:          {0}'.format(self.installer_framework_target_dir))
        print('installer_framework_payload_arch:        {0}'.format(self.installer_framework_payload_arch))
        print('product_key_checker:                     {0}'.format(self.product_key_checker_pri))
        print('-----------------------------------------')



###############################
# Build IFW
###############################
def build_ifw(options, create_installer=False):
    # verbose
    options.print_data()
    #clean environment first
    clean_build_environment(options)
    #checkout sources
    prepare_installer_framework(options)
    # copy qt sources
    prepare_qt_sources(options)
    # build qt
    build_qt(options, options.qt_build_dir, options.qt_configure_options, options.qt_build_modules)
    # build installer framework
    build_installer_framework(options)
    # steps when creating ifw installer
    if create_installer:
        configure_options = get_dynamic_qt_configure_options() + '-prefix ' + options.qt_build_dir_dynamic + os.sep + 'qtbase'
        build_qt(options, options.qt_build_dir_dynamic, configure_options, options.qt_build_modules_docs)
        install_docs(options, options.qt_build_dir_dynamic)
        build_ifw_docs(options)
        create_installer_package(options)
    #archive
    archive_installerbase(options)
    archive_installer_framework(options)
    return os.path.basename(options.installer_framework_build_dir)


###############################
# function
###############################
def prepare_qt_sources(options):
    if options.incremental_mode and os.path.exists(options.qt_source_dir):
        return
    print('--------------------------------------------------------------------')
    print('Prepare Qt src package: {0}'.format(options.qt_source_package_uri))
    prepare_src_package(options.qt_source_package_uri, options.qt_source_package_uri_saveas, options.qt_source_dir)

    if bldinstallercommon.is_win_platform():
        patch_win32_mkspecs(os.path.join(options.qt_source_dir, "qtbase", "mkspecs"))


###############################
# function
###############################
def prepare_src_package(src_pkg_uri, src_pkg_saveas, destination_dir):
    print('Fetching Src package from: {0}'.format(src_pkg_uri))
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
        qmake_bin = bldinstallercommon.locate_file(qt_build_dir, options.qt_qmake_bin)
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
    bldinstallercommon.do_execute_sub_process(shlex.split(cmd_args), qt_build_dir, True, False, get_build_env(options.openssl_dir))
    print('--------------------------------------------------------------------')
    print('Building Qt')
    cmd_args = options.make_cmd
    cmd_args += qt_modules
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), qt_build_dir, True, False, get_build_env(options.openssl_dir))


###############################
# function
###############################
def install_docs(options, qt_build_dir):
    print('--------------------------------------------------------------------')
    print('Installing Qt documentation')
    cmd_args = options.make_install_cmd
    cmd_args += " docs"
    qt_build_dir += os.sep + 'qtbase'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), qt_build_dir)


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
    if options.qt_installer_framework_uri.endswith('.git'):
        # clone repos
        bldinstallercommon.clone_repository(options.qt_installer_framework_uri, options.qt_installer_framework_branch, options.installer_framework_source_dir)
    else:
        # fetch src package
        prepare_src_package(options.qt_installer_framework_uri, options.qt_installer_framework_uri_saveas, options.installer_framework_source_dir)


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
    qmake_bin = bldinstallercommon.locate_file(options.qt_build_dir, options.qt_qmake_bin)
    if not os.path.isfile(qmake_bin):
        print('*** Unable to find qmake, aborting!')
        print('qmake: {0}'.format(qmake_bin))
        sys.exit(-1)
    if not os.path.exists(options.installer_framework_build_dir):
        bldinstallercommon.create_dirs(options.installer_framework_build_dir)
    cmd_args = [qmake_bin]
    cmd_args += options.qt_installer_framework_qmake_args
    cmd_args += [options.installer_framework_source_dir]
    bldinstallercommon.do_execute_sub_process(cmd_args, options.installer_framework_build_dir)
    cmd_args = options.make_cmd
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), options.installer_framework_build_dir)


###############################
# function
###############################
def build_ifw_docs(options):
    print('--------------------------------------------------------------------')
    print('Building Qt Installer Framework Documentation')
    qmake_bin = bldinstallercommon.locate_file(options.qt_build_dir_dynamic, options.qt_qmake_bin)
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
    cmd_args = ['7z', 'a', options.installer_framework_payload_arch, package_dir]
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


###############################
# function
###############################
def clean_build_environment(options):
    if os.path.isfile(options.installer_framework_archive_name):
        os.remove(options.installer_framework_archive_name)
    if os.path.isfile(options.installer_framework_payload_arch):
        os.remove(options.installer_framework_payload_arch)
    if os.path.exists(options.build_artifacts_dir):
        bldinstallercommon.remove_tree(options.build_artifacts_dir)
    bldinstallercommon.create_dirs(options.build_artifacts_dir)
    if os.path.exists(options.installer_framework_build_dir):
        bldinstallercommon.remove_tree(options.installer_framework_build_dir)

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
        bldinstallercommon.remove_tree(options.qt_build_dir)
    if os.path.isfile(options.qt_source_package_uri_saveas):
        os.remove(options.qt_source_package_uri_saveas)
    if os.path.isfile(options.qt_installer_framework_uri_saveas):
        os.remove(options.qt_installer_framework_uri_saveas)


###############################
# function
###############################
def archive_installer_framework(options):
    print('--------------------------------------------------------------------')
    print('Archive Installer Framework')
    # first strip out all unnecessary files
    for root, dummy, files in os.walk(options.installer_framework_build_dir):
        for filename in files:
            if filename.endswith(('.moc', 'Makefile', '.cpp', '.h', '.o')) or filename == 'Makefile':
                os.remove(os.path.join(root, filename))
    cmd_args = ['7z', 'a', options.installer_framework_archive_name, os.path.basename(options.installer_framework_build_dir)]
    bldinstallercommon.do_execute_sub_process(cmd_args, ROOT_DIR)
    shutil.move(options.installer_framework_archive_name, options.build_artifacts_dir)


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
        cmd_args_archive = ['7z', 'a', options.installer_base_archive_name, bin_temp]
        cmd_args_clean = ['rm', bin_temp]
    if bldinstallercommon.is_win_platform():
        bin_path = bldinstallercommon.locate_executable(options.installer_framework_build_dir, 'installerbase.exe')
        bin_temp = ROOT_DIR + os.sep + 'tempSDKMaintenanceToolBase.exe'
        shutil.copy(bin_path, bin_temp)
        cmd_args_archive = ['7z', 'a', options.installer_base_archive_name, bin_temp]
        cmd_args_clean = ['del', bin_temp]
    bldinstallercommon.do_execute_sub_process(cmd_args_archive, ROOT_DIR)
    bldinstallercommon.do_execute_sub_process(cmd_args_clean, ROOT_DIR)
    if not os.path.isfile(options.installer_base_archive_name):
        print('*** Failed to generate archive: {0}'.format(options.installer_base_archive_name))
        sys.exit(-1)
    shutil.move(options.installer_base_archive_name, options.build_artifacts_dir)


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
    cmd_args = ['7z', 'a', options.mac_qt_menu_nib_archive_name, content_root_path]
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
    cmd_args_archive = ['7z', 'a', options.mac_deploy_qt_archive_name, content_path]
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
                         CARGS.incremental
                        )
    # build ifw tools
    build_ifw(OPTIONS, CARGS.create_installer)


