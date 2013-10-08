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
## ensure the GNU General Public Lhttps://www.google.fi/icense version 3.0 requirements will be
## met: http://www.gnu.org/copyleft/gpl.html.
##
##
## $QT_END_LICENSE$
##
#############################################################################

"""Scripts to generate SDK installer based on open source InstallerFramework"""

# import the print function which is used in python 3.x
from __future__ import print_function
import ConfigParser
import os
import shutil
import sys
from time import gmtime, strftime
import urllib
from optparse import OptionParser, Option


import bldinstallercommon
import release_build_handler


# ----------------------------------------------------------------------
# external commands
CURL_COMMAND                = ''
SSH_COMMAND                 = ''
SCP_COMMAND                 = ''

# ----------------------------------------------------------------------
BUILD_TIMESTAMP             = strftime('%Y-%m-%d', gmtime())
SCRIPT_ROOT_DIR             = os.path.dirname(os.path.realpath(__file__))
REPO_OUTPUT_DIR             = os.path.normpath(os.path.join(SCRIPT_ROOT_DIR, 'repository'))
WORK_DIR                    = os.path.join(os.environ['PKG_NODE_ROOT'], 'build')
#WORK_DIR                    = os.environ['PKG_NODE_ROOT']
COMMAND                     = ''
LICENSE                     = ''
OPTION_PARSER               = 0
QT_VERSION                  = ''
QT_VERSION_TAG              = ''
QTCREATOR_VERSION           = ''
QTCREATOR_VERSION_DESCRIPTION = ''
QT_FULL_VERSION             = ''
TIME_STAMP                  = ''
BUILD_NUMBER                = ''
PKG_SERVER_ADDR             = ''
PATH                        = '/data/www/packages/jenkins'
TARGET_ENV                  = ''
ICU_LIBS                    = 'http://download.qt-project.org/development_releases/prebuilt/icu/src/icu4c-51_1-src.tgz'
QT_SRC_FOR_IFW_PREPARED     = 'http://download.qt-project.org/development_releases/prebuilt/qt-src-for-ifw/qt_4.8.4_ifw_prepared'
IFW_GIT_URL                 = 'git://gitorious.org/installer-framework/installer-framework.git'
SRC_URL_PREFIX              = 'http://qt-rnd.it.local/packages/jenkins'
SRC_URL                     = ''
PLATFORM                    = ''
SRC_DEST_DIRS               = ['src', 'src/submodules', 'src/examples_injection', 'src/licheck']
INSTALLER_BUILD_OUTPUT_DIR  = 'build_artifacts'
# TODO: target directories hard coded, should be figured out from somewhere!
BIN_TARGET_DIRS             = \
{'linux-g++-Ubuntu11.10-x86_Android-armv5':'android_armv5/linux_x86'\
,'linux-g++-Ubuntu11.10-x64_Android-armv5':'android_armv5/linux_x64'\
,'mac-clang-10.7-x64_Android-armv5':'android_armv5/mac_x64'\
,'win-MinGW4.8-Windows7-x86_Android-armv5':'android_armv5/mingw_x86'\
,'linux-g++-Ubuntu11.10-x86_Android-armv7':'android_armv7/linux_x86'\
,'linux-g++-Ubuntu11.10-x64_Android-armv7':'android_armv7/linux_x64'\
,'mac-clang-10.7-x64_Android-armv7':'android_armv7/mac_x64'\
,'win-MinGW4.8-Windows7-x86_Android-armv7':'android_armv7/mingw_x86'\
,'linux-g++-Ubuntu11.10-x86_Android-mips':'android_mips/linux_x86'\
,'linux-g++-Ubuntu11.10-x64_Android-mips':'android_mips/linux_x64'\
,'mac-clang-10.7-x64_Android-mips':'android_mips/mac_x64'\
,'win-MinGW4.8-Windows7-x86_Android-mips':'android_mips/mingw_x86'\
,'linux-g++-Ubuntu11.10-x86_Android-x86':'android_x86/linux_x86'\
,'linux-g++-Ubuntu11.10-x64_Android-x86':'android_x86/linux_x64'\
,'mac-clang-10.7-x64_Android-x86':'android_x86/mac_x64'\
,'win-MinGW4.8-Windows7-x86_Android-x86':'android_x86/mingw_x86'\
,'mac-clang-10.8-x64_iOS':'ios/mac_x64'\
,'mac-clang-10.8-x64_iOS-iphoneos':'ios_armv7/mac_x64'\
,'mac-clang-10.8-x64_iOS-iphonesimulator':'ios_x86/mac_x64'\
,'linux-g++-Ubuntu11.10-x86':'linux_gcc_32_ubuntu1110'\
,'linux-g++-Ubuntu11.10-x64':'linux_gcc_64_ubuntu1110'\
,'linux-g++-Ubuntu_11.10_x86':'linux_gcc_32_ubuntu1110'\
,'linux-g++-Ubuntu_11.10_x64':'linux_gcc_64_ubuntu1110'\
,'mac-clang-OSX_10.7_x64':'mac_cocoa_10.7'\
,'mac-clang-10.8-x64':'mac_cocoa_10.7'\
,'win-MinGW4.8-Windows7-x86_OpenGL':'windows_mingw'\
,'win-msvc2010-Windows7-x86_ANGLE':'windows_vs2010_32'\
,'win-msvc2010-Windows7-x86_OpenGL':'windows_vs2010_32_opengl'\
,'win-msvc2012-Windows8-x86_ANGLE':'windows_vs2012_32'\
,'win-msvc2012-Windows8-x64_ANGLE':'windows_vs2012_64'\
,'win-msvc2012-Windows8-x64_OpenGL':'windows_vs2012_64_opengl'\
,'win32-msvc2010_Windows_7':'windows_vs2010_32'\
,'win64-msvc2012_Windows_8':'windows_vs2012_64'\
,'macx-clang_OSX_10.7':'mac_cocoa_10.7'\
,'pkg-osx107-x64-01':'mac_cocoa_10.7'\
,'mac-clang-10.7-x64':'mac_cocoa_10.7'\
,'pkg-win7-x86-01':'windows_vs2010_32'}
REMOTE_DIR                  = ''
LATEST_DIR                  = ''
EXTRA_ENV                   = dict(os.environ)
MAKE_INSTALL_PADDING        = ''


class MultipleOption(Option):
    ACTIONS = Option.ACTIONS + ("extend",)
    STORE_ACTIONS = Option.STORE_ACTIONS + ("extend",)
    TYPED_ACTIONS = Option.TYPED_ACTIONS + ("extend",)
    ALWAYS_TYPED_ACTIONS = Option.ALWAYS_TYPED_ACTIONS + ("extend",)

    def take_action(self, action, dest, opt, value, values, parser):
        if action == "extend":
            values.ensure_value(dest, []).append(value)
        else:
            Option.take_action(self, action, dest, opt, value, values, parser)


###############################
# Sanity check packaging server
###############################
def sanity_check_packaging_server():
    if not PKG_SERVER_ADDR:
        print('*** Error - Packaging server address (PKG_SERVER_ADDR) not defined?')
        sys.exit(-1)

###############################
# sign windows executable
###############################
def sign_windows_executable(file_path, working_dir, abort_on_fail):
    cmd_args = ['C:\Utils\sign\signtool.exe', 'sign', '/v', '/du', os.environ['SIGNING_SERVER'], '/p', os.environ['SIGNING_PASSWORD'],
        '/t', 'http://timestamp.verisign.com/scripts/timestamp.dll', '/f', 'C:\utils\sign\keys.pfx', file_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, working_dir, abort_on_fail)


###############################
# Unlock keychain
###############################
def unlock_keychain():
    cmd_args = ['/Users/qt/unlock-keychain.py']
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


###############################
# Lock keychain
###############################
def lock_keychain():
    cmd_args = ['security', 'lock-keychain', 'Developer_ID_Digia.keychain']
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


###############################
# sign windows executable
###############################
def sign_mac_executable(file_path, working_dir, abort_on_fail):
    s_arg = 'Developer ID Application: Digia Plc'
    cmd_args = ['codesign', '-r', '/Users/qt/csreq.txt', '-s', s_arg, file_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, working_dir, abort_on_fail)


