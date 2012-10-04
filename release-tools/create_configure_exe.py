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
import bldinstallercommon
import zipfile

SCRIPT_ROOT_DIR                     = os.getcwd()
QT_SRC_URL                          = ''
QT_SRC_ZIP                          = ''
QT_SRC_DIR                          = SCRIPT_ROOT_DIR
QT_PKG_NAME                         = ''
CONFIGURE_OPTIONS                   = '-opensource -debug-and-release -release -nomake tests -confirm-license'
CONFIGURE_CMD                       = 'configure'



###############################
# function
###############################
def print_wrap(text):
    print 'QT5CONF_EXE: ' + text


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
    global QT_SRC_URL

    print_wrap('---------------- Parsing commandline arguments ---------------------')
    arg_count = len(sys.argv)
    if arg_count < 2:
        print_help()
        sys.exit(-1)
    #Parse command line options
    for item in sys.argv[1:]:
        #url for the sources
        if item.find('src_url') >= 0:
            values = item.split('=')
            QT_SRC_URL = values[1]
            print_wrap('        Qt source dir set to: ' + QT_SRC_URL)

    print_wrap('---------------------------------------------------------------------')
    return True


###############################
# function
###############################
def fetch_src_package():
    global QT_SRC_ZIP
    QT_SRC_ZIP = os.path.normpath(SCRIPT_ROOT_DIR + os.sep + os.path.basename(QT_SRC_URL))
    print_wrap('---------------- Fetching Qt src package ---------------------------')
    # check first if package on local file system
    if not os.path.isfile(QT_SRC_ZIP):
        if not bldinstallercommon.is_content_url_valid(QT_SRC_URL):
            print_wrap('*** Qt src package url: [' + QT_SRC_URL + '] is invalid! Abort!')
            sys.exit(-1)
        print_wrap('     Downloading:        ' + QT_SRC_URL)
        print_wrap('            into:        ' + QT_SRC_ZIP)
        # start download
        urllib.urlretrieve(QT_SRC_URL, QT_SRC_ZIP, reporthook=bldinstallercommon.dlProgress)
    else:
        print_wrap('Found local package, using that: ' + QT_SRC_ZIP)
    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def extract_src_package():
    global QT_SRC_DIR
    global QT_PKG_NAME

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

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def configure_qt():
    print_wrap('----------------------- Configuring qt -----------------------------')
    cmd_args = CONFIGURE_CMD + ' ' + CONFIGURE_OPTIONS
    gitignore = QT_SRC_DIR + os.sep + 'qtbase' + os.sep + '.gitignore'
    open(gitignore, 'w').close()
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SRC_DIR, True)
    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def archive_configure_exe():
    print_wrap('------------- Adding configure.exe to the archive -------------------')
    archive = os.path.basename(QT_SRC_ZIP)
    zip_archive_file = zipfile.ZipFile(archive, "a" )
    exe_location = QT_SRC_DIR + os.sep + 'qtbase' + os.sep + 'configure.exe'
    exe_in_zip = QT_PKG_NAME + '\\qtbase\\configure.exe'
    zip_archive_file.write(exe_location, exe_in_zip, zipfile.ZIP_DEFLATED )
    zip_archive_file.close()
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
