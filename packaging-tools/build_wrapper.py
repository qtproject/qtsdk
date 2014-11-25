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

from optparse import OptionParser, Option

import bldinstallercommon
import release_build_handler
import bld_icu_tools
import pkg_constants
import random
import operator
from pkg_constants import ICU_BUILD_OUTPUT_DIR


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
#WORK_DIR                    = os.environ['PKG_NODE_ROOT']
COMMAND                     = ''
LICENSE                     = ''
OPTION_PARSER               = 0
QTCREATOR_VERSION           = ''
QTCREATOR_VERSION_DESCRIPTION = ''
TIME_STAMP                  = ''
BUILD_NUMBER                = ''
PKG_SERVER_ADDR             = ''
PATH                        = '/data/www/packages/jenkins'
SNAPSHOT_SERVER             = ''
SNAPSHOT_PATH               = ''
TARGET_ENV                  = ''
ICU_LIBS                    = ''
ICU_SRC                     = ''
OPENSSL_LIBS                = ''
QT_SRC_FOR_IFW_PREPARED     = 'http://download.qt-project.org/development_releases/prebuilt/qt-src-for-ifw/qt-everywhere-opensource-src-4.8.6-ifw-patch'
IFW_GIT_URL                 = 'git://gitorious.org/installer-framework/installer-framework.git'
SRC_URL_PREFIX              = 'http://qt-rnd.it.local/packages/jenkins'
SRC_URL                     = ''
PLATFORM                    = ''
SRC_DEST_DIRS               = ['src', 'src/submodules', 'src/doc', 'src/single', 'src/examples_injection']
EXTRA_MODULE_DEST_DIRS      = ['src', 'doc', 'examples']
QT5_DOCS_ARCHIVE_NAME       = 'qt5_docs.7z'
BIN_TARGET_DIRS             = {} # dictionary populated based on the /packaging-tools/releases/release-<version>
REMOTE_EXTRA_MODULE_DIR         = ''
LATEST_EXTRA_MODULE_DIR         = ''
REMOTE_EXTRA_MODULE_BINARY_DIR  = ''
LATEST_EXTRA_MODULE_BINARY_DIR  = ''
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
    init_icu_bld                            = 'init_icu_bld'
    execute_icu_bld                         = 'icu_bld'

    def __init__(self, options):
        self.options = options

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
        commands += [self.init_icu_bld]
        commands += [self.execute_icu_bld]
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
        # ICU build
        elif cmd == self.init_icu_bld:
            return self.validate_icu_init_args()
        elif cmd == self.execute_icu_bld:
            return self.validate_icu_build_args()
        else:
            if len(sys.argv) < 12:
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
    # Validate build args for ICU build init
    ###########################################
    def validate_icu_init_args(self):
        if not self.options.server:
            print('*** ICU build is missing command line argument: --server')
            sys.exit(-1)
        if not self.options.time_stamp:
            print('*** ICU init is missing command line argument: --time_stamp')
            sys.exit(-1)
        if not self.options.build_number:
            print('*** ICU init is missing command line argument: --build_number')
            sys.exit(-1)
        if not os.environ.get('ICU_VERSION'):
            sys.exit('*** ICU init build is missing environment variable: ICU_VERSION')
        return True

    ###########################################
    # Validate build args for ICU build
    ###########################################
    def validate_icu_build_args(self):
        if not self.options.server:
            print('*** ICU build is missing command line argument: --server')
            sys.exit(-1)
        if not os.environ.get('ICU_SRC_PKG_URL_UNIX') or not os.environ.get('ICU_SRC_PKG_URL_WIN'):
            sys.exit('*** ICU build is missing environment variable: ICU_SRC_PKG_URL_[UNIX|WIN]')
        if not os.environ.get('ICU_VERSION'):
            sys.exit('*** ICU init build is missing environment variable: ICU_VERSION')
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
    cmd_args = ['/Users/qt/unlock-keychain.sh']
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


##############################################################
# Find the release description file
##############################################################
def get_release_description_file():
    conf_file = os.environ.get('RELEASE_BUILD_CONF_FILE')
    if not os.path.exists(conf_file):
        print('*** Unable to locate release description file: {0}'.format(conf_file))
        sys.exit(-1)
    return conf_file


##############################################################
# Parse Qt version and tag from release description file
##############################################################
def parse_qt_version_and_tag(release_description_file):
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(release_description_file))
    qt_version = ''
    qt_version_tag = ''
    for s in parser.sections():
        if s == 'release.global':
            # parse from conf file
            qt_version = bldinstallercommon.safe_config_key_fetch(parser, s, 'version')
            qt_version_tag = bldinstallercommon.safe_config_key_fetch(parser, s, 'version_tag')
            qt_full_version = qt_version
            if qt_version_tag:
                qt_full_version += '-' + qt_version_tag

            continue
    return qt_version, qt_version_tag, qt_full_version


##############################################################
# Determine the qt build snaphot directory name
##############################################################
def get_qt_snapshot_dir():
    qt_version, qt_version_tag, qt_full_version = parse_qt_version_and_tag(get_release_description_file())
    snapshot_qt_dir_base = PATH + '/' + LICENSE + '/qt/' + qt_version
    snapshot_qt_dir      = PATH + '/' + LICENSE + '/' + 'qt' + '/' + qt_version + '/' + TIME_STAMP + '-' + BUILD_NUMBER
    latest_qt_dir        = PATH + '/' + LICENSE + '/' + 'qt' + '/' + qt_version + '/' + 'latest'
    return QtSnapshotDir(snapshot_qt_dir_base, snapshot_qt_dir, latest_qt_dir)


###############################
# initialize_build
###############################
def initialize_qt5_build():
    sanity_check_packaging_server()
    snapshot_qt_dir = get_qt_snapshot_dir().snapshot_qt_dir
    latest_qt_dir   = get_qt_snapshot_dir().latest_qt_dir
    qt_dir_base     = get_qt_snapshot_dir().snapshot_qt_dir_base
    for dir_name in SRC_DEST_DIRS:
        dir_path = snapshot_qt_dir + '/' + dir_name
        create_remote_dirs(PKG_SERVER_ADDR, dir_path)
    if LICENSE == 'enterprise':
        dir_path = snapshot_qt_dir + '/' + 'src/licheck'
        create_remote_dirs(PKG_SERVER_ADDR, dir_path)
    # Update latest link
    cmd_args = [SSH_COMMAND, PKG_SERVER_ADDR, 'ln -sfn', snapshot_qt_dir, latest_qt_dir]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
    #Create latest_available_package
    latest_available_pkg = qt_dir_base + '/latest_available_package'
    create_remote_dirs(PKG_SERVER_ADDR, latest_available_pkg)
    # Update latest Qt Minor version link
    qt_dir_base = get_qt_snapshot_dir().snapshot_qt_dir_base
    remote_qt_minor_dir = qt_dir_base[:-2]
    cmd_args = [SSH_COMMAND, PKG_SERVER_ADDR, 'ln -sfn', latest_available_pkg , remote_qt_minor_dir]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


###############################
# initialize_extra_module_build
###############################
def initialize_extra_module_build_src():
    # initialize extra module src, doc and example directory hierarchy
    sanity_check_packaging_server()
    for dir_name in EXTRA_MODULE_DEST_DIRS:
        dir_path = REMOTE_EXTRA_MODULE_DIR + '/' + dir_name
        create_remote_dirs(PKG_SERVER_ADDR, dir_path)
    # Update latest link
    cmd_args = [SSH_COMMAND, PKG_SERVER_ADDR, 'ln -sfn', REMOTE_EXTRA_MODULE_DIR, LATEST_EXTRA_MODULE_DIR]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)

