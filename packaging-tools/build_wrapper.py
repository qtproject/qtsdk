#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2014 Digia Plc and/or its subsidiary(-ies).
## Copyright (C) 2014 BlackBerry Limited. All rights reserved.
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
import re
import platform
from time import gmtime, strftime
import urllib
import mkqt5bld
import build_doc
import bld_ifw_tools
from bld_ifw_tools import IfwOptions

from optparse import OptionParser, Option

import bldinstallercommon
import release_build_handler
import bld_icu_tools
import pkg_constants
import random
from pkg_constants import ICU_BUILD_OUTPUT_DIR
import imp


# ----------------------------------------------------------------------
# external commands
CURL_COMMAND                = ''
RM_COMMAND                  = ''
SSH_COMMAND                 = ''
SCP_COMMAND                 = ''

# ----------------------------------------------------------------------
BUILD_TIMESTAMP             = strftime('%Y-%m-%d', gmtime())
SCRIPT_ROOT_DIR             = os.path.dirname(os.path.realpath(__file__))
REPO_OUTPUT_DIR             = os.path.normpath(os.path.join(SCRIPT_ROOT_DIR, 'repository'))
WORK_DIR                    = os.path.join(os.environ['PKG_NODE_ROOT'], 'build')
OPTION_PARSER               = 0
QTCREATOR_VERSION           = ''
QTCREATOR_VERSION_DESCRIPTION = ''
PLATFORM                    = ''
SRC_DEST_DIRS               = ['src', 'src/submodules', 'src/doc', 'src/single', 'src/examples_injection']
BIN_DEST_DIRS               = ['android_armv5', 'android_armv7', 'android_x86', 'linux_gcc_64_rhel66', 'linux_gcc_32_rhel66', 'ios', 'mac_x64', 'windows_mingw492_x86', 'windows_vs2013_winrt_x64', 'winphone81', 'windows_vs2013_32', 'windows_vs2013_64', 'windows_vs2012_32', 'windows_vs2010_32', 'src/doc']
EXTRA_MODULE_DEST_DIRS      = ['src', 'doc', 'examples']
QT5_DOCS_ARCHIVE_NAME       = 'qt5_docs.7z'
BIN_TARGET_DIRS             = {} # dictionary populated based on the /packaging-tools/releases/release-<version>
EXTRA_ENV                   = dict(os.environ)
MAKE_INSTALL_PADDING        = ''
BUILD_META_INFO_FILE        = 'releases/build-meta'




###########################################
# Environment variable combining
###########################################
def combine_env_variable(a, b):
    if platform.system().lower().startswith('win'):
        return a + ';' + b
    else :
        return a + ':' + b

def combine_environment_dicts(a, b, op=combine_env_variable):
    return dict(a.items() + b.items() +
                [(k, combine_env_variable(a[k], b[k])) for k in set(b) & set(a)])


###########################################
# Define possible commands for this script
###########################################
class BldCommand:
    init_build_cycle                        = 'init'
    init_qtcreator_build_cycle              = 'init_qtcreator'
    execute_configure_exe_bld               = 'configure_exe'
    init_extra_module_build_cycle_src       = 'init_app_src'
    init_extra_module_build_cycle_binary    = 'init_app_binary'
    execute_qt5_src_pkg                     = 'build_src'
    execute_qt5_bin_bld                     = 'build_bin'
    execute_extra_module_build_cycle_src    = 'build_qt5_app_src'
    execute_extra_module_build_cycle_binary = 'build_qt5_app'
    execute_ifw_bld                         = 'ifw'
    execute_creator_bld                     = 'build_creator'
    execute_repo_bld                        = 'repo_build'
    execute_offline_inst_bld                = 'offline_installer'
    execute_online_inst_bld                 = 'online_installer'
    publish_qt5_src_pkg                     = 'publish_src_packages'
    publish_icu_pkg                         = 'publish_icu_packages'
    init_icu_bld                            = 'init_icu_bld'
    execute_icu_bld                         = 'icu_bld'
    execute_licheck_bld                     = 'licheck_bld'

    ##############################################################
    # init
    ##############################################################
    def __init__(self, options):
        self.options = options

         # license
        self.license = options.license
        if not self.license:
            self.license = os.environ.get('LICENSE')
        if not any(self.license in s for s in ['opensource', 'enterprise']):
            print('*** License unknown: {0}'.format(LICENSE))
            sys.exit(-1)
        # cfg
        self.target_env = options.target_env
        if not self.target_env:
            self.target_env = os.environ.get('cfg')
        # unique build number specifiers
        self.build_number = options.build_number
        if not self.build_number:
            self.build_number = os.environ.get('BUILD_NUMBER')
        self.build_time_stamp = options.time_stamp
        if not self.build_time_stamp:
            self.build_time_stamp = os.environ.get('BUILD_ID')
        # package storage server (ssh access)
        self.pkg_server_addr = options.server # -s
        if not self.pkg_server_addr:
            self.pkg_server_addr = os.environ.get('PACKAGE_STORAGE_SERVER_USER') + '@'
            self.pkg_server_addr += os.environ.get('PACKAGE_STORAGE_SERVER')
        # package storage (http access)
        self.pkg_server_addr_http = os.environ.get('PACKAGE_STORAGE_SERVER_PATH_HTTP')
        # server base path
        self.path = options.path

        # snapshot server
        self.snapshot_server = options.snapshot_server
        self.snapshot_path = options.snapshot_path

        # build command "enum"
        self.command = options.command

        # release description file
        self.release_description_file = os.getenv('RELEASE_DESCRIPTION_FILE', '')
        if os.path.exists(self.release_description_file):
            print('Using release description file: {0}'.format(self.release_description_file))
            self.parse_release_description_file()
            qt_pkg_url = self.pkg_server_addr_http + '/' + self.license
            qt_pkg_url +=  '/qt/' + self.version + '/latest/'
            self.qt_pkg_url_base = qt_pkg_url
            qt_pkg_url += 'src/'
            self.qt_src_url_base = qt_pkg_url
            qt_pkg_url += 'single/qt-everywhere-' + self.license + '-src-' + self.full_version
            qt_pkg_url += '.zip' if bldinstallercommon.is_win_platform() else '.tar.gz'
            self.qt_src_url = qt_pkg_url
        else:
            print('Release description file not used for this build')

        self.custom_build = options.custom_build

        # icu related
        self.icu_libs = os.environ.get('ICU_LIBS')
        self.icu_version = os.environ.get('ICU_VERSION')
        self.icu_src_pkg_url = os.environ.get('ICU_SRC_PKG_URL')

        # openssl
        self.openssl_libs = options.openssl_libs

        # qtcreator specific
        self.qtcreator_version = options.qtcreator_version
        self.qtcreator_version_description = options.qtcreator_version_description

        # define LATEST directories for extra module src & doc & examples packages
        self.remote_extra_module_dir = self.path + '/' + self.license + '/'
        self.latest_extra_module_dir = self.path + '/' + self.license + '/'
        # define LATEST directories for extra module binary packages
        self.remote_extra_module_binary_dir = self.path + '/' + self.license + '/'
        self.latest_extra_module_binary_dir = self.path + '/' + self.license + '/'

        # create output directories for extra module build
        if os.environ.get('APPLICATION_NAME'):
            self.package_storage_server_user = os.environ['PACKAGE_STORAGE_SERVER_USER']
            self.package_storage_server = os.environ['PACKAGE_STORAGE_SERVER']
            self.package_storage_server_base_dir = os.environ['PACKAGE_STORAGE_SERVER_BASE_DIR']
            # create directories for extra module src files
            self.app_name = os.environ['APPLICATION_NAME']
            self.app_version = os.environ['APPLICATION_VERSION']
            self.remote_extra_module_dir += self.app_name + '/' + self.app_version + '/' + self.build_time_stamp + '-' + self.build_number
            self.latest_extra_module_dir += self.app_name + '/' + self.app_version + '/' + 'latest'
            # create directories for extra module binaries
            # QT_VERSION_MINOR indicates that this is a binary build
            if os.environ.get('QT_VERSION_MINOR'):
                self.remote_extra_module_binary_dir += self.app_name + '/' + self.app_version + '/' + os.environ.get('QT_VERSION_MINOR') + '/' + self.build_time_stamp + '-' +  os.environ.get('BUILD_NUMBER')
                self.latest_extra_module_binary_dir += self.app_name + '/' + self.app_version + '/' + os.environ.get('QT_VERSION_MINOR') + '/' + 'latest'


    ###########################################
    # Validate the given command
    ###########################################
    def is_valid_cmd(self):
        commands = [self.init_build_cycle]
        commands += [self.init_qtcreator_build_cycle]
        commands += [self.init_extra_module_build_cycle_src]
        commands += [self.init_extra_module_build_cycle_binary]
        commands += [self.execute_qt5_src_pkg]
        commands += [self.execute_qt5_bin_bld]
        commands += [self.execute_extra_module_build_cycle_src]
        commands += [self.execute_extra_module_build_cycle_binary]
        commands += [self.execute_ifw_bld]
        commands += [self.execute_creator_bld]
        commands += [self.execute_repo_bld]
        commands += [self.execute_offline_inst_bld]
        commands += [self.execute_online_inst_bld]
        commands += [self.publish_qt5_src_pkg]
        commands += [self.execute_configure_exe_bld]
        commands += [self.publish_icu_pkg]
        commands += [self.init_icu_bld]
        commands += [self.execute_icu_bld]
        commands += [self.execute_licheck_bld]
        if self.options.command not in commands:
            return False
        return True

    ###########################################
    # Validate generic build arguments
    ###########################################
    def validate_bld_args(self):
        cmd = self.options.command
        if not cmd:
            print('*** Build command not given? Aborting....')
            return False
        if not self.is_valid_cmd():
            print('*** The given build command enum is invalid: {0}'.format(self.options.command))

        if cmd == self.execute_ifw_bld:
            if not self.options.server:
                print('*** Package storage server not defined i.e. where the build artifacts will be saved.')
                return False
            if not self.options.path:
                print('*** Base path on package storage server not defined i.e. where the build artifacts will be saved.')
                return False
            if not self.options.target_env:
                print('*** Target environment not defined.')
                return False
            if not self.options.time_stamp:
                print('*** Build time stamp not defined.')
                return False
            if not self.options.build_number:
                print('*** Build number not defined.')
                return False
        elif cmd == self.execute_repo_bld:
            if len(sys.argv) < 4:
                print('*** Insufficient arguments for repo build!')
                print('*** You must at least do: build_wrapper.py -c repo_build -license <LICENSE>')
                return False
        elif cmd == self.execute_online_inst_bld:
            if len(sys.argv) < 4:
                print('*** Insufficient arguments for online installer build!')
                return False
        # Extra Module specific validations
        elif cmd == self.init_extra_module_build_cycle_src:
            return self.validate_init_extra_module_build_cycle_src_args()
        elif cmd == self.init_extra_module_build_cycle_binary:
            return self.validate_init_extra_module_build_cycle_binary_args()
        elif cmd == self.execute_extra_module_build_cycle_src:
            return self.validate_execute_extra_module_build_cycle_src_args()
        elif cmd == self.execute_extra_module_build_cycle_binary:
            return self.validate_execute_extra_module_build_cycle_binary_args()
        # Qt Creator
        elif cmd == self.init_qtcreator_build_cycle:
            return self.validate_init_qtcreator_build_cycle_args()
        elif self.options.command == self.execute_configure_exe_bld:
            if len(sys.argv) < 7:
                return False
        return True


    #######################################################
    # Validate build args for Qt5 Extra Module src init
    #######################################################
    def validate_init_extra_module_build_cycle_src_args(self):
        print('Validating build args for Qt5 Extra Module src init')
        print(self.options)
        if not os.environ.get('LICENSE'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('LICENSE'))
        return True

    #######################################################
    # Validate build args for Qt5 Extra Module binary init
    #######################################################
    def validate_init_extra_module_build_cycle_binary_args(self):
        print('Validating build args for Qt5 Extra Module binary init')
        print(self.options)
        if not os.environ.get('LICENSE'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('LICENSE'))
        return True

    #######################################################
    # Validate build args for Qt5 Extra Module Src build
    #######################################################
    def validate_execute_extra_module_build_cycle_src_args(self):
        print('Validating build args for Qt5 Extra Module Src build')
        print(self.options)
        if not os.environ.get('LICENSE'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('LICENSE'))
        if not os.environ.get('APPLICATION_NAME'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('APPLICATION_NAME'))
        if not os.environ.get('APPLICATION_VERSION'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('APPLICATION_VERSION'))
        if not os.environ.get('GIT_APPLICATION_REPO'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('GIT_APPLICATION_REPO'))
        if not os.environ.get('GIT_APPLICATION_REPO_BRANCH'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('GIT_APPLICATION_REPO_BRANCH'))
        if not os.environ.get('BUILD_ID'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('BUILD_ID'))
        if not os.environ.get('BUILD_NUMBER'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('BUILD_NUMBER'))
        if not os.environ.get('PACKAGE_STORAGE_SERVER'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('PACKAGE_STORAGE_SERVER'))
        if not os.environ.get('PACKAGE_STORAGE_SERVER_USER'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('PACKAGE_STORAGE_SERVER_USER'))
        if not os.environ.get('PACKAGE_STORAGE_SERVER_BASE_DIR'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('PACKAGE_STORAGE_SERVER_BASE_DIR'))
        return True

    #######################################################
    # Validate build args for Qt5 Extra Module binary build
    #######################################################
    def validate_execute_extra_module_build_cycle_binary_args(self):
        print('Validating build args for Qt5 Extra Module binary build')
        print(self.options)
        # check env variables
        if not os.environ.get('LICENSE'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('LICENSE'))
        if not os.environ.get('PACKAGE_STORAGE_SERVER_PATH_HTTP'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('PACKAGE_STORAGE_SERVER_PATH_HTTP'))
        if not os.environ.get('QT_VERSION_MINOR'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('QT_VERSION_MINOR'))
        if not os.environ.get('APPLICATION_NAME'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('APPLICATION_NAME'))
        if not os.environ.get('APPLICATION_VERSION'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('APPLICATION_VERSION'))
        if not os.environ.get('QT5_APPLICATION_SRC_URI'):
            sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('QT5_APPLICATION_SRC_URI'))
        if bldinstallercommon.is_win_platform():
            if not os.environ.get('QT5_APPLICATION_BUILD_CMD'):
                sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('QT5_APPLICATION_BUILD_CMD'))
            if not os.environ.get('QT5_APPLICATION_INSTALL_CMD'):
                sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('QT5_APPLICATION_INSTALL_CMD'))
            if not os.environ.get('7Z_TOOL_PATH'):
                sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('7Z_TOOL_PATH'))
            if not os.environ.get('GIT_TOOL_PATH'):
                sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('GIT_TOOL_PATH'))
        if bldinstallercommon.is_mac_platform():
            if not os.environ.get('IFW_INSTALLERBASE_URI'):
                sys.exit('*** Error - Qt5 Extra Module build missing environment variable: {0}'.format('IFW_INSTALLERBASE_URI'))
        # check command line arguments
        if not self.options.server:
            sys.exit('*** Qt5 Extra Module build missing command line argument: --server')
        if not self.options.target_env:
            sys.exit('*** Qt5 Extra Module build missing command line argument: --target_env')
        if not self.options.path:
            sys.exit('*** Qt5 Extra Module build missing command line argument: --path')
        return True

    ###########################################
    # Validate build args for QtCreator init
    ###########################################
    def validate_init_qtcreator_build_cycle_args(self):
        if not self.options.license:
            print('*** QtCreator init is missing command line argument: --license')
            sys.exit(-1)
        if not self.options.time_stamp:
            print('*** QtCreator init is missing command line argument: --time_stamp')
            sys.exit(-1)
        if not self.options.build_number:
            print('*** QtCreator init is missing command line argument: --build_number')
            sys.exit(-1)
        if not self.options.server:
            print('*** QtCreator init is missing command line argument: --server')
            sys.exit(-1)
        if not self.options.path:
            print('*** QtCreator init is missing command line argument: --path')
            sys.exit(-1)
        return True

    ###########################################
    # Determine if command relates to qt5 builds
    ###########################################
    def is_qt5_release_build(self):
        cmd_list = [self.init_build_cycle]
        cmd_list += [self.execute_qt5_src_pkg]
        cmd_list += [self.execute_qt5_bin_bld]
        cmd_list += [self.publish_qt5_src_pkg]
        if self.options.command not in cmd_list:
            return False
        return True

    ###########################################
    # Determine if this is Enginio build
    ###########################################
    def is_enginio_build(self):
        if self.options.command == self.execute_extra_module_bld:
            app_name = os.environ.get('APPLICATION_NAME')
            if 'enginio' in app_name.lower():
                return True
        return False

    ##############################################################
    # Parse Qt version and tag from release description file
    ##############################################################
    def parse_release_description_file(self):
        self.parser = ConfigParser.ConfigParser()
        self.parser.readfp(open(self.release_description_file))
        self.version = ''
        self.version_tag = ''
        for s in self.parser.sections():
            if s == 'release.global':
                # parse from conf file
                self.version = bldinstallercommon.safe_config_key_fetch(self.parser, s, 'version')
                self.version_tag = bldinstallercommon.safe_config_key_fetch(self.parser, s, 'version_tag')
                self.full_version = self.version
                if self.version_tag:
                    self.full_version += '-' + self.version_tag
                temp = bldinstallercommon.safe_config_key_fetch(self.parser, s, 'module_separate_install_list')
                self.qt_module_separate_install_list = temp.replace(' ', '').split(',')
                break


