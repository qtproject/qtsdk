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
import collections
from glob import glob
import os
import sys
import re
import platform
import urllib
import bld_ifw_tools
from bld_ifw_tools import IfwOptions
import bld_utils

from optparse import OptionParser, Option

import bldinstallercommon
import release_build_handler
import bld_icu_tools
import pkg_constants
from pkg_constants import ICU_BUILD_OUTPUT_DIR


# ----------------------------------------------------------------------
# external commands
CURL_COMMAND                = ''
RM_COMMAND                  = ''
SSH_COMMAND                 = ''
SCP_COMMAND                 = ''

# ----------------------------------------------------------------------
SCRIPT_ROOT_DIR             = os.path.dirname(os.path.realpath(__file__))
REPO_OUTPUT_DIR             = os.path.normpath(os.path.join(SCRIPT_ROOT_DIR, 'repository'))
WORK_DIR                    = os.path.join(os.environ['PKG_NODE_ROOT'], 'build')
OPTION_PARSER               = 0
QTCREATOR_VERSION           = ''
QTCREATOR_VERSION_DESCRIPTION = ''
PLATFORM                    = ''
BIN_TARGET_DIRS             = {} # dictionary populated based on the /packaging-tools/releases/build-meta
CI_TARGET_POSTFIX           = {} # dictionary populated based on the /packaging-tools/releases/build-meta
EXTRA_ENV                   = dict(os.environ)
BUILD_META_INFO_FILE        = 'releases/build-meta'




###########################################
# Environment variable combining
###########################################
def combine_env_variable(a, b):
    if platform.system().lower().startswith('win'):
        return a + ';' + b
    else :
        return a + ':' + b

def combine_environment_dicts(a, b):
    return dict(a.items() + b.items() +
                [(k, combine_env_variable(a[k], b[k])) for k in set(b) & set(a)])


###########################################
# Define possible commands for this script
###########################################
class BldCommand:
    execute_ifw_bld                         = 'ifw'
    execute_creator_bld                     = 'build_creator'
    execute_gammaray_bld                    = 'build_gammaray'
    execute_repo_bld                        = 'repo_build'
    execute_offline_inst_bld                = 'offline_installer'
    execute_online_inst_bld                 = 'online_installer'
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
            raise RuntimeError('*** License unknown: %s' % self.license)
        # cfg
        self.target_env = options.target_env
        if not self.target_env:
            self.target_env = os.environ.get('cfg')
        # unique build number specifiers
        self.build_number = options.build_number
        if not self.build_number:
            self.build_number = os.environ.get('BUILD_NUMBER')
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
            version_num = int(''.join(re.findall(r'\d+', self.version)))
            if version_num >= 560:
                qt_pkg_url = self.pkg_server_addr_http
            else:
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
        if os.environ.get('MODULE_NAME'):
            self.package_storage_server_user = os.environ['PACKAGE_STORAGE_SERVER_USER']
            self.package_storage_server = os.environ['PACKAGE_STORAGE_SERVER']
            self.package_storage_server_base_dir = os.environ['PACKAGE_STORAGE_SERVER_BASE_DIR']
            # create directories for extra module src files
            self.module_name = os.environ['MODULE_NAME']
            self.module_version = os.environ['MODULE_VERSION']
            self.remote_extra_module_dir += self.module_name + '/' + self.module_version + '/' + self.build_number
            self.latest_extra_module_dir += self.module_name + '/' + self.module_version + '/' + 'latest'
            # create directories for extra module binaries
            # QT_VERSION_MINOR indicates that this is a binary build
            if os.environ.get('QT_VERSION_MINOR'):
                self.remote_extra_module_binary_dir += self.module_name + '/' + self.module_version + '/' + os.environ.get('QT_VERSION_MINOR') + '/' +  os.environ.get('BUILD_NUMBER')
                self.latest_extra_module_binary_dir += self.module_name + '/' + self.module_version + '/' + os.environ.get('QT_VERSION_MINOR') + '/' + 'latest'


    ###########################################
    # Validate the given command
    ###########################################
    def is_valid_cmd(self):
        commands = [self.execute_ifw_bld]
        commands += [self.execute_creator_bld]
        commands += [self.execute_gammaray_bld]
        commands += [self.execute_repo_bld]
        commands += [self.execute_offline_inst_bld]
        commands += [self.execute_online_inst_bld]
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
        return True

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
        raise RuntimeError('*** Error - Packaging server address not defined?')

###############################
# sign windows executable
###############################
def sign_windows_executable(file_path, working_dir, abort_on_fail):
    cmd_args = [r'C:\Utils\sign\signtool.exe', 'sign', '/v', '/du', os.environ['SIGNING_SERVER'], '/p', os.environ['SIGNING_PASSWORD'],
                '/t', 'http://timestamp.verisign.com/scripts/timestamp.dll', '/f', r'C:\utils\sign\keys.pfx', file_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, working_dir, abort_on_fail)


###############################
# Unlock keychain
###############################
def unlock_keychain():
    cmd_args = ['/Users/qt/unlock-keychain.sh']
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)


###############################
# Lock keychain
###############################
def lock_keychain():
    cmd_args = ['/Users/qt/lock-keychain.sh']
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)


###############################
# sign windows executable
###############################
def sign_mac_executable(file_path, working_dir, abort_on_fail):
    s_arg = 'Developer ID Application: The Qt Company Oy'
    cmd_args = ['codesign', '-r', '/Users/qt/csreq_qt_company.txt', '-s', s_arg, file_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, working_dir, abort_on_fail)


