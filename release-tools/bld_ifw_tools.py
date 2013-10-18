#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2013 Digia Plc and/or its subsidiary(-ies).
## Contact: http://www.qt-project.org/legal
##
## This file is part of the release tools of the Qt Toolkit.
##
## $QT_BEGIN_LICENSE:LGPL$
## Commercial License Usage
## Licensees holding valid commercial Qt licenses may use this file in
## accordance with the commercial license agreement provided with the
## Software or, alternatively, in accordance with the terms contained in
## a written agreement between you and Digia.  For licensing terms and
## conditions see http://qt.digia.com/licensing.  For further information
## use the contact form at http://qt.digia.com/contact-us.
##
## GNU Lesser General Public License Usage
## Alternatively, this file may be used under the terms of the GNU Lesser
## General Public License version 2.1 as published by the Free Software
## Foundation and appearing in the file LICENSE.LGPL included in the
## packaging of this file.  Please review the following information to
## ensure the GNU Lesser General Public License version 2.1 requirements
## will be met: http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.
##
## In addition, as a special exception, Digia gives you certain additional
## rights.  These rights are described in the Digia Qt LGPL Exception
## version 1.1, included in the file LGPL_EXCEPTION.txt in this package.
##
## GNU General Public License Usage
## Alternatively, this file may be used under the terms of the GNU
## General Public License version 3.0 as published by the Free Software
## Foundation and appearing in the file LICENSE.GPL included in the
## packaging of this file.  Please review the following information to
## ensure the GNU General Public License version 3.0 requirements will be
## met: http://www.gnu.org/copyleft/gpl.html.
##
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
import shutil
import shlex

ROOT_DIR = os.path.dirname(os.path.realpath(__file__))



###############################
# Helper function
###############################
def get_default_qt_configure_options():
    plat = platform.system().lower()
    default_options = IfwOptions.default_qt_configure_options_linux
    if plat.startswith('win'):
        default_options = IfwOptions.default_qt_configure_options_windows
    elif plat.startswith('darwin'):
        default_options = IfwOptions.default_qt_configure_options_mac
    default_options = '-static -release -opensource -confirm-license -nomake examples -nomake demos -nomake tests -nomake docs -no-webkit -no-phonon -no-qt3support -no-opengl -no-dbus -no-declarative -no-accessibility -no-xmlpatterns -no-phonon-backend -no-multimedia -no-declarative-debug {0}'.format(default_options)
    return default_options