###########################################
# Utility class to keep qt snapshot dir
###########################################
class QtSnapshotDir:
    def __init__(self):
        self.snapshot_qt_dir_base = ''
        self.snapshot_qt_dir      = ''
        self.latest_qt_dir        = ''

    def __init__(self, base_dir, snaphsot_dir, latest_dir):
        self.snapshot_qt_dir_base = base_dir
        self.snapshot_qt_dir      = snaphsot_dir
        self.latest_qt_dir        = latest_dir


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
def sanity_check_packaging_server(bld_command):
    if not bld_command.pkg_server_addr:
        print('*** Error - Packaging server address not defined?')
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
    cmd_args = ['/Users/qt/unlock-keychain.sh']
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


###############################
# Lock keychain
###############################
def lock_keychain():
    cmd_args = ['/Users/qt/lock-keychain.sh']
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


###############################
# sign windows executable
###############################
def sign_mac_executable(file_path, working_dir, abort_on_fail):
    s_arg = 'Developer ID Application: The Qt Company Oy'
    cmd_args = ['codesign', '-r', '/Users/qt/csreq_qt_company.txt', '-s', s_arg, file_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, working_dir, abort_on_fail)

##############################################################
# Determine the qt build snaphot directory name
##############################################################
def get_qt_snapshot_dir(bld_command):
    snapshot_qt_dir_base = bld_command.path + '/' + bld_command.license + '/qt/' + bld_command.version
    snapshot_qt_dir      = bld_command.path + '/' + bld_command.license + '/' + 'qt' + '/' + bld_command.version + '/' + bld_command.build_time_stamp + '-' + bld_command.build_number
    latest_qt_dir        = bld_command.path + '/' + bld_command.license + '/' + 'qt' + '/' + bld_command.version + '/' + 'latest'
    return QtSnapshotDir(snapshot_qt_dir_base, snapshot_qt_dir, latest_qt_dir)


###############################
# initialize_build
###############################
def initialize_qt5_build(bld_command):
    sanity_check_packaging_server(bld_command)
    snapshot_path = get_qt_snapshot_dir(bld_command)
    snapshot_qt_dir = snapshot_path.snapshot_qt_dir
    latest_qt_dir   = snapshot_path.latest_qt_dir
    qt_dir_base     = snapshot_path.snapshot_qt_dir_base
    for dir_name in SRC_DEST_DIRS:
        dir_path = snapshot_qt_dir + '/' + dir_name
        create_remote_dirs(bld_command.pkg_server_addr, dir_path)
    if bld_command.license == 'enterprise':
        dir_path = snapshot_qt_dir + '/' + 'src/licheck'
        create_remote_dirs(bld_command.pkg_server_addr, dir_path)
    # Update latest link
    cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, 'ln -sfn', snapshot_qt_dir, latest_qt_dir]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
    #Create latest_available_package
    latest_available_pkg = qt_dir_base + '/latest_available_package'
    create_remote_dirs(bld_command.pkg_server_addr, latest_available_pkg)
    # Update latest Qt Minor version link
    qt_dir_base = snapshot_path.snapshot_qt_dir_base
    remote_qt_minor_dir = qt_dir_base[:-2]
    cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, 'ln -sfn', latest_available_pkg , remote_qt_minor_dir]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
    # Create binary links for opensource
    version_num = int(''.join(re.findall(r'\d+', bld_command.version)))
    if (version_num >= 550):
        if bld_command.license == 'opensource':
            cmd_args = ['rm', '-rf', latest_qt_dir + '/' + 'src/doc']
            bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
            for dir_name in BIN_DEST_DIRS:
                link_name = latest_qt_dir + '/' + dir_name
                remote_dir = link_name.replace('opensource', 'enterprise')
                update_latest_link(bld_command, remote_dir, link_name)


###############################
# initialize_extra_module_build
###############################
def initialize_extra_module_build_src(bld_command):
    # initialize extra module src, doc and example directory hierarchy
    sanity_check_packaging_server(bld_command)
    for dir_name in EXTRA_MODULE_DEST_DIRS:
        dir_path = bld_command.remote_extra_module_dir + '/' + dir_name
        create_remote_dirs(bld_command.pkg_server_addr, dir_path)
    # Update latest link
    cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, 'ln -sfn', bld_command.remote_extra_module_dir, bld_command.latest_extra_module_dir]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)

