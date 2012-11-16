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

import os
import sys
import urllib
import zipfile
lib_path = os.path.abspath(os.path.dirname(sys.argv[0]) + os.sep + '..' + os.sep)
sys.path.append(lib_path)
import bldinstallercommon

SCRIPT_ROOT_DIR                     = os.getcwd()
QT_SRC_ZIP_URL                      = ''
QT_MODULE_ZIP_URL                   = ''
QT_SRC_7Z_URL                       = ''
QT_MODULE_7Z_URL                    = ''
QT_SRC_ZIP                          = ''
QT_MODULE_ZIP                       = ''
QT_SRC_7Z                           = ''
QT_MODULE_7Z                        = ''
QT_SRC_DIR                          = SCRIPT_ROOT_DIR
QT_PKG_NAME                         = ''
QT_MODULE_PKG_NAME                  = ''
CONFIGURE_OPTIONS                   = '-help'
CONFIGURE_CMD                       = 'configure'
DO_7Z                               = False
MODULE_DIR                          = SCRIPT_ROOT_DIR + os.sep + "module"


###############################
# function
###############################
def print_wrap(text):
    print 'QT5CONF_EXE: ' + text

###############################
# function
###############################
def print_help():
    print_wrap('*** Error! Insufficient arguments given!')
    print_wrap('')
    print_wrap('Example: python -u create_configure_exe.py src_url=qt-everywhere-opensource-src-5.0.0.zip mdl_url=qtbase-src.tar.zip do_7z')
    print_wrap('')
    print_wrap('Mandatory options:')
    print_wrap('')
    print_wrap('  src_url = [url where to fetch src package]')
    print_wrap('')
    print_wrap('Other options:')
    print_wrap('')
    print_wrap('  mdl_url = [url where to fetch module src package]')
    print_wrap('  do_7z   = [add also to .7z archives, assumes the basename to be as in src_url and mdl_url]')
    print_wrap('')

###############################
# function
###############################
def init():
    if bldinstallercommon.is_win_platform() == False:
        print_wrap(' *** Error: Not a windows platform, can not create configure.exe! Exiting...')
        sys.exit(-1)

    print_wrap('Emptying the working directory...')
    contents = os.listdir(QT_SRC_DIR)
    if len(contents) > 0:
        for item in contents:
            print_wrap('    Deleting ' + item)
            if os.path.isdir(item):
                bldinstallercommon.remove_tree(item)
            else:
                os.remove(item)
    else:
        print_wrap('    Nothing to delete.')


###############################
# function
###############################
def parse_cmd_line():
    global QT_SRC_ZIP_URL
    global QT_MODULE_ZIP_URL
    global DO_7Z

    print_wrap('---------------- Parsing commandline arguments ---------------------')
    arg_count = len(sys.argv)
    if not any('src_url' in s for s in sys.argv):
        print_help()
        sys.exit(-1)
    #Parse command line options
    for item in sys.argv[1:]:
        #url for the sources
        if item.find('src_url') >= 0:
            values = item.split('=')
            QT_SRC_ZIP_URL = values[1]
            print_wrap('        Qt source dir set to:        ' + QT_SRC_ZIP_URL)
        #url for the module sources
        if item.find('mdl_url') >= 0:
            values = item.split('=')
            QT_MODULE_ZIP_URL = values[1]
            print_wrap('        Qt module source dir set to: ' + QT_MODULE_ZIP_URL)
        #add configure exe also to 7zs
        if item.find('do_7z') >= 0:
            DO_7Z = True
            print_wrap('        Adding configure.exe also to .7z archives ')

    print_wrap('--------------------------------------------------------------------')
    return True