###############################
# Option class for ifw build
###############################
class IfwOptions:

    default_qt_source_package_uri               = 'http://download.qt-project.org/development_releases/prebuilt/qt-src-for-ifw/qt_4.8.4_ifw_prepared.tar.gz'
    if platform.system().lower().startswith('win'):
        default_qt_source_package_uri           = 'http://download.qt-project.org/development_releases/prebuilt/qt-src-for-ifw/qt_4.8.4_ifw_prepared.zip'
    default_qt_source_package_uri_saveas        = ROOT_DIR + os.sep + os.path.basename(default_qt_source_package_uri)
    default_qt_configure_options_linux          = '-silent -nomake plugins -qt-zlib -qt-libtiff -qt-libpng -qt-libmng -qt-libjpeg -no-svg -no-nis -no-cups -no-audio-backend -no-glib -no-gtkstyle -openssl'
    default_qt_configure_options_mac            = '-silent -nomake plugins -qt-zlib -qt-libtiff -qt-libpng -qt-libmng -qt-libjpeg -no-svg -no-nis -no-cups -no-audio-backend -openssl'
    default_qt_configure_options_windows        = '-openssl-linked OPENSSL_LIBS="-lssleay32MD -llibeay32MD"'
    default_qt_installer_framework_url          = 'git://gitorious.org/installer-framework/installer-framework.git'
    default_qt_installer_framework_branch       = '1.4'
    default_qt_installer_framework_qmake_args   = '-config release -config static -r'

    def __init__(self,
                 qt_source_package_uri,
                 qt_configure_options,
                 qt_installer_framework_url,
                 qt_installer_framework_branch,
                 qt_installer_framework_qmake_args,
                 product_key_checker_url,
                 product_key_checker_branch,
                 openssl_dir):
        self.development_mode                           = False
        self.incremental_mode                           = False
        self.qt_source_dir                              = os.path.normpath(ROOT_DIR + os.sep + 'qt-src')
        self.qt_build_dir                               = os.path.normpath(ROOT_DIR + os.sep + 'qt-bld')
        self.installer_framework_source_dir             = os.path.normpath(ROOT_DIR + os.sep + 'ifw-src')
        self.installer_framework_build_dir              = os.path.normpath(ROOT_DIR + os.sep + 'ifw-bld')
        self.make_cmd                                   = 'make -j' + str(multiprocessing.cpu_count() + 1)
        self.qt_qmake_bin                               = 'qmake'
        self.qt_configure_bin                           = self.qt_source_dir + os.sep + 'configure'
        if bldinstallercommon.is_win_platform():
            self.make_cmd                               = 'nmake'
            self.qt_qmake_bin                           = self.qt_qmake_bin + '.exe'
            self.qt_configure_bin                       = self.qt_configure_bin + '.exe'
        self.build_artifacts_dir                        = ROOT_DIR + os.sep + 'build_artifacts'
        self.mac_deploy_qt_archive_name                 = 'macdeployqt.7z'
        self.mac_qt_menu_nib_archive_name               = 'qt_menu.nib.7z'
        # determine filenames used later on
        architecture                                    = bldinstallercommon.get_architecture()
        plat_suffix                                     = bldinstallercommon.get_platform_suffix()
        self.installer_framework_archive_name           = 'installer-framework-build-' + plat_suffix + '-' + architecture + '.7z'
        self.installer_base_archive_name                = 'installerbase-' + plat_suffix + '-' + architecture + '.7z'
        # the rest
        self.qt_source_package_uri                      = qt_source_package_uri
        self.qt_source_package_uri_saveas               = ROOT_DIR + os.sep + os.path.basename(self.qt_source_package_uri)
        self.qt_configure_options                       = qt_configure_options + ' -prefix ' + self.qt_build_dir
        if platform.system().lower().startswith('win'):
            self.qt_configure_options = self.qt_configure_options + ' -I {0}\\include -L {0}\\lib\\VC\\static'.format(openssl_dir)
        self.qt_installer_framework_url                 = qt_installer_framework_url
        self.qt_installer_framework_branch              = qt_installer_framework_branch
        self.qt_installer_framework_qmake_args          = qt_installer_framework_qmake_args
        self.product_key_checker_url                    = product_key_checker_url
        self.product_key_checker_branch                 = product_key_checker_branch
        self.openssl_dir                                = openssl_dir
        self.product_key_checker_source_dir             = ''
        if product_key_checker_url:
            if os.path.isfile(product_key_checker_url):
                self.qt_installer_framework_qmake_args      += ' PRODUCTKEYCHECK_PRI_FILE=' + self.product_key_checker_url
            else:
                self.product_key_checker_source_dir         = os.path.normpath(ROOT_DIR + os.sep + 'product_key_checker')
                self.qt_installer_framework_qmake_args      += ' PRODUCTKEYCHECK_PRI_FILE=' + self.product_key_checker_source_dir + os.sep + 'qt_product_key_checker.pri'
        if bldinstallercommon.is_mac_platform():
            self.qt_installer_framework_qmake_args += ' QT_MENU_NIB_DIR=' + self.qt_source_dir + os.sep + 'src/gui/mac/qt_menu.nib'
        # sanity check
        self.sanity_check()

    def sanity_check(self):
        # check qt src package url
        res = bldinstallercommon.is_content_url_valid(self.qt_source_package_uri)
        if not(res):
            print('*** Qt src package uri is invalid: {0}'.format(self.qt_source_package_uri))
            sys.exit(-1)
        if (self.product_key_checker_url or self.product_key_checker_branch):
            if os.path.isfile(self.product_key_checker_url):
                print('Using product key checker: '.format(self.product_key_checker_url))
                return
            if not (self.product_key_checker_url and self.product_key_checker_branch):
                print('*** Product key checker has incomplete data: {0} | {1}'.format(self.product_key_checker_url, self.product_key_checker_branch))
                sys.exit(-1)

    def print_data(self):
        print('-----------------------------------------')
        print('make cmd:                                {0}'.format(self.make_cmd))
        print('qt_source_package_uri:                   {0}'.format(self.qt_source_package_uri))
        print('qt_source_package_uri_saveas:            {0}'.format(self.qt_source_package_uri_saveas))
        print('qt_source_dir:                           {0}'.format(self.qt_source_dir))
        print('qt_build_dir:                            {0}'.format(self.qt_build_dir))
        print('qt_configure_options:                    {0}'.format(self.qt_configure_options))
        print('qt_qmake_bin:                            {0}'.format(self.qt_qmake_bin))
        print('qt_configure_bin:                        {0}'.format(self.qt_configure_bin))
        print('qt_installer_framework_url:              {0}'.format(self.qt_installer_framework_url))
        print('qt_installer_framework_branch:           {0}'.format(self.qt_installer_framework_branch))
        print('qt_installer_framework_qmake_args:       {0}'.format(self.qt_installer_framework_qmake_args))
        print('installer_framework_source_dir:          {0}'.format(self.installer_framework_source_dir))
        print('installer_framework_build_dir:           {0}'.format(self.installer_framework_build_dir))
        print('installer_framework_archive_name:        {0}'.format(self.installer_framework_archive_name))
        print('installer_base_archive_name:             {0}'.format(self.installer_base_archive_name))
        print('product_key_checker_url:                 {0}'.format(self.product_key_checker_url))
        print('product_key_checker_branch:              {0}'.format(self.product_key_checker_branch))
        if platform.system().lower().startswith('win'):
            print('openssl_dir:              {0}'.format(self.openssl_dir))
        print('-----------------------------------------')