###############################
# handle_qt_licheck_build
###############################
def handle_qt_licheck_build(bld_command):
    if bld_command.license == 'enterprise':
        # Build license checker
        exe_dir = WORK_DIR + '/qtsdk-enterprise/license-managing/licheck'
        upload_path = bld_command.pkg_server_addr + ':' + bld_command.path + '/' + bld_command.license + '/qt/' + bld_command.version + '/latest/src/licheck/'
        if bld_command.target_env.lower().startswith("win"):
            cmd_args = ['c:\Utils\jom\jom.exe', '-f', 'Makefile_win']
            bldinstallercommon.do_execute_sub_process(cmd_args, exe_dir, True)
            cmd_args = [SCP_COMMAND, 'licheck.exe', upload_path]
            bldinstallercommon.do_execute_sub_process(cmd_args, exe_dir, True)
        elif bld_command.target_env.lower().startswith("linux"):
            cmd_args = ['make', '-j6', '-f', 'Makefile_unix']
            bldinstallercommon.do_execute_sub_process(cmd_args, exe_dir, True)
            cmd_args = ['strip', 'licheck']
            bldinstallercommon.do_execute_sub_process(cmd_args, exe_dir, True)
            if bld_command.target_env.find("x64") >= 1:
                cmd_args = ['rsync', '-r', 'licheck', upload_path +'licheck64']
            else:
                cmd_args = ['rsync', '-r', 'licheck', upload_path +'licheck32']
            bldinstallercommon.do_execute_sub_process(cmd_args, exe_dir, True)
        else:
            cmd_args = ['make', '-j6', '-f', 'Makefile_unix']
            bldinstallercommon.do_execute_sub_process(cmd_args, exe_dir, True)
            cmd_args = ['strip', 'licheck']
            bldinstallercommon.do_execute_sub_process(cmd_args, exe_dir, True)
            cmd_args = ['rsync', '-r', 'licheck', upload_path +'licheck_mac']
            bldinstallercommon.do_execute_sub_process(cmd_args, exe_dir, True)
    else:
        #opensource, do nothing
        print('*** opensource build, nothing to build ...')

###############################
# handle_qt_configure_exe_build
###############################
def handle_qt_configure_exe_build(bld_command):
    # create configure.exe and inject it into src package
    if bld_command.custom_build:
        src_package_name = 'qt-everywhere-' + bld_command.custom_build + '-' + bld_command.license + '-src-' + bld_command.full_version
        src_module_name = 'qtbase-' + bld_command.custom_build + '-' + bld_command.license + '-src-' + bld_command.full_version
    else:
        src_package_name = 'qt-everywhere-' + bld_command.license + '-src-' + bld_command.full_version
        src_module_name = 'qtbase-' + bld_command.license + '-src-' + bld_command.full_version
    cmd_args = ['python', '-u', WORK_DIR + '\qtsdk\packaging-tools\helpers\create_configure_exe.py', 'src_url=' + bld_command.qt_src_url_base + 'single/' + src_package_name + '.zip', 'mdl_url=' + bld_command.qt_src_url_base + 'submodules/' + src_module_name + '.zip', 'do_7z']
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)

    # upload packages
    ARTF_UPLOAD_PATH=bld_command.pkg_server_addr + ':' + bld_command.path + '/' + bld_command.license + '/' + 'qt/' + bld_command.version + '/latest/src'
    temp_file = src_package_name + '.zip'
    cmd_args = [SCP_COMMAND, temp_file, ARTF_UPLOAD_PATH + '/single/']
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
    temp_file = src_package_name + '.7z'
    cmd_args = [SCP_COMMAND, temp_file, ARTF_UPLOAD_PATH + '/single/']
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
    temp_file = src_module_name + '.zip'
    cmd_args = [SCP_COMMAND, temp_file, ARTF_UPLOAD_PATH + '/submodules/']
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
    temp_file = src_module_name + '.7z'
    cmd_args = [SCP_COMMAND, temp_file, ARTF_UPLOAD_PATH + '/submodules/']
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)

###############################
# build_extra_module_src_pkg
###############################
def build_extra_module_src_pkg(bld_command):
    sanity_check_packaging_server(bld_command)
    #create dir
    application_dir = os.path.join(WORK_DIR, bld_command.app_name)
    bldinstallercommon.create_dirs(application_dir)
    #clone repo
    bldinstallercommon.clone_repository(os.environ['GIT_APPLICATION_REPO'], os.environ['GIT_APPLICATION_REPO_BRANCH'], application_dir, True)
    if os.environ.get('APPLICATION_SHA1'):
        cmd_args = ['git', 'checkout', os.environ['APPLICATION_SHA1']]
        bldinstallercommon.do_execute_sub_process(cmd_args, application_dir, True)
    #make src package
    cmd_args = ['../qtsdk/packaging-tools/mksrc.sh', '-v', bld_command.app_version, '-l', bld_command.license, '--single-module']
    bldinstallercommon.do_execute_sub_process(cmd_args, application_dir, True)
    #extract examples
    cmd_args = ['../qtsdk/packaging-tools/extract_examples.sh', '-n', bld_command.app_name, '-l', bld_command.license, '-v', bld_command.app_version, '-u', bld_command.package_storage_server_user, '-s', bld_command.package_storage_server, '-d', bld_command.package_storage_server_base_dir, '-i', os.environ['BUILD_ID'], '-b', bld_command.build_number]
    bldinstallercommon.do_execute_sub_process(cmd_args, application_dir, True)
    #Copy src package to the server
    extra_module_src_dir = bld_command.package_storage_server_user + '@' + bld_command.package_storage_server + ':' + bld_command.package_storage_server_base_dir + '/' + bld_command.license + '/' + bld_command.app_name + '/' + bld_command.app_version
    src_pkg = False
    file_list = os.listdir(application_dir)
    for file_name in file_list:
        if file_name.startswith(bld_command.app_name + '-' + bld_command.license + '-src-' + bld_command.app_version):
            src_pkg = True
            cmd_args = ['scp', file_name, extra_module_src_dir + '/latest/src']
            bldinstallercommon.do_execute_sub_process(cmd_args, application_dir, True)
    # handle doc package creation
    build_doc.handle_extra_module_doc_build()
    # copy archived doc files to network drive if exists, we use Linux only to generate doc archives
    local_docs_dir = os.path.join(SCRIPT_ROOT_DIR, 'doc_archives')
    doc_pkg = False
    if os.path.exists(local_docs_dir):
        doc_pkg = True
        # create remote doc dir
        doc_target_dir = bld_command.pkg_server_addr + ':' + bld_command.latest_extra_module_dir + '/' + 'doc'
        remote_copy_archives(doc_target_dir, local_docs_dir)
    # if we got here, we have all the packages, update symlink latest_successful -> latest
    if src_pkg and doc_pkg:
        latest_successful_dir = bld_command.latest_extra_module_dir + '_successful'
        update_latest_link(bld_command, bld_command.latest_extra_module_dir, latest_successful_dir)

###############################
# initialize_extra_module_binary_build
###############################
def initialize_extra_module_binary_build(bld_command):
    # initialize extra module binary directory hierarchy
    sanity_check_packaging_server(bld_command)
    #Create binary upload folder
    create_remote_dirs(bld_command.pkg_server_addr, bld_command.remote_extra_module_binary_dir)
    # Update latest link
    cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, 'ln -sfn', bld_command.remote_extra_module_binary_dir, bld_command.latest_extra_module_binary_dir]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)

###############################
# initialize_build
###############################
def initialize_qtcreator_build(bld_command):
    sanity_check_packaging_server(bld_command)
    qtcreator_edition_name = os.environ.get('QT_CREATOR_EDITION_NAME')
    dir_name = 'qtcreator'
    if qtcreator_edition_name:
        dir_name += '_' + qtcreator_edition_name
    # Qt Creator directory
    remote_base_dir = bld_command.path + '/' + bld_command.license + '/' + dir_name
    remote_dest_dir = remote_base_dir + '/' + bld_command.build_time_stamp[:10] + '_' + bld_command.build_number
    remote_latest_dir = remote_base_dir + '/' + 'latest'
    # remote destination directory
    create_remote_dirs(bld_command.pkg_server_addr, remote_dest_dir)
    # 'latest' symlink pointing to remote destination directory
    update_latest_link(bld_command, remote_dest_dir, remote_latest_dir)


###############################
# handle_ifw_build()
###############################
def handle_ifw_build(bld_command):
    sanity_check_packaging_server(bld_command)
    os.chdir(SCRIPT_ROOT_DIR)
    # Qt
    qt_src_pkg = os.environ['IFW_QT_SRC_PKG'] # mandatory env variable
    is_qt5_ifw_build = True
    regex = re.compile('-((5)\.\d.\d)')
    regex_result = regex.findall(qt_src_pkg)
    if not regex_result:
        is_qt5_ifw_build = False
    qt_configure_options = bld_ifw_tools.get_default_qt_configure_options(is_qt5_ifw_build)
    # Installer-Framework
    ifw_url    = os.environ['IFW_GIT_URL'] # mandatory env variable
    ifw_branch = os.environ['IFW_GIT_VERSION'] # mandatory env variable
    ifw_dest_dir_name = os.environ.get('IFW_REMOTE_RESULT_DEST_DIR_NAME')
    # Destination dir name on network disk for build artifacts
    if not ifw_dest_dir_name:
        ifw_dest_dir_name = ifw_branch
    ifw_qmake_args = IfwOptions.default_qt_installer_framework_qmake_args
    # check for debug build
    if os.environ.get('IFW_DEBUG_BUILD'):
        qt_configure_options = qt_configure_options.replace('-release', '-debug')
        ifw_qmake_args = ' '.join(ifw_qmake_args).replace('-config release', '-config debug').split()
    # extra qt configure options for qt/ifw build
    if os.environ.get('IFW_QT_EXTRA_CONFIGURE_OPTIONS'):
        qt_configure_options += ' ' + os.environ.get('IFW_QT_EXTRA_CONFIGURE_OPTIONS')
    # Product Key Checker
    product_key_checker_pri = ''
    if bld_command.license == 'enterprise':
        product_key_checker_pri = os.environ['PRODUCT_KEY_CHECKER_PRI']
        temp = bldinstallercommon.locate_file(os.environ['PKG_NODE_ROOT'], product_key_checker_pri)
        product_key_checker_pri = temp if temp else product_key_checker_pri
    # OpenSSL
    openssl_dir = os.environ.get('IFW_OPENSSL_DIR')

    # options object for ifw build
    ifw_bld_options = IfwOptions(is_qt5_ifw_build, qt_src_pkg,
                                 qt_configure_options,
                                 ifw_url, ifw_branch,
                                 ifw_qmake_args,
                                 product_key_checker_pri,
                                 openssl_dir)
    # build ifw tools
    bld_ifw_tools.build_ifw(ifw_bld_options)

    ## create destination dirs on network disk
    # internal
    create_remote_dirs(bld_command.pkg_server_addr, bld_command.path + '/' + bld_command.license + '/ifw/' + ifw_dest_dir_name)
    # public
    if bld_command.license == 'opensource':
        # public server address and path
        ext_server_base_url  = os.environ['EXT_SERVER_BASE_URL']
        ext_server_base_path = os.environ['EXT_SERVER_BASE_PATH']
        # public server directories
        ext_dest_dir = ext_server_base_path + '/snapshots/ifw/' + ifw_dest_dir_name + '/' + bld_command.build_time_stamp[:10] + '_' + bld_command.build_number
        cmd_args_mkdir_pkg = [SSH_COMMAND, bld_command.pkg_server_addr]
        cmd_args_mkdir_ext = cmd_args_mkdir_pkg + ['ssh', ext_server_base_url, 'mkdir', '-p', ext_dest_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_ext, SCRIPT_ROOT_DIR, True)

    if bldinstallercommon.is_win_platform():
        file_list = os.listdir(SCRIPT_ROOT_DIR+'/' + pkg_constants.IFW_BUILD_ARTIFACTS_DIR)
        for file_name in file_list:
            if file_name.endswith(".7z"):
                cmd_args = [SCP_COMMAND, file_name, bld_command.pkg_server_addr + ':' + bld_command.path + '/' + bld_command.license + '/ifw/' + ifw_dest_dir_name + '/']
                bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR + '/' + pkg_constants.IFW_BUILD_ARTIFACTS_DIR, True)
    else:
        cmd_args = ['rsync', '-r', './', bld_command.pkg_server_addr + ':' + bld_command.path + '/' + bld_command.license + '/ifw/' + ifw_dest_dir_name + '/']
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR + '/' + pkg_constants.IFW_BUILD_ARTIFACTS_DIR, True)

    # copy ifw snapshot to public server
    if bld_command.license == 'opensource':
        cmd_args_copy_ifw_pkg = [SSH_COMMAND, bld_command.pkg_server_addr]
        cmd_args_copy_ifw_ext = cmd_args_copy_ifw_pkg + ['scp', bld_command.path + '/' + bld_command.license + '/ifw/' + ifw_dest_dir_name + '/' + 'installer-framework-build*.7z', ext_server_base_url + ':' + ext_dest_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_copy_ifw_ext, SCRIPT_ROOT_DIR, True)

