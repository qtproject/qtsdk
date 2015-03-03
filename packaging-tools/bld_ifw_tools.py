#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2015 The Qt Company Ltd.
## Contact: http://www.qt-project.org/legal
##
## This file is part of the release tools of the Qt Toolkit.
##
## $QT_BEGIN_LICENSE:LGPL21$
## Commercial License Usage
## Licensees holding valid commercial Qt licenses may use this file in
## accordance with the commercial license agreement provided with the
## Software or, alternatively, in accordance with the terms contained in
## a written agreement between you and The Qt Company. For licensing terms
## and conditions see http://www.qt.io/terms-conditions. For further
## information use the contact form at http://www.qt.io/contact-us.
##
## GNU Lesser General Public License Usage
## Alternatively, this file may be used under the terms of the GNU Lesser
## General Public License version 2.1 or version 3 as published by the Free
## Software Foundation and appearing in the file LICENSE.LGPLv21 and
## LICENSE.LGPLv3 included in the packaging of this file. Please review the
## following information to ensure the GNU Lesser General Public License
## requirements will be met: https://www.gnu.org/licenses/lgpl.html and
## http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.
##
## As a special exception, The Qt Company gives you certain additional
## rights. These rights are described in The Qt Company LGPL Exception
## version 1.1, included in the file LGPL_EXCEPTION.txt in this package.
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
# Get common Qt configure arguments for all platforms (qt4 & qt5)
##################################################################
def get_common_allos_qt_configure_options():
    options = '-static -release -opensource -confirm-license '
    options += '-nomake examples -nomake tests '
    options += '-accessibility '
    return options


##################################################################
# Get common Qt configure arguments for unix platform (qt4 & qt5)
##################################################################
def get_common_unix_qt_configure_options():
    options = '-qt-zlib -qt-libpng -qt-libjpeg -no-cups '
    options += '-openssl '
    return options


##################################################################
# Get default Qt4 configure arguments. Platform is detected.
##################################################################
def get_default_qt4_configure_options():
    plat = platform.system().lower()
    # common
    options = get_common_allos_qt_configure_options()
    options += '-nomake demos -nomake docs '
    options += '-no-webkit -no-phonon -no-phonon-backend -no-opengl -no-dbus '
    options += '-no-xmlpatterns -no-qt3support -no-multimedia -no-declarative -no-declarative-debug '
    # Windows
    if plat.startswith('win'):
        options += '-openssl-linked OPENSSL_LIBS="-lssleay32MD -llibeay32MD -lcrypt32" '
    # Unix
    else:
        options += get_common_unix_qt_configure_options()
        options += '-silent -nomake plugins -qt-libtiff -qt-libmng '
        options += '-no-svg -no-nis -no-audio-backend '
        # Mac
        if plat.startswith('darwin'):
            options += '-no-pch '
        # Linux
        else:
            options += '-no-gtkstyle -no-glib '
    return options


##################################################################
# Get default Qt5 configure arguments. Platform is detected.
##################################################################
def get_default_qt5_configure_options():
    plat = platform.system().lower()
    # common
    options = get_common_allos_qt_configure_options()
    options += '-no-sql-sqlite -no-qml-debug '
    options += '-skip qtenginio -skip qtlocation -skip qtmultimedia -skip qtserialport '
    options += '-skip qtquick1 -skip qtquickcontrols -skip qtscript -skip qtsensors '
    options += '-skip qtwebkit -skip qtwebsockets -skip qtxmlpatterns -skip qtactiveqt '
    # Windows
    if plat.startswith('win'):
        options += '-target xp -no-opengl -no-icu '
        options += '-openssl-linked OPENSSL_LIBS="-lssleay32MT -llibeay32MT -lcrypt32 -lgdi32" '
    # Unix
    else:
        # OSX and Linux
        options += get_common_unix_qt_configure_options()
        # Linux
        if plat.startswith('linux'):
            options += '-qt-xcb -no-opengl -no-icu '
            options += '-qt-pcre -qt-freetype -no-glib -no-egl -no-xinput '
            options += '-no-xinput2 -no-sm '
    return options


##################################################################
# Get default Qt configure arguments. Platform is detected.
##################################################################
def get_default_qt_configure_options(qt5_build = True):
    if qt5_build:
        return get_default_qt5_configure_options()
    else:
        return get_default_qt4_configure_options()