###############################
# handle_qt_licheck_build
###############################
def handle_qt_licheck_build(bld_command):
    if bld_command.license == 'enterprise':
        # Build license checker
        exe_dir = WORK_DIR + '/license-managing/licheck'
        upload_path = bld_command.pkg_server_addr + ':' + bld_command.path + '/' + bld_command.license + '/licheck/'
        if bld_command.target_env.lower().startswith("win"):
            cmd_args = [r'c:\Utils\jom\jom.exe', '-f', 'Makefile_win']
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
            cmd_args = ['make', '-j6', '-f', 'Makefile_osx']
            bldinstallercommon.do_execute_sub_process(cmd_args, exe_dir, True)
            cmd_args = ['strip', 'licheck']
            bldinstallercommon.do_execute_sub_process(cmd_args, exe_dir, True)
            cmd_args = ['rsync', '-r', 'licheck', upload_path +'licheck_mac']
            bldinstallercommon.do_execute_sub_process(cmd_args, exe_dir, True)
    else:
        #opensource, do nothing
        print('*** opensource build, nothing to build ...')


###############################
# handle_ifw_build()
###############################
def handle_ifw_build(bld_command):
    sanity_check_packaging_server(bld_command)
    os.chdir(SCRIPT_ROOT_DIR)
    # Qt
    qt_src_pkg = os.environ['IFW_QT_SRC_PKG'] # mandatory env variable
    # OpenSSL
    openssl_dir = os.environ.get('IFW_OPENSSL_DIR')
    qt_configure_options = bld_ifw_tools.get_default_qt_configure_options(openssl_dir)
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
        product_key_checker_pri = os.environ.get('PRODUCT_KEY_CHECKER_PRI')
        if product_key_checker_pri:
            temp = bldinstallercommon.locate_file(os.environ['PKG_NODE_ROOT'], product_key_checker_pri)
            product_key_checker_pri = temp if temp else product_key_checker_pri

    # options object for ifw build
    ifw_bld_options = IfwOptions(qt_src_pkg,
                                 qt_configure_options,
                                 ifw_url, ifw_branch,
                                 ifw_qmake_args,
                                 product_key_checker_pri,
                                 False)
    # build ifw tools
    bld_ifw_installer = True if os.environ.get('CREATE_IFW_INSTALLER') else False
    bld_ifw_tools.build_ifw(ifw_bld_options, bld_ifw_installer)

    ## create destination dirs on network disk
    # internal
    create_remote_dirs(bld_command.pkg_server_addr, bld_command.path + '/' + bld_command.license + '/ifw/' + ifw_dest_dir_name)
    # public
    if bld_command.license == 'opensource':
        # public server address and path
        ext_server_base_url  = os.environ['EXT_SERVER_BASE_URL']
        ext_server_base_path = os.environ['EXT_SERVER_BASE_PATH']
        # public server directories
        ext_dest_dir = ext_server_base_path + '/snapshots/ifw/' + ifw_dest_dir_name + '/' + bld_command.build_number
        cmd_args_mkdir_pkg = [SSH_COMMAND, bld_command.pkg_server_addr]
        cmd_args_mkdir_ext = cmd_args_mkdir_pkg + ['ssh', ext_server_base_url, 'mkdir', '-p', ext_dest_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_ext, SCRIPT_ROOT_DIR)

    artifacts_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.IFW_BUILD_ARTIFACTS_DIR)
    # Create disk image(s) if any .app found
    if bldinstallercommon.is_mac_platform():
        artifact_list = [f for f in os.listdir(artifacts_dir) if f.endswith(".app")]
        for item in artifact_list:
            base_name = item.split(".app")[0]
            # create disk image
            cmd_args = ['hdiutil', 'create', '-srcfolder', os.path.join(artifacts_dir, item),
                        '-volname', base_name, '-format', 'UDBZ',
                        os.path.join(artifacts_dir, base_name + '.dmg'),
                        '-ov', '-scrub', '-size', '1g']
            bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)
    # Sign if there is anything to be signed
    file_list = [f for f in os.listdir(artifacts_dir) if f.endswith((".dmg", ".run", ".exe"))]
    for file_name in file_list:
        installer_name, installer_name_base, installer_name_final = generate_installer_final_name(bld_command, file_name)
        sign_installer(artifacts_dir, installer_name, installer_name_base)
    # Upload
    files_to_upload = [f for f in os.listdir(artifacts_dir) if f.endswith((".dmg", ".run", ".exe", ".7z"))]
    for item in files_to_upload:
        if bldinstallercommon.is_win_platform():
            cmd_args = [SCP_COMMAND, item, bld_command.pkg_server_addr + ':' + bld_command.path + '/' + bld_command.license + '/ifw/' + ifw_dest_dir_name + '/']
        else:
            cmd_args = ['rsync', '-r', './', bld_command.pkg_server_addr + ':' + bld_command.path + '/' + bld_command.license + '/ifw/' + ifw_dest_dir_name + '/']
        bldinstallercommon.do_execute_sub_process(cmd_args, artifacts_dir)
    # Copy ifw .7z files to public server
    if bld_command.license == 'opensource':
        cmd_args_copy_ifw_pkg = [SSH_COMMAND, bld_command.pkg_server_addr]
        cmd_args_copy_ifw_ext = cmd_args_copy_ifw_pkg + ['scp', bld_command.path + '/' + bld_command.license + '/ifw/' + ifw_dest_dir_name + '/' + 'installer-framework-build*.7z', ext_server_base_url + ':' + ext_dest_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_copy_ifw_ext, SCRIPT_ROOT_DIR)


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
            bldinstallercommon.do_execute_sub_process(cmd_args, from_where_path)


###############################
# Generate binary target dictionary
###############################
def generate_bin_target_dictionary():
    global BIN_TARGET_DIRS
    global CI_TARGET_POSTFIX
    # parse module exclude list from release description file
    conf_file_base_path = os.path.join(SCRIPT_ROOT_DIR, BUILD_META_INFO_FILE)
    if not os.path.isfile(conf_file_base_path):
        raise IOError('*** Not a valid release description file: %s' % conf_file_base_path)
    parser = ConfigParser.ConfigParser()
    parser.readfp(open(conf_file_base_path))
    # parse
    for s in parser.sections():
        section_parts = s.split('.')
        if section_parts[0] != 'meta':
            continue
        build_target_dir = bldinstallercommon.safe_config_key_fetch(parser, s, 'build_target_dir')
        ci_target_postfix = bldinstallercommon.safe_config_key_fetch(parser, s, 'ci_target_postfix')
        build_node_labels = bldinstallercommon.safe_config_key_fetch(parser, s, 'build_node_labels').replace(' ', '')
        label_list = build_node_labels.split(',')
        if not build_target_dir:
            raise RuntimeError('*** No build target directory defined for: %s' % s)
        if not label_list:
            raise RuntimeError('*** No build slave label defined for: %s' % s)
        for label in label_list:
            BIN_TARGET_DIRS[label] = build_target_dir
            if ci_target_postfix:
                CI_TARGET_POSTFIX[label] = ci_target_postfix