###############################
# handle_qt_configure_exe_build
###############################
def handle_qt_configure_exe_build():
    # create configure.exe and inject it into src package
    qt_version, qt_version_tag, qt_full_version = parse_qt_version_and_tag(get_release_description_file())
    cmd_args = ['python', '-u', WORK_DIR + '\qtsdk\packaging-tools\helpers\create_configure_exe.py', 'src_url=' + SRC_URL + '/single/qt-everywhere-' + LICENSE + '-src-' + qt_full_version + '.zip', 'mdl_url=' + SRC_URL + '/submodules/qtbase-' + LICENSE + '-src-' + qt_full_version + '.zip', 'do_7z']
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)

    # upload packages
    ARTF_UPLOAD_PATH=PKG_SERVER_ADDR + ':' + PATH + '/' + LICENSE + '/' + 'qt/' + qt_version + '/latest/src'
    temp_file = 'qt-everywhere-' + LICENSE + '-src-' + qt_full_version + '.zip'
    cmd_args = [SCP_COMMAND, temp_file, ARTF_UPLOAD_PATH + '/single/']
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
    temp_file = 'qt-everywhere-' + LICENSE + '-src-' + qt_full_version + '.7z'
    cmd_args = [SCP_COMMAND, temp_file, ARTF_UPLOAD_PATH + '/single/']
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
    temp_file = 'qtbase-' + LICENSE + '-src-' + qt_full_version + '.zip'
    cmd_args = [SCP_COMMAND, temp_file, ARTF_UPLOAD_PATH + '/submodules/']
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
    temp_file = 'qtbase-' + LICENSE + '-src-' + qt_full_version + '.7z'
    cmd_args = [SCP_COMMAND, temp_file, ARTF_UPLOAD_PATH + '/submodules/']
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)

###############################
# build_extra_module_src_pkg
###############################
def build_extra_module_src_pkg():
    sanity_check_packaging_server()
    #create dir
    application_dir = os.path.join(WORK_DIR, os.environ['APPLICATION_NAME'])
    bldinstallercommon.create_dirs(application_dir)
    #clone repo
    bldinstallercommon.clone_repository(os.environ['GIT_APPLICATION_REPO'], os.environ['GIT_APPLICATION_REPO_BRANCH'], application_dir)
    if os.environ.get('APPLICATION_SHA1'):
        cmd_args = ['git', 'checkout', os.environ['APPLICATION_SHA1']]
        bldinstallercommon.do_execute_sub_process(cmd_args, application_dir, True)
    #make src package
    cmd_args = ['../qtsdk/packaging-tools/mksrc.sh', '-v', os.environ['APPLICATION_VERSION'], '-l', LICENSE, '--single-module']
    bldinstallercommon.do_execute_sub_process(cmd_args, application_dir, True)
    #extract examples
    cmd_args = ['../qtsdk/packaging-tools/extract_examples.sh', '-n', os.environ['APPLICATION_NAME'], '-l', LICENSE, '-v', os.environ['APPLICATION_VERSION'], '-u', os.environ['PACKAGE_STORAGE_SERVER_USER'], '-s', os.environ['PACKAGE_STORAGE_SERVER'], '-d', os.environ['PACKAGE_STORAGE_SERVER_BASE_DIR'], '-i', os.environ['BUILD_ID'], '-b', os.environ['BUILD_NUMBER']]
    bldinstallercommon.do_execute_sub_process(cmd_args, application_dir, True)
    #Copy src package to the server
    file_list = os.listdir(application_dir)
    for file_name in file_list:
        if file_name.startswith(os.environ['APPLICATION_NAME'] + '-' + LICENSE + '-src-' + os.environ['APPLICATION_VERSION']):
            cmd_args = ['scp', file_name, os.environ['PACKAGE_STORAGE_SERVER_USER'] + '@' + os.environ['PACKAGE_STORAGE_SERVER'] + ':' + os.environ['PACKAGE_STORAGE_SERVER_BASE_DIR'] + '/' + LICENSE + '/' + os.environ['APPLICATION_NAME'] + '/' + os.environ['APPLICATION_VERSION'] + '/latest/src']
            bldinstallercommon.do_execute_sub_process(cmd_args, application_dir, True)
    # handle doc package creation
    build_doc.handle_extra_module_doc_build()
    # copy archived doc files to network drive if exists, we use Linux only to generate doc archives
    local_docs_dir = os.path.join(SCRIPT_ROOT_DIR, 'doc_archives')
    if os.path.exists(local_docs_dir):
        # create remote doc dir
        doc_target_dir = PKG_SERVER_ADDR + ':' + LATEST_EXTRA_MODULE_DIR + '/' + 'doc'
        remote_copy_archives(doc_target_dir, local_docs_dir)


###############################
# initialize_extra_module_binary_build
###############################
def initialize_extra_module_binary_build():
    # initialize extra module binary directory hierarchy
    sanity_check_packaging_server()
    #Create binary upload folder
    create_remote_dirs(PKG_SERVER_ADDR, REMOTE_EXTRA_MODULE_BINARY_DIR)
    # Update latest link
    cmd_args = [SSH_COMMAND, PKG_SERVER_ADDR, 'ln -sfn', REMOTE_EXTRA_MODULE_BINARY_DIR, LATEST_EXTRA_MODULE_BINARY_DIR]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)

###############################
# initialize_build
###############################
def initialize_qtcreator_build():
    sanity_check_packaging_server()
    qtcreator_edition_name = os.environ.get('QT_CREATOR_EDITION_NAME')
    dir_name = 'qtcreator'
    if qtcreator_edition_name:
        dir_name += '_' + qtcreator_edition_name
    # Qt Creator directory
    remote_base_dir = PATH + '/' + LICENSE + '/' + dir_name
    remote_dest_dir = remote_base_dir + '/' + TIME_STAMP[:10] + '_' + BUILD_NUMBER
    remote_latest_dir = remote_base_dir + '/' + 'latest'
    # remote destination directory
    create_remote_dirs(PKG_SERVER_ADDR, remote_dest_dir)
    # 'latest' symlink pointing to remote destination directory
    update_latest_link(remote_dest_dir, remote_latest_dir)