###############################
# Option class for ifw build
###############################
class IfwOptions:

    default_qt5_src_pkg = 'http://download.qt.io/official_releases/qt/5.4/5.4.0/single/qt-everywhere-opensource-src-5.4.0' + ARCH_EXT
    default_qt4_src_pkg = 'http://download.qt.io/development_releases/prebuilt/qt-src-for-ifw/qt-everywhere-opensource-src-4.8.6-ifw-patch' + ARCH_EXT

    default_qt_installer_framework_url          = 'git://gitorious.org/installer-framework/installer-framework.git'

    default_qt_installer_framework_branch_qt4   = '1.6'
    default_qt_installer_framework_branch_qt5   = '2.0'

    default_qt_installer_framework_qmake_args   = ['-config', 'release', '-config', 'static']

    def __init__(self,
                 qt5_build,
                 qt_source_package_uri,
                 qt_configure_options,
                 qt_installer_framework_url,
                 qt_installer_framework_branch,
                 qt_installer_framework_qmake_args,
                 product_key_checker_pri,
                 openssl_dir,
                 incremental_build = False):
        self.incremental_mode                           = incremental_build
        self.qt5_build                                  = qt5_build
        self.qt_source_dir                              = os.path.join(ROOT_DIR, 'qt-src')
        self.qt_build_dir                               = os.path.join(ROOT_DIR, 'qt-bld')
        self.installer_framework_source_dir             = os.path.join(ROOT_DIR, 'ifw-src')
        self.installer_framework_build_dir              = os.path.join(ROOT_DIR, 'ifw-bld')
        self.qt_installer_framework_url                 = qt_installer_framework_url
        self.qt_installer_framework_branch              = qt_installer_framework_branch
        self.qt_installer_framework_qmake_args          = qt_installer_framework_qmake_args
        if bldinstallercommon.is_win_platform():
            self.make_cmd                               = 'nmake'
            self.make_install_cmd                       = 'nmake install'
            self.qt_qmake_bin                           = 'qmake.exe'
            if qt5_build:
                self.qt_configure_bin                       = self.qt_source_dir + os.sep + 'configure.bat'
            else:
                self.qt_configure_bin                       = self.qt_source_dir + os.sep + 'configure.exe'
        else:
            self.make_cmd                               = 'make -j' + str(multiprocessing.cpu_count() + 1)
            self.make_install_cmd                       = 'make install'
            self.qt_qmake_bin                           = 'qmake'
            self.qt_configure_bin                       = self.qt_source_dir + os.sep + 'configure'

        self.build_artifacts_dir                        = os.path.join(ROOT_DIR, pkg_constants.IFW_BUILD_ARTIFACTS_DIR)
        self.mac_deploy_qt_archive_name                 = 'macdeployqt.7z'
        self.mac_qt_menu_nib_archive_name               = 'qt_menu.nib.7z'
        # determine filenames used later on
        architecture                                    = bldinstallercommon.get_architecture()
        plat_suffix                                     = bldinstallercommon.get_platform_suffix()
        self.installer_framework_archive_name           = 'installer-framework-build-' + plat_suffix + '-' + architecture + '.7z'
        self.installer_base_archive_name                = 'installerbase-' + plat_suffix + '-' + architecture + '.7z'
        self.qt_source_package_uri                      = qt_source_package_uri
        self.qt_source_package_uri_saveas               = os.path.join(ROOT_DIR, os.path.basename(self.qt_source_package_uri))
        # Set Qt build prefix
        qt_prefix = ' -prefix ' + self.qt_build_dir
        if qt5_build:
            qt_prefix += os.sep + 'qtbase'
        self.qt_configure_options = qt_configure_options + qt_prefix
        # OpenSSL (Win)
        if platform.system().lower().startswith('win'):
            self.qt_configure_options += ' -I {0}\\include -L {0}\\lib\\VC\\static'.format(openssl_dir)
        self.openssl_dir                                = openssl_dir
        # Product key checker
        self.product_key_checker_pri                    = product_key_checker_pri
        if product_key_checker_pri:
            if os.path.isfile(product_key_checker_pri):
                self.qt_installer_framework_qmake_args      += ['-r', 'PRODUCTKEYCHECK_PRI_FILE=' + self.product_key_checker_pri]
        # Mac specific
        if bldinstallercommon.is_mac_platform():
            if not qt5_build:
                self.qt_installer_framework_qmake_args += ['QT_MENU_NIB_DIR=' + self.qt_source_dir + os.sep + 'src/gui/mac/qt_menu.nib']
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
        print('Qt5 usage:                               {0}'.format(self.qt5_build))
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
        print('product_key_checker:                     {0}'.format(self.product_key_checker_pri))
        if platform.system().lower().startswith('win'):
            print('openssl_dir:              {0}'.format(self.openssl_dir))
        print('-----------------------------------------')



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
    # build qt
    build_qt(options)
    # build installer framework
    build_installer_framework(options)
    #archive
    archive_installerbase(options)
    archive_installer_framework(options)
    # for mac we do some extra work
    if bldinstallercommon.is_mac_platform() and not options.qt5_build:
        archive_nib(options)
        archive_macdeployqt(options)
    return os.path.basename(options.installer_framework_build_dir)