###############################
# init_qt_build_cycle
###############################
def init_qt_build_cycle():
    sanity_check_packaging_server()
    # create dir structures in network drive
    # TODO: Figure out correct path + check parameters!
    for dir_name in SRC_DEST_DIRS:
        if dir_name != 'src/licheck':
            dir_path = REMOTE_DIR + '/' + dir_name
            create_remote_dirs(PKG_SERVER_ADDR, dir_path)
        elif LICENSE == 'enterprise':
            dir_path = REMOTE_DIR + '/' + dir_name
            create_remote_dirs(PKG_SERVER_ADDR, dir_path)

    # Create directories for targets
    # for dir_name in BIN_TARGET_DIRS:
    #    dir_path = os.path.join(REMOTE_DIR, dir_name)
    #    create_remote_dirs(PKG_SERVER_ADDR, dir_path)

    # Update latest link
    cmd_args = [SSH_COMMAND, PKG_SERVER_ADDR, 'ln -sfn', REMOTE_DIR, LATEST_DIR]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)



###############################
# handle_ifw_build()
###############################
def handle_ifw_build():
    sanity_check_packaging_server()
    os.chdir(SCRIPT_ROOT_DIR)
    extension = '.tar.gz'
    qt_src_pkg = QT_SRC_FOR_IFW_PREPARED
    ifw_url = IFW_GIT_URL
    ifw_branch = '1.4'
    if bldinstallercommon.is_win_platform():
        extension = '.zip'
    qt_src_pkg += extension
    cmd_args = ['python', '-u', 'bld_ifw_tools.py', '--qt_archive_uri=' + qt_src_pkg, '--ifw_url=' + ifw_url, '--ifw_branch=' + ifw_branch]
    if LICENSE == 'enterprise':
        cmd_args += ['--product_key_checker_url=' + WORK_DIR + '/qtsdk-enterprise/productkeycheck/qt_product_key_checker.pri']
    # execute
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)

    ## create destination dirs
    # internal
    create_remote_dirs(PKG_SERVER_ADDR, PATH + '/' + LICENSE + '/ifw/' + ifw_branch)
    # public
    if LICENSE == 'opensource':
        # public server address and path
        ext_server_base_url  = os.environ['EXT_SERVER_BASE_URL']
        ext_server_base_path = os.environ['EXT_SERVER_BASE_PATH']
        # public server directories
        ext_dest_dir = ext_server_base_path + '/snapshots/ifw/' + ifw_branch + '/' + TIME_STAMP[:10] + '_' + BUILD_NUMBER
        cmd_args_mkdir_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
        cmd_args_mkdir_ext = cmd_args_mkdir_pkg + ['ssh', ext_server_base_url, 'mkdir', '-p', ext_dest_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_ext, SCRIPT_ROOT_DIR, True)

    if bldinstallercommon.is_win_platform():
        file_list = os.listdir(SCRIPT_ROOT_DIR+'/' + INSTALLER_BUILD_OUTPUT_DIR)
        for file_name in file_list:
            if file_name.endswith(".7z"):
                cmd_args = [SCP_COMMAND, file_name, PKG_SERVER_ADDR + ':' + PATH + '/' + LICENSE + '/ifw/' + ifw_branch + '/']
                bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR + '/' + INSTALLER_BUILD_OUTPUT_DIR, True)
    else:
        cmd_args = ['rsync', '-r', './', PKG_SERVER_ADDR + ':' + PATH + '/' + LICENSE + '/ifw/' + ifw_branch + '/']
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR + '/' + INSTALLER_BUILD_OUTPUT_DIR, True)

    # copy ifw snapshot to public server
    if LICENSE == 'opensource':
        cmd_args_copy_ifw_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
        cmd_args_copy_ifw_ext = cmd_args_copy_ifw_pkg + ['scp', PATH + '/' + LICENSE + '/ifw/' + ifw_branch + '/' + 'installer-framework-build*.7z', ext_server_base_url + ':' + ext_dest_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_copy_ifw_ext, SCRIPT_ROOT_DIR, True)


###############################
# handle_qt_src_package_build
###############################
def handle_qt_src_package_build():
    sanity_check_packaging_server()
    exec_path = os.path.join(WORK_DIR, 'qt5')
    #bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    if LICENSE == 'enterprise':
        cmd_args = ['../patches/apply.sh']
        bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)

    if LICENSE == 'enterprise':
        copy_license_checkers()
    package_path = os.path.join(WORK_DIR, 'src_pkg')
    bldinstallercommon.create_dirs(package_path)
    # parse module exclude list from release description file
    conf_file_base_path = os.path.join(SCRIPT_ROOT_DIR, 'releases', os.environ['RELEASE_BUILD_CONF_FILE'])
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(conf_file_base_path))
    exclude_list = bldinstallercommon.safe_config_key_fetch(parser, 'release.global', 'module_exclude_list')
    split_exclude_list = exclude_list.split(',')
    module_exclude_list = []
    for item in split_exclude_list:
        module_exclude_list += ['-i', item]
    # cmd args for source packaging srcipt
    cmd_args = [os.path.join(SCRIPT_ROOT_DIR, 'mksrc.sh'), '-u', os.path.join(WORK_DIR, 'qt5')]
    cmd_args += ['-v', QT_FULL_VERSION, '-m', '-N', '-l', LICENSE]
    cmd_args += module_exclude_list
    # create src package
    bldinstallercommon.do_execute_sub_process(cmd_args, package_path, True)

    # Example injection
    package_name = 'qt-everywhere-' + LICENSE + '-src-' + QT_FULL_VERSION

    cmd_args = ['tar', 'xzf', 'single/' + package_name + '.tar.gz']

    bldinstallercommon.do_execute_sub_process(cmd_args, package_path, True)
    essentials_path = os.path.join(WORK_DIR, 'src_pkg', 'examples_essentials')
    bldinstallercommon.create_dirs(essentials_path)
    addons_path = os.path.join(WORK_DIR, 'src_pkg', 'examples_addons')
    bldinstallercommon.create_dirs(addons_path)

    src_dirs = os.listdir(os.path.join(package_path, package_name))
    current_path = os.getcwd()
    os.chdir(os.path.join(package_path, package_name))
    for dir_name in src_dirs:
        if os.path.isdir(dir_name):
            module_dirs = os.listdir(dir_name)
            for example_dir in module_dirs:
                if example_dir == 'examples':
                    bldinstallercommon.copy_tree(os.path.join(package_path, package_name, dir_name, example_dir), essentials_path)
    os.chdir(current_path)
    cmd_args = ['cp', '-r', os.path.join(package_name, 'qtbase', 'examples', 'examples.pro'), essentials_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, package_path, True)

    # remove documentation source files ('doc' subdirs) from examples
    doc_dir = 'doc'
    for root, dirs, files in os.walk(essentials_path):
        if doc_dir in dirs:
            # do not recurse into doc directory
            dirs.remove(doc_dir)
            shutil.rmtree(os.path.join(root, doc_dir))

    # remove out of place top level files from qtdeclarative
    if os.path.exists(os.path.join(essentials_path, 'HACKING')):
        os.remove(os.path.join(essentials_path, 'HACKING'))
    if os.path.exists(os.path.join(essentials_path, 'README')):
        os.remove(os.path.join(essentials_path, 'README'))

    shutil.move(os.path.join(essentials_path, 'activeqt'), addons_path)
    shutil.move(os.path.join(essentials_path, 'svg'), addons_path)

    cmd_args = ['7z', 'a', os.path.join('..', 'examples_essentials.7z'), '*']
    bldinstallercommon.do_execute_sub_process(cmd_args, essentials_path, True)
    cmd_args = [os.path.join(SCRIPT_ROOT_DIR, 'winzipdir.sh'), os.path.join('..', 'examples_essentials.zip'), '.' ]
    bldinstallercommon.do_execute_sub_process(cmd_args, essentials_path, True)

    cmd_args = ['7z', 'a', os.path.join('..', 'examples_addons.7z'), '*']
    bldinstallercommon.do_execute_sub_process(cmd_args, addons_path, True)
    cmd_args = [os.path.join(SCRIPT_ROOT_DIR, 'winzipdir.sh'), os.path.join('..', 'examples_addons.zip'), '.' ]
    bldinstallercommon.do_execute_sub_process(cmd_args, addons_path, True)


    # Upload packages
    exec_path = SCRIPT_ROOT_DIR
    cmd_args = ['rsync', '-r', '../../src_pkg/single/', PKG_SERVER_ADDR + ':' + os.path.join(LATEST_DIR, 'src', 'single', '')]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = ['rsync', '-r', '../../src_pkg/submodules_tar/', PKG_SERVER_ADDR + ':' + os.path.join(LATEST_DIR, 'src', 'submodules', '')]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = ['rsync', '-r', '../../src_pkg/submodules_zip/', PKG_SERVER_ADDR + ':' + os.path.join(LATEST_DIR, 'src', 'submodules', '')]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)

    file_list = os.listdir(package_path)
    for file_name in file_list:
        if file_name.startswith("examples_addons."):
            cmd_args = ['scp', file_name, PKG_SERVER_ADDR + ':' + os.path.join(LATEST_DIR, 'src', 'examples_injection')]
            bldinstallercommon.do_execute_sub_process(cmd_args, package_path, True)
        if file_name.startswith("examples_essentials."):
            cmd_args = ['scp', file_name, PKG_SERVER_ADDR + ':' + os.path.join(LATEST_DIR, 'src', 'examples_injection')]
            bldinstallercommon.do_execute_sub_process(cmd_args, package_path, True)