###############################
# handle_ifw_build()
###############################
def handle_ifw_build():
    sanity_check_packaging_server()
    os.chdir(SCRIPT_ROOT_DIR)
    extension = '.tar.gz'
    qt_src_pkg = QT_SRC_FOR_IFW_PREPARED
    ifw_url = IFW_GIT_URL
    ifw_branch = os.environ['QT_INSTALLER_FRAMEWORK_VERSION']
    ifw_dest_dir_name = os.environ.get('IFW_REMOTE_RESULT_DEST_DIR_NAME')
    if not ifw_dest_dir_name:
        ifw_dest_dir_name = ifw_branch
    if bldinstallercommon.is_win_platform():
        extension = '.zip'
    qt_src_pkg += extension
    cmd_args = ['python', '-u', 'bld_ifw_tools.py', '--qt_archive_uri=' + qt_src_pkg, '--ifw_url=' + ifw_url, '--ifw_branch=' + ifw_branch]
    if LICENSE == 'enterprise':
        product_key_checker = os.environ['PRODUCT_KEY_CHECKER_URI']
        cmd_args += ['--product_key_checker_url=' + product_key_checker]
    if (os.environ.get('IFW_DEBUG_BUILD')):
        cmd_args += ['--debug']
    # execute
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)

    ## create destination dirs
    # internal
    create_remote_dirs(PKG_SERVER_ADDR, PATH + '/' + LICENSE + '/ifw/' + ifw_dest_dir_name)
    # public
    if LICENSE == 'opensource':
        # public server address and path
        ext_server_base_url  = os.environ['EXT_SERVER_BASE_URL']
        ext_server_base_path = os.environ['EXT_SERVER_BASE_PATH']
        # public server directories
        ext_dest_dir = ext_server_base_path + '/snapshots/ifw/' + ifw_dest_dir_name + '/' + TIME_STAMP[:10] + '_' + BUILD_NUMBER
        cmd_args_mkdir_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
        cmd_args_mkdir_ext = cmd_args_mkdir_pkg + ['ssh', ext_server_base_url, 'mkdir', '-p', ext_dest_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_ext, SCRIPT_ROOT_DIR, True)

    if bldinstallercommon.is_win_platform():
        file_list = os.listdir(SCRIPT_ROOT_DIR+'/' + pkg_constants.IFW_BUILD_OUTPUT_DIR)
        for file_name in file_list:
            if file_name.endswith(".7z"):
                cmd_args = [SCP_COMMAND, file_name, PKG_SERVER_ADDR + ':' + PATH + '/' + LICENSE + '/ifw/' + ifw_dest_dir_name + '/']
                bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR + '/' + pkg_constants.IFW_BUILD_OUTPUT_DIR, True)
    else:
        cmd_args = ['rsync', '-r', './', PKG_SERVER_ADDR + ':' + PATH + '/' + LICENSE + '/ifw/' + ifw_dest_dir_name + '/']
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR + '/' + pkg_constants.IFW_BUILD_OUTPUT_DIR, True)

    # copy ifw snapshot to public server
    if LICENSE == 'opensource':
        cmd_args_copy_ifw_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
        cmd_args_copy_ifw_ext = cmd_args_copy_ifw_pkg + ['scp', PATH + '/' + LICENSE + '/ifw/' + ifw_dest_dir_name + '/' + 'installer-framework-build*.7z', ext_server_base_url + ':' + ext_dest_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_copy_ifw_ext, SCRIPT_ROOT_DIR, True)


###############################
# handle_qt_src_package_build
###############################
def handle_qt_src_package_build():
    sanity_check_packaging_server()
    qt_version, qt_version_tag, qt_full_version = parse_qt_version_and_tag(get_release_description_file())
    exec_path = os.path.join(WORK_DIR, 'qt5')
    cmd_args = ['./init-repository', '-f', '--mirror', os.environ['QT5_GIT_MIRROR']]
    exec_path = os.path.join(WORK_DIR, 'qt5')
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
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
    cmd_args += ['-v', qt_full_version, '-m', '-N', '-l', LICENSE]
    cmd_args += module_exclude_list
    # create src package
    bldinstallercommon.do_execute_sub_process(cmd_args, package_path, True)

    # Example injection
    package_name = 'qt-everywhere-' + LICENSE + '-src-' + qt_full_version

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

    ## QTBUG-34967
    # remove 'location' subfolder from examples
    # this is just a workaround that should be removed once QtLocation is officially released
    if os.path.exists(os.path.join(essentials_path, 'location')):
        shutil.rmtree(os.path.join(essentials_path, 'location'))

    cmd_args = ['7z', 'a', os.path.join('..', 'qt5_examples.7z'), '*']
    bldinstallercommon.do_execute_sub_process(cmd_args, essentials_path, True)


    # Create necessary directories
    latest_qt_dir = get_qt_snapshot_dir().latest_qt_dir
    create_remote_dirs(PKG_SERVER_ADDR, os.path.join(latest_qt_dir, 'src', 'single', ''))
    create_remote_dirs(PKG_SERVER_ADDR, os.path.join(latest_qt_dir, 'src', 'submodules', ''))
    create_remote_dirs(PKG_SERVER_ADDR, os.path.join(latest_qt_dir, 'src', 'examples_injection', ''))

    # Upload packages
    exec_path = SCRIPT_ROOT_DIR
    cmd_args = ['rsync', '-r', '../../src_pkg/single/', PKG_SERVER_ADDR + ':' + os.path.join(latest_qt_dir, 'src', 'single', '')]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = ['rsync', '-r', '../../src_pkg/submodules_tar/', PKG_SERVER_ADDR + ':' + os.path.join(latest_qt_dir, 'src', 'submodules', '')]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = ['rsync', '-r', '../../src_pkg/submodules_zip/', PKG_SERVER_ADDR + ':' + os.path.join(latest_qt_dir, 'src', 'submodules', '')]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)

    file_list = os.listdir(package_path)
    for file_name in file_list:
        if file_name.startswith("qt5_examples."):
            cmd_args = ['scp', file_name, PKG_SERVER_ADDR + ':' + os.path.join(latest_qt_dir, 'src', 'examples_injection')]
            bldinstallercommon.do_execute_sub_process(cmd_args, package_path, True)


###############################
# handle_qt_android_release_build
###############################
def handle_qt_android_release_build(qt_full_version):
    cmd_args = ''
    script_path = os.path.join(SCRIPT_ROOT_DIR, 'mkqt5bld.py')
    source_url = SRC_URL+'/single/qt-everywhere-' + LICENSE + '-src-' + qt_full_version

    qt_configure_options_file = get_qt_configuration_options()
    if not os.path.isfile(qt_configure_options_file):
        print('*** No valid qt configutation file found!')
        sys.exit(-1)

    configure_extra_options = os.environ['EXTRA_QT_CONFIGURE_OPTIONS'] if os.environ.get('EXTRA_QT_CONFIGURE_OPTIONS') else ''

    qt_version, qt_version_tag, qt_full_version = parse_qt_version_and_tag(get_release_description_file())
    if LICENSE.lower() == 'enterprise':
        if not 'alpha' in qt_version_tag.lower():
            if bldinstallercommon.is_win_platform():
                configure_extra_options += ' -D QT_EVAL'
            else:
                configure_extra_options += ' -DQT_EVAL'

    android_ndk_host          = os.environ['ANDROID_NDK_HOST']
    android_toolchain_version = os.environ['ANDROID_TOOLCHAIN_VERSION']
    android_api_version       = os.environ['ANDROID_API_VERSION']
    android_sdk_home          = os.environ['ANDROID_SDK_HOME']
    android_ndk_home          = os.environ['ANDROID_NDK_HOME']
    extension = '.tar.gz'
    if bldinstallercommon.is_win_platform():
        extension = '.zip'

    cmd_args = ['python', '-u', script_path, '-u', source_url + extension]
    if bldinstallercommon.is_win_platform():
        cmd_args += ['-m', 'mingw32-make']
    cmd_args += ['-c', qt_configure_options_file]
    cmd_args += ['--android-ndk-host=' + android_ndk_host]          # "linux-x86" or "linux-x86_64" or "windows" or "darwin-x86_64"
    cmd_args += ['--android-api-version=' + android_api_version]    # e.g. "android-10"
    cmd_args += ['--android-sdk-home=' + android_sdk_home]          # e.g. "/opt/android/sdk"
    cmd_args += ['--android-ndk-home=' + android_ndk_home]          # e.g. "/opt/android/ndk"
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
def handle_qt_ios_release_build(qt_full_version):
    cmd_args = ''
    script_path = os.path.join(SCRIPT_ROOT_DIR, 'mkqt5bld.py')
    source_url = SRC_URL+'/single/qt-everywhere-' + LICENSE + '-src-' + qt_full_version

    qt_configure_options_file = get_qt_configuration_options()
    if not os.path.isfile(qt_configure_options_file):
        print('*** No valid qt configutation file found!')
        sys.exit(-1)

    configure_extra_options   = os.environ['EXTRA_QT_CONFIGURE_OPTIONS'] if os.environ.get('EXTRA_QT_CONFIGURE_OPTIONS') else ''

    qt_version, qt_version_tag, qt_full_version = parse_qt_version_and_tag(get_release_description_file())
    if LICENSE.lower() == 'enterprise':
        if not 'alpha' in qt_version_tag.lower():
            configure_extra_options += ' -DQT_EVAL'

    if bldinstallercommon.is_mac_platform():
        if TARGET_ENV.find("x64") >= 1:
            cmd_args = ['python', '-u', script_path, '-u', source_url + '.tar.gz', '-c', qt_configure_options_file, '-a', configure_extra_options + ' -prefix ' + os.path.join(WORK_DIR, MAKE_INSTALL_PADDING)]
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)


