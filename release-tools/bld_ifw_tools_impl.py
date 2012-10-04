#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2012 Digia Plc and/or its subsidiary(-ies).
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

import sys
import os
import sys
import urllib
import shutil
import ConfigParser
import bldinstallercommon

DEVELOPMENT_MODE                    = False
INCREMENTAL_MODE                    = False
CONFIG_IFW                          = ''
SCRIPT_ROOT_DIR                     = os.getcwd()
PLATFORM_IDENTIFIER                 = ''
MAKE_CMD                            = ''
QT_QMAKE_BIN                        = ''
QT_CONFIGURE_BIN                    = ''
QT_SRC_PACKAGE_URL                  = ''
QT_SRC_PACKAGE_URL_SAVE_AS          = ''
QT_SOURCE_DIR                       = ''
QT_BUILD_DIR                        = ''
QT_INSTALLERFW_QT_CONFIGURE_LINE    = ''
INSTALLER_FRAMEWORK_URL             = ''
INSTALLER_FRAMEWORK_SOURCE_DIR      = ''
INSTALLER_FRAMEWORK_BUILD_DIR       = ''
INSTALLER_FRAMEWORK_VERSION_TAG     = ''
INSTALLER_FRAMEWORK_QMAKE_ARGS      = ''
INSTALLER_FRAMEWORK_ARCHIVE_NAME    = ''
INSTALLERBASE_ARCHIVE_NAME          = ''