###############################
# Setup argument parser
###############################
def setup_argument_parser():
    parser = argparse.ArgumentParser(prog = os.path.basename(sys.argv[0]),
              add_help=True, description="Build Qt Installer-Framework",
               formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('--qt_archive_uri', help="Qt source package for Qt Installer-Framework", required=False, default=IfwOptions.default_qt_source_package_uri)
    parser.add_argument('--qt_configure_options', help="Configure options for (static) Qt build", required=False, default=get_default_qt_configure_options())
    parser.add_argument('--ifw_url', help="Git URL for Qt Installer-Framework", required=False, default=IfwOptions.default_qt_installer_framework_url)
    parser.add_argument('--ifw_branch', help="Git branch for Qt Installer-Framework", required=False, default=IfwOptions.default_qt_installer_framework_branch)
    parser.add_argument('--ifw_qmake_args', help="Qmake arguments for Installer-Framework build ", required=False, default=IfwOptions.default_qt_installer_framework_qmake_args)
    parser.add_argument('--product_key_checker_url', help="Git URL for enterprise product key checker", required=False)
    parser.add_argument('--product_key_checker_branch', help="Git branch for enterprise product key checker", required=False)
    parser.add_argument('--openssl_dir', help="Path where it can find the openssl installation(libs, includes) on windows.", required=False, default='C:\\OpenSSL')
    return parser


###############################
# Build IFW
###############################
def build_ifw(options):
    # verbose
    options.print_data()
    #clean environment first
    clean_build_environment(options)
    #checkout sources
    prepare_installer_framework(options)
    # copy qt sources
    prepare_qt_sources(options)
    # product key checker
    prepare_product_key_checker(options)
    # build qt
    build_qt(options)
    # build installer framework
    build_installer_framework(options)
    #archive
    archive_installerbase(options)
    archive_installer_framework(options)
    # for mac we do some extra work
    if bldinstallercommon.is_mac_platform():
        archive_nib(options)
        archive_macdeployqt(options)
    if options.development_mode:
        return os.path.basename(options.installer_framework_build_dir)
    else:
        return ''


###############################
# function
###############################
def prepare_qt_sources(options):
    if options.development_mode:
        if os.path.exists(options.qt_source_dir):
            return
    if options.incremental_mode and os.path.exists(options.qt_source_dir):
        return
    print('--------------------------------------------------------------------')
    print('Fetching Qt src package from: {0}'.format(options.qt_source_package_uri))
    if not os.path.isfile(options.qt_source_package_uri_saveas):
        if not bldinstallercommon.is_content_url_valid(options.qt_source_package_uri):
            print('*** Qt src package url is invalid! Abort!')
            sys.exit(-1)
        bldinstallercommon.retrieve_url(options.qt_source_package_uri, options.qt_source_package_uri_saveas)
    else:
        print('Found old local package, using that: {0}'.format(options.qt_source_package_uri_saveas))
    print('Done')
    print('--------------------------------------------------------------------')
    bldinstallercommon.create_dirs(options.qt_source_dir)
    bldinstallercommon.extract_file(options.qt_source_package_uri_saveas, options.qt_source_dir)
    l = os.listdir(options.qt_source_dir)
    items = len(l)
    if items == 1:
        dir_name = l[0]
        full_dir_name = options.qt_source_dir + os.sep + dir_name
        bldinstallercommon.move_tree(full_dir_name, options.qt_source_dir)
        bldinstallercommon.remove_tree(full_dir_name)
    else:
        print('*** Invalid dir structure encountered?!')
        sys.exit(-1)


###############################
# function
###############################
def build_qt(options):
    if options.development_mode:
        if os.path.exists(options.qt_build_dir):
            return
    if options.incremental_mode and os.path.exists(options.qt_build_dir):
        return
    bldinstallercommon.create_dirs(options.qt_build_dir)
    # configure first
    print('--------------------------------------------------------------------')
    print('Configuring Qt')
    configure_options = re.sub(' +', ' ', options.qt_configure_options)
    cmd_args = options.qt_configure_bin + ' ' + configure_options
    # shlex does not like backslashes
    cmd_args = cmd_args.replace('\\', '/')
    bldinstallercommon.do_execute_sub_process(shlex.split(cmd_args), options.qt_build_dir, True)
    print('--------------------------------------------------------------------')
    print('Building Qt')
    cmd_args = options.make_cmd
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), options.qt_build_dir, True)