###############################
# handle_qt_qnx6_release_build
###############################
def handle_qt_qnx6_release_build(qt_full_version):
    cmd_args = ''
    script_path = os.path.join(SCRIPT_ROOT_DIR, 'mkqt5bld.py')
    source_url = SRC_URL + '/single/qt-everywhere-' + LICENSE + '-src-' + qt_full_version

    qt_configure_options_file = get_qt_configuration_options()
    if not os.path.isfile(qt_configure_options_file):
        print('*** No valid qt configutation file found!')
        sys.exit(-1)

    configure_extra_options   = os.environ['EXTRA_QT_CONFIGURE_OPTIONS'] if os.environ.get('EXTRA_QT_CONFIGURE_OPTIONS') else ''

    qt_version, qt_version_tag, qt_full_version = parse_qt_version_and_tag(get_release_description_file())
    if LICENSE.lower() == 'enterprise':
        if not 'alpha' in qt_version_tag.lower():
            if bldinstallercommon.is_win_platform():
                configure_extra_options += ' -D QT_EVAL'
            else:
                configure_extra_options += ' -DQT_EVAL'

    extension = '.tar.gz'
    if bldinstallercommon.is_win_platform():
        extension = '.zip'

    cmd_args = ['python', '-u', script_path, '-u', source_url + extension]
    if bldinstallercommon.is_win_platform():
        cmd_args += ['-m', 'mingw32-make']
    cmd_args += ['-c', qt_configure_options_file]
    cmd_args += ['-a', configure_extra_options + ' -prefix ' + os.path.join(WORK_DIR,  MAKE_INSTALL_PADDING)]
    if bldinstallercommon.is_linux_platform():
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
    elif bldinstallercommon.is_win_platform():
        exec_dir = os.getcwd()
        bldinstallercommon.do_execute_sub_process(cmd_args, exec_dir, True)

###############################
# Get configuration options
###############################
def get_qt_configuration_options():
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
        if TARGET_ENV in label_list:
            tmp_conf += 'tmp' + str(random.randint(1, 1000))
            break
    if not tmp:
        print('*** No valid configuration for {0} found'.format(TARGET_ENV))
        tmp_conf = ''
    else:
        f = open(tmp_conf,"w")
        f.write(tmp)
        f.close()
    return tmp_conf


###############################
# handle_qt_desktop_release_build
###############################
def handle_qt_desktop_release_build(qt_full_version):
    global EXTRA_ENV
    # Use custom ICU when required (build from sources or use pre-built icu libs)
    if platform.system().lower().startswith('linux'):
        icu_configuration = bld_icu_tools.init_build_icu(ICU_SRC, '', EXTRA_ENV, False)
    ## let's build Qt
    # some common variables
    source_url = SRC_URL + '/single/qt-everywhere-' + LICENSE + '-src-' + qt_full_version

    qt_configure_options_file = get_qt_configuration_options()
    if not os.path.isfile(qt_configure_options_file):
        print('*** No valid qt configutation file found!')
        sys.exit(-1)

    ## common cmd_args for all platforms
    # we need to change the extension to .zip on windows. os x and linux use .tar.gz for the source file (.zip includes configure.exe)
    extension = '.tar.gz'
    if bldinstallercommon.is_win_platform():
        extension = '.zip'
    qt5BuildOptions = mkqt5bld.MkQtBuildOptions()
    qt5BuildOptions.src_url = source_url + extension
    if os.path.exists(os.path.join(WORK_DIR, 'qt-creator')):
        qt5BuildOptions.qt_creator_src_dir = os.path.join(WORK_DIR, 'qt-creator')

    ext_args = os.environ['EXTRA_QT_CONFIGURE_OPTIONS'] if os.environ.get('EXTRA_QT_CONFIGURE_OPTIONS') else ''
    # on windows we build with jom instead of make
    if bldinstallercommon.is_win_platform():
        qt5BuildOptions.make_cmd = 'jom'

    qt_version, qt_version_tag, qt_full_version = parse_qt_version_and_tag(get_release_description_file())
    if LICENSE.lower() == 'enterprise':
        if not 'alpha' in qt_version_tag.lower():
            if bldinstallercommon.is_win_platform():
                ext_args += ' -D QT_EVAL'
            else:
                ext_args += ' -DQT_EVAL'

    # If custom ICU used
    if platform.system().lower().startswith('linux'):
        EXTRA_ENV = combine_environment_dicts(EXTRA_ENV, icu_configuration.environment)
    # run mkqt5bld.py with the correct options according to the platform and license being used
    if bldinstallercommon.is_linux_platform():
        ext_args += ' -prefix ' + os.path.join(WORK_DIR, MAKE_INSTALL_PADDING)
        ext_args += ' -R ' + os.path.join(WORK_DIR, MAKE_INSTALL_PADDING)
    elif bldinstallercommon.is_win_platform():
        ext_args += ' -prefix ' + os.path.join(WORK_DIR, MAKE_INSTALL_PADDING)
    elif bldinstallercommon.is_mac_platform():
        ext_args += ' -prefix ' + os.path.join(WORK_DIR, MAKE_INSTALL_PADDING)
    qt5BuildOptions.configure_options = qt_configure_options_file
    qt5BuildOptions.add_configure_option = ext_args
    qt5BuildOptions.system_env = EXTRA_ENV
    mkqt5bld.QT_BUILD_OPTIONS = qt5BuildOptions
    mkqt5bld.main_call_parameters()


