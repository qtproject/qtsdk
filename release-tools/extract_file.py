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
import tarfile
import shutil


SCRIPT_ROOT_DIR                     = os.getcwd()
WORK_DIR                            = SCRIPT_ROOT_DIR + os.sep + 'work'
QT_SRC_URL                          = ''
QT_SRC_TAR                          = ''
FILE_TO_EXTRACT                     = ''
FILE_NAME_TO_EXTRACT                = ''
STRICT_MODE                         = True


###############################
# function
###############################
def print_wrap(text):
    print 'QT5EXT_FILE: ' + text


###############################
# function
###############################
def print_help():
    print_wrap('*** Error! Insufficient arguments given!')
    print_wrap('')
    print_wrap('Example: python -u extract_file.py tar_url=qt-everywhere-opensource-src-5.0.0.tar.gz file=/path/to/file_to_extract.txt strict_mode=false')
    print_wrap('')
    print_wrap('Available options:')
    print_wrap('')
    print_wrap('  tar_url     = [url where to fetch src package]')
    print_wrap('  file        = [full path to file to extract from the tar]')
    print_wrap('  strict_mode = [true/false] defaults to true')
    print_wrap('')

###############################
# function
###############################
def init():
    print_wrap('Emptying the working directory...')

    if os.path.isdir(WORK_DIR):
        bldinstallercommon.remove_tree(WORK_DIR)
    else:
        print_wrap('    Nothing to delete.')


###############################
# function
###############################
def parse_cmd_line():
    global QT_SRC_URL
    global FILE_TO_EXTRACT
    global FILE_NAME_TO_EXTRACT
    global STRICT_MODE

    print_wrap('---------------- Parsing commandline arguments ---------------------')
    arg_count = len(sys.argv)
    if arg_count < 2:
        print_help()
        sys.exit(-1)
    #Parse command line options
    for item in sys.argv[1:]:
        #url for the sources
        if item.find('tar_url') >= 0:
            values = item.split('=')
            QT_SRC_URL = values[1]
            print_wrap('        Qt source dir set to: ' + QT_SRC_URL)
        #file to extract
        if item.find('file') >= 0:
            values = item.split('=')
            FILE_TO_EXTRACT = values[1]
            FILE_NAME_TO_EXTRACT = os.path.basename(FILE_TO_EXTRACT)
            print_wrap('        File to extract: ' + FILE_TO_EXTRACT)
        #strict mode
        if item.find('strict_mode') >= 0:
            values = item.split('=')
            if values[1] == 'false' or values[1] == 0:
                STRICT_MODE = False
            print_wrap('        Using strict mode: ' + str(STRICT_MODE))

    print_wrap('---------------------------------------------------------------------')
    return True


###############################
# function
###############################
def fetch_src_package():
    global QT_SRC_TAR
    QT_SRC_TAR = os.path.normpath(WORK_DIR + os.sep + os.path.basename(QT_SRC_URL))
    print_wrap('---------------- Fetching Qt src package ---------------------------')
    # check first if package on local file system
    if not os.path.isfile(QT_SRC_TAR):
        if not bldinstallercommon.is_content_url_valid(QT_SRC_URL):
            print_wrap('*** Qt src package url: [' + QT_SRC_URL + '] is invalid! Abort!')
            sys.exit(-1)
        print_wrap('     Downloading:        ' + QT_SRC_URL)
        print_wrap('            into:        ' + QT_SRC_TAR)
        # start download
        urllib.urlretrieve(QT_SRC_URL, QT_SRC_TAR, reporthook=bldinstallercommon.dlProgress)
    else:
        print_wrap('Found local package, using that: ' + QT_SRC_TAR)
    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def extract_file():
    print_wrap('------------ Extracting ' + FILE_TO_EXTRACT + ' -----------------')
    tar_file = tarfile.open(QT_SRC_TAR, 'r')
    file_dst = WORK_DIR
    file_found = True

    try:
        tar_file.extract(FILE_TO_EXTRACT, WORK_DIR)
    except KeyError, err:
        file_found = False
        print_wrap(' *** Error: ' + str(err))
        if STRICT_MODE:
            sys.exit(-1)
        else:
            print_wrap('    Not running in strict mode, continuing the script..')

    if file_found:
        shutil.move(WORK_DIR + os.sep + FILE_TO_EXTRACT, SCRIPT_ROOT_DIR + os.sep + FILE_NAME_TO_EXTRACT)
        print_wrap('    Found the file ' + FILE_NAME_TO_EXTRACT + '. Saved to ' + SCRIPT_ROOT_DIR + os.sep + FILE_NAME_TO_EXTRACT)
    else:
        print_wrap('    File not copied to destination!')

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
    # create work dir
    bldinstallercommon.create_dirs(WORK_DIR)
    # fetch src package
    fetch_src_package()
    # extract the file from archive
    extract_file()


###############################
# function
###############################
main()