###############################
# handle_gammaray_build
###############################
def handle_gammaray_build(bld_command):
    sanity_check_packaging_server(bld_command)
    gammaray_version = os.environ['GAMMARAY_VERSION']
    graphviz_filename = os.environ['GRAPHVIZ_BASE_FILENAME'] + '-' + bld_command.target_env + '.7z'
    graphviz_url = (bld_command.pkg_server_addr_http + '/' + os.environ['GRAPHVIZ_BASE_PATH']
                    + '/' + graphviz_filename)
    graphviz_download_filepath = os.path.join(WORK_DIR, graphviz_filename)
    graphviz_target_path = os.path.join(WORK_DIR, 'graphviz')
    qt_base_path = os.environ['QT_BASE_PATH']
    qt_module_urls = []
    if "/5.5" in qt_base_path: # Qt 5.5 compat mode
        qt_modules = ['essentials', 'addons']
        qt_base_url = (bld_command.pkg_server_addr_http + '/' + qt_base_path
                       + '/' + BIN_TARGET_DIRS[bld_command.target_env])
        qt_module_urls = [qt_base_url + '/qt5_' + module + '.7z' for module in qt_modules]
    else:
        qt_modules = ['qtbase', 'qtdeclarative', 'qtscript', 'qtxmlpatterns']
        qt_base_url = bld_command.pkg_server_addr_http + '/' + qt_base_path
        qt_postfix = CI_TARGET_POSTFIX[bld_command.target_env]
        qt_module_urls = [qt_base_url + '/' + module + '/' + module + '-' + qt_postfix + '.7z'
                          for module in qt_modules]

    # download and extract graphviz
    bld_utils.download(graphviz_url, graphviz_download_filepath)
    extract_graphviz_cmd = ['7z', 'x', '-y', graphviz_download_filepath,
                   '-o' + graphviz_target_path]
    bldinstallercommon.do_execute_sub_process(extract_graphviz_cmd, WORK_DIR)

    build_environment = dict(os.environ)
    if bldinstallercommon.is_linux_platform():
        build_environment['LD_LIBRARY_PATH'] = ':'.join(filter(None, [os.path.join(graphviz_target_path, 'lib'),
                                                                      build_environment.get('LD_LIBRARY_PATH')]))

    def common_gammaray_args():
        cmd_args = ['python', '-u', os.path.join(SCRIPT_ROOT_DIR, 'bld_module.py'),
                    '--clean',
                    '--use-cmake']
        for module_url in qt_module_urls:
            cmd_args.extend(['--qt5_module_url', module_url])
        if not bldinstallercommon.is_mac_platform():
            cmd_args.extend(['--icu7z', bld_command.icu_libs])
        if bldinstallercommon.is_win_platform():
            cmd_args.extend(['--add-config-arg=-G', '--add-config-arg=NMake Makefiles',
                             '--buildcommand', 'nmake',
                             '--installcommand', 'nmake'])
        return cmd_args

    # build kdstatemachineeditor
    cmd_args = common_gammaray_args()
    cmd_args.extend(['--module_dir', os.path.join(WORK_DIR, 'kdsme'),
                     '--module-name', 'kdsme',
                     '--qt5path', os.path.join(WORK_DIR, 'kdsme_qt5_install'),
                     '--add-config-arg=-DBUILD_EXAMPLES=OFF',
                     '--add-config-arg=-DBUILD_TESTING=OFF',
                     '--add-config-arg=-DGRAPHVIZ_ROOT={0}'.format(graphviz_target_path)])
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, extra_env=build_environment)

    # build gammaray
    cmd_args = common_gammaray_args()
    cmd_args.extend(['--module_dir', os.path.join(WORK_DIR, 'gammaray'),
                     '--module-name', 'gammaray',
                     '--qt5path', os.path.join(WORK_DIR, 'gammaray_qt5_install'),
                     '--add-config-arg=-DCMAKE_INSTALL_RPATH_USE_LINK_PATH=FALSE',
                     '--qt5_module_url', bld_utils.file_url(os.path.join(SCRIPT_ROOT_DIR, 'module_archives', 'qt5_kdsme.7z'))])
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, extra_env=build_environment)

    # upload
    base_path = bld_command.path + '/gammaray/' + gammaray_version
    base_upload_path = base_path + '/' + bld_command.build_number
    upload_path =  base_upload_path + '/' + BIN_TARGET_DIRS[bld_command.target_env]
    latest_path = base_path + '/latest'
    create_remote_dirs(bld_command.pkg_server_addr, upload_path)
    update_latest_link(bld_command, base_upload_path, latest_path)
    for module in ['kdsme', 'gammaray']:
        cmd_args = [SCP_COMMAND, 'qt5_{0}.7z'.format(module),
                    bld_command.pkg_server_addr + ':' + upload_path + '/']
        bldinstallercommon.do_execute_sub_process(cmd_args, os.path.join(SCRIPT_ROOT_DIR, 'module_archives'))