###############################
# function
###############################
def init_config(configurations_dir):
    global CONFIG_IFW
    global MAKE_CMD
    global QT_QMAKE_BIN
    global QT_CONFIGURE_BIN
    global QT_SRC_PACKAGE_URL
    global QT_SRC_PACKAGE_URL_SAVE_AS
    global QT_SOURCE_DIR
    global QT_BUILD_DIR
    global QT_INSTALLERFW_QT_CONFIGURE_LINE
    global INSTALLER_FRAMEWORK_URL
    global INSTALLER_FRAMEWORK_SOURCE_DIR
    global INSTALLER_FRAMEWORK_BUILD_DIR
    global INSTALLER_FRAMEWORK_VERSION_TAG
    global INSTALLER_FRAMEWORK_QMAKE_ARGS
    global INSTALLER_FRAMEWORK_ARCHIVE_NAME
    global INSTALLERBASE_ARCHIVE_NAME

    conf_path = SCRIPT_ROOT_DIR + os.sep + configurations_dir + os.sep + PLATFORM_IDENTIFIER + os.sep + 'installer-framework'
    CONFIG_IFW = ConfigParser.ConfigParser()
    CONFIG_IFW.readfp(open(conf_path))

    print '----------------------------------------'
    print 'Installer-Framework build configuration:'
    print ''
    print 'Configuration file: ' + conf_path
    print ''

    MAKE_CMD                            = bldinstallercommon.config_section_map(CONFIG_IFW,'make')['make_cmd']
    QT_SRC_PACKAGE_URL                  = bldinstallercommon.config_section_map(CONFIG_IFW,'QtForInstallerFramework')['qt_src_package_url']
    QT_SRC_PACKAGE_URL_SAVE_AS          = SCRIPT_ROOT_DIR + os.sep + os.path.basename(QT_SRC_PACKAGE_URL)
    QT_SOURCE_DIR                       = SCRIPT_ROOT_DIR + os.sep + bldinstallercommon.config_section_map(CONFIG_IFW,'QtForInstallerFramework')['qt_source_dir']
    QT_BUILD_DIR                        = SCRIPT_ROOT_DIR + os.sep + bldinstallercommon.config_section_map(CONFIG_IFW,'QtForInstallerFramework')['qt_build_dir']
    QT_INSTALLERFW_QT_CONFIGURE_LINE    = bldinstallercommon.config_section_map(CONFIG_IFW,'QtForInstallerFramework')['qt_installerfw_qt_configure_line']

    QT_QMAKE_BIN                            = 'qmake'
    if bldinstallercommon.is_win_platform():
        QT_QMAKE_BIN += '.exe'
    QT_CONFIGURE_BIN                        = QT_SOURCE_DIR + os.sep + 'configure'
    if bldinstallercommon.is_win_platform():
        QT_CONFIGURE_BIN += '.exe'

    INSTALLER_FRAMEWORK_URL             = bldinstallercommon.config_section_map(CONFIG_IFW,'InstallerFramework')['installer_framework_url']
    INSTALLER_FRAMEWORK_SOURCE_DIR      = SCRIPT_ROOT_DIR + os.sep + bldinstallercommon.config_section_map(CONFIG_IFW,'InstallerFramework')['installer_framework_source_dir']
    INSTALLER_FRAMEWORK_BUILD_DIR       = SCRIPT_ROOT_DIR + os.sep + bldinstallercommon.config_section_map(CONFIG_IFW,'InstallerFramework')['installer_framework_build_dir']
    INSTALLER_FRAMEWORK_VERSION_TAG     = bldinstallercommon.config_section_map(CONFIG_IFW,'InstallerFramework')['installer_framework_version_tag']
    INSTALLER_FRAMEWORK_QMAKE_ARGS      = bldinstallercommon.config_section_map(CONFIG_IFW,'InstallerFramework')['installer_framework_qmake_args']
    QT_SOURCE_DIR                       = os.path.normpath(QT_SOURCE_DIR)
    QT_BUILD_DIR                        = os.path.normpath(QT_BUILD_DIR)
    INSTALLER_FRAMEWORK_SOURCE_DIR      = os.path.normpath(INSTALLER_FRAMEWORK_SOURCE_DIR)
    INSTALLER_FRAMEWORK_BUILD_DIR       = os.path.normpath(INSTALLER_FRAMEWORK_BUILD_DIR)
    INSTALLER_FRAMEWORK_ARCHIVE_NAME    = bldinstallercommon.config_section_map(CONFIG_IFW,'Output')['installer_framework_archive_name']
    INSTALLERBASE_ARCHIVE_NAME          = bldinstallercommon.config_section_map(CONFIG_IFW,'Output')['installerbase_archive_name']

    print 'make:                                ' + MAKE_CMD
    print ''
    print 'QT_SRC_PACKAGE_URL:                  ' + QT_SRC_PACKAGE_URL
    print 'QT_SRC_PACKAGE_URL_SAVE_ASL:         ' + QT_SRC_PACKAGE_URL_SAVE_AS
    print 'QT_SOURCE_DIR:                       ' + QT_SOURCE_DIR
    print 'QT_BUILD_DIR:                        ' + QT_BUILD_DIR
    print 'QT_INSTALLERFW_QT_CONFIGURE_LINE:    [' + QT_INSTALLERFW_QT_CONFIGURE_LINE + ']'
    print 'QT_QMAKE_BIN:                        ' + QT_QMAKE_BIN
    print 'QT_CONFIGURE_BIN:                    ' + QT_CONFIGURE_BIN
    print ''
    print 'INSTALLER_FRAMEWORK_URL:             ' + INSTALLER_FRAMEWORK_URL
    print 'INSTALLER_FRAMEWORK_SOURCE_DIR:      ' + INSTALLER_FRAMEWORK_SOURCE_DIR
    print 'INSTALLER_FRAMEWORK_BUILD_DIR:       ' + INSTALLER_FRAMEWORK_BUILD_DIR
    print 'INSTALLER_FRAMEWORK_VERSION_TAG:     ' + INSTALLER_FRAMEWORK_VERSION_TAG
    print 'INSTALLER_FRAMEWORK_QMAKE_ARGS:      [' + INSTALLER_FRAMEWORK_QMAKE_ARGS + ']'
    print ''
    print 'Installer-Framework Output: ' + INSTALLER_FRAMEWORK_ARCHIVE_NAME
    print 'Installerbase Output: ' + INSTALLERBASE_ARCHIVE_NAME
    print '----------------------------------------'