###############################
# Handle extra module release build
###############################
def handle_extra_module_release_build():
    qt_version_minor = os.environ['QT_VERSION_MINOR']
    script_path = os.path.join(SCRIPT_ROOT_DIR, 'bld_app.py')
    icu7z_package = os.environ.get('ICU7Z')
    pkg_storage_server = os.environ['PACKAGE_STORAGE_SERVER_PATH_HTTP']
    build_command = os.environ.get('QT5_APPLICATION_BUILD_CMD')
    install_command = os.environ.get('QT5_APPLICATION_INSTALL_CMD')
    collect_docs_command = os.environ.get('QT5_APPLICATION_COLLECT_DOCS_CMD')
    make_docs_command = os.environ.get('QT5_APPLICATION_MAKE_DOCS_CMD')
    qt5_bin_pkg_base_path = pkg_storage_server + '/' + LICENSE + '/' + 'qt' + '/' + qt_version_minor + '/' + BIN_TARGET_DIRS[TARGET_ENV]
    qt5_essentials_lib_package_uri = qt5_bin_pkg_base_path + '/qt5_essentials.7z'
    qt5_addons_lib_package_uri = qt5_bin_pkg_base_path + '/qt5_addons.7z'
    qt5_webengine_lib_package_url = qt5_bin_pkg_base_path + '/qt5_qtwebengine.7z'
    extra_module_src_uri = pkg_storage_server + '/' + LICENSE + '/' + os.environ.get('APPLICATION_NAME') + '/' + os.environ.get('APPLICATION_VERSION') + '/latest/src/' + os.environ.get('APPLICATION_NAME') + '-' + LICENSE + '-src-' + os.environ.get('APPLICATION_VERSION') + '.7z'

    # build command
    cmd_args = ['python', '-u', script_path, '--clean']
    cmd_args += ['--qt5path', 'qt5_package_dir']
    cmd_args += ['--qt5_essentials7z', qt5_essentials_lib_package_uri]
    cmd_args += ['--qt5_addons7z', qt5_addons_lib_package_uri]
    cmd_args += ['--application7z', extra_module_src_uri]

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
    create_remote_dirs(PKG_SERVER_ADDR, LATEST_EXTRA_MODULE_BINARY_DIR + '/' + BIN_TARGET_DIRS[TARGET_ENV])
    # execute build
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)
    # copy 7z files to network drive
    remote_target_dir = PKG_SERVER_ADDR + ':' + LATEST_EXTRA_MODULE_BINARY_DIR + '/' + BIN_TARGET_DIRS[TARGET_ENV]
    if bldinstallercommon.is_win_platform():
        remote_target_dir += '/'
    remote_copy_archives(remote_target_dir, os.path.join(SCRIPT_ROOT_DIR, 'module_archives'))
    # copy archived doc files to network drive if exists
    local_docs_dir = os.path.join(SCRIPT_ROOT_DIR, 'doc_archives')
    if os.path.exists(local_docs_dir):
        # create remote doc dir
        doc_target_dir = PKG_SERVER_ADDR + ':' + LATEST_EXTRA_MODULE_DIR + '/' + 'doc'
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
def handle_examples_injection():
    # Inject examples
    if bldinstallercommon.is_linux_platform():
        cmd_args = ['wget', SRC_URL + '/examples_injection/qt5_examples.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR + '/module_archives', True)
    else:
        cmd_args = [CURL_COMMAND, '-O', SRC_URL + '/examples_injection/qt5_examples.7z']
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
def handle_qt_release_build():
    sanity_check_packaging_server()
    qt_version, qt_version_tag, qt_full_version = parse_qt_version_and_tag(get_release_description_file())
    # Handle Android build
    if TARGET_ENV.find("Android") >= 1:
        handle_qt_android_release_build(qt_full_version)
    elif TARGET_ENV.find("iOS") >= 1:
        handle_qt_ios_release_build(qt_full_version)
    elif TARGET_ENV.find("QNX") >= 1:
        handle_qt_qnx6_release_build(qt_full_version)
    else:
        handle_qt_desktop_release_build(qt_full_version)

    qt_dir_base   = get_qt_snapshot_dir().snapshot_qt_dir_base
    latest_qt_dir = get_qt_snapshot_dir().latest_qt_dir
    remote_dir    = latest_qt_dir + '/' + BIN_TARGET_DIRS[TARGET_ENV]
    srv_and_remote_dir = PKG_SERVER_ADDR + ':' + remote_dir

    #Upload file also into latest_available_package
    latest_available_pkg = qt_dir_base + '/latest_available_package/' + BIN_TARGET_DIRS[TARGET_ENV]
    srv_and_latest_available_pkg = PKG_SERVER_ADDR + ':' + latest_available_pkg

    # Create target directories
    create_remote_dirs(PKG_SERVER_ADDR, remote_dir)
    create_remote_dirs(PKG_SERVER_ADDR, latest_available_pkg)

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
                if not bldinstallercommon.remote_path_exists(PKG_SERVER_ADDR, doc_archive_on_remote_disk, SSH_COMMAND):
                    cmd_args = [SCP_COMMAND, file_name, PKG_SERVER_ADDR + ':' + latest_qt_dir + '/src/doc/']
                    bldinstallercommon.do_execute_sub_process(cmd_args, local_archives_dir, True)


###############################
# handle_qt_creator_build
###############################
def handle_qt_creator_build():
    sanity_check_packaging_server()

    # Qt Creator directory
    qtcreator_edition_name = os.environ.get('QT_CREATOR_EDITION_NAME')
    dir_path = PATH + LICENSE + '/qtcreator/latest'
    if qtcreator_edition_name:
        dir_path = PATH + LICENSE + '/qtcreator' + '_' + qtcreator_edition_name + '/latest'

    # snapshot directory
    snapshot_path = SNAPSHOT_PATH
    if SNAPSHOT_SERVER and SNAPSHOT_PATH:
        if QTCREATOR_VERSION:
            snapshot_path += '/' + QTCREATOR_VERSION
        cmd_args = [SSH_COMMAND, PKG_SERVER_ADDR, "ssh", SNAPSHOT_SERVER,
            'mkdir', '-p', snapshot_path + '/' + TIME_STAMP[:10] + '_' + BUILD_NUMBER]
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
        cmd_args = [SSH_COMMAND, PKG_SERVER_ADDR, "ssh", SNAPSHOT_SERVER,
            'mkdir', '-p', snapshot_path + '/' + TIME_STAMP[:10] + '_' + BUILD_NUMBER + '/installer_source']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
        cmd_args = [SSH_COMMAND, PKG_SERVER_ADDR, "ssh", SNAPSHOT_SERVER,
            'ln', '-sfn', snapshot_path + '/' + TIME_STAMP[:10] + '_' + BUILD_NUMBER,
                    snapshot_path + '/latest']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
        snapshot_path += '/latest'

    cmd_args = ['python', '-u', 'bld_qtcreator.py',
        '--clean',
        '--qt5path', os.path.normpath('../../qt5_install_dir'),
        '--qt5_essentials7z', SRC_URL + BIN_TARGET_DIRS[TARGET_ENV] + '/qt5_essentials.7z',
        '--qt5_addons7z', SRC_URL + BIN_TARGET_DIRS[TARGET_ENV] + '/qt5_addons.7z',
        '--versiondescription', '"' + QTCREATOR_VERSION_DESCRIPTION + '"']

    if LICENSE == 'enterprise':
        cmd_args.extend(['--additional_plugin', os.path.normpath(WORK_DIR + '/licensechecker'),
                         '--additional_plugin', os.path.normpath(WORK_DIR + '/qmlprofiler'),
                         '--additional_plugin', os.path.normpath(WORK_DIR + '/clangstaticanalyzer'),
                         '--additional_plugin', os.path.normpath(WORK_DIR + '/qtquickdesigner')])
        if bldinstallercommon.is_linux_platform():
            cmd_args.extend(['--additional_plugin', os.path.normpath(WORK_DIR + '/b2qt-qtcreator-plugin')])

    if bldinstallercommon.is_linux_platform():
        cmd_args.extend(['--icu7z', ICU_LIBS])
        if TARGET_ENV.find('64') != -1:
            cmd_args.extend(['--installerbase7z', 'http://ci-files02-hki.ci.local/packages/jenkins/' + LICENSE + '/ifw/1.6/installer-framework-build-linux-x64.7z'])
        else:
            cmd_args.extend(['--installerbase7z', 'http://ci-files02-hki.ci.local/packages/jenkins/' + LICENSE + '/ifw/1.6/installer-framework-build-linux-x86.7z'])
    elif bldinstallercommon.is_mac_platform():
        cmd_args.extend(['--installcommand', 'make -j1',
                         '--installerbase7z', 'http://ci-files02-hki.ci.local/packages/jenkins/' + LICENSE + '/ifw/1.6/installer-framework-build-mac-x64.7z',
                         '--keychain_unlock_script', '/Users/qt/unlock-keychain.sh'])
    else:
        cmd_args.extend(['--buildcommand', os.path.normpath('C:/Utils/jom/jom.exe'),
                         '--installcommand', os.path.normpath('C:/Program Files/Microsoft Visual Studio 10.0/VC/bin/nmake.exe'),
                         '--icu7z', ICU_LIBS,
                         '--sevenzippath', os.path.normpath('C:/Utils/sevenzip'),
                         '--gitpath', os.path.normpath('C:/Program Files/Git/bin'),
                         '--d3dcompiler7z', 'http://download.qt-project.org/development_releases/prebuilt/d3dcompiler/msvc2010/D3DCompiler_43-x86.dll.7z',
                         '--installerbase7z', 'http://ci-files02-hki.ci.local/packages/jenkins/' + LICENSE + '/ifw/1.6/installer-framework-build-win-x86.7z',
                         '--environment_batch', os.path.normpath('C:/Program Files/Microsoft Visual Studio 10.0/VC/vcvarsall.bat'),
                         '--environment_batch_argument', 'x86'])
        if OPENSSL_LIBS:
            cmd_args.extend(['--openssl7z', OPENSSL_LIBS])

    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)

    if bldinstallercommon.is_mac_platform():
        lock_keychain()

    postfix = ''
    if QTCREATOR_VERSION:
        postfix = '-' + QTCREATOR_VERSION
    file_upload_list = [] # pairs (source, dest), source relative to WORK_DIR, dest relative to server + dir_path
    snapshot_upload_list = [] # pairs (source, dest), source relative to server + dir_path, dest relative to snapshot server + snapshot_path
    if bldinstallercommon.is_linux_platform():
        linux_bits = '32'
        linux_arch = 'x86'
        if TARGET_ENV.find('64') != -1:
            linux_bits = '64'
            linux_arch = 'x86_64'
        file_upload_list.append(('qt-creator_build/qt-creator-installer-archive.7z', 'qtcreator_linux_gcc_' + linux_bits + '_ubuntu1110.7z'))
        file_upload_list.append(('qt-creator_build/qt-creator.run', 'qt-creator-' + LICENSE + '-linux-' + linux_arch + postfix + '.run'))
        snapshot_upload_list.append(('qtcreator_linux_gcc_' + linux_bits + '_ubuntu1110.7z', 'installer_source/'))
        snapshot_upload_list.append(('qt-creator-' + LICENSE + '-linux-' + linux_arch + postfix + '.run', ''))
    elif bldinstallercommon.is_mac_platform():
        file_upload_list.append(('qt-creator_build/qt-creator-installer-archive.7z', 'qtcreator_mac_cocoa_10_7.7z'))
        if LICENSE == 'opensource': # opensource gets pure disk image with app and license.txt
            file_upload_list.append(('qt-creator_build/qt-creator.dmg', 'qt-creator-' + LICENSE + '-mac-x86_64' + postfix + '.dmg'))
        else: # enterprise gets installer with license check
            file_upload_list.append(('qt-creator_build/qt-creator-installer.dmg', 'qt-creator-' + LICENSE + '-mac-x86_64' + postfix + '.dmg'))
        snapshot_upload_list.append(('qtcreator_mac_cocoa_10_7.7z', 'installer_source/'))
        snapshot_upload_list.append(('qt-creator-' + LICENSE + '-mac-x86_64' + postfix + '.dmg', ''))
    else: # --> windows
        file_upload_list.append(('qt-creator_build/qt-creator-installer-archive.7z', 'qtcreator_windows_vs2010_32.7z'))
        sign_windows_executable('qt-creator_build/qt-creator.exe', WORK_DIR, True)
        file_upload_list.append(('qt-creator_build/qt-creator.exe', 'qt-creator-' + LICENSE + '-windows-x86' + postfix + '.exe'))
        snapshot_upload_list.append(('qtcreator_windows_vs2010_32.7z', 'installer_source/'))
        snapshot_upload_list.append(('qt-creator-' + LICENSE + '-windows-x86' + postfix + '.exe', ''))

    # upload files
    for source, destination in file_upload_list:
        cmd_args = [SCP_COMMAND, source, PKG_SERVER_ADDR + ':' + dir_path + '/' + destination]
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
    if SNAPSHOT_SERVER and SNAPSHOT_PATH:
        for source, destination in snapshot_upload_list:
            cmd_args = [SSH_COMMAND, PKG_SERVER_ADDR, "scp",
                dir_path + '/' + source,
                SNAPSHOT_SERVER + ':' + snapshot_path + '/' + destination]
            bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)