###############################
# handle_icu_build
###############################
def handle_icu_build():
    dir_list = os.listdir(WORK_DIR)
    for file_name in dir_list:
        if file_name.startswith("icu"):
            cmd_args = 'rm -rf ' + file_name
            bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), WORK_DIR, True)

    cmd_args = 'rm -rf icu*'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), WORK_DIR, True)
    bldinstallercommon.create_dirs(os.path.join(WORK_DIR, 'icu_install'))
    exec_path = WORK_DIR
    cmd_args = ['wget', ICU_LIBS]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    dir_list = os.listdir(WORK_DIR)
    for file_name in dir_list:
        if file_name.startswith("icu4c"):
            cmd_args = ['tar', 'xvzf', file_name]
            bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    EXTRA_ENV['LFLAGS'] = '-Wl,-rpath,\$ORIGIN'
    cmd_args = ['./runConfigureICU', 'Linux', '--enable-rpath', '--prefix=' + os.path.join(WORK_DIR, 'icu_install')]
    exec_path = os.path.join(WORK_DIR, 'icu', 'source')
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True, EXTRA_ENV)
    cmd_args = ['make', '-j6']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True, EXTRA_ENV)
    cmd_args = ['make', 'install']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True, EXTRA_ENV)

    cmd_args = 'chrpath -r $ORIGIN libicuuc.so'
    exec_path = os.path.join(WORK_DIR, 'icu_install', 'lib')
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), exec_path, True, EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libicui18n.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), exec_path, True, EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libicudata.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), exec_path, True, EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libicuio.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), exec_path, True, EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libicule.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), exec_path, True, EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libiculx.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), exec_path, True, EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libicutest.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), exec_path, True, EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libicutu.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), exec_path, True, EXTRA_ENV)

    dir_list = os.listdir(WORK_DIR)
    for file_name in dir_list:
        if file_name.startswith("icu"):
            if file_name != 'icu_install':
                cmd_args = 'rm -rf ' + file_name
                bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), WORK_DIR, True)

###############################
# handle_qt_android_release_build
###############################
def handle_qt_android_release_build():
    cmd_args = ''
    script_path = os.path.join(SCRIPT_ROOT_DIR, 'mkqt5bld.py')
    source_url = SRC_URL+'/single/qt-everywhere-' + LICENSE + '-src-' + QT_FULL_VERSION
    configure_files_path = os.path.join(SCRIPT_ROOT_DIR, 'bld_config', '')

    qt_configure_options_file = os.environ['RELEASE_BUILD_QT_CONFIGURE_OPTIONS_FILE']
    android_ndk_host          = os.environ['ANDROID_NDK_HOST']
    android_toolchain_version = os.environ['ANDROID_TOOLCHAIN_VERSION']
    android_api_version       = os.environ['ANDROID_API_VERSION']
    android_sdk_home          = os.environ['ANDROID_SDK_HOME']
    android_ndk_home          = os.environ['ANDROID_NDK_HOME']
    if os.environ.get('EXTRA_QT_CONFIGURE_OPTIONS'):
        configure_extra_options = os.environ['EXTRA_QT_CONFIGURE_OPTIONS']
    else:
        configure_extra_options = ''
    extension = '.tar.gz'
    if bldinstallercommon.is_win_platform():
        extension = '.zip'

    cmd_args = ['python', '-u', script_path, '-u', source_url + extension]
    if bldinstallercommon.is_win_platform():
        cmd_args += ['-m', 'mingw32-make']
    cmd_args += ['-c', configure_files_path + qt_configure_options_file]
    cmd_args += ['--android-ndk-host=' + android_ndk_host]          # "linux-x86" or "linux-x86_64" or "windows" or "darwin-x86_64"
    cmd_args += ['--android-api-version=' + android_api_version]    # e.g. "android-10"
    cmd_args += ['--android-sdk-home=' + android_sdk_home]          # e.g. "/opt/android/sdk"
    cmd_args += ['--android-ndk-home=' + android_ndk_home]          # e.g. "/opt/android/ndk"
    if bldinstallercommon.is_linux_platform():
        cmd_args += ['--replace-rpath']
    cmd_args += ['-a', configure_extra_options + ' -prefix ' + os.path.join(WORK_DIR,  MAKE_INSTALL_PADDING)]
    cmd_args += [' -android-toolchain-version ' + android_toolchain_version]    # e.g. "4.8"

    if bldinstallercommon.is_linux_platform() or bldinstallercommon.is_mac_platform():
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
    elif bldinstallercommon.is_win_platform():
        exec_dir = os.getcwd()
        bldinstallercommon.do_execute_sub_process(cmd_args, exec_dir, True)


###############################
# handle_qt_ios_release_build
###############################
def handle_qt_ios_release_build():
    qt_configure_options_file = os.environ['RELEASE_BUILD_QT_CONFIGURE_OPTIONS_FILE']
    configure_extra_options   = os.environ['EXTRA_QT_CONFIGURE_OPTIONS']

    cmd_args = ''
    script_path = os.path.join(SCRIPT_ROOT_DIR, 'mkqt5bld.py')
    source_url = SRC_URL+'/single/qt-everywhere-' + LICENSE + '-src-' + QT_FULL_VERSION
    configure_files_path = os.path.join(SCRIPT_ROOT_DIR, 'bld_config', '')
    if bldinstallercommon.is_mac_platform():
        if TARGET_ENV.find("x64") >= 1:
            cmd_args = ['python', '-u', script_path, '-u', source_url + '.tar.gz', '-c', configure_files_path + qt_configure_options_file, '-a', configure_extra_options + ' -prefix ' + os.path.join(WORK_DIR, MAKE_INSTALL_PADDING)]
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)