###############################
# handle_qt_creator_build
###############################
def handle_qt_creator_build(bld_command):
    sanity_check_packaging_server(bld_command)
    installer_version_number = os.environ['QTC_INSTALLER_VERSION']
    target_env_dir = BIN_TARGET_DIRS[bld_command.target_env]

    # gammaray and graphviz
    kdsme_url = (bld_command.pkg_server_addr_http + '/'
                    + os.environ["GAMMARAY_BASE_DIR"] + '/'
                    + target_env_dir + '/qt5_kdsme.7z')
    gammaray_url = (bld_command.pkg_server_addr_http + '/'
                    + os.environ["GAMMARAY_BASE_DIR"] + '/'
                    + target_env_dir + '/qt5_gammaray.7z')
    graphviz_url = (bld_command.pkg_server_addr_http + '/'
                    + os.environ["GRAPHVIZ_BASE_DIR"] + '-' + bld_command.target_env + '.7z')

    qt_base_path = os.environ['QTC_QT_BASE_DIR']
    qt_module_urls = []
    qt_module_filenames = []
    if "/5.5" in qt_base_path: # Qt 5.5 compat mode
        qt_modules = ['essentials', 'addons', 'qtscript', 'qtwebkit',
                      'qtlocation', 'qtpositioning', 'qtquickcontrols']
        qt_module_filenames = ['qt5_' + module + '.7z' for module in qt_modules]
        qt_base_url = (bld_command.pkg_server_addr_http + '/' + qt_base_path
                       + '/' + BIN_TARGET_DIRS[bld_command.target_env])
        qt_module_urls = [qt_base_url + '/' + filename for filename in qt_module_filenames]
    else:
        qt_modules = ['qtbase', 'qtdeclarative', 'qtgraphicaleffects',
                      'qtimageformats', 'qtlocation', 'qtmacextras',
                      'qtquickcontrols', 'qtquickcontrols2', 'qtscript', 'qtsvg', 'qttools',
                      'qttranslations', 'qtx11extras', 'qtxmlpatterns']
        qt_postfix = CI_TARGET_POSTFIX[bld_command.target_env]
        qt_module_filenames = [module + '-' + qt_postfix + '.7z' for module in qt_modules]
        qt_base_url = bld_command.pkg_server_addr_http + '/' + qt_base_path
        qt_module_urls = [qt_base_url + '/' + module + '/' + filename
                          for (module, filename) in zip(qt_modules, qt_module_filenames)]

    common_arguments = []
    if not bldinstallercommon.is_win_platform():
        common_arguments.extend(['--installcommand', 'make -j1'])
    else:
        common_arguments.extend(['--buildcommand', os.path.normpath('C:/Utils/jom/jom.exe'),
                         '--installcommand', os.path.normpath('nmake.exe'),
                         '--sevenzippath', os.path.normpath('C:/Utils/sevenzip'),
                         '--gitpath', os.path.normpath('C:/Program Files/Git/bin')])
    cmd_args = ['python', '-u', os.path.normpath(SCRIPT_ROOT_DIR + '/bld_qtcreator.py'),
                '--clean',
                '--qt5path', os.path.normpath(WORK_DIR + '/qt5_install_dir'),
                '--versiondescription', '"' + bld_command.qtcreator_version_description + '"']
    for module_url in qt_module_urls:
        cmd_args.extend(['--qt-module', module_url])

    if bldinstallercommon.is_linux_platform():
        cmd_args.extend(['--icu7z', bld_command.icu_libs])
    elif bldinstallercommon.is_mac_platform():
        cmd_args.extend(['--keychain_unlock_script', '/Users/qt/unlock-keychain.sh'])
    else:
        d3d_url = 'http://download.qt.io/development_releases/prebuilt/d3dcompiler/msvc2013/d3dcompiler_47-x86.7z'
        opengl_url = 'http://download.qt.io/development_releases/prebuilt/llvmpipe/windows/opengl32sw-32.7z'
        cmd_args.extend(['--d3dcompiler7z', d3d_url,
                         '--opengl32sw7z', opengl_url,
                         '--icu7z', bld_command.icu_libs])
        if bld_command.openssl_libs:
            cmd_args.extend(['--openssl7z', bld_command.openssl_libs])
    cmd_args.extend(common_arguments)

    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR)

    if bldinstallercommon.is_mac_platform():
        lock_keychain()

    # Qt Creator enterprise plugins
    additional_qmake_arguments = ['CONFIG+=licensechecker']
    Plugin = collections.namedtuple('Plugin', ['name', 'path', 'dependencies', 'modules', 'additional_arguments', 'include_in_package'])
    Plugin.__new__.__defaults__ = ([], [], [], True) # 'name' and 'path' are mandatory
    additional_plugins = [Plugin(name='licensechecker', path='licensechecker'),
                          Plugin(name='vxworks-qtcreator-plugin', path='vxworks-qtcreator-plugin',
                                 dependencies=['licensechecker']),
                          Plugin(name='isoiconbrowser', path='qtquickdesigner',
                                 dependencies=['licensechecker'])
                          ]
    if bld_command.qtcreator_version.startswith("3.6"):
        additional_plugins.extend([Plugin(name='clangstaticanalyzer', path='clangstaticanalyzer',
                                          dependencies=['licensechecker']),
                                   Plugin(name='qmlprofiler', path='qmlprofiler',
                                          dependencies=['licensechecker']),
                                   Plugin(name='autotest-qtcreator-plugin', path='autotest-qtcreator-plugin',
                                          dependencies=['licensechecker'])])
    if bldinstallercommon.is_linux_platform():
        additional_qmake_arguments.extend(['PERFPARSER_BUNDLED_ELFUTILS=true',
                                           'PERFPARSER_APP_DESTDIR=' + os.path.join(WORK_DIR, 'perfparser-target', 'libexec', 'qtcreator'),
                                           'PERFPARSER_ELFUTILS_DESTDIR=' + os.path.join(WORK_DIR, 'perfparser-target', 'lib', 'qtcreator'),
                                           'PERFPARSER_APP_INSTALLDIR=' + os.path.join(WORK_DIR, 'perfparser-target', 'libexec', 'qtcreator'),
                                           'PERFPARSER_ELFUTILS_INSTALLDIR=' + os.path.join(WORK_DIR, 'perfparser-target', 'lib', 'qtcreator')
                                           ])
        additional_plugins.extend([Plugin(name='perfparser', path='perfparser')])

    if not bldinstallercommon.is_mac_platform():
        # download and extract graphviz
        graphviz_download_filepath = os.path.join(WORK_DIR, 'qt-creator_temp', 'graphviz.7z')
        graphviz_target_path = os.path.join(WORK_DIR, 'graphviz')
        bld_utils.download(graphviz_url, graphviz_download_filepath)
        bldinstallercommon.extract_file(graphviz_download_filepath, graphviz_target_path)

        additional_plugins.extend([Plugin(name='perfprofiler', path='perfprofiler',
                                          dependencies=['licensechecker']),
                                   Plugin(name='b2qt-qtcreator-plugin', path='b2qt-qtcreator-plugin',
                                          dependencies=['licensechecker', 'perfprofiler']),
                                   Plugin(name='gammarayintegration', path='gammarayintegration',
                                          dependencies=['licensechecker', 'b2qt-qtcreator-plugin', 'perfprofiler'], modules=[kdsme_url, gammaray_url],
                                          additional_arguments=[
                                          '--deploy-command', 'python',
                                          '--deploy-command=-u',
                                          '--deploy-command', os.path.join(WORK_DIR, 'gammarayintegration', 'scripts', 'deploy.py'),
                                          '--deploy-command=--graphviz-libs',
                                          '--deploy-command', graphviz_target_path],
                                          include_in_package=False)
                                  ])

    for plugin in additional_plugins:
        cmd_arguments = ['python', '-u', os.path.join(SCRIPT_ROOT_DIR, 'bld_qtcreator_plugins.py'),
                         '--clean',
                         '--qtc-build', os.path.join(WORK_DIR, 'qt-creator_build'),
                         '--qtc-dev', os.path.join(WORK_DIR, 'qt-creator'),
                         '--plugin-path', os.path.join(WORK_DIR, plugin.path),
                         '--build-path', WORK_DIR]
        for module_filename in qt_module_filenames:
            cmd_arguments.extend(['--qt-module', bld_utils.file_url(os.path.join(WORK_DIR, 'qt-creator_temp', module_filename))])
        for module in plugin.modules:
            cmd_arguments.extend(['--qt-module', module])
        cmd_arguments.extend(plugin.additional_arguments)
        for qmake_arg in additional_qmake_arguments:
            cmd_arguments.extend(['--add-qmake-argument', qmake_arg])

        if not bldinstallercommon.is_mac_platform():
            cmd_arguments.extend(['--icu7z', bld_utils.file_url(os.path.join(WORK_DIR, 'qt-creator_temp', os.path.basename(bld_command.icu_libs)))])
        if bldinstallercommon.is_win_platform():
            cmd_arguments.extend(['--d3dcompiler7z', bld_utils.file_url(os.path.join(WORK_DIR, 'qt-creator_temp', os.path.basename(d3d_url))),
                                  '--opengl32sw7z', bld_utils.file_url(os.path.join(WORK_DIR, 'qt-creator_temp', os.path.basename(opengl_url)))])
            if bld_command.openssl_libs:
                cmd_args.extend(['--openssl7z', bld_utils.file_url(os.path.join(WORK_DIR, 'qt-creator_temp', os.path.basename(bld_command.openssl_libs)))])
        libs_paths = []
        for dependency_name in plugin.dependencies:
            matches = [dep for dep in additional_plugins if dep.name == dependency_name]
            if not matches:
                raise RuntimeError('did not find dependency "{0}" for plugin "{1}"'.format(dependency_name, plugin.name))
            dependency = matches[0]
            cmd_arguments.extend(['--plugin-search-path', os.path.join(WORK_DIR, dependency.path, 'plugins')])
            libs_base = os.path.join(WORK_DIR, dependency.name + '-target')
            if bldinstallercommon.is_mac_platform():
                libs_paths.append(os.path.join(libs_base, 'PlugIns'))
            else:
                libs_paths.append(os.path.join(libs_base, 'lib', 'qtcreator', 'plugins'))
        if libs_paths:
            cmd_arguments.extend(['--add-qmake-argument', 'LIBS*=' + ' '.join(['-L'+path for path in libs_paths])])
        cmd_arguments.extend(common_arguments)
        cmd_arguments.append(os.path.join(WORK_DIR, plugin.name + '.7z'))
        bldinstallercommon.do_execute_sub_process(cmd_arguments, WORK_DIR)

    # Create opensource source package
    if bldinstallercommon.is_linux_platform():
        bldinstallercommon.do_execute_sub_process([os.path.join(WORK_DIR, 'qt-creator', 'scripts', 'createSourcePackages.sh'), bld_command.qtcreator_version, 'opensource'], WORK_DIR)

    # Create installers. TODO: This is just a hack until it uses the setup from the Qt installers
    postfix = ''
    if bld_command.qtcreator_version:
        postfix = '-' + bld_command.qtcreator_version
    if bld_command.target_env.find('64') != -1:
        postfix = 'x86_64' + postfix
    else:
        postfix = 'x86' + postfix
    # get ifw
    ifw_base_url = 'http://ci-files02-hki.ci.local/packages/jenkins/enterprise/ifw/unifiedqt'
    if bldinstallercommon.is_linux_platform():
        if bld_command.target_env.find('64') != -1:
            ifw_url = ifw_base_url + '/installer-framework-build-linux-x64.7z'
        else:
            ifw_url = ifw_base_url + '/installer-framework-build-linux-x86.7z'
    elif bldinstallercommon.is_mac_platform():
        ifw_url = ifw_base_url + '/installer-framework-build-mac-x64.7z'
    else:
        ifw_url = ifw_base_url + '/installer-framework-build-win-x86.7z'
    ifw_download_filepath = os.path.join(WORK_DIR, os.path.basename(ifw_url))
    ifw_path = os.path.join(WORK_DIR, 'ifw-bld')
    bld_utils.download(ifw_url, ifw_download_filepath)
    bldinstallercommon.do_execute_sub_process(['7z', 'x', '-y', ifw_download_filepath], WORK_DIR)
    # installer name
    if bldinstallercommon.is_linux_platform():
        installer_basename_template = 'qt-creator-{0}-linux-' + postfix
    elif bldinstallercommon.is_mac_platform():
        installer_basename_template = 'qt-creator-{0}-mac-' + postfix
    else: # -> windows
        installer_basename_template = 'qt-creator-{0}-windows-' + postfix
    common_args = ['python', '-u', os.path.join(WORK_DIR, 'qt-creator', 'scripts', 'packageIfw.py'),
        '-v', installer_version_number]
    if not bld_command.qtcreator_version.startswith("3.6"):
        common_args.extend(['-d', bld_command.qtcreator_version])
    common_args.extend([
        '-i', ifw_path,
        '-a', os.path.join(WORK_DIR, 'qt-creator_build/qtcreator.7z')])
    # opensource installers
    cmd_args = list(common_args) + [installer_basename_template.format('opensource')]
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR)
    # enterprise installers
    patch_filepath = os.environ.get('INSTALLER_PATCH')
    if patch_filepath:
        bldinstallercommon.do_execute_sub_process(['git', 'am', '-3', patch_filepath],
                                                  os.path.join(WORK_DIR, 'qt-creator'))
    cmd_args = list(common_args)
    for plugin in additional_plugins:
        if plugin.include_in_package:
            cmd_args.extend(['-a', os.path.join(WORK_DIR, plugin.name + '.7z')])
    cmd_args.append(installer_basename_template.format('enterprise'))
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR)
    # mac signing and installer dmg
    if bldinstallercommon.is_mac_platform():
        unlock_keychain()
        common_signing_args = ['codesign', '-s', os.environ['SIGNING_IDENTITY']]
        signing_flags_env = os.environ.get('SIGNING_FLAGS')
        if signing_flags_env:
            common_signing_args.extend(signing_flags_env.split())
        common_dmg_args = ['hdiutil', 'create', '-volname', 'Qt Creator',
                           '-format', 'UDBZ', '-ov', '-scrub', '-size', '1g', '-verbose']
        for license in ['opensource', 'enterprise']:
            installer_base_filepath = os.path.join(WORK_DIR, installer_basename_template.format(license))
            bldinstallercommon.do_execute_sub_process(common_signing_args + [installer_base_filepath + '.app'], WORK_DIR)
            bldinstallercommon.do_execute_sub_process(common_dmg_args + ['-srcfolder', installer_base_filepath + '.app', installer_base_filepath + '.dmg'], WORK_DIR)
        lock_keychain()
    elif bldinstallercommon.is_win_platform():
        sign_windows_executable('qt-creator-opensource-windows-' + postfix + '.exe', WORK_DIR, True)
        sign_windows_executable('qt-creator-enterprise-windows-' + postfix + '.exe', WORK_DIR, True)

    # Create enterprise source package
    # THIS DEPENDS ON THE ENTERPRISE PATCHING ABOVE!!!! ('INSTALLER_PATCH' and the git am)
    if bldinstallercommon.is_linux_platform():
        bldinstallercommon.do_execute_sub_process([os.path.join(WORK_DIR, 'qt-creator', 'scripts', 'createSourcePackages.sh'), bld_command.qtcreator_version, 'enterprise'], WORK_DIR)

    # Qt Creator directory
    qtcreator_edition_name = os.environ.get('QT_CREATOR_EDITION_NAME')
    build_id = bld_command.build_number
    base_path = bld_command.path + '/qtcreator/snapshots/' + bld_command.qtcreator_version
    if qtcreator_edition_name:
        base_path += '_' + qtcreator_edition_name
    dir_path = base_path + '/' + build_id
    latest_path = base_path + '/latest'
    create_remote_dirs(bld_command.pkg_server_addr, dir_path + '/' + target_env_dir)
    update_latest_link(bld_command, dir_path, latest_path)

    # snapshot directory
    snapshot_path = bld_command.snapshot_path
    if bld_command.snapshot_server and bld_command.snapshot_path:
        if bld_command.qtcreator_version:
            snapshot_path += '/' + bld_command.qtcreator_version
        cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, "ssh", bld_command.snapshot_server,
            'mkdir', '-p', snapshot_path + '/' + build_id + '/installer_source/' + target_env_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
        cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, "ssh", bld_command.snapshot_server,
            'ln', '-sfn', snapshot_path + '/' + build_id, snapshot_path + '/latest']
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR, True)
        snapshot_path += '/' + build_id

    file_upload_list = [] # pairs (source, dest), source relative to WORK_DIR, dest relative to server + dir_path
    snapshot_upload_list = [] # pairs (source, dest), source relative to server + dir_path, dest relative to snapshot server + snapshot_path

    # installers
    if bld_command.qtcreator_version.startswith("3.") or bld_command.qtcreator_version.startswith("4.0"):
        if bldinstallercommon.is_linux_platform():
            file_upload_list.append(('qt-creator-opensource-linux-' + postfix + '.run', ''))
            file_upload_list.append(('qt-creator-enterprise-linux-' + postfix + '.run', ''))
            snapshot_upload_list.append(('qt-creator-opensource-linux-' + postfix + '.run', ''))
        elif bldinstallercommon.is_mac_platform():
            # opensource gets simple disk image.
            file_upload_list.append(('qt-creator_build/qt-creator.dmg', 'qt-creator-opensource-mac-' + postfix + '.dmg'))
            file_upload_list.append(('qt-creator-enterprise-mac-' + postfix + '.dmg', ''))
            snapshot_upload_list.append(('qt-creator-opensource-mac-' + postfix + '.dmg', ''))
        else: # --> windows
            file_upload_list.append(('qt-creator-opensource-windows-' + postfix + '.exe', ''))
            file_upload_list.append(('qt-creator-enterprise-windows-' + postfix + '.exe', ''))
            snapshot_upload_list.append(('qt-creator-opensource-windows-' + postfix + '.exe', ''))

    # source packages
    if bldinstallercommon.is_linux_platform():
        source_package_list = glob(os.path.join(WORK_DIR, 'qt-creator', 'qt-creator-*-src-' + bld_command.qtcreator_version + '.*'))
        file_upload_list.extend([(fn, '') for fn in source_package_list])

    # installer 7z sources
    file_upload_list.append(('qt-creator_build/qtcreator.7z', target_env_dir + '/qtcreator.7z'))
    snapshot_upload_list.append((target_env_dir + '/qtcreator.7z', 'installer_source/' + target_env_dir + '/qtcreator.7z'))
    for plugin in additional_plugins:
        file_upload_list.append((plugin.name + '.7z', target_env_dir + '/' + plugin.name + '.7z'))

    # upload files
    for source, destination in file_upload_list:
        cmd_args = [SCP_COMMAND, source, bld_command.pkg_server_addr + ':' + dir_path + '/' + destination]
        bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR)
    if bld_command.snapshot_server and bld_command.snapshot_path:
        for source, destination in snapshot_upload_list:
            cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, "scp",
                dir_path + '/' + source,
                bld_command.snapshot_server + ':' + snapshot_path + '/' + destination]
            bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR)