###############################
# handle_offline_installer_build
###############################
def handle_offline_installer_build():
    handle_installer_build('offline')


###############################
# handle_online_installer_build
###############################
def handle_online_installer_build():
    handle_installer_build('online')


###############################
# save_latest_successful_installer
###############################
def save_latest_successful_installer(qt_full_version, installer_name, installer_name_final, ls_installer_dir, installer_output):
    # check installer type
    if 'online' in installer_name_final.lower():
        regex = re.compile('.*online')
        if "embedded" in installer_name_final.lower():
            regex = re.compile('.*online(?:(?!_\d{4}).)*')
    else:
        regex = re.compile('.*' + qt_full_version)
    installer_base_name = "".join(regex.findall(installer_name_final))
    if not installer_base_name:
        print('*** Empty installer base name string')
    else:
        old_installer = ls_installer_dir + '/' + installer_base_name + '*'
        # delete old installer
        cmd_args = [SSH_COMMAND, PKG_SERVER_ADDR, 'rm', old_installer]
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, False)
        # save new installer to latest_successful directory
        cmd_args = [SCP_COMMAND, installer_name, PKG_SERVER_ADDR + ':' + ls_installer_dir + '/' + installer_name_final]
        bldinstallercommon.do_execute_sub_process(cmd_args, installer_output, True)


###############################
# generic handle installer build
###############################
def handle_installer_build(installer_type):
    sanity_check_packaging_server()
    qt_version, qt_version_tag, qt_full_version = parse_qt_version_and_tag(get_release_description_file())
    conf_file = os.environ['RELEASE_BUILD_CONF_FILE']
    if not os.path.exists(conf_file):
        print('*** The given file does not exist: {0}'.format(conf_file))
        sys.exit(-1)
    branch = 'release' # TODO
    if TARGET_ENV.find('64') != -1:
        arch = 'x64'
    else:
        arch = 'x86'
    # Internal server address
    packages_base_url = os.environ['PKG_SERVER_URL']
    # determine local installer output directory
    installer_output_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.INSTALLER_OUTPUT_DIR_NAME)
    # (1) create all installers for this host
    release_build_handler.handle_installer_build(conf_file, installer_type, LICENSE, branch, PLATFORM, arch, packages_base_url)
    temp_path = '/' + installer_type + '_installers/'
    # Create remote directories
    remote_dest_dir = PATH + '/' + LICENSE + temp_path + TIME_STAMP[:10] + '_' + BUILD_NUMBER
    latest_dir = PATH + '/' + LICENSE + temp_path + 'latest'
    latest_successful_dir = PATH + '/' + LICENSE + temp_path + 'latest_successful'
    create_remote_dirs(PKG_SERVER_ADDR, remote_dest_dir)
    create_remote_dirs(PKG_SERVER_ADDR, latest_successful_dir)
    # Create remote dirs in opensource distribution server
    if LICENSE == 'opensource':
        # opensource distribution server address and path
        ext_server_base_url  = os.environ['EXT_SERVER_BASE_URL']
        ext_server_base_path = os.environ['EXT_SERVER_BASE_PATH']
        # opensource distribution server directories
        ext_dest_dir = ext_server_base_path + '/snapshots/qt/' + qt_version[:3] + '/' + qt_full_version + '/' + TIME_STAMP[:10] + '_' + BUILD_NUMBER
        cmd_args_mkdir_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
        cmd_args_mkdir_ext = cmd_args_mkdir_pkg + ['ssh', ext_server_base_url, 'mkdir -p', ext_dest_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_ext, SCRIPT_ROOT_DIR, True)

    # (2) copy all installers from 'installer_output_dir' into network disk
    installer_name = ''
    installer_name_base = ''
    dir_list = os.listdir(installer_output_dir)
    for file_name in dir_list:
        installer_name, installer_name_base, installer_name_final = generate_installer_final_name(file_name)
        if not (installer_name and installer_name_base and installer_name_final):
            print('*** Skipped file: {0}'.format(file_name))
            continue
        # sign
        sign_installer(installer_output_dir, installer_name, installer_name_base)
        # copy installer to internal server
        remote_copy_installer(remote_dest_dir, installer_name, installer_output_dir, installer_name_final)
        # remove old successful and save latest successful installer
        save_latest_successful_installer(qt_full_version, installer_name, installer_name_final, latest_successful_dir, installer_output_dir)
        # copy installer to mirror brain server
        if LICENSE == 'opensource':
            remote_copy_installer_opensource(remote_dest_dir, ext_server_base_url, ext_dest_dir, installer_name_final)

    #Update latest link
    update_latest_link(remote_dest_dir, latest_dir)

    # copy rta description file(s) to network drive
    rta_descr_output_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.RTA_DESCRIPTION_FILE_DIR_NAME)
    for file_name in rta_descr_output_dir:
        if file_name.startswith(pkg_constants.RTA_DESCRIPTION_FILE_NAME_BASE):
            cmd_args = [SCP_COMMAND, file_name, PKG_SERVER_ADDR + ':' + remote_dest_dir + '/' + file_name]
            bldinstallercommon.do_execute_sub_process(cmd_args, installer_output_dir, True)
    # (3) trigger rta cases
    rta_descr_output_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.RTA_DESCRIPTION_FILE_DIR_NAME)
    trigger_rta(rta_descr_output_dir)