###############################
# function
###############################
def fetch_src_package():
    global QT_SRC_ZIP
    global QT_MODULE_ZIP
    global QT_SRC_7Z
    global QT_MODULE_7Z
    global QT_SRC_7Z_URL
    global QT_MODULE_7Z_URL

    #strip base name for the archive to be downloaded (qt-opensource-xxxx)
    src_pack_basename = os.path.splitext(os.path.basename(QT_SRC_ZIP_URL))[0]
    mdl_pack_basename = os.path.splitext(os.path.basename(QT_MODULE_ZIP_URL))[0]
    #strip base path for the archive to be downloaded (\path\to\the\archive\qt-opensource-xxxx)
    src_pack_basepath = os.path.splitext(QT_SRC_ZIP_URL)[0]
    mdl_pack_basepath = os.path.splitext(QT_MODULE_ZIP_URL)[0]

    print_wrap('------------------- Fetching packages ------------------------------')
    QT_SRC_ZIP = os.path.normpath(SCRIPT_ROOT_DIR + os.sep + os.path.basename(QT_SRC_ZIP_URL))
    print_wrap('    Fetching ' + QT_SRC_ZIP)
    # check first if package on local file system
    if not os.path.isfile(QT_SRC_ZIP):
        if not bldinstallercommon.is_content_url_valid(QT_SRC_ZIP_URL):
            print_wrap('*** Qt src package url: [' + QT_SRC_ZIP_URL + '] is invalid! Abort!')
            sys.exit(-1)
        print_wrap('     Downloading:        ' + QT_SRC_ZIP_URL)
        print_wrap('            into:        ' + QT_SRC_ZIP)
        # start download
        urllib.urlretrieve(QT_SRC_ZIP_URL, QT_SRC_ZIP, reporthook=bldinstallercommon.dlProgress)
    else:
        print_wrap('Found local package, using that: ' + QT_SRC_ZIP)

    print_wrap('    Fetching module ' + QT_MODULE_ZIP)
    QT_MODULE_ZIP = os.path.normpath(SCRIPT_ROOT_DIR + os.sep + os.path.basename(QT_MODULE_ZIP_URL))
    # check first if package on local file system
    if not os.path.isfile(QT_MODULE_ZIP):
        if not bldinstallercommon.is_content_url_valid(QT_MODULE_ZIP_URL):
            print_wrap('*** Module src package url: [' + QT_MODULE_ZIP_URL + '] is invalid! Abort!')
            sys.exit(-1)
        print_wrap('     Downloading:        ' + QT_MODULE_ZIP_URL)
        print_wrap('            into:        ' + QT_MODULE_ZIP)
        # start download
        urllib.urlretrieve(QT_MODULE_ZIP_URL, QT_MODULE_ZIP, reporthook=bldinstallercommon.dlProgress)
    else:
        print_wrap('Found local module package, using that: ' + QT_MODULE_ZIP)

    if DO_7Z:
        QT_SRC_7Z = os.path.normpath(SCRIPT_ROOT_DIR + os.sep + src_pack_basename + '.7z')
        QT_SRC_7Z_URL = src_pack_basepath + '.7z'
        print_wrap('    Fetching ' + QT_SRC_7Z)
        # check first if package on local file system
        if not os.path.isfile(QT_SRC_7Z):
            if not bldinstallercommon.is_content_url_valid(QT_SRC_7Z_URL):
                print_wrap('*** Qt src package url: [' + QT_SRC_7Z_URL + '] is invalid! Abort!')
                sys.exit(-1)
            print_wrap('     Downloading:        ' + QT_SRC_7Z_URL)
            print_wrap('            into:        ' + QT_SRC_7Z)
            # start download
            urllib.urlretrieve(QT_SRC_7Z_URL, QT_SRC_7Z, reporthook=bldinstallercommon.dlProgress)
        else:
            print_wrap('Found local package, using that: ' + QT_SRC_7Z)

        QT_MODULE_7Z = os.path.normpath(SCRIPT_ROOT_DIR + os.sep + mdl_pack_basename + '.7z')
        QT_MODULE_7Z_URL = mdl_pack_basepath + '.7z'
        print_wrap('    Fetching module ' + QT_MODULE_7Z)
        # check first if package on local file system
        if not os.path.isfile(QT_MODULE_7Z):
            if not bldinstallercommon.is_content_url_valid(QT_MODULE_7Z_URL):
                print_wrap('*** Module src package url: [' + QT_MODULE_7Z_URL + '] is invalid! Abort!')
                sys.exit(-1)
            print_wrap('     Downloading:        ' + QT_MODULE_7Z_URL)
            print_wrap('            into:        ' + QT_MODULE_7Z)
            # start download
            urllib.urlretrieve(QT_MODULE_7Z_URL, QT_MODULE_7Z, reporthook=bldinstallercommon.dlProgress)
        else:
            print_wrap('Found local module package, using that: ' + QT_MODULE_7Z)

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def extract_src_package():
    global QT_SRC_DIR
    global QT_PKG_NAME
    global QT_MODULE_PKG_NAME

    print_wrap('---------------- Extracting source package -------------------------')

    contents_before = os.listdir(QT_SRC_DIR)
    bldinstallercommon.extract_file(QT_SRC_ZIP, QT_SRC_DIR)

    contents_after = os.listdir(QT_SRC_DIR)
    items_b = len(contents_before)
    items_a = len(contents_after)
    if items_b < items_a:
        print_wrap('    Source package extracted.')
        for item in contents_after:
            if os.path.isdir(item):
                QT_SRC_DIR = QT_SRC_DIR + os.sep + item
                QT_PKG_NAME = item
        print_wrap('    Source dir: ' + QT_SRC_DIR)
    else:
        print_wrap('*** Unsupported directory structure!!!')
        sys.exit(-1)
    print_wrap('------------')
    print_wrap('    Extracting module zip')
    bldinstallercommon.create_dirs(MODULE_DIR)
    before = os.listdir(MODULE_DIR)
    bldinstallercommon.extract_file(QT_MODULE_ZIP, MODULE_DIR)
    after = os.listdir(MODULE_DIR)
    items_b = len(before)
    items_a = len(after)
    if items_b < items_a:
        print_wrap('    Module package extracted.')
        for item in after:
            if os.path.isdir(MODULE_DIR + os.sep + item):
                QT_MODULE_PKG_NAME = item
                print_wrap('    Module pkg name: ' + QT_MODULE_PKG_NAME)
    else:
        print_wrap('*** Unsupported directory structure!!!')
        sys.exit(-1)

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def configure_qt():
    print_wrap('----------------------- Configuring qt -----------------------------')
    cmd_args = CONFIGURE_CMD + ' ' + CONFIGURE_OPTIONS
    gitignore = QT_SRC_DIR + os.sep + 'qtbase' + os.sep + '.gitignore'
    open(gitignore, 'w').close()

    if os.path.exists(QT_SRC_DIR + os.sep + CONFIGURE_CMD):
        print_wrap(' configure found from ' + QT_SRC_DIR )
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SRC_DIR, False)
    else:
        print_wrap(' configure found from ' + QT_SRC_DIR + os.sep + 'qtbase')
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SRC_DIR + os.sep + 'qtbase', False)

    if QT_MODULE_ZIP_URL:
        cmd_args = "copy " + QT_SRC_DIR + os.sep + 'qtbase' + os.sep + 'configure.exe ' + MODULE_DIR + os.sep + QT_MODULE_PKG_NAME
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), '.', True)
        print_wrap('    copied configure.exe')
    else:
        print_wrap(' module url empty')
        sys.exit(-1)
    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def archive_configure_exe():
    print_wrap('------------- Adding configure.exe to the archive(s) -------------------')
    print_wrap('    Adding to ' + QT_SRC_ZIP)
    archive = os.path.basename(QT_SRC_ZIP)
    zip_archive_file = zipfile.ZipFile(archive, "a" )
    exe_location = QT_SRC_DIR + os.sep + 'qtbase' + os.sep + 'configure.exe'
    exe_in_zip = QT_PKG_NAME + '\\qtbase\\configure.exe'
    try:
        zip_archive_file.write(exe_location, exe_in_zip, zipfile.ZIP_DEFLATED )
    except WindowsError:
        print_wrap('*** Error, failed to add configure.exe to ' + QT_SRC_ZIP)
        print_wrap('*** Exiting..')
        sys.exit(-1)
    zip_archive_file.close()

    print_wrap('    Adding to ' + QT_MODULE_ZIP)
    archive2 = os.path.basename(QT_MODULE_ZIP)
    zip_archive_file2 = zipfile.ZipFile(archive2, "a" )
    exe_in_zip2 = QT_MODULE_PKG_NAME + '\\configure.exe'
    try:
        zip_archive_file2.write(exe_location, exe_in_zip2, zipfile.ZIP_DEFLATED )
    except WindowsError:
        print_wrap('*** Error, failed to add configure.exe to ' + QT_MODULE_ZIP)
        print_wrap('*** Exiting..')
        sys.exit(-1)
    zip_archive_file2.close()

    if DO_7Z:
        print_wrap('    Adding to ' + QT_SRC_7Z)
        cmd_args = ['7z', 'u', QT_SRC_7Z, exe_in_zip]
        bldinstallercommon.do_execute_sub_process_get_std_out(cmd_args, SCRIPT_ROOT_DIR, True, False)

        print_wrap('    Adding to ' + QT_MODULE_7Z)
        cmd_args = ['7z', 'u', QT_MODULE_7Z, QT_MODULE_PKG_NAME + os.sep + 'configure.exe']
        bldinstallercommon.do_execute_sub_process_get_std_out(cmd_args, MODULE_DIR, True, False)

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def main():
    # init
    bldinstallercommon.init_common_module(SCRIPT_ROOT_DIR)
    # init build, check that script is run in Windows
    init()
    # parse cmd line
    parse_cmd_line()
    # fetch src package
    fetch_src_package()
    # extract src package
    extract_src_package()
    # configure
    configure_qt()
    # add configure.exe to the zip
    archive_configure_exe()

###############################
# function
###############################
main()