###############################
# handle_qt_src_package_build
###############################
def handle_qt_src_package_build(bld_command):
    sanity_check_packaging_server(bld_command)
    exec_path = os.path.join(WORK_DIR, 'qt5')
    cmd_args = ['./init-repository', '-f', '--mirror', os.environ['QT5_GIT_MIRROR']]
    exec_path = os.path.join(WORK_DIR, 'qt5')
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    if bld_command.license == 'enterprise':
        if bld_command.custom_build != 0:
            module = None
            uri = os.path.normpath(os.path.join(os.path.dirname(__file__), os.environ.get('CUSTOM_COMMANDS')))
            path, fname = os.path.split(uri)
            mname, ext = os.path.splitext(fname)
            if os.path.exists(os.path.join(path,mname)+'.py'):
                module = imp.load_source(mname, uri)
                print('Running {0} custom commands'.format(bld_command.custom_build))
                module.handle_custom_commands(bld_command.custom_build, WORK_DIR)
            else:
                print('*** No custom functions found')
                sys.exit(-1)
    if bld_command.license == 'enterprise':
        cmd_args = ['../patches/apply.sh']
        bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    if bld_command.license == 'enterprise':
        copy_license_checkers(bld_command)
    package_path = os.path.join(WORK_DIR, 'src_pkg')
    bldinstallercommon.create_dirs(package_path)
    # parse module exclude list from release description file
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(bld_command.release_description_file))
    exclude_list = bldinstallercommon.safe_config_key_fetch(parser, 'release.global', 'module_exclude_list')
    split_exclude_list = exclude_list.split(',')
    module_exclude_list = []
    for item in split_exclude_list:
        module_exclude_list += ['-i', item]
    # cmd args for source packaging srcipt
    cmd_args = [os.path.join(SCRIPT_ROOT_DIR, 'mksrc.sh'), '-u', os.path.join(WORK_DIR, 'qt5')]
    cmd_args += ['-v', bld_command.full_version, '-m', '-N', '-l', bld_command.license]
    cmd_args += module_exclude_list
    if bld_command.custom_build != 0:
        cmd_args += ['--product-name', bld_command.custom_build]
    # create src package
    bldinstallercommon.do_execute_sub_process(cmd_args, package_path, True)

    # Example injection
    if bld_command.custom_build == 0:
        package_name = 'qt-everywhere-' + bld_command.license + '-src-' + bld_command.full_version
    else:
        package_name = 'qt-everywhere-' + bld_command.custom_build + '-' + bld_command.license + '-src-' + bld_command.full_version

    cmd_args = ['tar', 'xzf', 'single/' + package_name + '.tar.gz']

    bldinstallercommon.do_execute_sub_process(cmd_args, package_path, True)
    essentials_path = os.path.join(WORK_DIR, 'src_pkg', 'examples_essentials')
    bldinstallercommon.create_dirs(essentials_path)

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
    for root, dirs, dummy in os.walk(essentials_path):
        if doc_dir in dirs:
            # do not recurse into doc directory
            dirs.remove(doc_dir)
            shutil.rmtree(os.path.join(root, doc_dir))

    # remove out of place top level files from qtdeclarative
    if os.path.exists(os.path.join(essentials_path, 'HACKING')):
        os.remove(os.path.join(essentials_path, 'HACKING'))
    if os.path.exists(os.path.join(essentials_path, 'README')):
        os.remove(os.path.join(essentials_path, 'README'))

    if bld_command.custom_build == 0:
        cmd_args = ['7z', 'a', os.path.join('..', 'qt5_examples.7z'), '*']
        bldinstallercommon.do_execute_sub_process(cmd_args, essentials_path, True)

    # Create necessary directories
    latest_qt_dir = get_qt_snapshot_dir(bld_command).latest_qt_dir
    create_remote_dirs(bld_command.pkg_server_addr, os.path.join(latest_qt_dir, 'src', 'single', ''))
    create_remote_dirs(bld_command.pkg_server_addr, os.path.join(latest_qt_dir, 'src', 'submodules', ''))
    create_remote_dirs(bld_command.pkg_server_addr, os.path.join(latest_qt_dir, 'src', 'examples_injection', ''))

    # Upload packages
    exec_path = SCRIPT_ROOT_DIR
    cmd_args = ['rsync', '-r', '../../src_pkg/single/', bld_command.pkg_server_addr + ':' + os.path.join(latest_qt_dir, 'src', 'single', '')]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = ['rsync', '-r', '../../src_pkg/submodules_tar/', bld_command.pkg_server_addr + ':' + os.path.join(latest_qt_dir, 'src', 'submodules', '')]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = ['rsync', '-r', '../../src_pkg/submodules_zip/', bld_command.pkg_server_addr + ':' + os.path.join(latest_qt_dir, 'src', 'submodules', '')]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)

    if bld_command.custom_build == 0:
        file_list = os.listdir(package_path)
        for file_name in file_list:
            if file_name.startswith("qt5_examples."):
                cmd_args = ['scp', file_name, bld_command.pkg_server_addr + ':' + os.path.join(latest_qt_dir, 'src', 'examples_injection')]
                bldinstallercommon.do_execute_sub_process(cmd_args, package_path, True)


#######################################################
# Get extra Qt configure options for Desktop builds
#######################################################
def qt_desktop_release_build_extra_configure_options(bld_command):
    global EXTRA_ENV
    # Use custom ICU when required (build from sources or use pre-built icu libs)
    if platform.system().lower().startswith('linux'):
        extra_options = ' -R ' + os.path.join(WORK_DIR, MAKE_INSTALL_PADDING)
        icu_configuration = bld_icu_tools.init_build_icu(bld_command.icu_src_pkg_url, '', False, EXTRA_ENV)
        EXTRA_ENV = combine_environment_dicts(EXTRA_ENV, icu_configuration.environment)
        extra_options += ' ' + icu_configuration.qt_configure_extra_args
        return extra_options
    else:
        return ''


###############################
# Get configuration options
###############################
def get_qt_configuration_options(bld_command):
    tmp = ''
    qt_configure_options_file = os.environ['RELEASE_BUILD_QT_CONFIGURE_OPTIONS_FILE']
    # parse qt configuration arguments from release description file
    if not os.path.isfile(qt_configure_options_file):
        print('*** Not a valid release description file: {0}'.format(qt_configure_options_file))
        sys.exit(-1)
    tmp_conf = os.path.dirname(qt_configure_options_file)
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(qt_configure_options_file))
    # parse
    for s in parser.sections():
        section_parts = s.split('.')
        if section_parts[0] != 'release':
            continue
        build_node_labels = bldinstallercommon.safe_config_key_fetch(parser, s, 'build_node_labels').replace(' ', '')
        tmp = bldinstallercommon.safe_config_key_fetch(parser, s, 'configure_options')
        label_list = build_node_labels.split(',')
        if bld_command.target_env in label_list:
            tmp_conf += 'tmp' + str(random.randint(1, 1000))
            break
    if not tmp:
        print('*** No valid configuration for {0} found'.format(bld_command.target_env))
        tmp_conf = ''
    else:
        f = open(tmp_conf,"w")
        f.write(tmp)
        f.close()
    return tmp_conf