###############################
# handle_qt_desktop_release_build
###############################
def handle_qt_desktop_release_build():
    # download pre-compiled ICU
    icu_lib_path = ''
    icu_include_path = ''
    if ICU_LIBS != '':
        handle_icu_build()

    # del os.environ['QTDIR']
    if ICU_LIBS != '':
        dir_list = os.listdir(WORK_DIR)
        print(dir_list)
        for file_name in dir_list:
            print(file_name)
            if file_name.startswith("icu"):
                print(file_name)
                if os.path.isdir(os.path.join(WORK_DIR, file_name)):
                    icu_lib_path = os.path.join(WORK_DIR, file_name, 'lib')
                    icu_include_path = os.path.join(WORK_DIR, file_name, 'include')
                    EXTRA_ENV['LD_LIBRARY_PATH'] = icu_lib_path

    ## let's build Qt
    # some common variables
    script_path = os.path.join(SCRIPT_ROOT_DIR, 'mkqt5bld.py')
    source_url = SRC_URL + '/single/qt-everywhere-' + LICENSE + '-src-' + QT_FULL_VERSION
    configure_files_path = os.path.join(SCRIPT_ROOT_DIR, 'bld_config', '')

    ## common cmd_args for all platforms
    # we need to change the extension to .zip on windows. os x and linux use .tar.gz for the source file (.zip includes configure.exe)
    extension = '.tar.gz'
    if bldinstallercommon.is_win_platform():
        extension = '.zip'
    # this args don't change, so we can re-use them
    cmd_args = ['python', '-u', script_path, '-u', source_url + extension, '--creator-dir=' + os.path.join(WORK_DIR, 'qt-creator')]
    # on windows we build with jom instead of make
    if bldinstallercommon.is_win_platform():
        cmd_args += ['-m', 'jom']

    # run mkqt5bld.py with the correct options according to the platform and license being used
    if bldinstallercommon.is_linux_platform():
        icu_lib_prefix_rpath = icu_lib_path + ' -I ' + icu_include_path + ' -prefix ' + os.path.join(WORK_DIR, MAKE_INSTALL_PADDING) + ' -R ' + os.path.join(WORK_DIR, MAKE_INSTALL_PADDING)
        cmd_args += ['-c', configure_files_path + 'configure_linux_' + LICENSE]
        if LICENSE == 'enterprise':
            cmd_args += ['-a', '-DQT_EVAL -L ' + icu_lib_prefix_rpath]
        elif LICENSE == 'opensource':
            cmd_args += ['-a', '-L ' + icu_lib_prefix_rpath]
        else:
            print('*** License unknown: {0}'.format(LICENSE))
            sys.exit(-1)
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True, EXTRA_ENV)
    elif bldinstallercommon.is_win_platform():
        exec_path = os.getcwd()
        if LICENSE == 'enterprise':
            if TARGET_ENV.find('opengl') >= 1 or TARGET_ENV.find('OpenGL') >= 1:
                cmd_args += ['-c', configure_files_path + 'configure_win_opengl_' + LICENSE]
            else:
                cmd_args += ['-c', configure_files_path + 'configure_win_' + LICENSE]
            cmd_args += ['-a', '-D QT_EVAL' + ' -prefix ' + os.path.join(WORK_DIR, MAKE_INSTALL_PADDING)]
        elif LICENSE == 'opensource':
            if TARGET_ENV.find('opengl') >=1 or TARGET_ENV.find('OpenGL') >= 1:
                cmd_args += ['-c', configure_files_path + 'configure_win_opengl_' + LICENSE]
            else:
                cmd_args += ['-c', configure_files_path + 'configure_win_' + LICENSE]
            cmd_args += ['-a', '-prefix ' + os.path.join(WORK_DIR, MAKE_INSTALL_PADDING)]
        else:
            print('*** License unknown: {0}'.format(LICENSE))
            sys.exit(-1)
        bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    elif bldinstallercommon.is_mac_platform():
        cmd_args += ['-c', configure_files_path + 'configure_mac_' + LICENSE, '-a', '-prefix ' + os.path.join(WORK_DIR, MAKE_INSTALL_PADDING)]
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)


###############################
# Validate build args for Enginio build
###############################
def validate_enginio_build_args(cmd_line_options):
    # check env variables
    if not os.environ.get('QT5_ENGINIO_SRC_URI'):
        print('*** Enginio build missing environment variable: {0}'.format('QT5_ENGINIO_SRC_URI'))
        sys.exit(-1)
    if not os.environ.get('QT5_ESSENTIALS_LIB_PACKAGE_URI'):
        print('*** Enginio build missing environment variable: {0}'.format('QT5_ESSENTIALS_LIB_PACKAGE_URI'))
        sys.exit(-1)
    if not os.environ.get('QT5_ADDONS_LIB_PACKAGE_URI'):
        print('*** Enginio build missing environment variable: {0}'.format('QT5_ADDONS_LIB_PACKAGE_URI'))
        sys.exit(-1)
    if bldinstallercommon.is_win_platform():
        if not os.environ.get('WINDOWS_BUILD_COMMAND'):
            print('*** Enginio build missing environment variable: {0}'.format('WINDOWS_BUILD_COMMAND'))
            sys.exit(-1)
        if not os.environ.get('WINDOWS_INSTALL_COMMAND'):
            print('*** Enginio build missing environment variable: {0}'.format('WINDOWS_INSTALL_COMMAND'))
            sys.exit(-1)
        if not os.environ.get('7Z_TOOL_PATH'):
            print('*** Enginio build missing environment variable: {0}'.format('7Z_TOOL_PATH'))
            sys.exit(-1)
        if not os.environ.get('GIT_TOOL_PATH'):
            print('*** Enginio build missing environment variable: {0}'.format('GIT_TOOL_PATH'))
            sys.exit(-1)
    if bldinstallercommon.is_mac_platform():
        if not os.environ.get('IFW_INSTALLERBASE_URI'):
            print('*** Enginio build missing environment variable: {0}'.format('IFW_INSTALLERBASE_URI'))
            sys.exit(-1)
        if not os.environ.get('MAC_INSTALL_COMMAND'):
            print('*** Enginio build missing environment variable: {0}'.format('MAC_INSTALL_COMMAND'))
            sys.exit(-1)
    # check command line arguments
    if not cmd_line_options.license:
        print('*** Enginio build missing command line argument: --license')
        sys.exit(-1)
    if not cmd_line_options.server:
        print('*** Enginio build missing command line argument: --server')
        sys.exit(-1)
    if not cmd_line_options.qt_version:
        print('*** Enginio build missing command line argument: --qt_version')
        sys.exit(-1)
    if not cmd_line_options.target_env:
        print('*** Enginio build missing command line argument: --target_env')
        sys.exit(-1)
    if not cmd_line_options.path:
        print('*** Enginio build missing command line argument: --path')
        sys.exit(-1)

    return True


###############################
# Handle Enginio release build
###############################
def handle_qt_enginio_release_build():
    script_path = os.path.join(SCRIPT_ROOT_DIR, 'bld_app.py')
    qt5_enginio_source_uri          = os.environ['QT5_ENGINIO_SRC_URI']
    qt5_essentials_lib_package_uri  = os.environ['QT5_ESSENTIALS_LIB_PACKAGE_URI']
    qt5_addons_lib_package_uri      = os.environ['QT5_ADDONS_LIB_PACKAGE_URI']
    icu7z_package                   = os.environ.get('ICU7Z')

    ## common cmd_args for all platforms
    # we need to change the extension to .zip on windows. os x and linux use .tar.gz for the source file (.zip includes configure.exe)
    extension = '.tar.gz'
    if bldinstallercommon.is_win_platform():
        extension = '.zip'
    # build command
    cmd_args = ['python', '-u', script_path, '--clean']
    cmd_args += ['--qt5path', 'qt5_package_dir']
    cmd_args += ['--qt5_essentials7z', os.environ['QT5_ESSENTIALS_LIB_PACKAGE_URI']]
    cmd_args += ['--qt5_addons7z', os.environ['QT5_ADDONS_LIB_PACKAGE_URI']]
    cmd_args += ['--application7z', os.environ['QT5_ENGINIO_SRC_URI']]
    if icu7z_package:
        cmd_args += ['--icu7z', icu7z_package]
    if bldinstallercommon.is_win_platform():
        cmd_args += ['--buildcommand', os.environ['WINDOWS_BUILD_COMMAND']]
        cmd_args += ['--installcommand', os.environ['WINDOWS_INSTALL_COMMAND']]
        cmd_args += ['--sevenzippath', os.environ['7Z_TOOL_PATH']]
        cmd_args += ['--gitpath', os.environ['GIT_TOOL_PATH']]
    if bldinstallercommon.is_mac_platform():
        cmd_args += ['--installerbase7z', os.environ['IFW_INSTALLERBASE_URI']]
        cmd_args += ['--installcommand', os.environ['MAC_INSTALL_COMMAND']]
    # execute build
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
    # copy 7z files to network drive
    remote_target_dir = PKG_SERVER_ADDR + ':' + LATEST_DIR + '/' + BIN_TARGET_DIRS[TARGET_ENV]
    if bldinstallercommon.is_win_platform():
        remote_target_dir += '/'
    remote_copy_archives(remote_target_dir, os.path.join(SCRIPT_ROOT_DIR, 'module_archives'))