###############################
# handle_offline_installer_build
###############################
def handle_offline_installer_build(bld_command):
    # Project name, default is always "qt"
    project_name = os.getenv('PROJECT_NAME', 'qt')
    handle_installer_build(bld_command, project_name, 'offline')


###############################
# handle_online_installer_build
###############################
def handle_online_installer_build(bld_command):
    # Project name, default is always "qt"
    project_name = os.getenv('PROJECT_NAME', 'online_installers')
    handle_installer_build(bld_command, project_name, 'online')


###############################
# handle_installer_build
###############################
def handle_installer_build(bld_command, project_name, installer_type):
    sanity_check_packaging_server(bld_command)
    # Create remote directories under <project_name>/<version>
    remote_path_base                        = bld_command.path + '/' + project_name + '/' + bld_command.version + '/' + 'installers'
    remote_path_snapshot                    = remote_path_base + '/' + bld_command.build_number
    remote_path_latest_available            = remote_path_base + '/' + 'latest_available'
    # ensure remote directories exist
    create_remote_dirs(bld_command.pkg_server_addr, remote_path_snapshot)
    create_remote_dirs(bld_command.pkg_server_addr, remote_path_latest_available)
    # Determine local installer output directory
    installer_output_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.INSTALLER_OUTPUT_DIR_NAME)
    # Create all installers for this host
    arch = 'x64' if (bld_command.target_env.find('64') != -1) else 'x86'
    release_build_handler.handle_installer_build(bld_command.release_description_file, installer_type, bld_command.license, 'release', PLATFORM, arch, bld_command.pkg_server_addr_http)
    # Generate installer file name list
    installer_list = []
    dir_list = [f for f in os.listdir(installer_output_dir) if not f.endswith(".app")]
    for file_name in dir_list:
        installer_name, installer_name_base, installer_name_final = generate_installer_final_name(bld_command, file_name)
        installer_list.append((file_name, installer_name, installer_name_base, installer_name_final))
    # Sign and copy to network drive
    for item in installer_list:
        installer_name = item[1]
        installer_name_base = item[2]
        installer_name_final = item[3]
        # sign
        sign_installer(installer_output_dir, installer_name, installer_name_base)
        # copy installer(s) to various locations:
        remote_copy_installer(bld_command, remote_path_snapshot, installer_name, installer_output_dir, installer_name_final)
        remote_copy_installer(bld_command, remote_path_latest_available, installer_name, installer_output_dir, installer_name_final)
        # Keep only the latest one in the "latest_available" directory i.e. delete the previous one
        replace_latest_successful_installer(bld_command, installer_name, installer_name_final, remote_path_latest_available, installer_output_dir)
    # Trigger rta cases
    trigger_rta(os.path.join(SCRIPT_ROOT_DIR, pkg_constants.RTA_DESCRIPTION_FILE_DIR_NAME))
    # Do we upload the installers to opensource/public network drive?
    if os.getenv('EXPORT_OPENSOURCE_INSTALLER'):
        # opensource distribution server address and path
        ext_server_base_url  = os.environ['EXT_SERVER_BASE_URL']
        ext_server_base_path = os.environ['EXT_SERVER_BASE_PATH']
        # opensource distribution server directories
        ext_dest_dir = ext_server_base_path + '/snapshots/' + project_name + '/' + bld_command.version[:3] + '/' + bld_command.full_version + '/' + bld_command.build_number
        cmd_args_mkdir_pkg = [SSH_COMMAND, bld_command.pkg_server_addr]
        cmd_args_mkdir_ext = cmd_args_mkdir_pkg + ['ssh', ext_server_base_url, 'mkdir -p', ext_dest_dir]
        bldinstallercommon.do_execute_sub_process(cmd_args_mkdir_ext, SCRIPT_ROOT_DIR)
        # Copy installers
        for item in installer_list:
            remote_copy_installer_opensource(bld_command, remote_path_snapshot, ext_server_base_url, ext_dest_dir, item[3])