###############################
# function
###############################
def prepare_qt_sources():
    if DEVELOPMENT_MODE:
        if os.path.exists(QT_SOURCE_DIR):
            return

    if INCREMENTAL_MODE and os.path.exists(QT_SOURCE_DIR):
        return

    print '--------------------------------------------------------------------'
    print 'Fetching Qt src package from: ' + QT_SRC_PACKAGE_URL
    if not os.path.isfile(QT_SRC_PACKAGE_URL_SAVE_AS):
        if not bldinstallercommon.is_content_url_valid(QT_SRC_PACKAGE_URL):
            print '*** Qt src package url is invalid! Abort!'
            sys.exit(-1)
        bldinstallercommon.retrieve_url(QT_SRC_PACKAGE_URL, QT_SRC_PACKAGE_URL_SAVE_AS)
    else:
        print 'Found old local package, using that: ' + QT_SRC_PACKAGE_URL_SAVE_AS
    print 'Done'
    print '--------------------------------------------------------------------'

    bldinstallercommon.create_dirs(QT_SOURCE_DIR)
    bldinstallercommon.extract_file(QT_SRC_PACKAGE_URL_SAVE_AS, QT_SOURCE_DIR)

    l = os.listdir(QT_SOURCE_DIR)
    items = len(l)
    if items == 1:
        dir_name = l[0]
        full_dir_name = QT_SOURCE_DIR + os.sep + dir_name
        bldinstallercommon.move_tree(full_dir_name, QT_SOURCE_DIR)
        bldinstallercommon.remove_tree(full_dir_name)
    else:
        print '*** Invalid dir structure encountered?!'
        sys.exit(-1)


###############################
# function
###############################
def build_qt():
    if DEVELOPMENT_MODE:
        if os.path.exists(QT_BUILD_DIR):
            return

    if INCREMENTAL_MODE and os.path.exists(QT_BUILD_DIR):
        return

    bldinstallercommon.create_dirs(QT_BUILD_DIR)
    # configure first
    print '--------------------------------------------------------------------'
    print 'Configuring Qt'
    # TODO, nasty hack, beucause of a bug in python ConfigParser module, loses trailing white spaces!!
    cmd_args = QT_CONFIGURE_BIN + ' ' + QT_INSTALLERFW_QT_CONFIGURE_LINE + ' ' + QT_BUILD_DIR
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_BUILD_DIR, True)

    print '--------------------------------------------------------------------'
    print 'Building Qt'
    cmd_args = MAKE_CMD
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_BUILD_DIR, True)


###############################
# function
###############################
def prepare_installer_framework():
    if DEVELOPMENT_MODE:
        if os.path.exists(INSTALLER_FRAMEWORK_SOURCE_DIR):
            return

    if INCREMENTAL_MODE and os.path.exists(INSTALLER_FRAMEWORK_SOURCE_DIR):
        return

    print '--------------------------------------------------------------------'
    print 'Prepare Installer Framework source'
    #create dirs
    bldinstallercommon.create_dirs(INSTALLER_FRAMEWORK_BUILD_DIR)
    # clone repos
    bldinstallercommon.clone_repository(INSTALLER_FRAMEWORK_URL, INSTALLER_FRAMEWORK_VERSION_TAG, INSTALLER_FRAMEWORK_SOURCE_DIR)


###############################
# function
###############################
def build_installer_framework():
    if INCREMENTAL_MODE:
        print 'INCREMENTAL_MODE'
        print INSTALLER_FRAMEWORK_BUILD_DIR
        if os.path.exists(os.path.join(INSTALLER_FRAMEWORK_BUILD_DIR, 'bin', 'installerbase.exe')):
            print 'exists'
            return

    print '--------------------------------------------------------------------'
    print 'Building Installer Framework'

    qmake_bin = QT_BUILD_DIR + os.sep + 'bin' + os.sep + QT_QMAKE_BIN
    if not os.path.isfile(qmake_bin):
        print '*** Unable to find qmake, aborting!'
        print 'qmake: ' + qmake_bin
        sys.exit(-1)

    if not os.path.exists(INSTALLER_FRAMEWORK_BUILD_DIR):
        bldinstallercommon.create_dirs(INSTALLER_FRAMEWORK_BUILD_DIR)

    cmd_args = qmake_bin + ' ' + INSTALLER_FRAMEWORK_QMAKE_ARGS + ' ' + INSTALLER_FRAMEWORK_SOURCE_DIR
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), INSTALLER_FRAMEWORK_BUILD_DIR, True)

    cmd_args = MAKE_CMD
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), INSTALLER_FRAMEWORK_BUILD_DIR, True)