###############################
# Remote copy files
###############################
def remote_copy_archives(remote_target, from_where_path):
    remote_copy_cmd = SCP_COMMAND
    if bldinstallercommon.is_mac_platform():
        remote_copy_cmd = 'rsync'
    dir_list = os.listdir(from_where_path)
    for file_name in dir_list:
        if file_name.endswith(".7z"):
            cmd_args = [remote_copy_cmd, file_name, remote_target]
            bldinstallercommon.do_execute_sub_process(cmd_args, from_where_path, True)


###############################
# handle_examples_injection
###############################
def handle_examples_injection():
    # Inject examples
    if bldinstallercommon.is_linux_platform():
        cmd_args = ['wget', SRC_URL + '/examples_injection/examples_essentials.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR + '/module_archives', True)
        cmd_args = ['wget', SRC_URL + '/examples_injection/examples_addons.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR + '/module_archives', True)
    elif bldinstallercommon.is_mac_platform():
        cmd_args = [CURL_COMMAND, '-O', SRC_URL + '/examples_injection/examples_essentials.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
        cmd_args = [CURL_COMMAND, '-O', SRC_URL + '/examples_injection/examples_addons.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
    else:
        if TARGET_ENV.find('x86') >=1:
            cmd_args = [CURL_COMMAND, '-O', SRC_URL + '/examples_injection/examples_essentials.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
            cmd_args = [CURL_COMMAND, '-O', SRC_URL + '/examples_injection/examples_addons.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
        else:
            cmd_args = [CURL_COMMAND, '-O', SRC_URL + '/examples_injection/examples_essentials.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
            cmd_args = [CURL_COMMAND, '-O', SRC_URL + '/examples_injection/examples_addons.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

    bldinstallercommon.create_dirs(os.path.join(WORK_DIR, 'module_archives', 'essentials'))
    bldinstallercommon.create_dirs(os.path.join(WORK_DIR, 'module_archives', 'addons'))

    if bldinstallercommon.is_win_platform():
        if TARGET_ENV.find('x86') >= 1:
            cmd_args = ['7z', 'x', 'qt5_essentials.7z', '-oessentials']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
            cmd_args = ['7z', 'x', 'examples_essentials.7z', os.path.join('-oessentials', 'examples'), '-y']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

            cmd_args = ['C:\Program Files\Git\\bin\\rm', 'qt5_essentials.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
            cmd_args = ['C:\Program Files\Git\\bin\\rm', 'examples_essentials.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

            cmd_args = ['7z', 'a', os.path.join('..', 'qt5_essentials.7z'), '*']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives/essentials'), True)

            cmd_args = ['7z', 'x', 'qt5_addons.7z', '-oaddons']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
            cmd_args = ['7z', 'x', 'examples_addons.7z', os.path.join('-oaddons', 'examples'), '-y']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

            cmd_args = ['C:\Program Files\Git\\bin\\rm', 'qt5_addons.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
            cmd_args = ['C:\Program Files\Git\\bin\\rm', 'examples_addons.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

            cmd_args = ['7z', 'a', os.path.join('..', 'qt5_addons.7z'), '*']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives/addons'), True)
        else:
            cmd_args = ['7z', 'x', 'qt5_essentials.7z', '-oessentials']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
            cmd_args = ['7z', 'x', 'examples_essentials.7z', os.path.join('-oessentials', 'examples'), '-y']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

            cmd_args = ['C:\Program Files (x86)\Git\\bin\\rm', 'qt5_essentials.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
            cmd_args = ['C:\Program Files (x86)\Git\\bin\\rm', 'examples_essentials.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

            cmd_args = ['7z', 'a', os.path.join('..', 'qt5_essentials.7z'), '*']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives/essentials'), True)

            cmd_args = ['7z', 'x', 'qt5_addons.7z', '-oaddons']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
            cmd_args = ['7z', 'x', 'examples_addons.7z', os.path.join('-oaddons', 'examples'), '-y']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

            cmd_args = ['C:\Program Files (x86)\Git\\bin\\rm', 'qt5_addons.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
            cmd_args = ['C:\Program Files (x86)\Git\\bin\\rm', 'examples_addons.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

            cmd_args = ['7z', 'a', os.path.join('..', 'qt5_addons.7z'), '*']
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives/addons'), True)
    else:
        cmd_args = ['7z', 'x', 'qt5_essentials.7z', '-oessentials']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
        cmd_args = ['7z', 'x', 'examples_essentials.7z', os.path.join('-oessentials', 'examples'), '-y']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

        cmd_args = ['rm', 'qt5_essentials.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
        cmd_args = ['rm', 'examples_essentials.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

        cmd_args = ['7z', 'a', os.path.join('..', 'qt5_essentials.7z'), '*']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives/essentials'), True)

        cmd_args = ['7z', 'x', 'qt5_addons.7z', '-oaddons']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
        cmd_args = ['7z', 'x', 'examples_addons.7z', os.path.join('-oaddons', 'examples'), '-y']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

        cmd_args = ['rm', 'qt5_addons.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
        cmd_args = ['rm', 'examples_addons.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

        cmd_args = ['7z', 'a', os.path.join('..', 'qt5_addons.7z'), '*']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives/addons'), True)


###############################
# handle_qt_release_build
###############################
def handle_qt_release_build():
    sanity_check_packaging_server()
    # Handle Android build
    if TARGET_ENV.find("Android") >= 1:
        handle_qt_android_release_build()
    elif TARGET_ENV.find("iOS") >= 1:
        handle_qt_ios_release_build()
    else:
        handle_qt_desktop_release_build()
        handle_examples_injection()

    # Create target directory
    create_remote_dirs(PKG_SERVER_ADDR, LATEST_DIR + '/' + BIN_TARGET_DIRS[TARGET_ENV])

    dir_list = os.listdir(os.path.join(WORK_DIR, 'module_archives'))
    print(dir_list)
    for file_name in dir_list:
        print(file_name)
        if file_name.endswith(".7z"):
            print(file_name)
            if bldinstallercommon.is_linux_platform():
                cmd_args = [SCP_COMMAND, os.path.join(WORK_DIR, 'module_archives', file_name), PKG_SERVER_ADDR + ':' + LATEST_DIR + '/' + BIN_TARGET_DIRS[TARGET_ENV]]
            elif bldinstallercommon.is_win_platform():
                cmd_args = [SCP_COMMAND, file_name, PKG_SERVER_ADDR + ':' + LATEST_DIR + '/' + BIN_TARGET_DIRS[TARGET_ENV] + '/']
            else:
                cmd_args = ['rsync', os.path.join(WORK_DIR, 'module_archives', file_name), PKG_SERVER_ADDR + ':' + LATEST_DIR + '/' + BIN_TARGET_DIRS[TARGET_ENV]]
            bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

    # TODO: Missing_modules.txt upload

###############################
# handle_qt_creator_build
###############################
def handle_qt_creator_build():
    sanity_check_packaging_server()

    # QT Creator directory
    dir_path = PATH + '/' + LICENSE + '/' + 'qtcreator'
    create_remote_dirs(PKG_SERVER_ADDR, dir_path + '/' + TIME_STAMP[:10] + '_' + BUILD_NUMBER)

    cmd_args = [SSH_COMMAND, PKG_SERVER_ADDR, 'ln -sfn', dir_path + '/' + TIME_STAMP[:10] + '_' + BUILD_NUMBER, dir_path + '/' + 'latest']
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)

    dir_path = PATH + LICENSE + '/qtcreator/latest'
    cmd_args = ['python', '-u', 'bld_qtcreator.py',
        '--clean',
        '--qt5path', os.path.normpath('../../qt5_install_dir'),
        '--qt5_essentials7z', SRC_URL + BIN_TARGET_DIRS[TARGET_ENV] + '/qt5_essentials.7z',
        '--qt5_addons7z', SRC_URL + BIN_TARGET_DIRS[TARGET_ENV] + '/qt5_addons.7z',
        '--versiondescription', '"' + QTCREATOR_VERSION_DESCRIPTION + '"']

    if LICENSE == 'enterprise':
        cmd_args.extend(['--additional_plugin', os.path.normpath(WORK_DIR + '/qmlprofiler'),
                         '--additional_plugin', os.path.normpath(WORK_DIR + '/qtquickdesigner')])

    if bldinstallercommon.is_linux_platform():
        cmd_args.extend(['--icu7z', ICU_LIBS])
        if TARGET_ENV.find('64') != -1:
            cmd_args.extend(['--installerbase7z', 'http://it-dl241-hki/packages/jenkins/' + LICENSE + '/ifw/1.4/installer-framework-build-linux-x64.7z'])
        else:
            cmd_args.extend(['--installerbase7z', 'http://it-dl241-hki/packages/jenkins/' + LICENSE + '/ifw/1.4/installer-framework-build-linux-x86.7z'])
    elif bldinstallercommon.is_mac_platform():
        cmd_args.extend(['--installcommand', 'make -j1',
                         '--installerbase7z', 'http://it-dl241-hki/packages/jenkins/' + LICENSE + '/ifw/1.4/installer-framework-build-mac-x64.7z',
                         '--keychain_unlock_script', '/Users/qt/unlock-keychain.sh'])
    else:
        cmd_args.extend(['--buildcommand', os.path.normpath('C:/Utils/jom/jom.exe'),
                         '--installcommand', os.path.normpath('C:/Program Files/Microsoft Visual Studio 10.0/VC/bin/nmake.exe'),
                         '--icu7z', ICU_LIBS,
                         '--sevenzippath', os.path.normpath('C:/Utils/sevenzip'),
                         '--gitpath', os.path.normpath('C:/Program Files/Git/bin'),
                         '--d3dcompiler7z', 'http://download.qt-project.org/development_releases/prebuilt/d3dcompiler/msvc2010/D3DCompiler_43-x86.dll.7z',
                         '--installerbase7z', 'http://it-dl241-hki/packages/jenkins/' + LICENSE + '/ifw/1.4/installer-framework-build-win-x86.7z',
                         '--environment_batch', os.path.normpath('C:/Program Files/Microsoft Visual Studio 10.0/VC/vcvarsall.bat'),
                         '--environment_batch_argument', 'x86'])

    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)

    if bldinstallercommon.is_mac_platform():
        lock_keychain()

    postfix = ''
    if QTCREATOR_VERSION:
        postfix = '-' + QTCREATOR_VERSION
    if bldinstallercommon.is_linux_platform():
        linux_bits = '32'
        linux_arch = 'x86'
        if TARGET_ENV.find('64') != -1:
            linux_bits = '64'
            linux_arch = 'x86_64'
        cmd_args = [SCP_COMMAND, 'qt-creator_build/qt-creator-installer-archive.7z',
            PKG_SERVER_ADDR + ':' + dir_path + '/qtcreator_linux_gcc_' + linux_bits + '_ubuntu1110.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
        cmd_args = [SCP_COMMAND, 'qt-creator_build/qt-creator.run',
            PKG_SERVER_ADDR + ':' + dir_path + '/qt-creator-linux-' + linux_arch + '-' + LICENSE + postfix + '.run']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
    elif bldinstallercommon.is_mac_platform():
        cmd_args = [SCP_COMMAND, 'qt-creator_build/qt-creator-installer-archive.7z',
            PKG_SERVER_ADDR + ':' + dir_path + '/qtcreator_mac_cocoa_10_7.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
        cmd_args = [SCP_COMMAND, 'qt-creator_build/qt-creator.dmg',
            PKG_SERVER_ADDR + ':' + dir_path + '/qt-creator-mac-' + LICENSE + postfix + '.dmg']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
        cmd_args = [SCP_COMMAND, 'qt-creator_build/qt-creator-installer.dmg',
            PKG_SERVER_ADDR + ':' + dir_path + '/qt-creator-mac-' + LICENSE + postfix + '-installer.dmg']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
    else:
        cmd_args = [SCP_COMMAND, 'qt-creator_build/qt-creator-installer-archive.7z',
            PKG_SERVER_ADDR + ':' + dir_path + '/qtcreator_windows_vs2010_32.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
        sign_windows_executable('qt-creator_build/qt-creator.exe', WORK_DIR, True)
        cmd_args = [SCP_COMMAND, 'qt-creator_build/qt-creator.exe', PKG_SERVER_ADDR + ':' + dir_path + '/qt-creator-windows-' + LICENSE + postfix + '.exe']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)

    #TODO: Check qt-creator checkout!


###############################
# handle_offline_installer_build
###############################
def handle_offline_installer_build():
    handle_installer_build(True)


###############################
# handle_online_installer_build
###############################
def handle_online_installer_build():
    handle_installer_build(False)


###############################
# generic handle installer build
###############################
def handle_installer_build(offline_installer_build):
    sanity_check_packaging_server()
    conf_file = os.environ['RELEASE_BUILD_CONF_FILE']
    if not os.path.exists(conf_file):
        print('*** The given file does not exist: {0}'.format(conf_file))
        sys.exit(-1)
    branch = 'release' # TODO
    platform = PLATFORM
    if TARGET_ENV.find('64') != -1:
        arch = 'x64'
    else:
        arch = 'x86'
    # Internal server address
    packages_base_url = os.environ['PKG_SERVER_URL']
    temp_path = ''
    # determine local installer output directory
    installer_output_dir = os.path.join(SCRIPT_ROOT_DIR, 'installer_output')
    # (1) create all installers for this host
    if offline_installer_build:
        release_build_handler.handle_offline_installer_build(conf_file, LICENSE, branch, platform, arch, packages_base_url)
        temp_path = '/offline_installers/'
    else:
        release_build_handler.handle_online_installer_build(conf_file, LICENSE, branch, platform, arch, packages_base_url)
        temp_path = '/online_installers/'
    # (2) copy all installers from 'installer_output_dir' into network disk
    # Crete remote directories
    dest_dir = PATH + '/' + LICENSE + temp_path + TIME_STAMP[:10] + '_' + BUILD_NUMBER
    latest_dir = PATH + '/' + LICENSE + temp_path + 'latest'
    create_remote_dirs(PKG_SERVER_ADDR, dest_dir)
    # Create remote dirs in Mirror Brain
    if LICENSE == 'opensource':
        # Mirror Brain server address and path
        ext_server_base_url  = os.environ['EXT_SERVER_BASE_URL']
        ext_server_base_path = os.environ['EXT_SERVER_BASE_PATH']
        # mirror brain directories
        ext_dest_dir = ext_server_base_path + '/snapshots/qt/' + QT_VERSION[:3] + '/' + QT_FULL_VERSION + '/' + TIME_STAMP[:10] + '_' + BUILD_NUMBER
        cmd_args_mkdir_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
        cmd_args_mkdir_ext = cmd_args_mkdir_pkg + ['ssh', ext_server_base_url, 'mkdir -p', ext_dest_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_ext, SCRIPT_ROOT_DIR, True)

    installer_name = ''
    installer_name_base = ''
    dir_list = os.listdir(installer_output_dir)
    if bldinstallercommon.is_linux_platform():
        for file_name in dir_list:
            if file_name.endswith(".run"):
                installer_name = file_name
                installer_name_base = os.path.splitext(file_name)[0]
                installer_name_final = installer_name_base + '_' + TIME_STAMP + '-' + BUILD_NUMBER + '.run'
                # copy installer to internal server
                cmd_args = [SCP_COMMAND, installer_name, PKG_SERVER_ADDR + ':' + dest_dir + '/' + installer_name_final]
                bldinstallercommon.do_execute_sub_process(cmd_args, installer_output_dir, True)
                # copy installer to mirror brain server
                if LICENSE == 'opensource':
                    cmd_args_copy_to_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
                    cmd_args_copy_to_ext = cmd_args_copy_to_pkg + ['scp', dest_dir + '/' + installer_name_final, ext_server_base_url + ':' + ext_dest_dir  + '/' + installer_name_final]
                    bldinstallercommon.do_execute_sub_process(cmd_args_copy_to_ext, installer_output_dir, True)
    elif bldinstallercommon.is_mac_platform():
        unlock_keychain()
        for file_name in dir_list:
            if file_name.endswith(".dmg"):
                installer_name = file_name
                installer_name_base = os.path.splitext(file_name)[0]
                installer_name_final = installer_name_base + '_' + TIME_STAMP + '-' + BUILD_NUMBER + '.dmg'
                # sign executable
                sign_mac_executable(installer_name_base + '.app', installer_output_dir, True)
                cmd_args = ['hdiutil', 'create', '-srcfolder', os.path.join(installer_output_dir, installer_name_base) + '.app', '-volname', installer_name_base, '-format', 'UDBZ', os.path.join(installer_output_dir, installer_name_base) + '.dmg', '-ov', '-scrub', '-size', '2g']
                bldinstallercommon.do_execute_sub_process(cmd_args, installer_output_dir, True)
                # copy installer to internal server
                cmd_args = [SCP_COMMAND, installer_name, PKG_SERVER_ADDR + ':' + dest_dir + '/' + installer_name_final]
                bldinstallercommon.do_execute_sub_process(cmd_args, installer_output_dir, True)
                # copy installer to mirror brain server
                if LICENSE == 'opensource':
                    cmd_args_copy_to_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
                    cmd_args_copy_to_ext = cmd_args_copy_to_pkg + ['scp', dest_dir + '/' + installer_name_final, ext_server_base_url + ':' + ext_dest_dir + '/' + installer_name_final]
                    bldinstallercommon.do_execute_sub_process(cmd_args_copy_to_ext, installer_output_dir, True)
        lock_keychain()
    else:
        for file_name in dir_list:
            if file_name.endswith(".exe"):
                installer_name = file_name
                installer_name_base = os.path.splitext(file_name)[0]
                installer_name_final = installer_name_base + '_' + TIME_STAMP + '-' + BUILD_NUMBER + '.exe'
                sign_windows_executable(installer_name, installer_output_dir, True)
                # copy installer to internal server
                cmd_args = [SCP_COMMAND, installer_name, PKG_SERVER_ADDR + ':' + dest_dir + '/' + installer_name_final]
                bldinstallercommon.do_execute_sub_process(cmd_args, installer_output_dir, True)
                # copy installer to mirror brain server
                if LICENSE == 'opensource':
                    cmd_args_copy_to_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
                    cmd_args_copy_to_ext = cmd_args_copy_to_pkg + ['scp', dest_dir + '/' + installer_name_final, ext_server_base_url + ':' + ext_dest_dir + '/' + installer_name_final]
                    bldinstallercommon.do_execute_sub_process(cmd_args_copy_to_ext, installer_output_dir, True)
    #Update latest link
    cmd_args = [SSH_COMMAND, PKG_SERVER_ADDR, 'ln -sfn', dest_dir, latest_dir]
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
    # copy rta description file(s)
    for file_name in dir_list:
        if file_name.endswith('.txt'):
            cmd_args = [SCP_COMMAND, file_name, PKG_SERVER_ADDR + ':' + dest_dir + '/' + file_name]
            bldinstallercommon.do_execute_sub_process(cmd_args, installer_output_dir, True)
    # (3) trigger rta cases
    trigger_rta(installer_output_dir)


###############################
# Trigger RTA cases
###############################
def trigger_rta(installer_output_dir):
    # obtain RTA server base url
    if not os.environ.get('RTA_SERVER_BASE_URL'):
        print('*** Error - RTA server base url is not defined. Unable to proceed!')
        sys.exit(-1)
    rta_server_base_url = os.environ['RTA_SERVER_BASE_URL']
    if not (rta_server_base_url.endswith('/')):
        rta_server_base_url += '/'

    if not os.path.isdir(installer_output_dir):
        print('*** Error - Given installer_output_dir does not exist: {0}'.format(installer_output_dir))
        sys.exit(-1)
    dir_list = os.listdir(installer_output_dir)
    matching = [s for s in dir_list if 'rta_description_file' in s]
    # sanity check, should contain only one rta test case file
    if len(matching) != 1:
        print('*** Warning - Given installer_output_dir contained {0} rta description files?'.format(len(matching)))
        return
    rta_file = os.path.join(installer_output_dir, matching[0])
    f = open(rta_file)
    for line in iter(f):
        line_split = line.split(' ')
        if len(line_split) != 2:
            print('*** Error - Invalid format in rta description file {0}, line: {1}'.format(rta_file, line))
            sys.exit(-1)
        rta_keys = line_split[1].split(',')
        for item in rta_keys:
            url = rta_server_base_url + item.rstrip() + '/build?token=JENKINS_SQUISH'
            print('Triggering RTA case: {0}'.format(url))
            urllib.urlretrieve(url)
    f.close()


#def handle_online_installer_build(license, ....):


def handle_online_repository_build():
    conf_file = os.environ['RELEASE_BUILD_CONF_FILE']
    if not os.path.exists(conf_file):
        print('*** The given file does not exist: {0}'.format(conf_file))
        sys.exit(-1)
    if TARGET_ENV.find('64') != -1:
        arch = 'x64'
    else:
        arch = 'x86'
    packages_base_url = os.environ['PKG_SERVER_URL']
    # do we also update production repository?
    update_production_repo = False
    if os.environ.get('DO_UPDATE_PRODUCTION_REPOSITORY'):
        update = os.environ['DO_UPDATE_PRODUCTION_REPOSITORY']
        if update.lower() in ['yes', 'true', '1']:
            update_production_repo = True
    release_build_handler.handle_repo_build(conf_file, LICENSE, 'release', PLATFORM, arch, packages_base_url, update_production_repo)


###############################
# copy_license_checkers
###############################
def copy_license_checkers():
    sanity_check_packaging_server()
    exec_path = os.path.join(WORK_DIR, 'qt5', 'qtbase', 'bin')
    cmd_args = [SCP_COMMAND, PKG_SERVER_ADDR + ':' + os.path.join(LATEST_DIR, 'src', 'licheck', 'licheck.exe'), '.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = [SCP_COMMAND, PKG_SERVER_ADDR + ':' + os.path.join(LATEST_DIR, 'src', 'licheck', 'licheck32'), '.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = [SCP_COMMAND, PKG_SERVER_ADDR + ':' + os.path.join(LATEST_DIR, 'src', 'licheck', 'licheck64'), '.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = [SCP_COMMAND, PKG_SERVER_ADDR + ':' + os.path.join(LATEST_DIR, 'src', 'licheck', 'licheck_mac'), '.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    #change permissions
    os.chdir(os.path.join(WORK_DIR, 'qt5', 'qtbase', 'bin'))
    os.system('chmod u+x licheck32')
    os.system('chmod u+x licheck64')
    os.system('chmod u+x licheck_mac')

    cmd_args = ['git', 'add', '.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = ['git', 'commit', '-m', '"Add license checkers into enterprise source package"']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    exec_path = os.path.join(WORK_DIR, 'qt5')
    cmd_args = ['git', 'add', '.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = ['git', 'commit', '-m', '"Add license checkers into enterprise source package"']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)

    os.chdir(SCRIPT_ROOT_DIR)


###############################
# publish_src_packages
###############################
def publish_src_packages():
    # Mirror Brain server address and path
    ext_server_base_url  = os.environ['EXT_SERVER_BASE_URL']
    ext_server_base_path = os.environ['EXT_SERVER_BASE_PATH']

    ext_dest_dir = ext_server_base_path + '/snapshots/qt/' + QT_VERSION[:3] + '/' + QT_FULL_VERSION + '/' + TIME_STAMP[:10] + '_' + BUILD_NUMBER

    # copy source packages to public server
    if LICENSE == 'opensource':
        # create source directories
        cmd_args_mkdir_src_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
        cmd_args_mkdir_src_ext = cmd_args_mkdir_src_pkg + ['ssh', ext_server_base_url, 'mkdir', '-p', ext_dest_dir + '/' + 'single']
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_src_ext, SCRIPT_ROOT_DIR, True)
        cmd_args_mkdir_src_ext = cmd_args_mkdir_src_pkg + ['ssh', ext_server_base_url, 'mkdir', '-p', ext_dest_dir + '/' + 'submodules']
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_src_ext, SCRIPT_ROOT_DIR, True)
        # copy the source packages to the remove directory
        cmd_args_copy_src_to_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
        cmd_args_copy_src_to_ext = cmd_args_copy_src_to_pkg + ['scp', '-r', LATEST_DIR + '/' + 'src/single/*', ext_server_base_url + ':' + ext_dest_dir + '/' + 'single']
        bldinstallercommon.do_execute_sub_process(cmd_args_copy_src_to_ext, SCRIPT_ROOT_DIR, True)
        cmd_args_copy_src_to_ext = cmd_args_copy_src_to_pkg + ['scp', '-r', LATEST_DIR + '/' + 'src/submodules/*', ext_server_base_url + ':' + ext_dest_dir + '/' + 'submodules']
        bldinstallercommon.do_execute_sub_process(cmd_args_copy_src_to_ext, SCRIPT_ROOT_DIR, True)


###############################
# create_remote_dirs
###############################
def create_remote_dirs(server, dir_path):
    cmd_args = [SSH_COMMAND, '-t', '-t', server, 'mkdir -p', dir_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


###############################
# sanity check command line options
###############################
def sanity_check_options(options):
    if not options.command in ['init', 'build_src', 'build_bin', 'build_enginio', 'offline_installer', 'ifw', 'build_creator', 'repo_build', 'online_installer', 'publish_src_packages']:
        return False
    if options.command == 'repo_build':
        if len(sys.argv) < 4:
            return False
    elif options.command == 'online_installer':
        if len(sys.argv) < 4:
            print('*** Insufficient arguments for online installer build!')
            return False
    elif options.command == 'build_enginio':
        return validate_enginio_build_args(options)
    else:
        if len(sys.argv) < 15:
            return False
    return True


###############################
# parse_cmd_line
###############################
def parse_cmd_line():
    global COMMAND
    global LICENSE
    global QT_VERSION
    global TIME_STAMP
    global BUILD_NUMBER
    global PKG_SERVER_ADDR
    global PATH
    global TARGET_ENV
    global ICU_LIBS
    global SRC_URL
    global REMOTE_DIR
    global LATEST_DIR
    global PLATFORM
    global QT_VERSION_TAG
    global QT_FULL_VERSION
    global QTCREATOR_VERSION
    global QTCREATOR_VERSION_DESCRIPTION

    setup_option_parser()
    arg_count = len(sys.argv)
    if arg_count < 2:
        OPTION_PARSER.print_help()
        sys.exit(-1)

    (options, args) = OPTION_PARSER.parse_args()
    COMMAND = options.command
    if (sanity_check_options(options)):
        COMMAND           = options.command
        LICENSE           = options.license
        QT_VERSION        = options.qt_version
        TIME_STAMP        = options.time_stamp
        BUILD_NUMBER      = options.build_number
        PKG_SERVER_ADDR   = options.server
        PATH              = options.path
        TARGET_ENV        = options.target_env
        ICU_LIBS          = options.icu_libs
        SRC_URL           = options.src_url
        QT_VERSION_TAG    = options.version_tag
        QTCREATOR_VERSION = options.qtcreator_version
        QT_FULL_VERSION   = QT_VERSION
        if QT_VERSION_TAG:
            QT_FULL_VERSION += '-' + QT_VERSION_TAG
        if options.qtcreator_set_description:
            QTCREATOR_VERSION_DESCRIPTION = QTCREATOR_VERSION
        else:
            QTCREATOR_VERSION_DESCRIPTION = ''
        REMOTE_DIR      = PATH + '/' + LICENSE + '/' + 'qt' + '/' + QT_VERSION + '/' + TIME_STAMP + '-' + BUILD_NUMBER
        LATEST_DIR      = PATH + '/' + LICENSE + '/' + 'qt' + '/' + QT_VERSION + '/' + 'latest'
    else:
        OPTION_PARSER.print_help()
        sys.exit(-1)
    if not any(LICENSE in s for s in ['opensource', 'enterprise']):
        print('*** License unknown: {0}'.format(LICENSE))
        sys.exit(-1)
    if bldinstallercommon.is_linux_platform():
        PLATFORM = 'linux'
    elif bldinstallercommon.is_mac_platform():
        PLATFORM = 'mac'
    else:
        PLATFORM = 'windows'

    return True


##############################################################
# Setup Option Parser
##############################################################
def setup_option_parser():
    global OPTION_PARSER
    OPTION_PARSER = OptionParser(option_class=MultipleOption)

    OPTION_PARSER.add_option("-c", "--command",
                      action="store", type="string", dest="command", default="",
                      help="command to be executed: e.g. -c init")
    OPTION_PARSER.add_option("-l", "--license",
                      action="store", type="string", dest="license", default="",
                      help="license type: enterprise or opensource")
    OPTION_PARSER.add_option("-v", "--qt_version",
                      action="store", type="string", dest="qt_version", default="",
                      help="Qt version e.g. 5.0.2")
    OPTION_PARSER.add_option("-t", "--time_stamp",
                      action="store", type="string", dest="time_stamp", default="",
                      help="Jenkins build time stamp")
    OPTION_PARSER.add_option("-b", "--build_number",
                      action="store", type="string", dest="build_number", default="",
                      help="Jenkins build number")
    OPTION_PARSER.add_option("-s", "--server",
                      action="store", type="string", dest="server", default="",
                      help="Upload server e.g. <user>@<host>")
    OPTION_PARSER.add_option("-p", "--path",
                      action="store", type="string", dest="path", default="",
                      help="Path on server")
    OPTION_PARSER.add_option("-e", "--target_env",
                      action="store", type="string", dest="target_env", default="",
                      help="Target environment: Linux, Linux_64, mac, win")
    OPTION_PARSER.add_option("-i", "--icu_libs",
                      action="store", type="string", dest="icu_libs", default="",
                      help="Url for pre-compiled icu libraries")
    OPTION_PARSER.add_option("-u", "--src_url",
                      action="store", type="string", dest="src_url", default="",
                      help="Url for source code")
    OPTION_PARSER.add_option("--version-tag",
                      action="store", type="string", dest="version_tag", default="",
                      help="Version tag e.g. alpha, beta, rc1")
    OPTION_PARSER.add_option("--qtcreator-version",
                      action="store", type="string", dest="qtcreator_version", default="",
                      help="Qt Creator version, e.g. 3.0.0-rc, used in file names and for --qtcreator-set-description")
    OPTION_PARSER.add_option("--qtcreator-set-description",
                      action="store_true", dest="qtcreator_set_description", default=False,
                      help="Sets Qt Creator's version description to the value given in --qtcreator-version")


##############################################################
# Initialize Environment
##############################################################
def init_env():
    global MAKE_INSTALL_PADDING
    global CURL_COMMAND
    global SSH_COMMAND
    global SCP_COMMAND

    # prefix build
    MAKE_INSTALL_PADDING = 'PADDING' if bldinstallercommon.is_win_platform() else '______________________________PADDING______________________________'
    # external commands
    CURL_COMMAND         = '%CURL%'  if bldinstallercommon.is_win_platform() else 'curl'
    SSH_COMMAND          = '%SSH%'   if bldinstallercommon.is_win_platform() else 'ssh'
    SCP_COMMAND          = '%SCP%'   if bldinstallercommon.is_win_platform() else 'scp'

###############################
# Main
###############################
def main():
    bldinstallercommon.init_common_module(SCRIPT_ROOT_DIR)

    init_env()

    parse_cmd_line()
    if COMMAND == 'init':
        init_qt_build_cycle()
    elif COMMAND == 'build_src':
        if LICENSE == 'opensource':
            init_qt_build_cycle()
        handle_qt_src_package_build()
    elif COMMAND == 'build_bin':
        handle_qt_release_build()
    elif COMMAND == 'build_enginio':
        handle_qt_enginio_release_build()
    elif COMMAND == 'ifw':
        handle_ifw_build()
    elif COMMAND == 'build_creator':
        handle_qt_creator_build()
    elif COMMAND == 'repo_build':
        handle_online_repository_build()
    elif COMMAND == 'offline_installer':
        handle_offline_installer_build()
    elif COMMAND == 'online_installer':
        handle_online_installer_build()
    elif COMMAND == 'publish_src_packages':
        publish_src_packages()
    else:
        print('Unsupported command')

if __name__ == "__main__":
    main()