###############################
# Sign installer
###############################
def sign_installer(installer_output_dir, installer_name, installer_name_base):
    if installer_name.endswith(".dmg"):
        unlock_keychain()
        sign_mac_executable(installer_name_base + '.app', installer_output_dir, True)
        cmd_args = ['hdiutil', 'create', '-srcfolder', os.path.join(installer_output_dir, installer_name_base) + '.app', '-volname', installer_name_base, '-format', 'UDBZ', os.path.join(installer_output_dir, installer_name_base) + '.dmg', '-ov', '-scrub', '-size', '2g']
        bldinstallercommon.do_execute_sub_process(cmd_args, installer_output_dir, True)
    if installer_name.endswith(".exe"):
        sign_windows_executable(installer_name, installer_output_dir, True)


###############################
# Remote copy installer
###############################
def remote_copy_installer(remote_dest_dir, file_name, installer_output_dir, installer_name_final):
    cmd_args = [SCP_COMMAND, file_name, PKG_SERVER_ADDR + ':' + remote_dest_dir + '/' + installer_name_final]
    bldinstallercommon.do_execute_sub_process(cmd_args, installer_output_dir, True)


###############################
# Remote copy installer (Opensource)
###############################
def remote_copy_installer_opensource(remote_dest_dir, ext_server_base_url, ext_dest_dir, installer_name_final):
    # copy installer to mirror brain server
    if LICENSE == 'opensource':
        cmd_args_copy_to_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
        cmd_args_copy_to_ext = cmd_args_copy_to_pkg + ['scp', remote_dest_dir + '/' + installer_name_final, ext_server_base_url + ':' + ext_dest_dir  + '/' + installer_name_final]
        bldinstallercommon.do_execute_sub_process(cmd_args_copy_to_ext, SCRIPT_ROOT_DIR, True)


###############################
# Helper to generate installer final name
###############################
def generate_installer_final_name(file_name):
    installer_name = ''
    installer_name_base = ''
    installer_name_final = ''
    # Linux
    if file_name.endswith(".run"):
        installer_name = file_name
        installer_name_base = os.path.splitext(file_name)[0]
        installer_name_final = installer_name_base + '_' + TIME_STAMP + '-' + BUILD_NUMBER + '.run'
    # Mac
    if file_name.endswith(".dmg"):
        installer_name = file_name
        installer_name_base = os.path.splitext(file_name)[0]
        installer_name_final = installer_name_base + '_' + TIME_STAMP + '-' + BUILD_NUMBER + '.dmg'
    # Windows
    if file_name.endswith(".exe"):
        installer_name = file_name
        installer_name_base = os.path.splitext(file_name)[0]
        installer_name_final = installer_name_base + '_' + TIME_STAMP + '-' + BUILD_NUMBER + '.exe'
    return installer_name, installer_name_base, installer_name_final


###############################
# Update latest link
###############################
def update_latest_link(remote_dest_dir, latest_dir):
    cmd_args = [SSH_COMMAND, PKG_SERVER_ADDR, 'ln -sfn', remote_dest_dir, latest_dir]
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
    release_build_handler.handle_repo_build(conf_file, LICENSE, 'release', PLATFORM, arch, packages_base_url, update_staging_repo, update_production_repo)
    # (3) trigger rta cases
    rta_descr_output_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.RTA_DESCRIPTION_FILE_DIR_NAME)
    trigger_rta(rta_descr_output_dir)


###############################
# copy_license_checkers
###############################
def copy_license_checkers():
    sanity_check_packaging_server()
    latest_qt_dir = get_qt_snapshot_dir().latest_qt_dir
    exec_path = os.path.join(WORK_DIR, 'qt5', 'qtbase', 'bin')
    cmd_args = [SCP_COMMAND, PKG_SERVER_ADDR + ':' + os.path.join(latest_qt_dir, 'src', 'licheck', 'licheck.exe'), '.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = [SCP_COMMAND, PKG_SERVER_ADDR + ':' + os.path.join(latest_qt_dir, 'src', 'licheck', 'licheck32'), '.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = [SCP_COMMAND, PKG_SERVER_ADDR + ':' + os.path.join(latest_qt_dir, 'src', 'licheck', 'licheck64'), '.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = [SCP_COMMAND, PKG_SERVER_ADDR + ':' + os.path.join(latest_qt_dir, 'src', 'licheck', 'licheck_mac'), '.']
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
def publish_qt5_src_packages():
    # Mirror Brain server address and path
    ext_server_base_url  = os.environ['EXT_SERVER_BASE_URL']
    ext_server_base_path = os.environ['EXT_SERVER_BASE_PATH']

    qt_version, qt_version_tag, qt_full_version = parse_qt_version_and_tag(get_release_description_file())
    ext_dest_dir = ext_server_base_path + '/snapshots/qt/' + qt_version[:3] + '/' + qt_full_version + '/' + TIME_STAMP[:10] + '_' + BUILD_NUMBER

    # copy source packages to public server
    if LICENSE == 'opensource':
        # create source directories
        latest_qt_dir = get_qt_snapshot_dir().latest_qt_dir
        cmd_args_mkdir_src_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
        cmd_args_mkdir_src_ext = cmd_args_mkdir_src_pkg + ['ssh', ext_server_base_url, 'mkdir', '-p', ext_dest_dir + '/' + 'single']
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_src_ext, SCRIPT_ROOT_DIR, True)
        cmd_args_mkdir_src_ext = cmd_args_mkdir_src_pkg + ['ssh', ext_server_base_url, 'mkdir', '-p', ext_dest_dir + '/' + 'submodules']
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_src_ext, SCRIPT_ROOT_DIR, True)
        # copy the source packages to the remove directory
        cmd_args_copy_src_to_pkg = [SSH_COMMAND, PKG_SERVER_ADDR]
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
def initialize_icu_build():
    sanity_check_packaging_server()
    remote_snaphot_dir_base = PATH + '/' + 'icu' + '/' + os.environ['ICU_VERSION']
    remote_snaphot_dir = remote_snaphot_dir_base + '/' + TIME_STAMP + '-' + BUILD_NUMBER
    remote_latest_dir = remote_snaphot_dir_base + '/' + 'latest'
    # create remote snapshot dir
    create_remote_dirs(PKG_SERVER_ADDR, remote_snaphot_dir)
    # update latest symlink
    update_latest_link(remote_snaphot_dir, remote_latest_dir)