###############################
# function
###############################
def prepare_installer_framework(options):
    if options.development_mode:
        if os.path.exists(options.installer_framework_source_dir):
            return
    if options.incremental_mode and os.path.exists(options.installer_framework_source_dir):
        return
    print('--------------------------------------------------------------------')
    print('Prepare Installer Framework source')
    #create dirs
    bldinstallercommon.create_dirs(options.installer_framework_build_dir)
    # clone repos
    bldinstallercommon.clone_repository(options.qt_installer_framework_url, options.qt_installer_framework_branch, options.installer_framework_source_dir)


###############################
# function
###############################
def prepare_product_key_checker(options):
    if not (options.product_key_checker_url and options.product_key_checker_branch):
        return
    if options.development_mode:
        if os.path.exists(options.product_key_checker_source_dir):
            return
    if options.incremental_mode and os.path.exists(options.product_key_checker_source_dir):
        return
    print('--------------------------------------------------------------------')
    print('Prepare Product Key Checker')
    #create dirs
    bldinstallercommon.create_dirs(options.product_key_checker_source_dir)
    # clone repos
    bldinstallercommon.clone_repository(options.product_key_checker_url, options.product_key_checker_branch, options.product_key_checker_source_dir)


###############################
# function
###############################
def build_installer_framework(options):
    if options.incremental_mode:
        print('INCREMENTAL_MODE')
        print(options.installer_framework_build_dir)
        if os.path.exists(os.path.join(options.installer_framework_build_dir, 'bin', 'installerbase.exe')):
            print('exists')
            return
    print('--------------------------------------------------------------------')
    print('Building Installer Framework')
    qmake_bin = options.qt_build_dir + os.sep + 'bin' + os.sep + options.qt_qmake_bin
    if not os.path.isfile(qmake_bin):
        print('*** Unable to find qmake, aborting!')
        print('qmake: {0}'.format(qmake_bin))
        sys.exit(-1)
    if not os.path.exists(options.installer_framework_build_dir):
        bldinstallercommon.create_dirs(options.installer_framework_build_dir)
    cmd_args = qmake_bin + ' ' + options.qt_installer_framework_qmake_args + ' ' + options.installer_framework_source_dir
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), options.installer_framework_build_dir, True)
    cmd_args = options.make_cmd
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), options.installer_framework_build_dir, True)