###############################
# function
###############################
def prepare_qt_sources(options):
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
    if bldinstallercommon.is_win_platform():
        patch_win32_mkspecs(os.path.join(options.qt_source_dir, "qtbase", "mkspecs"))

###############################
# function
###############################
def build_qt(options):
    if options.incremental_mode:
        qmake_bin = bldinstallercommon.locate_file(options.qt_build_dir, options.qt_qmake_bin)
        qt_lib_dir = bldinstallercommon.locate_directory(options.qt_build_dir, 'lib')
        if os.path.isfile(qmake_bin) and os.path.isdir(qt_lib_dir):
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
    bldinstallercommon.do_execute_sub_process(cmd_args, options.installer_framework_build_dir, True)
    cmd_args = options.make_cmd
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), options.installer_framework_build_dir, True)


###############################
# function
###############################
def clean_build_environment(options):
    if os.path.isfile(options.installer_framework_archive_name):
        os.remove(options.installer_framework_archive_name)
    if os.path.exists(options.build_artifacts_dir):
        bldinstallercommon.remove_tree(options.build_artifacts_dir)
    bldinstallercommon.create_dirs(options.build_artifacts_dir)
    if os.path.exists(options.installer_framework_build_dir):
        bldinstallercommon.remove_tree(options.installer_framework_build_dir)

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


###############################
# function
###############################
def archive_installer_framework(options):
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
    for root, dirs, files in os.walk(mkspecsdir):
        for file in files:
            if "win32" in root and file == "qmake.conf":
                patch(os.path.join(root, file), {"-MD" : "-MT", "embed_manifest_dll" : "", "embed_manifest_exe" : "" })

###############################
# Setup argument parser
###############################
def setup_argument_parser():
    parser = argparse.ArgumentParser(prog = os.path.basename(sys.argv[0]),
              add_help=True, description="Build Qt Installer-Framework",
               formatter_class=argparse.RawTextHelpFormatter)

    parser.add_argument('--qt4', help="For legacy Qt4 based Installer-Framework build", required=False, action='store_true', default=False)
    parser.add_argument('--qt_archive_uri', help="Qt source package for Qt Installer-Framework", required=False)
    parser.add_argument('--qt_configure_options', help="Configure options for (static) Qt build", required=False)
    parser.add_argument('--ifw_url', help="Git URL for Qt Installer-Framework", required=False, default=IfwOptions.default_qt_installer_framework_url)
    parser.add_argument('--ifw_branch', help="Git branch for Qt Installer-Framework", required=False)
    parser.add_argument('--ifw_qmake_args', help="Qmake arguments for Installer-Framework build ", required=False, default=IfwOptions.default_qt_installer_framework_qmake_args)
    parser.add_argument('--product_key_checker_pri', help="Custom product key checker (.pri file)", required=False)
    parser.add_argument('--openssl_dir', help="Path where it can find the openssl installation(libs, includes) on windows.", required=False, default='C:\\OpenSSL')
    parser.add_argument('--debug', help="Build the ifw in debug mode", action='store_true', required=False, default=False)
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
    qt5_build = True if not CARGS.qt4 else False
    if qt5_build:
        qt_src               = IfwOptions.default_qt5_src_pkg if not CARGS.qt_archive_uri else CARGS.qt_archive_uri
        qt_configure_options = get_default_qt5_configure_options() if not CARGS.qt_configure_options else CARGS.qt_configure_options
        ifw_branch           = IfwOptions.default_qt_installer_framework_branch_qt5 if not CARGS.ifw_branch else CARGS.ifw_branch
    else:
        qt_src               = IfwOptions.default_qt4_src_pkg if not CARGS.qt_archive_uri else CARGS.qt_archive_uri
        qt_configure_options = get_default_qt4_configure_options() if not CARGS.qt_configure_options else CARGS.qt_configure_options
        ifw_branch           = IfwOptions.default_qt_installer_framework_branch_qt4 if not CARGS.ifw_branch else CARGS.ifw_branch

    qt_conf_args = CARGS.qt_configure_options
    ifw_qmake_args = CARGS.ifw_qmake_args
    if CARGS.debug:
        qt_conf_args = qt_conf_args.replace('-release', '-debug')
        ifw_qmake_args = ifw_qmake_args.replace('-config release', '-config debug')
    # create options object
    OPTIONS = IfwOptions(qt5_build,
                         qt_src,
                         qt_configure_options,
                         CARGS.ifw_url,
                         ifw_branch,
                         ifw_qmake_args,
                         CARGS.product_key_checker_pri,
                         CARGS.openssl_dir,
                         CARGS.incremental
                        )
    # build ifw tools
    build_ifw(OPTIONS)