###############################
# Handle ICU builds
###############################
def handle_icu_build():
    if os.environ.get('ICU_SRC_PKG_URL'):
        icu_src = os.environ['ICU_SRC_PKG_URL']
    elif platform.system().lower().startswith('win'):
        icu_src = os.environ['ICU_SRC_PKG_URL_WIN']
    else:
        icu_src = os.environ['ICU_SRC_PKG_URL_UNIX']
    icu_version = '' # can be left empty, not cloning from git
    sanity_check_packaging_server()
    bld_icu_tools.init_build_icu(icu_src, icu_version, True)
    # define remote dir where to upload
    remote_snaphot_dir = PATH + '/' + 'icu' + '/' + os.environ['ICU_VERSION'] + '/' + 'latest'
    srv_and_remote_dir = PKG_SERVER_ADDR + ':' + remote_snaphot_dir
    # check the build artifacts
    local_archives_dir = bldinstallercommon.locate_directory(SCRIPT_ROOT_DIR, ICU_BUILD_OUTPUT_DIR)
    dir_list = os.listdir(local_archives_dir)
    for file_name in dir_list:
        if file_name.endswith('.7z'):
            cmd_args = [SCP_COMMAND, file_name, srv_and_remote_dir + '/']
            bldinstallercommon.do_execute_sub_process(cmd_args, local_archives_dir, True)


###############################
# parse_cmd_line
###############################
def parse_cmd_line():
    global COMMAND
    global LICENSE
    global TIME_STAMP
    global BUILD_NUMBER
    global PKG_SERVER_ADDR
    global PATH
    global TARGET_ENV
    global ICU_LIBS
    global ICU_SRC
    global OPENSSL_LIBS
    global SRC_URL
    global REMOTE_EXTRA_MODULE_DIR
    global LATEST_EXTRA_MODULE_DIR
    global REMOTE_EXTRA_MODULE_BINARY_DIR
    global LATEST_EXTRA_MODULE_BINARY_DIR
    global PLATFORM
    global QTCREATOR_VERSION
    global QTCREATOR_VERSION_DESCRIPTION
    global SNAPSHOT_SERVER
    global SNAPSHOT_PATH

    setup_option_parser()
    arg_count = len(sys.argv)
    if arg_count < 2:
        OPTION_PARSER.print_help()
        sys.exit(-1)

    (options, args) = OPTION_PARSER.parse_args()
    COMMAND = options.command
    bld_cmd_validator = BldCommand(options)
    if bld_cmd_validator.validate_bld_args():
        COMMAND           = options.command
        LICENSE           = options.license
        TIME_STAMP        = options.time_stamp
        BUILD_NUMBER      = options.build_number
        PKG_SERVER_ADDR   = options.server
        PATH              = options.path
        SNAPSHOT_SERVER   = options.snapshot_server
        SNAPSHOT_PATH     = options.snapshot_path
        TARGET_ENV        = options.target_env
        ICU_LIBS          = options.icu_libs
        ICU_SRC           = options.icu_src
        OPENSSL_LIBS      = options.openssl_libs
        SRC_URL           = options.src_url
        QTCREATOR_VERSION = options.qtcreator_version
        QTCREATOR_VERSION_DESCRIPTION = options.qtcreator_version_description
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

    # define LATEST directories for extra module src & doc & examples packages
    REMOTE_EXTRA_MODULE_DIR = PATH + '/' + LICENSE + '/'
    LATEST_EXTRA_MODULE_DIR = PATH + '/' + LICENSE + '/'
    # define LATEST directories for extra module binary packages
    REMOTE_EXTRA_MODULE_BINARY_DIR = PATH + '/' + LICENSE + '/'
    LATEST_EXTRA_MODULE_BINARY_DIR = PATH + '/' + LICENSE + '/'

    # create output directories for extra module build
    if os.environ.get('APPLICATION_NAME'):
        # create directories for extra module src files
        app_name = os.environ['APPLICATION_NAME']
        app_ver  = os.environ['APPLICATION_VERSION']
        REMOTE_EXTRA_MODULE_DIR += app_name + '/' + app_ver + '/' + TIME_STAMP + '-' + BUILD_NUMBER
        LATEST_EXTRA_MODULE_DIR += app_name + '/' + app_ver + '/' + 'latest'
        # create directories for extra module binaries
        # QT_VERSION_MINOR indicates that this is a binary build
        if os.environ.get('QT_VERSION_MINOR'):
            REMOTE_EXTRA_MODULE_BINARY_DIR += app_name + '/' + app_ver + '/' + os.environ.get('QT_VERSION_MINOR') + '/' + TIME_STAMP + '-' + BUILD_NUMBER
            LATEST_EXTRA_MODULE_BINARY_DIR += app_name + '/' + app_ver + '/' + os.environ.get('QT_VERSION_MINOR') + '/' + 'latest'

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
    OPTION_PARSER.add_option("--icu_src",
                      action="store", type="string", dest="icu_src", default="",
                      help="Url for icu src package to be used for the Qt build")
    OPTION_PARSER.add_option("-o", "--openssl_libs",
                      action="store", type="string", dest="openssl_libs", default="",
                      help="Url for pre-compiled openssl libraries")
    OPTION_PARSER.add_option("-u", "--src_url",
                      action="store", type="string", dest="src_url", default="",
                      help="Url for source code")
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

    parse_cmd_line()
    # Qt5 specific
    if COMMAND == BldCommand.init_build_cycle:
        initialize_qt5_build()
    elif COMMAND == BldCommand.execute_qt5_src_pkg:
        handle_qt_src_package_build()
    elif COMMAND == BldCommand.execute_qt5_bin_bld:
        handle_qt_release_build()
    elif COMMAND == BldCommand.publish_qt5_src_pkg:
        publish_qt5_src_packages()
    # Extra module specific
    elif COMMAND == BldCommand.init_extra_module_build_cycle_src:
        initialize_extra_module_build_src()
    elif COMMAND == BldCommand.execute_extra_module_build_cycle_src:
        build_extra_module_src_pkg()
    elif COMMAND == BldCommand.init_extra_module_build_cycle_binary:
        initialize_extra_module_binary_build()
    elif COMMAND == BldCommand.execute_extra_module_build_cycle_binary:
        handle_extra_module_release_build()
    # QtCreator specific
    elif COMMAND == BldCommand.init_qtcreator_build_cycle:
        initialize_qtcreator_build()
    elif COMMAND == BldCommand.execute_creator_bld:
        handle_qt_creator_build()
    # Qt Installer-Framework specific
    elif COMMAND == BldCommand.execute_ifw_bld:
        handle_ifw_build()
    # Installer build specific
    elif COMMAND == BldCommand.execute_repo_bld:
        handle_online_repository_build()
    elif COMMAND == BldCommand.execute_offline_inst_bld:
        handle_offline_installer_build()
    elif COMMAND == BldCommand.execute_online_inst_bld:
        handle_online_installer_build()
    elif COMMAND == BldCommand.execute_configure_exe_bld:
        handle_qt_configure_exe_build()
    elif COMMAND == BldCommand.init_icu_bld:
        initialize_icu_build()
    elif COMMAND == BldCommand.execute_icu_bld:
        handle_icu_build()
    else:
        print('Unsupported command')


if __name__ == "__main__":
    main()