###############################
# Handle extra module release build
###############################
def handle_extra_module_release_build(bld_command):
    qt_version = os.environ['QT_VERSION']
    script_path = os.path.join(SCRIPT_ROOT_DIR, 'bld_app.py')
    icu7z_package = os.environ.get('ICU7Z')
    pkg_storage_server = os.environ['PACKAGE_STORAGE_SERVER_PATH_HTTP']
    build_command = os.environ.get('QT5_APPLICATION_BUILD_CMD')
    install_command = os.environ.get('QT5_APPLICATION_INSTALL_CMD')
    collect_docs_command = os.environ.get('QT5_APPLICATION_COLLECT_DOCS_CMD')
    make_docs_command = os.environ.get('QT5_APPLICATION_MAKE_DOCS_CMD')
    qt5_bin_pkg_base_path = pkg_storage_server + '/' + bld_command.license + '/' + 'qt' + '/' + qt_version + '/' + 'latest_available_package/' +  BIN_TARGET_DIRS[bld_command.target_env]
    qt5_essentials_lib_package_uri = qt5_bin_pkg_base_path + '/qt5_essentials.7z'
    qt5_addons_lib_package_uri = qt5_bin_pkg_base_path + '/qt5_addons.7z'
    qt5_webengine_lib_package_url = qt5_bin_pkg_base_path + '/qt5_qtwebengine.7z'
    extra_module_src_uri = pkg_storage_server + '/' + bld_command.license + '/' + bld_command.app_name + '/' + bld_command.app_version + '/latest/src/' + bld_command.app_name + '-' + bld_command.license + '-src-' + bld_command.app_version + '.7z'

    # build command
    cmd_args = ['python', '-u', script_path, '--clean']
    cmd_args += ['--qt5path', 'qt5_package_dir']
    cmd_args += ['--qt5_essentials7z', qt5_essentials_lib_package_uri]
    cmd_args += ['--application7z', extra_module_src_uri]

    if bldinstallercommon.is_content_url_valid(qt5_addons_lib_package_uri):
        cmd_args += ['--qt5_addons7z', qt5_addons_lib_package_uri]
    if bldinstallercommon.is_content_url_valid(qt5_webengine_lib_package_url):
        cmd_args += ['--qt5_webengine7z', qt5_webengine_lib_package_url]
    if icu7z_package:
        cmd_args += ['--icu7z', icu7z_package]
    if build_command:
        cmd_args += ['--buildcommand', build_command]
    if install_command:
        cmd_args += ['--installcommand', install_command]
    if collect_docs_command:
        cmd_args += ['--collectDocs']
    if make_docs_command:
        cmd_args += ['--makeDocs']
    if bldinstallercommon.is_win_platform():
        cmd_args += ['--sevenzippath', os.environ.get('7Z_TOOL_PATH')]
        cmd_args += ['--gitpath', os.environ.get('GIT_TOOL_PATH')]
    if bldinstallercommon.is_mac_platform():
        cmd_args += ['--installerbase7z', os.environ['IFW_INSTALLERBASE_URI']]
    # init result directories
    create_remote_dirs(bld_command.pkg_server_addr, bld_command.latest_extra_module_binary_dir + '/' + BIN_TARGET_DIRS[bld_command.target_env])
    # execute build
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
    # copy 7z files to network drive
    remote_target_dir = bld_command.pkg_server_addr + ':' + bld_command.latest_extra_module_binary_dir + '/' + BIN_TARGET_DIRS[bld_command.target_env]
    if bldinstallercommon.is_win_platform():
        remote_target_dir += '/'
    remote_copy_archives(remote_target_dir, os.path.join(SCRIPT_ROOT_DIR, 'module_archives'))
    # copy archived doc files to network drive if exists
    local_docs_dir = os.path.join(SCRIPT_ROOT_DIR, 'doc_archives')
    if os.path.exists(local_docs_dir):
        # create remote doc dir
        doc_target_dir = bld_command.pkg_server_addr + ':' + bld_command.latest_extra_module_dir + '/' + 'doc'
        if bldinstallercommon.is_win_platform():
            doc_target_dir += '/'
        remote_copy_archives(doc_target_dir, local_docs_dir)


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
def handle_examples_injection(bld_command):
    # Inject examples
    if bldinstallercommon.is_linux_platform():
        cmd_args = ['wget', bld_command.qt_src_url_base + 'examples_injection/qt5_examples.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR + '/module_archives', True)
    else:
        cmd_args = [CURL_COMMAND, '-O', bld_command.qt_src_url_base + 'examples_injection/qt5_examples.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

    bldinstallercommon.create_dirs(os.path.join(WORK_DIR, 'module_archives', 'essentials'))
    bldinstallercommon.create_dirs(os.path.join(WORK_DIR, 'module_archives', 'addons'))

    # essentials
    cmd_args = ['7z', 'x', 'qt5_essentials.7z', '-oessentials']
    bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
    cmd_args = ['7z', 'x', 'qt5_examples.7z', os.path.join('-oessentials', 'examples'), '-y']
    bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

    cmd_args = [RM_COMMAND, 'qt5_essentials.7z']
    bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)
    cmd_args = [RM_COMMAND, 'qt5_examples.7z']
    bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

    cmd_args = ['7z', 'a', os.path.join('..', 'qt5_essentials.7z'), '*']
    bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives/essentials'), True)

    # addons
    cmd_args = ['7z', 'x', 'qt5_addons.7z', '-oaddons']
    bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

    cmd_args = [RM_COMMAND, 'qt5_addons.7z']
    bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives'), True)

    cmd_args = ['7z', 'a', os.path.join('..', 'qt5_addons.7z'), '*']
    bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(WORK_DIR, 'module_archives/addons'), True)


###############################
# Generate binary target dictionary
###############################
def generate_bin_target_dictionary():
    global BIN_TARGET_DIRS
    # parse module exclude list from release description file
    conf_file_base_path = os.path.join(SCRIPT_ROOT_DIR, BUILD_META_INFO_FILE)
    if not os.path.isfile(conf_file_base_path):
        print('*** Not a valid release description file: {0}'.format(conf_file_base_path))
        sys.exit(-1)
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(conf_file_base_path))
    # parse
    for s in parser.sections():
        section_parts = s.split('.')
        if section_parts[0] != 'meta':
            continue
        build_target_dir = bldinstallercommon.safe_config_key_fetch(parser, s, 'build_target_dir')
        build_node_labels = bldinstallercommon.safe_config_key_fetch(parser, s, 'build_node_labels').replace(' ', '')
        label_list = build_node_labels.split(',')
        if not build_target_dir:
            print('*** No build target directory defined for: {0}'.format(s))
            sys.exit(-1)
        if not label_list:
            print('*** No build slave label defined for: {0}'.format(s))
            sys.exit(-1)
        for label in label_list:
            BIN_TARGET_DIRS[label] = build_target_dir


###############################
# handle_qt_release_build
###############################
def handle_qt_release_build(bld_command):
    sanity_check_packaging_server(bld_command)
    # Qt configure options
    qt_configure_options_file = get_qt_configuration_options(bld_command)
    if not os.path.isfile(qt_configure_options_file):
        print('*** No valid Qt configuration file found: {0}'.format(qt_configure_options_file))
        sys.exit(-1)
    # additional Qt configure options
    qt_configure_extra_options = os.getenv('EXTRA_QT_CONFIGURE_OPTIONS', '')
    if bld_command.license.lower() == 'enterprise':
        version_num = int(''.join(re.findall(r'\d+', bld_command.version)))
        if (version_num < 550):
            if not 'alpha' or 'beta' in bld_command.version_tag.lower():
                if bldinstallercommon.is_win_platform():
                    qt_configure_extra_options += ' -D QT_EVAL'
                else:
                    qt_configure_extra_options += ' -DQT_EVAL'

    # Qt build options
    qt5BuildOptions = mkqt5bld.MkQtBuildOptions()
    qt5BuildOptions.src_url = bld_command.qt_src_url

    # Android specific
    if bld_command.target_env.find("Android") >= 1:
        print('Setting Android specific build options..')
        # on windows we build with jom instead of make
        if bldinstallercommon.is_win_platform():
            qt5BuildOptions.make_cmd = 'mingw32-make'
        # e.g. "linux-x86" or "linux-x86_64" or "windows" or "darwin-x86_64"
        qt5BuildOptions.android_ndk_host    = os.environ['ANDROID_NDK_HOST']
        # e.g. "/opt/android/ndk"
        qt5BuildOptions.android_ndk_home    = os.environ['ANDROID_NDK_HOME']
        # e.g. "/opt/android/sdk"
        qt5BuildOptions.android_sdk_home    = os.environ['ANDROID_SDK_HOME']
        # e.g. "android-10"
        qt5BuildOptions.android_api_version = os.getenv('ANDROID_API_VERSION', '')
        # e.g. "4.8"
        qt_configure_extra_options += ' -android-toolchain-version ' + os.environ['ANDROID_TOOLCHAIN_VERSION']
    # iOS specific
    elif bld_command.target_env.find("iOS") >= 1:
        print('Setting iOS specific build options..')
    # QNX specific
    elif bld_command.target_env.find("QNX") >= 1:
        print('Setting QNX specific build options..')
        # on windows we build with jom instead of make
        if bldinstallercommon.is_win_platform():
            qt5BuildOptions.make_cmd = 'mingw32-make'
    # Desktop specific
    else:
        print('Setting Desktop specific build options..')
        # on windows we build with jom instead of make
        if bldinstallercommon.is_win_platform():
            qt5BuildOptions.make_cmd = 'jom'
        if os.path.exists(os.path.join(WORK_DIR, 'qt-creator')):
            qt5BuildOptions.qt_creator_src_dir = os.path.join(WORK_DIR, 'qt-creator')
        qt_configure_extra_options += qt_desktop_release_build_extra_configure_options(bld_command)

    # prefix
    qt_configure_extra_options += ' -prefix ' + os.path.join(WORK_DIR,  MAKE_INSTALL_PADDING)

    qt5BuildOptions.configure_options = qt_configure_options_file
    qt5BuildOptions.add_configure_option = qt_configure_extra_options
    qt5BuildOptions.module_separate_install_list = bld_command.qt_module_separate_install_list
    qt5BuildOptions.system_env = EXTRA_ENV

    # Execute Qt build
    mkqt5bld.QT_BUILD_OPTIONS = qt5BuildOptions
    mkqt5bld.main_call_parameters()

    # Define upload directories
    qt_dir_base   = get_qt_snapshot_dir(bld_command).snapshot_qt_dir_base
    latest_qt_dir = get_qt_snapshot_dir(bld_command).latest_qt_dir
    remote_dir    = latest_qt_dir + '/' + BIN_TARGET_DIRS[bld_command.target_env]
    srv_and_remote_dir = bld_command.pkg_server_addr + ':' + remote_dir
    latest_available_pkg = qt_dir_base + '/latest_available_package/' + BIN_TARGET_DIRS[bld_command.target_env]
    srv_and_latest_available_pkg = bld_command.pkg_server_addr + ':' + latest_available_pkg

    # Create target directories where to upload packages
    create_remote_dirs(bld_command.pkg_server_addr, remote_dir)
    create_remote_dirs(bld_command.pkg_server_addr, latest_available_pkg)

    # Upload
    local_archives_dir = os.path.join(WORK_DIR, 'module_archives')
    dir_list = os.listdir(local_archives_dir)
    print(dir_list)
    for file_name in dir_list:
        if file_name.endswith('.7z'):
            cmd_args = [SCP_COMMAND, file_name, srv_and_remote_dir + '/']
            bldinstallercommon.do_execute_sub_process(cmd_args, local_archives_dir, True)
            cmd_args = [SCP_COMMAND, file_name, srv_and_latest_available_pkg + '/']
            bldinstallercommon.do_execute_sub_process(cmd_args, local_archives_dir, True)
            if QT5_DOCS_ARCHIVE_NAME in file_name and bldinstallercommon.is_linux_platform():
                doc_archive_on_remote_disk = latest_qt_dir + '/src/doc/' + QT5_DOCS_ARCHIVE_NAME
                if not bldinstallercommon.remote_path_exists(bld_command.pkg_server_addr, doc_archive_on_remote_disk, SSH_COMMAND):
                    cmd_args = [SCP_COMMAND, file_name, bld_command.pkg_server_addr + ':' + latest_qt_dir + '/src/doc/']
                    bldinstallercommon.do_execute_sub_process(cmd_args, local_archives_dir, True)