###############################
# replace_latest_successful_installer
###############################
def replace_latest_successful_installer(bld_command, installer_name, installer_name_final, ls_installer_dir, installer_output):
    # check installer type
    if 'online' in installer_name_final.lower():
        regex = re.compile('.*online')
        if "embedded" in installer_name_final.lower():
            regex = re.compile(r'.*online(?:(?!_\d{4}).)*')
    else:
        regex = re.compile('.*' + bld_command.full_version)
    installer_base_name = "".join(regex.findall(installer_name_final))
    if not installer_base_name:
        print('*** Empty installer base name string')
    else:
        old_installer = ls_installer_dir + '/' + installer_base_name + '*'
        # delete old installer
        cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, 'rm', '-f', old_installer]
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, False)
        # save new installer to latest_successful directory
        cmd_args = [SCP_COMMAND, installer_name, bld_command.pkg_server_addr + ':' + ls_installer_dir + '/' + installer_name_final]
        bldinstallercommon.do_execute_sub_process(cmd_args, installer_output)


###############################
# Sign installer
###############################
def sign_installer(installer_output_dir, installer_name, installer_name_base):
    if installer_name.endswith(".dmg"):
        unlock_keychain()
        sign_mac_executable(installer_name_base + '.app', installer_output_dir, True)
        cmd_args = ['hdiutil', 'create', '-srcfolder', os.path.join(installer_output_dir, installer_name_base) + '.app', '-volname', installer_name_base, '-format', 'UDBZ', os.path.join(installer_output_dir, installer_name_base) + '.dmg', '-ov', '-scrub', '-size', '3g']
        bldinstallercommon.do_execute_sub_process(cmd_args, installer_output_dir)
    if installer_name.endswith(".exe"):
        sign_windows_executable(installer_name, installer_output_dir, True)


