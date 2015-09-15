#!/usr/bin/env

############################################################################
##
## Copyright (C) 2015 The Qt Company Ltd.
## Contact: http://www.qt.io/licensing/
##
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
############################################################################

from __future__ import print_function
import os
import re
import sys
import shutil
import urllib
import bldinstallercommon


locationDir = "qt5_qtlocation"
positioningDir = "qt5_qtpositioning"

###############################
# function
###############################
def do_content_comparison(pkgLocation, fileCount):
    pkgFileList = []
    for root, dirs, files in os.walk(pkgLocation):
        for fileName in files:
            pkgFileList.append(fileName)
    # exit if files added to qt5_qtlocation.7z
    if fileCount < len(pkgFileList):
        diff = len(pkgFileList) - fileCount
        # sys.exit('Exiting, file count difference found: %s ' % diff)

###############################
# function
###############################
def do_cleanup(regExp, pkgLocation):
    geoservicesDir = "geoservices"
    print("CLEANUP: ", pkgLocation)
    os.chdir(pkgLocation)
    for root, dirs, files in os.walk(pkgLocation):
        for dirName in dirs:
            if regExp.findall(dirName):
                print("REMOVING DIR: ", os.path.join(root, dirName))
                shutil.rmtree(os.path.join(root, dirName))
            if geoservicesDir in dirName and positioningDir in pkgLocation:
                shutil.rmtree(os.path.join(root, dirName))
        for fileName in files:
            if regExp.findall(fileName):
                if os.path.islink(os.path.join(root, fileName)):
                    print("UNLINK: ", os.path.join(root, fileName))
                    os.unlink(os.path.join(root, fileName))
                if os.path.isfile(os.path.join(root, fileName)):
                    print("REMOVING FILE: ", os.path.join(root, fileName))
                    os.remove(os.path.join(root, fileName))

###############################
# function
###############################
def getFileCount(package):
    filecount = 0
    if "android" in package:
        filecount = 225
    elif "linux_gcc_64_rhel66" in package:
        filecount = 227
    elif "linux_gcc_32_rhel66" in package:
        filecount = 225
    elif "ios" in package:
        filecount = 301
    elif "windows_mingw492_x86" in package:
        filecount = 231
    elif "windows_vs2013_winrt_x64" in package:
        filecount = 241
    elif "windows_vs" in package:
        filecount = 237
    elif "winphone" in package:
        filecount = 241
    else: # mac_x64
        filecount = 243
    return filecount

###############################
# function
###############################
def do_split(location_archive, archives_dir, tmp_archive_dir):

    archivePath = location_archive
    tmpDir = tmp_archive_dir

    # create temp directories for location & positioning
    if not os.path.exists(os.path.join(tmpDir, locationDir)):
        os.makedirs(os.path.join(tmpDir, locationDir))
    if not os.path.exists(os.path.join(tmpDir, positioningDir)):
        os.makedirs(os.path.join(tmpDir, positioningDir))

    locationDest = os.path.join(tmpDir, locationDir)
    positioningDest = os.path.join(tmpDir, positioningDir)
    bldinstallercommon.extract_file(archivePath, locationDest)
    bldinstallercommon.extract_file(archivePath, positioningDest)

    # check for new files in the qtlocation archive
    do_content_comparison(locationDest, getFileCount(archivePath))

    # remove *qtpositioning* from qt5_qtlocation.7z
    locRegex = re.compile('\.*osition\.*')
    do_cleanup(locRegex, locationDest)
    # remove *qtlocation* from qt5_qtpositionign.7z
    posRegex = re.compile('\.*ocation\.*')
    do_cleanup(posRegex, positioningDest)

    # remove original qtlocation
    os.remove(archivePath)

    # archive qt5_qtlocation.7z
    os.chdir(locationDest)
    cmd_args_archive = ['7z', 'a', locationDir, '*']
    bldinstallercommon.do_execute_sub_process(cmd_args_archive, locationDest)
    shutil.copy2(os.path.join(locationDest, locationDir) + '.7z', archives_dir)
    # archive qt5_qtpositioning.7z
    os.chdir(positioningDest)
    cmd_args_archive = ['7z', 'a', positioningDir, '*']
    bldinstallercommon.do_execute_sub_process(cmd_args_archive, positioningDest)
    shutil.copy2(os.path.join(positioningDest, positioningDir) + '.7z', archives_dir)