###############################
# handle_qt_creator_build
###############################
def handle_qt_creator_build(bld_command):
    sanity_check_packaging_server(bld_command)

    # Qt Creator directory
    qtcreator_edition_name = os.environ.get('QT_CREATOR_EDITION_NAME')
    dir_path = bld_command.path + bld_command.license + '/qtcreator/latest'
    if qtcreator_edition_name:
        dir_path = bld_command.path + bld_command.license + '/qtcreator' + '_' + qtcreator_edition_name + '/latest'

    # snapshot directory
    snapshot_path = bld_command.snapshot_path
    if bld_command.snapshot_server and bld_command.snapshot_path:
        if bld_command.qtcreator_version:
            snapshot_path += '/' + bld_command.qtcreator_version
        cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, "ssh", bld_command.snapshot_server,
            'mkdir', '-p', snapshot_path + '/' + bld_command.build_time_stamp[:10] + '_' + bld_command.build_number]
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
        cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, "ssh", bld_command.snapshot_server,
            'mkdir', '-p', snapshot_path + '/' + bld_command.build_time_stamp[:10] + '_' + bld_command.build_number + '/installer_source']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
        cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, "ssh", bld_command.snapshot_server,
            'ln', '-sfn', snapshot_path + '/' + bld_command.build_time_stamp[:10] + '_' + self.build_number,

                    snapshot_path + '/latest']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
        snapshot_path += '/latest'
    cmd_args = ['python', '-u', 'bld_qtcreator.py',
                '--clean',
                '--qt5path', os.path.normpath('../../qt5_install_dir'),
                '--qt5_essentials7z', bld_command.qt_pkg_url_base + BIN_TARGET_DIRS[bld_command.target_env] + '/qt5_essentials.7z',
                '--qt5_addons7z', bld_command.qt_pkg_url_base + BIN_TARGET_DIRS[bld_command.target_env] + '/qt5_addons.7z',
                '--versiondescription', '"' + bld_command.qtcreator_version_description + '"']

    if bld_command.license == 'enterprise':
        cmd_args.extend(['--additional_plugin', os.path.normpath(WORK_DIR + '/licensechecker'),
                         '--additional_plugin', os.path.normpath(WORK_DIR + '/qmlprofiler'),
                         '--additional_plugin', os.path.normpath(WORK_DIR + '/clangstaticanalyzer'),
                         '--additional_plugin', os.path.normpath(WORK_DIR + '/autotest-qtcreator-plugin'),
                         '--additional_plugin', os.path.normpath(WORK_DIR + '/vxworks-qtcreator-plugin'),
                         '--additional_plugin', os.path.normpath(WORK_DIR + '/qtquickdesigner')])
        if bldinstallercommon.is_linux_platform():
            cmd_args.extend(['--additional_plugin', os.path.normpath(WORK_DIR + '/perfprofiler'),
                             '--additional_plugin', os.path.normpath(WORK_DIR + '/b2qt-qtcreator-plugin')])

    if bldinstallercommon.is_linux_platform():
        cmd_args.extend(['--icu7z', bld_command.icu_libs])
        if bld_command.target_env.find('64') != -1:
            cmd_args.extend(['--installerbase7z', 'http://ci-files02-hki.ci.local/packages/jenkins/' + bld_command.license + '/ifw/1.6/installer-framework-build-linux-x64.7z'])
        else:
            cmd_args.extend(['--installerbase7z', 'http://ci-files02-hki.ci.local/packages/jenkins/' + bld_command.license + '/ifw/1.6/installer-framework-build-linux-x86.7z'])
    elif bldinstallercommon.is_mac_platform():
        cmd_args.extend(['--installcommand', 'make -j1',
                         '--installerbase7z', 'http://ci-files02-hki.ci.local/packages/jenkins/' + bld_command.license + '/ifw/1.6/installer-framework-build-mac-x64.7z',
                         '--keychain_unlock_script', '/Users/qt/unlock-keychain.sh'])
    else:
        cmd_args.extend(['--buildcommand', os.path.normpath('C:/Utils/jom/jom.exe'),
                         '--installcommand', os.path.normpath('C:/Program Files/Microsoft Visual Studio 10.0/VC/bin/nmake.exe'),
                         '--icu7z', bld_command.icu_libs,
                         '--sevenzippath', os.path.normpath('C:/Utils/sevenzip'),
                         '--gitpath', os.path.normpath('C:/Program Files/Git/bin'),
                         '--d3dcompiler7z', 'http://download.qt.io/development_releases/prebuilt/d3dcompiler/msvc2010/D3DCompiler_43-x86.dll.7z',
                         '--opengl32sw7z', 'http://download.qt.io/development_releases/prebuilt/llvmpipe/windows/opengl32sw-32.7z',
                         '--installerbase7z', 'http://ci-files02-hki.ci.local/packages/jenkins/' + LICENSE + '/ifw/1.6/installer-framework-build-win-x86.7z',
                         '--environment_batch', os.path.normpath('C:/Program Files/Microsoft Visual Studio 12.0/VC/vcvarsall.bat'),
                         '--environment_batch_argument', 'x86'])
        if bld_command.openssl_libs:
            cmd_args.extend(['--openssl7z', bld_command.openssl_libs])

    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)

    if bldinstallercommon.is_mac_platform():
        lock_keychain()

    postfix = ''
    if bld_command.qtcreator_version:
        postfix = '-' + bld_command.qtcreator_version
    file_upload_list = [] # pairs (source, dest), source relative to WORK_DIR, dest relative to server + dir_path
    snapshot_upload_list = [] # pairs (source, dest), source relative to server + dir_path, dest relative to snapshot server + snapshot_path
    if bldinstallercommon.is_linux_platform():
        linux_bits = '32'
        linux_arch = 'x86'
        if bld_command.target_env.find('64') != -1:
            linux_bits = '64'
            linux_arch = 'x86_64'
        file_upload_list.append(('qt-creator_build/qt-creator-installer-archive.7z', 'qtcreator_linux_gcc_' + linux_bits + '_ubuntu1110.7z'))
        file_upload_list.append(('qt-creator_build/qt-creator.run', 'qt-creator-' + bld_command.license + '-linux-' + linux_arch + postfix + '.run'))
        snapshot_upload_list.append(('qtcreator_linux_gcc_' + linux_bits + '_ubuntu1110.7z', 'installer_source/'))
        snapshot_upload_list.append(('qt-creator-' + bld_command.license + '-linux-' + linux_arch + postfix + '.run', ''))
    elif bldinstallercommon.is_mac_platform():
        file_upload_list.append(('qt-creator_build/qt-creator-installer-archive.7z', 'qtcreator_mac_cocoa_10_7.7z'))
        if bld_command.license == 'opensource': # opensource gets pure disk image with app and license.txt
            file_upload_list.append(('qt-creator_build/qt-creator.dmg', 'qt-creator-' + bld_command.license + '-mac-x86_64' + postfix + '.dmg'))
        else: # enterprise gets installer with license check
            file_upload_list.append(('qt-creator_build/qt-creator-installer.dmg', 'qt-creator-' + bld_command.license + '-mac-x86_64' + postfix + '.dmg'))
        snapshot_upload_list.append(('qtcreator_mac_cocoa_10_7.7z', 'installer_source/'))
        snapshot_upload_list.append(('qt-creator-' + bld_command.license + '-mac-x86_64' + postfix + '.dmg', ''))
    else: # --> windows
        file_upload_list.append(('qt-creator_build/qt-creator-installer-archive.7z', 'qtcreator_windows_vs2013_32.7z'))
        sign_windows_executable('qt-creator_build/qt-creator.exe', WORK_DIR, True)
        file_upload_list.append(('qt-creator_build/qt-creator.exe', 'qt-creator-' + bld_command.license + '-windows-x86' + postfix + '.exe'))
        snapshot_upload_list.append(('qtcreator_windows_vs2013_32.7z', 'installer_source/'))
        snapshot_upload_list.append(('qt-creator-' + bld_command.license + '-windows-x86' + postfix + '.exe', ''))

    # upload files
    for source, destination in file_upload_list:
        cmd_args = [SCP_COMMAND, source, bld_command.pkg_server_addr + ':' + dir_path + '/' + destination]
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
    if bld_command.snapshot_server and bld_command.snapshot_path:
        for source, destination in snapshot_upload_list:
            cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, "scp",
                dir_path + '/' + source,
                bld_command.snapshot_server + ':' + snapshot_path + '/' + destination]

            bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)


###############################
# handle_offline_installer_build
###############################
def handle_offline_installer_build(bld_command):
    handle_installer_build('offline', bld_command)


###############################
# handle_online_installer_build
###############################
def handle_online_installer_build(bld_command):
    handle_installer_build('online', bld_command)


###############################
# replace_latest_successful_installer
###############################
def replace_latest_successful_installer(bld_command, installer_name, installer_name_final, ls_installer_dir, installer_output):
    # check installer type
    if 'online' in installer_name_final.lower():
        regex = re.compile('.*online')
        if "embedded" in installer_name_final.lower():
            regex = re.compile('.*online(?:(?!_\d{4}).)*')
    else:
        regex = re.compile('.*' + bld_command.full_version)
    installer_base_name = "".join(regex.findall(installer_name_final))
    if not installer_base_name:
        print('*** Empty installer base name string')
    else:
        old_installer = ls_installer_dir + '/' + installer_base_name + '*'
        # delete old installer
        cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, 'rm', old_installer]
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, False)
        # save new installer to latest_successful directory
        cmd_args = [SCP_COMMAND, installer_name, bld_command.pkg_server_addr + ':' + ls_installer_dir + '/' + installer_name_final]
        bldinstallercommon.do_execute_sub_process(cmd_args, installer_output, True)