###############################
# Remote copy installer
###############################
def remote_copy_installer(bld_command, remote_dest_dir, file_name, installer_output_dir, installer_name_final):
    # ensure remote directory exists
    create_remote_dirs(bld_command.pkg_server_addr, remote_dest_dir)
    cmd_args = [SCP_COMMAND, file_name, bld_command.pkg_server_addr + ':' + remote_dest_dir + '/' + installer_name_final]
    bldinstallercommon.do_execute_sub_process(cmd_args, installer_output_dir)


###############################
# Remote copy installer (Opensource)
###############################
def remote_copy_installer_opensource(bld_command, remote_dest_dir, ext_server_base_url, ext_dest_dir, installer_name_final):
    # copy installer to mirror brain server
    if bld_command.license == 'opensource':
        cmd_args_copy_to_pkg = [SSH_COMMAND, bld_command.pkg_server_addr]
        cmd_args_copy_to_ext = cmd_args_copy_to_pkg + ['scp', remote_dest_dir + '/' + installer_name_final, ext_server_base_url + ':' + ext_dest_dir  + '/' + installer_name_final]
        bldinstallercommon.do_execute_sub_process(cmd_args_copy_to_ext, SCRIPT_ROOT_DIR)


###############################
# Helper to generate installer final name
###############################
def generate_installer_final_name(bld_command, file_name):
    suffix = file_name.split(".")[-1]
    installer_name = file_name
    installer_name_base = os.path.splitext(file_name)[0]
    installer_name_final = installer_name_base + '_' + bld_command.build_number + '.' + suffix
    return installer_name, installer_name_base, installer_name_final