###############################
# function
###############################
def clean_build_environment(options):
    if options.development_mode or options.incremental_mode:
        return
    # delete existing stuff if exists
    if os.path.exists(options.installer_framework_source_dir):
        bldinstallercommon.remove_tree(options.installer_framework_source_dir)
    if os.path.exists(options.installer_framework_build_dir):
        bldinstallercommon.remove_tree(options.installer_framework_build_dir)
    if os.path.exists(options.qt_source_dir):
        bldinstallercommon.remove_tree(options.qt_source_dir)
    if os.path.exists(options.qt_build_dir):
        bldinstallercommon.remove_tree(options.qt_build_dir)
    if os.path.isfile(options.installer_framework_archive_name):
        os.remove(options.installer_framework_archive_name)
    if os.path.isfile(options.qt_source_package_uri_saveas):
        os.remove(options.qt_source_package_uri_saveas)
    if os.path.exists(options.build_artifacts_dir):
        bldinstallercommon.remove_tree(options.build_artifacts_dir)
    if os.path.exists(options.product_key_checker_source_dir):
        bldinstallercommon.remove_tree(options.product_key_checker_source_dir)
    # create build artifacts directory
    bldinstallercommon.create_dirs(options.build_artifacts_dir)


###############################
# function
###############################
def archive_installer_framework(options):
    if options.development_mode or options.incremental_mode:
        return
    if options.incremental_mode and os.path.isfile(options.installer_framework_archive_name):
        return
    print('--------------------------------------------------------------------')
    print('Archive Installer Framework')
    # first strip out all unnecessary files
    for root, dirs, files in os.walk(options.installer_framework_build_dir):
        for filename in files:
            if filename.endswith(('.moc', 'Makefile', '.cpp', '.h', '.o')) or filename == 'Makefile':
                os.remove(os.path.join(root, filename))
    cmd_args = ['7z', 'a', options.installer_framework_archive_name, os.path.basename(options.installer_framework_build_dir)]
    bldinstallercommon.do_execute_sub_process(cmd_args, ROOT_DIR, True)
    shutil.move(options.installer_framework_archive_name, options.build_artifacts_dir)


###############################
# function
###############################
def archive_installerbase(options):
    if options.development_mode:
        return
    if options.incremental_mode and os.path.isfile(options.installer_base_archive_name):
        return
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
        bin_temp = ROOT_DIR + os.sep + 'temp'
        bldinstallercommon.create_dirs(bin_temp)
        shutil.copy(bin_path, bin_temp + os.sep + 'SDKMaintenanceToolBase.exe')
        cmd_args_archive = ['7z', 'a', options.installer_base_archive_name, bin_temp]
        cmd_args_clean = ['rmdir' , '/q/s', bin_temp]
    bldinstallercommon.do_execute_sub_process(cmd_args_archive, ROOT_DIR, True)
    bldinstallercommon.do_execute_sub_process(cmd_args_clean, ROOT_DIR, True)
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
    bldinstallercommon.do_execute_sub_process(cmd_args, ROOT_DIR, True)
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
    bldinstallercommon.do_execute_sub_process(cmd_args_archive, ROOT_DIR, True)
    if not os.path.isfile(options.mac_deploy_qt_archive_name):
        print('*** Failed to generate archive: {0}'.format( options.mac_deploy_qt_archive_name))
        sys.exit(-1)
    shutil.move(options.mac_deploy_qt_archive_name, options.build_artifacts_dir)


###############################
# Main
###############################
if __name__ == "__main__":
    # init things
    bldinstallercommon.init_common_module(ROOT_DIR)
    PARSER = setup_argument_parser()
    # parse args
    CALLER_ARGUMENTS = PARSER.parse_args()
    # create options object
    OPTIONS = IfwOptions(CALLER_ARGUMENTS.qt_archive_uri,
                         CALLER_ARGUMENTS.qt_configure_options,
                         CALLER_ARGUMENTS.ifw_url,
                         CALLER_ARGUMENTS.ifw_branch,
                         CALLER_ARGUMENTS.ifw_qmake_args,
                         CALLER_ARGUMENTS.product_key_checker_url,
                         CALLER_ARGUMENTS.product_key_checker_branch,
                         CALLER_ARGUMENTS.openssl_dir
                        )
    # build ifw tools
    build_ifw(OPTIONS)