###############################
# generic handle installer build
###############################
def handle_installer_build(installer_type, bld_command):
    sanity_check_packaging_server(bld_command)
    conf_file = bld_command.release_description_file
    if not os.path.exists(conf_file):
        print('*** The given file does not exist: {0}'.format(conf_file))
        sys.exit(-1)
    export_opensource_offline_installer = False
    # Is this opensource offline build job?
    if bld_command.license == 'opensource' and installer_type == 'offline':
        export_opensource_offline_installer = True
    branch = 'release' # TODO
    if bld_command.target_env.find('64') != -1:
        arch = 'x64'
    else:
        arch = 'x86'

    # Determine local installer output directory
    installer_output_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.INSTALLER_OUTPUT_DIR_NAME)
    # Create all installers for this host
    release_build_handler.handle_installer_build(conf_file, installer_type, bld_command.license, branch, PLATFORM, arch, bld_command.pkg_server_addr_http)
    # Create directories under <LICENSE>/<installer_type>_installers/
    remote_path_base = bld_command.path + '/' + bld_command.license + '/'
    remote_path_top_level_base              = remote_path_base + '/' + installer_type + '_installers' + '/' + bld_command.version + '/'
    remote_path_top_level                   = remote_path_top_level_base + bld_command.build_time_stamp[:10] + '_' + bld_command.build_number
    remote_path_top_level_latest            = remote_path_top_level_base + '/' + 'latest'
    remote_path_top_level_latest_available  = remote_path_top_level_base + '/' + 'latest_available_offline_installers'
    create_remote_dirs(bld_command.pkg_server_addr, remote_path_top_level)
    create_remote_dirs(bld_command.pkg_server_addr, remote_path_top_level_latest_available)
    #Update latest link
    update_latest_link(bld_command, remote_path_top_level, remote_path_top_level_latest)
    # Create remote directories under <LICENSE>/qt/<version>
    if installer_type == 'offline':
        remote_path_base_qt              = remote_path_base + 'qt' + '/' + bld_command.version + '/'
        remote_path_qt_latest            = remote_path_base_qt + 'latest' + '/' + 'offline_installers'
        remote_path_qt_latest_available  = remote_path_base_qt + 'latest_available_offline_installers'
        # create symlinks
        update_latest_link(bld_command, remote_path_top_level, remote_path_qt_latest)
        update_latest_link(bld_command, remote_path_top_level, remote_path_qt_latest_available)

    # Create remote dirs on opensource distribution server
    if export_opensource_offline_installer:
        # opensource distribution server address and path
        ext_server_base_url  = os.environ['EXT_SERVER_BASE_URL']
        ext_server_base_path = os.environ['EXT_SERVER_BASE_PATH']
        # opensource distribution server directories
        ext_dest_dir = ext_server_base_path + '/snapshots/qt/' + bld_command.version[:3] + '/' + bld_command.full_version + '/' + bld_command.build_time_stamp[:10] + '_' + bld_command.build_number
        cmd_args_mkdir_pkg = [SSH_COMMAND, bld_command.pkg_server_addr]
        cmd_args_mkdir_ext = cmd_args_mkdir_pkg + ['ssh', ext_server_base_url, 'mkdir -p', ext_dest_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_ext, SCRIPT_ROOT_DIR, True)

    # Copy all installers from 'installer_output_dir' into network disk
    dir_list = os.listdir(installer_output_dir)
    for file_name in dir_list:
        installer_name, installer_name_base, installer_name_final = generate_installer_final_name(bld_command, file_name)
        if not (installer_name and installer_name_base and installer_name_final):
            print('*** Skipped file: {0}'.format(file_name))
            continue
        # sign
        sign_installer(installer_output_dir, installer_name, installer_name_base)
        # copy installer(s) to various locations:
        if installer_type == 'offline':
            # under:
            # <LICENSE>/qt/<version>/latest/offline_installers/    i.e. the snapshot directory, may not contain all installers
            remote_copy_installer(bld_command, remote_path_qt_latest, installer_name, installer_output_dir, installer_name_final)
            # <LICENSE>/qt/<version>/latest_available_offline_installers/    may contain installer from different builds, always the latest successful ones
            replace_latest_successful_installer(bld_command, installer_name, installer_name_final, remote_path_qt_latest_available, installer_output_dir)

        # under:
        # i.e. separate location where offline installers only reside, separated by version number in path
        # <LICENSE>/<installer_type>_installers/<version>/<time_stamp>/
        remote_copy_installer(bld_command, remote_path_top_level_latest, installer_name, installer_output_dir, installer_name_final)
        # <LICENSE>/<installer_type>_installers/<version>/latest_available_offline_installers/
        replace_latest_successful_installer(bld_command, installer_name, installer_name_final, remote_path_top_level_latest_available, installer_output_dir)

        # copy offline installer to mirror brain server
        if export_opensource_offline_installer:
            remote_copy_installer_opensource(bld_command, remote_path_top_level, ext_server_base_url, ext_dest_dir, installer_name_final)

    # Copy rta description file(s) to network drive
    rta_descr_output_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.RTA_DESCRIPTION_FILE_DIR_NAME)
    for file_name in rta_descr_output_dir:
        if file_name.startswith(pkg_constants.RTA_DESCRIPTION_FILE_NAME_BASE):
            cmd_args = [SCP_COMMAND, file_name, bld_command.pkg_server_addr + ':' + remote_path_top_level + '/' + file_name]
            bldinstallercommon.do_execute_sub_process(cmd_args, installer_output_dir, True)

    # Trigger rta cases
    rta_descr_output_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.RTA_DESCRIPTION_FILE_DIR_NAME)
    trigger_rta(rta_descr_output_dir)


###############################
# Sign installer
###############################
def sign_installer(installer_output_dir, installer_name, installer_name_base):
    if installer_name.endswith(".dmg"):
        unlock_keychain()
        sign_mac_executable(installer_name_base + '.app', installer_output_dir, True)
        cmd_args = ['hdiutil', 'create', '-srcfolder', os.path.join(installer_output_dir, installer_name_base) + '.app', '-volname', installer_name_base, '-format', 'UDBZ', os.path.join(installer_output_dir, installer_name_base) + '.dmg', '-ov', '-scrub', '-size', '3g']
        bldinstallercommon.do_execute_sub_process(cmd_args, installer_output_dir, True)
    if installer_name.endswith(".exe"):
        sign_windows_executable(installer_name, installer_output_dir, True)


###############################
# Remote copy installer
###############################
def remote_copy_installer(bld_command, remote_dest_dir, file_name, installer_output_dir, installer_name_final):
    cmd_args = [SCP_COMMAND, file_name, bld_command.pkg_server_addr + ':' + remote_dest_dir + '/' + installer_name_final]
    bldinstallercommon.do_execute_sub_process(cmd_args, installer_output_dir, True)


###############################
# Remote copy installer (Opensource)
###############################
def remote_copy_installer_opensource(bld_command, remote_dest_dir, ext_server_base_url, ext_dest_dir, installer_name_final):
    # copy installer to mirror brain server
    if bld_command.license == 'opensource':
        cmd_args_copy_to_pkg = [SSH_COMMAND, bld_command.pkg_server_addr]
        cmd_args_copy_to_ext = cmd_args_copy_to_pkg + ['scp', remote_dest_dir + '/' + installer_name_final, ext_server_base_url + ':' + ext_dest_dir  + '/' + installer_name_final]
        bldinstallercommon.do_execute_sub_process(cmd_args_copy_to_ext, SCRIPT_ROOT_DIR, True)


###############################
# Helper to generate installer final name
###############################
def generate_installer_final_name(bld_command, file_name):
    installer_name = ''
    installer_name_base = ''
    installer_name_final = ''
    # Linux
    if file_name.endswith(".run"):
        installer_name = file_name
        installer_name_base = os.path.splitext(file_name)[0]
        installer_name_final = installer_name_base + '_' + bld_command.build_time_stamp + '-' + bld_command.build_number + '.run'
    # Mac
    if file_name.endswith(".dmg"):
        installer_name = file_name
        installer_name_base = os.path.splitext(file_name)[0]
        installer_name_final = installer_name_base + '_' + bld_command.build_time_stamp + '-' + bld_command.build_number + '.dmg'
    # Windows
    if file_name.endswith(".exe"):
        installer_name = file_name
        installer_name_base = os.path.splitext(file_name)[0]
        installer_name_final = installer_name_base + '_' + bld_command.build_time_stamp + '-' + bld_command.build_number + '.exe'
    return installer_name, installer_name_base, installer_name_final


###############################
# Update latest link
###############################
def update_latest_link(bld_command, remote_dest_dir, latest_dir):
    cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, 'ln -sfn', remote_dest_dir, latest_dir]
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)


###############################
# Trigger RTA cases
###############################
def trigger_rta(rta_description_files_dir):
    # check if rta cases define for this build job
    if not os.path.isdir(rta_description_files_dir):
        print('*** Error - Given rta_description_files_dir does not exist: {0}'.format(rta_description_files_dir))
        sys.exit(-1)
    dir_list = os.listdir(rta_description_files_dir)
    matching = [s for s in dir_list if pkg_constants.RTA_DESCRIPTION_FILE_NAME_BASE in s]
    if not matching:
        print('No RTA cases defined for this build job.')
        return
    # obtain RTA server base url
    if not os.environ.get('RTA_SERVER_BASE_URL'):
        print('*** Error - RTA_SERVER_BASE_URL env. variable is not defined. Unable to proceed! RTA not run for this build job!')
        return
    rta_server_base_url = os.environ['RTA_SERVER_BASE_URL']
    if not (rta_server_base_url.endswith('/')):
        rta_server_base_url += '/'
    # iterate rta description files
    for rta_description_file in matching:
        print('Reading RTA description file: {0}'.format(os.path.join(rta_description_files_dir, rta_description_file)))
        rta_file = os.path.join(rta_description_files_dir, rta_description_file)
        f = open(rta_file)
        for line in iter(f):
            line_split = line.split(' ')
            if len(line_split) != 2:
                print('*** Error - Invalid format in rta description file {0}, line: {1}'.format(rta_file, line))
                sys.exit(-1)
            rta_keys = line_split[1].split(',')
            for item in rta_keys:
                item = item.rstrip().replace(' ', '')
                if item:
                    url = rta_server_base_url + item + '/build?token=JENKINS_SQUISH'
                    print('Triggering RTA case: {0}'.format(url))
                    urllib.urlretrieve(url)
        f.close()


################################
# Handle online repository build
################################
def handle_online_repository_build(bld_command):
    conf_file = bld_command.release_description_file
    if not os.path.exists(conf_file):
        print('*** The given file does not exist: {0}'.format(conf_file))
        sys.exit(-1)
    if bld_command.target_env.find('64') != -1:
        arch = 'x64'
    else:
        arch = 'x86'

    # do we update staging repository?
    update_staging_repo = True
    if os.environ.get('DO_UPDATE_STAGING_REPOSITORY'):
        update = os.environ['DO_UPDATE_STAGING_REPOSITORY']
        if update.lower() in ['no', 'false', '0']:
            update_staging_repo = False
    # do we also update production repository?
    update_production_repo = False
    if os.environ.get('DO_UPDATE_PRODUCTION_REPOSITORY'):
        update = os.environ['DO_UPDATE_PRODUCTION_REPOSITORY']
        if update.lower() in ['yes', 'true', '1']:
            update_production_repo = True
    release_build_handler.handle_repo_build(conf_file, bld_command.license, 'release', PLATFORM, arch, bld_command.pkg_server_addr_http, update_staging_repo, update_production_repo)
    # (3) trigger rta cases
    rta_descr_output_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.RTA_DESCRIPTION_FILE_DIR_NAME)
    trigger_rta(rta_descr_output_dir)


###############################
# copy_license_checkers
###############################
def copy_license_checkers(bld_command):
    sanity_check_packaging_server(bld_command)
    latest_qt_dir = get_qt_snapshot_dir(bld_command).latest_qt_dir
    exec_path = os.path.join(WORK_DIR, 'qt5', 'qtbase', 'bin')
    cmd_args = [SCP_COMMAND, bld_command.pkg_server_addr + ':' + os.path.join(latest_qt_dir, 'src', 'licheck', 'licheck.exe'), '.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = [SCP_COMMAND, bld_command.pkg_server_addr + ':' + os.path.join(latest_qt_dir, 'src', 'licheck', 'licheck32'), '.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = [SCP_COMMAND, bld_command.pkg_server_addr + ':' + os.path.join(latest_qt_dir, 'src', 'licheck', 'licheck64'), '.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = [SCP_COMMAND, bld_command.pkg_server_addr + ':' + os.path.join(latest_qt_dir, 'src', 'licheck', 'licheck_mac'), '.']
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
# publish_qt5_src_packages
###############################
def publish_qt5_src_packages(bld_command):
    # Mirror Brain server address and path
    ext_server_base_url  = os.environ['EXT_SERVER_BASE_URL']
    ext_server_base_path = os.environ['EXT_SERVER_BASE_PATH']

    ext_dest_dir = ext_server_base_path + '/snapshots/qt/' + bld_command.version[:3] + '/' + bld_command.full_version + '/' + bld_command.build_time_stamp[:10] + '_' + bld_command.build_number

    # copy source packages to public server
    if bld_command.license == 'opensource':
        # create source directories
        latest_qt_dir = get_qt_snapshot_dir(bld_command).latest_qt_dir
        cmd_args_mkdir_src_pkg = [SSH_COMMAND, bld_command.pkg_server_addr]
        cmd_args_mkdir_src_ext = cmd_args_mkdir_src_pkg + ['ssh', ext_server_base_url, 'mkdir', '-p', ext_dest_dir + '/' + 'single']
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_src_ext, SCRIPT_ROOT_DIR, True)
        cmd_args_mkdir_src_ext = cmd_args_mkdir_src_pkg + ['ssh', ext_server_base_url, 'mkdir', '-p', ext_dest_dir + '/' + 'submodules']
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_src_ext, SCRIPT_ROOT_DIR, True)
        # copy the source packages to the remove directory
        cmd_args_copy_src_to_pkg = [SSH_COMMAND, bld_command.pkg_server_addr]
        cmd_args_copy_src_to_ext = cmd_args_copy_src_to_pkg + ['scp', '-r', latest_qt_dir + '/' + 'src/single/*', ext_server_base_url + ':' + ext_dest_dir + '/' + 'single']
        bldinstallercommon.do_execute_sub_process(cmd_args_copy_src_to_ext, SCRIPT_ROOT_DIR, True)
        cmd_args_copy_src_to_ext = cmd_args_copy_src_to_pkg + ['scp', '-r', latest_qt_dir + '/' + 'src/submodules/*', ext_server_base_url + ':' + ext_dest_dir + '/' + 'submodules']
        bldinstallercommon.do_execute_sub_process(cmd_args_copy_src_to_ext, SCRIPT_ROOT_DIR, True)