###############################
# function
###############################
def clean_build_environment():
    if DEVELOPMENT_MODE or INCREMENTAL_MODE:
        return

    # delete existing stuff if exists
    if os.path.exists(INSTALLER_FRAMEWORK_SOURCE_DIR):
        bldinstallercommon.remove_tree(INSTALLER_FRAMEWORK_SOURCE_DIR)
    if os.path.exists(INSTALLER_FRAMEWORK_BUILD_DIR):
        bldinstallercommon.remove_tree(INSTALLER_FRAMEWORK_BUILD_DIR)
    if os.path.exists(QT_SOURCE_DIR):
        bldinstallercommon.remove_tree(QT_SOURCE_DIR)
    if os.path.exists(QT_BUILD_DIR):
        bldinstallercommon.remove_tree(QT_BUILD_DIR)
    if os.path.isfile(INSTALLER_FRAMEWORK_ARCHIVE_NAME):
        os.remove(INSTALLER_FRAMEWORK_ARCHIVE_NAME)
    if os.path.isfile(QT_SRC_PACKAGE_URL_SAVE_AS):
        os.remove(QT_SRC_PACKAGE_URL_SAVE_AS)


###############################
# function
###############################
def archive_installer_framework():
    if DEVELOPMENT_MODE or INCREMENTAL_MODE:
        return

    if INCREMENTAL_MODE and os.path.isfile(INSTALLER_FRAMEWORK_ARCHIVE_NAME):
        return

    print '--------------------------------------------------------------------'
    print 'Archive Installer Framework'
    # first strip out all unnecessary files
    for root, dirs, files in os.walk(INSTALLER_FRAMEWORK_BUILD_DIR):
        for filename in files:
            if filename.endswith(('.moc', 'Makefile', '.cpp', '.h', '.o')) or filename == 'Makefile':
                os.remove(os.path.join(root, filename))

    cmd_args = ['7z', 'a', INSTALLER_FRAMEWORK_ARCHIVE_NAME, os.path.basename(INSTALLER_FRAMEWORK_BUILD_DIR)]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


###############################
# function
###############################
def archive_installerbase():
    if DEVELOPMENT_MODE:
        return

    if INCREMENTAL_MODE and os.path.isfile(INSTALLERBASE_ARCHIVE_NAME):
        return

    print '--------------------------------------------------------------------'
    print 'Archive Installerbase'
    cmd_args_archive = []
    cmd_args_clean = []

    bin_temp = ''
    if bldinstallercommon.is_linux_platform() or bldinstallercommon.is_mac_platform():
        bin_path = bldinstallercommon.locate_executable(INSTALLER_FRAMEWORK_BUILD_DIR, 'installerbase')
        bin_temp = SCRIPT_ROOT_DIR + os.sep + '.tempSDKMaintenanceTool'
        shutil.copy(bin_path, bin_temp)
        cmd_args_archive = ['7z', 'a', INSTALLERBASE_ARCHIVE_NAME, bin_temp]
        cmd_args_clean = ['rm', bin_temp]
    if bldinstallercommon.is_win_platform():
        bin_path = bldinstallercommon.locate_executable(INSTALLER_FRAMEWORK_BUILD_DIR, 'installerbase.exe')
        bin_temp = SCRIPT_ROOT_DIR + os.sep + 'temp'
        bldinstallercommon.create_dirs(bin_temp)
        shutil.copy(bin_path, bin_temp + os.sep + 'SDKMaintenanceToolBase.exe')
        cmd_args_archive = ['7z', 'a', INSTALLERBASE_ARCHIVE_NAME, bin_temp]
        cmd_args_clean = ['rmdir' ,'/q/s', bin_temp]

    bldinstallercommon.do_execute_sub_process(cmd_args_archive, SCRIPT_ROOT_DIR, True)
    bldinstallercommon.do_execute_sub_process(cmd_args_clean, SCRIPT_ROOT_DIR, True)

    if not os.path.isfile(INSTALLERBASE_ARCHIVE_NAME):
        print '*** Failed to generate archive: ' + INSTALLERBASE_ARCHIVE_NAME
        sys.exit(-1)