###############################
# Update latest link
###############################
def update_latest_link(bld_command, remote_dest_dir, latest_dir):
    cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, 'ln -sfn', remote_dest_dir, latest_dir]
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR)


###############################
# Delete remote directory tree
###############################
def delete_remote_directory_tree(bld_command, remote_dir):
    cmd_args = [SSH_COMMAND, bld_command.pkg_server_addr, 'rm -rf', remote_dir]
    bldinstallercommon.do_execute_sub_process(cmd_args, WORK_DIR)


###############################
# Trigger RTA cases
###############################
def trigger_rta(rta_description_files_dir):
    # check if rta cases define for this build job
    if not os.path.isdir(rta_description_files_dir):
        raise IOError('*** Error - Given rta_description_files_dir does not exist: %s' % rta_description_files_dir)
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
    if not rta_server_base_url.endswith('/'):
        rta_server_base_url += '/'
    # iterate rta description files
    for rta_description_file in matching:
        print('Reading RTA description file: {0}'.format(os.path.join(rta_description_files_dir, rta_description_file)))
        rta_file = os.path.join(rta_description_files_dir, rta_description_file)
        f = open(rta_file)
        for line in iter(f):
            line_split = line.split(' ')
            if len(line_split) != 2:
                raise RuntimeError('*** Error - Invalid format in rta description file %s, line: %s' % (rta_file, line))
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
        raise IOError('*** The given file does not exist: %s' % conf_file)
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
# create_remote_dirs
###############################
def create_remote_dirs(server, dir_path):
    cmd_args = [SSH_COMMAND, '-t', '-t', server, 'mkdir -p', dir_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)


###############################
# ICU build init
###############################
def initialize_icu_build(bld_command):
    # sanity check icu args in bld_command
    sanity_check_packaging_server(bld_command)
    if not bld_command.icu_version:
        raise RuntimeError('*** ICU build is missing: icu_version')
    if not bld_command.path:
        raise RuntimeError('*** ICU build is missing: path')
    if not bld_command.build_number:
        raise RuntimeError('*** ICU build is missing: build_number')
    remote_snaphot_dir_base = bld_command.path + '/' + 'icu' + '/' + bld_command.icu_version
    remote_snaphot_dir = remote_snaphot_dir_base + '/' + bld_command.build_number
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
        raise RuntimeError('*** ICU build is missing: icu_version')
    if not bld_command.path:
        raise RuntimeError('*** ICU build is missing: path')
    if not bld_command.icu_src_pkg_url:
        raise RuntimeError('*** ICU build is missing: icu_src_pkg_url')
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
            bldinstallercommon.do_execute_sub_process(cmd_args, local_archives_dir)


################################
# Publish prebuilt ICU packages
################################
def publish_icu_packages(bld_command):
    # sanity check icu args in bld_command
    sanity_check_packaging_server(bld_command)
    if not bld_command.icu_version:
        raise RuntimeError('*** ICU build is missing: icu_version')
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
        raise RuntimeError()

    (options, dummy) = OPTION_PARSER.parse_args()
    bld_cmd_validator = BldCommand(options)

    if not bld_cmd_validator.validate_bld_args():
        OPTION_PARSER.print_help()
        raise RuntimeError()

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


##############################################################
# Initialize Environment
##############################################################
def init_env():
    global MAKE_INSTALL_PADDING
    global CURL_COMMAND
    global RM_COMMAND
    global SSH_COMMAND
    global SCP_COMMAND

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
    # QtCreator specific
    if bld_command.command == BldCommand.execute_creator_bld:
        handle_qt_creator_build(bld_command)
    # GammaRay Qt module
    elif bld_command.command == BldCommand.execute_gammaray_bld:
        handle_gammaray_build(bld_command)
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