###############################
# create_remote_dirs
###############################
def create_remote_dirs(server, dir_path):
    cmd_args = [SSH_COMMAND, '-t', '-t', server, 'mkdir -p', dir_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


###############################
# ICU build init
###############################
def initialize_icu_build(bld_command):
    # sanity check icu args in bld_command
    sanity_check_packaging_server(bld_command)
    if not bld_command.icu_version:
        sys.exit('*** ICU build is missing: icu_version')
    if not bld_command.path:
        sys.exit('*** ICU build is missing: path')
    if not bld_command.build_time_stamp:
        sys.exit('*** ICU build is missing: build_time_stamp')
    if not bld_command.build_number:
        sys.exit('*** ICU build is missing: build_number')
    remote_snaphot_dir_base = bld_command.path + '/' + 'icu' + '/' + bld_command.icu_version
    remote_snaphot_dir = remote_snaphot_dir_base + '/' + bld_command.build_time_stamp + '-' + bld_command.build_number
    remote_latest_dir = remote_snaphot_dir_base + '/' + 'latest'
    # create remote snapshot dir
    create_remote_dirs(bld_command.pkg_server_addr, remote_snaphot_dir)
    # update latest symlink
    update_latest_link(bld_command, remote_snaphot_dir, remote_latest_dir)


###############################
# Handle ICU builds
###############################
def handle_icu_build(bld_command):
    # sanity check icu args in bld_command
    sanity_check_packaging_server(bld_command)
    if not bld_command.icu_version:
        sys.exit('*** ICU build is missing: icu_version')
    if not bld_command.path:
        sys.exit('*** ICU build is missing: path')
    if not bld_command.icu_src_pkg_url:
        sys.exit('*** ICU build is missing: icu_src_pkg_url')
    bld_icu_tools.init_build_icu(bld_command.icu_src_pkg_url, bld_command.icu_version, True)
    # define remote dir where to upload
    remote_snaphot_dir = bld_command.path + '/' + 'icu' + '/' + bld_command.icu_version + '/' + 'latest'
    srv_and_remote_dir = bld_command.pkg_server_addr + ':' + remote_snaphot_dir
    # check the build artifacts
    local_archives_dir = bldinstallercommon.locate_directory(SCRIPT_ROOT_DIR, ICU_BUILD_OUTPUT_DIR)
    dir_list = os.listdir(local_archives_dir)
    for file_name in dir_list:
        if file_name.endswith('.7z'):
            cmd_args = [SCP_COMMAND, file_name, srv_and_remote_dir + '/']
            bldinstallercommon.do_execute_sub_process(cmd_args, local_archives_dir, True)


################################
# Publish prebuilt ICU packages
################################
def publish_icu_packages(bld_command):
    # sanity check icu args in bld_command
    sanity_check_packaging_server(bld_command)
    if not bld_command.icu_version:
        sys.exit('*** ICU build is missing: icu_version')
    # Opensource server address and path
    ext_server_base_url  = os.environ['EXT_SERVER_BASE_URL']
    ext_server_base_path = os.environ['EXT_SERVER_BASE_PATH']
    ext_icu_snapshot_dir = os.environ.get('EXT_ICU_SNAPSHOT_DIR')
    if not ext_icu_snapshot_dir:
        ext_icu_snapshot_dir = '/development_releases/prebuilt/icu/prebuilt/'
    else:
        ext_icu_snapshot_dir = '/' + ext_icu_snapshot_dir + '/'
        ext_icu_snapshot_dir.replace('//', '/')
    ext_dest_dir = ext_server_base_path + ext_icu_snapshot_dir + bld_command.icu_version + '/'
    # Create remote directories
    cmd_pkg_login = [SSH_COMMAND, bld_command.pkg_server_addr]
    cmd_mkdir_ext = cmd_pkg_login + ['ssh', ext_server_base_url, 'mkdir', '-p', ext_dest_dir]
    bldinstallercommon.do_execute_sub_process(cmd_mkdir_ext, SCRIPT_ROOT_DIR, True)
    # Copy the pre-built ICU packages to the remote directory
    print('Starting to copy pre-build icu packages to ext: {0}'.format(ext_dest_dir))
    cmd_copy_icu_to_ext = cmd_pkg_login + ['scp', '-r', '-v', PATH + '/icu/' + bld_command.icu_version + '/latest/*', ext_server_base_url + ':' + ext_dest_dir]
    bldinstallercommon.do_execute_sub_process(cmd_copy_icu_to_ext, SCRIPT_ROOT_DIR, True)


###############################
# parse_cmd_line
###############################
def parse_cmd_line():
    global PLATFORM

    setup_option_parser()
    arg_count = len(sys.argv)
    if arg_count < 2:
        OPTION_PARSER.print_help()
        sys.exit(-1)

    (options, dummy) = OPTION_PARSER.parse_args()
    bld_cmd_validator = BldCommand(options)

    if not bld_cmd_validator.validate_bld_args():
        OPTION_PARSER.print_help()
        sys.exit(-1)

    if bldinstallercommon.is_linux_platform():
        PLATFORM = 'linux'
    elif bldinstallercommon.is_mac_platform():
        PLATFORM = 'mac'
    else:
        PLATFORM = 'windows'

    return bld_cmd_validator


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
    OPTION_PARSER.add_option("-o", "--openssl_libs",
                             action="store", type="string", dest="openssl_libs", default="",
                             help="Url for pre-compiled openssl libraries")
    OPTION_PARSER.add_option("--qtcreator-version",
                             action="store", type="string", dest="qtcreator_version", default="",
                             help="Qt Creator version, e.g. '3.0.0-rc', used in file names")
    OPTION_PARSER.add_option("--qtcreator-version-description",
                             action="store", dest="qtcreator_version_description", default="",
                             help="Qt Creator's version description, e.g. '3.0.0-rc-enterprise', or 'opensource', shown in Qt Creator's about dialog in addition to the version")
    OPTION_PARSER.add_option("--snapshot-server",
                             action="store", type="string", dest="snapshot_server", default="",
                             help="Additional snapshot upload server <user>@<host> (is uploaded from upload server)")
    OPTION_PARSER.add_option("--snapshot-path",
                             action="store", type="string", dest="snapshot_path", default="",
                             help="Path on additional snapshot upload server")

    OPTION_PARSER.add_option("--custom-build", action="store", type="string", dest="custom_build", default=0, help="Custom build option")


##############################################################
# Initialize Environment
##############################################################
def init_env():
    global MAKE_INSTALL_PADDING
    global CURL_COMMAND
    global RM_COMMAND
    global SSH_COMMAND
    global SCP_COMMAND

    # prefix build
    MAKE_INSTALL_PADDING = 'PADDING' if bldinstallercommon.is_win_platform() else '______________________________PADDING______________________________'
    # external commands
    CURL_COMMAND         = '%CURL%'  if bldinstallercommon.is_win_platform() else 'curl'
    RM_COMMAND           = '%RM%'    if bldinstallercommon.is_win_platform() else 'rm'
    SSH_COMMAND          = '%SSH%'   if bldinstallercommon.is_win_platform() else 'ssh'
    SCP_COMMAND          = '%SCP%'   if bldinstallercommon.is_win_platform() else 'scp'

    # generate build slave label/build result target dir dictionary
    generate_bin_target_dictionary()


###############################
# Main
###############################
def main():
    bldinstallercommon.init_common_module(SCRIPT_ROOT_DIR)

    init_env()

    bld_command = parse_cmd_line()
    # Qt5 specific
    if bld_command.command == BldCommand.init_build_cycle:
        initialize_qt5_build(bld_command)
    elif bld_command.command == BldCommand.execute_qt5_src_pkg:
        handle_qt_src_package_build(bld_command)
    elif bld_command.command == BldCommand.execute_qt5_bin_bld:
        handle_qt_release_build(bld_command)
    elif bld_command.command == BldCommand.publish_qt5_src_pkg:
        publish_qt5_src_packages(bld_command)
    # Extra module specific
    elif bld_command.command == BldCommand.init_extra_module_build_cycle_src:
        initialize_extra_module_build_src(bld_command)
    elif bld_command.command == BldCommand.execute_extra_module_build_cycle_src:
        build_extra_module_src_pkg(bld_command)
    elif bld_command.command == BldCommand.init_extra_module_build_cycle_binary:
        initialize_extra_module_binary_build(bld_command)
    elif bld_command.command == BldCommand.execute_extra_module_build_cycle_binary:
        handle_extra_module_release_build(bld_command)
    # QtCreator specific
    elif bld_command.command == BldCommand.init_qtcreator_build_cycle:
        initialize_qtcreator_build(bld_command)
    elif bld_command.command == BldCommand.execute_creator_bld:
        handle_qt_creator_build(bld_command)
    # Qt Installer-Framework specific
    elif bld_command.command == BldCommand.execute_ifw_bld:
        handle_ifw_build(bld_command)
    # Installer build specific
    elif bld_command.command == BldCommand.execute_repo_bld:
        handle_online_repository_build(bld_command)
    elif bld_command.command == BldCommand.execute_offline_inst_bld:
        handle_offline_installer_build(bld_command)
    elif bld_command.command == BldCommand.execute_online_inst_bld:
        handle_online_installer_build(bld_command)
    elif bld_command.command == BldCommand.execute_configure_exe_bld:
        handle_qt_configure_exe_build(bld_command)
    elif bld_command.command == BldCommand.publish_icu_pkg:
        publish_icu_packages(bld_command)
    elif bld_command.command == BldCommand.init_icu_bld:
        initialize_icu_build(bld_command)
    elif bld_command.command == BldCommand.execute_icu_bld:
        handle_icu_build(bld_command)
    elif bld_command.command == BldCommand.execute_licheck_bld:
        handle_qt_licheck_build(bld_command)
    else:
        print('Unsupported command')


if __name__ == "__main__":
    main()

