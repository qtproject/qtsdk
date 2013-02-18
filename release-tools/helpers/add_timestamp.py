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

import sys
import os
from datetime import date


###############################
# function
###############################
def print_help():
    print '  Usage:'
    print '    add_timestamp.py file=file_to_rename.run build=21'
    print '  Mandatory options:'
    print '    file      = file to rename'
    print '    build     = build number to use in renaming'
    print '  Available options:'
    print '    help      = print this help'


###############################
# function
###############################
def main():
    installer = ''
    build_number = ''
    for item in sys.argv[1:]:
        #original filename
        if item.find('file') >= 0:
            values = item.split('=')
            installer = values[1]
            if not os.path.isfile(installer):
                print '*** Error: can\'t open file ' + installer
                sys.exit(-1)
            print '        Installer name: ' + installer
        #bld number
        elif item.find('build') >= 0:
            values = item.split('=')
            build_number = values[1]
            print '        Build number:   ' + build_number
        elif item.find('help') >= 0:
            print_help()
            sys.exit(-1)
        else:
            print '*** Error: unknown option!'
            print_help()
            sys.exit(-1)
    if not installer or not build_number:
        print '*** Error: insufficient arguments given!'
        print_help()
        sys.exit(-1)

    root, ext = os.path.splitext(installer)
    new_name = root + '-' + str(date.today()) + '-' + build_number + ext
    os.rename(installer, new_name)
    print '    Renamed ' + installer + ' to ' + new_name

main()