###############################
# function
###############################
def archive_nib():
    print '--------------------------------------------------------------------'
    print 'Archive qt_menu.nib'

    content_parent_path = QT_SOURCE_DIR + os.sep + 'src/gui/mac'
    content_root_path = content_parent_path + os.sep + 'qt_menu.nib'

    content_parent_path = os.path.normpath(content_parent_path)
    content_root_path = os.path.normpath(content_root_path)
    archive_name = 'qt_menu.nib.7z'

    cmd_args = ['7z', 'a', archive_name, content_root_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)

    if not os.path.isfile(archive_name):
        print '*** Failed to generate archive: ' + archive_name
        sys.exit(-1)


###############################
# function
###############################
def archive_macdeployqt():
    print '--------------------------------------------------------------------'
    print 'Archive macdeployqt'

    content_path = QT_BUILD_DIR + os.sep + 'tools/macdeployqt/macchangeqt/macchangeqt'
    archive_name = bldinstallercommon.config_section_map(CONFIG_IFW,'Output')['macdeployqt_archive_name']
    if not archive_name:
        print '*** Error! macdeployqt_archive_name not defined?!'
        sys.exit(-1)
    cmd_args_archive = ['7z', 'a', archive_name, content_path]
    bldinstallercommon.do_execute_sub_process(cmd_args_archive, SCRIPT_ROOT_DIR, True)

    if not os.path.isfile(archive_name):
        print '*** Failed to generate archive: ' + archive_name
        sys.exit(-1)


###############################
# function
###############################
def archive_qt():
    archive_name = bldinstallercommon.config_section_map(CONFIG_IFW,'Output')['qt_archive_name']
    if INCREMENTAL_MODE and os.path.exists(archive_name):
        return

    print '--------------------------------------------------------------------'
    print 'Archive static Qt build'

    content_path = QT_BUILD_DIR
    if not archive_name:
        print '*** Error! macdeployqt_archive_name not defined?!'
        sys.exit(-1)
    # these directories can be deleted from the Qt binary package (built for SDK purposes only)
    directories_to_delete = ['config.tests', 'src', 'qmake', 'doc', 'imports', 'lib' + os.sep + 'pkgconfig', 'tools']
    for item in directories_to_delete:
        full_path = content_path + os.sep + item
        if os.path.exists(full_path) and not os.path.islink(full_path):
            print 'Deleting: ' + item
            shutil.rmtree(full_path)
    # then strip out all remaining unnecessary files
    for root, dirs, files in os.walk(content_path + os.sep + 'bin'):
        for filename in files:
            if filename.endswith(('.moc', 'Makefile', '.cpp', '.h', '.o')) or filename == 'Makefile':
                os.remove(os.path.join(root, filename))
            if filename.startswith(('designer', 'assistant', 'qcollectiongenerator', 'linguist', 'qhelpconverter', 'qhelpgenerator', 'pixeltool', 'qdoc3', 'qt3to4')):
                os.remove(os.path.join(root, filename))
    # archive libraries
    cmd_args_archive = ['7z', 'a', archive_name, content_path]
    bldinstallercommon.do_execute_sub_process(cmd_args_archive, SCRIPT_ROOT_DIR, True)
    # check archive was generated successfully
    if not os.path.isfile(archive_name):
        print '*** Failed to generate archive: ' + archive_name
        sys.exit(-1)


###############################
# main
###############################
def build_ifw(development_mode, incremental_mode, configurations_dir, platform):
    global DEVELOPMENT_MODE
    global INCREMENTAL_MODE
    global PLATFORM_IDENTIFIER
    DEVELOPMENT_MODE = development_mode
    INCREMENTAL_MODE = incremental_mode
    PLATFORM_IDENTIFIER = platform

    # init
    bldinstallercommon.init_common_module(SCRIPT_ROOT_DIR)
    init_config(configurations_dir)
    #clean environment first
    clean_build_environment()
    #checkout sources
    prepare_installer_framework()
    # copy qt sources
    prepare_qt_sources()
    # build qt
    build_qt()
    # build installer framework
    build_installer_framework()
    #archive
    archive_installerbase()
    archive_installer_framework()
    # for mac we do some extra work
    if bldinstallercommon.is_mac_platform():
        archive_nib()
        archive_macdeployqt()
    # archive static qt package
    archive_qt()
    if DEVELOPMENT_MODE:
        #TODO, the returned values should be in config file, not return it here!
        return os.path.basename(INSTALLER_FRAMEWORK_BUILD_DIR)
    else:
        return ''

