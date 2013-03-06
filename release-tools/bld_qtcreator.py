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

# import the print function which is used in python 3.x
from __future__ import print_function

# built in imports
import argparse # commandline argument parser
import multiprocessing
import os
import stat
import sys

# own imports
from threadedwork import *
from bld_utils import *

def createDownloadExtract7zTask(url, targetPath, tempPath, callerArguments):
    sevenzipFile = os.path.join(tempPath, getFileNameFromUrl(url))
    downloadExtract7zTask = Task("download {} to {} and extract it to {}".format(url, sevenzipFile, targetPath))

    downloadExtract7zTask.addFunction(download, url, sevenzipFile)
    downloadExtract7zTask.addFunction(runCommand, "7z x -y {} -o{}".format(
        sevenzipFile, targetPath), tempPath, callerArguments)
    return downloadExtract7zTask

# install an argument parser
parser = argparse.ArgumentParser(prog = os.path.basename(sys.argv[0]),
    add_help=True, description="build Qt 5 based Qt Creator", formatter_class=argparse.RawTextHelpFormatter)
if os.name == 'nt':
    parser.epilog = "example on windows: " + os.linesep + "\tpython {} --clean " \
        "--buildcommand C:\\bin\\ibjom.cmd --installcommand nmake --qt5path ..\\..\\creator_qt5 " \
        "--qt5_essentials7z http://it-dl241-hki.it.local/packages/qt/5.0.1-released/windows_vs2010_32/qt5_essentials.7z " \
        "--qt5_addons7z http://it-dl241-hki.it.local/packages/qt/5.0.1-released/windows_vs2010_32/qt5_addons.7z " \
        "--sevenzippath \"C:\\Program Files\\7-Zip\" " \
        "--gitpath \"C:\\Program Files (x86)\\Git\\cmd\" "\
        "--icu7z http://origin.releases.qt-project.org/prebuilt/icu_49_win_32_release.7z " \
        "--d3dcompiler7z http://origin.releases.qt-project.org/prebuilt/D3DCompiler_43-x86.dll.7z " \
        "--environment_batch \"C:\\Program Files (x86)\\Microsoft Visual Studio 10.0\\VC\\vcvarsall.bat\" " \
        "--environment_batch_argument x86 " \
        "".format(os.path.basename(sys.argv[0]))
elif sys.platform == "darwin":
    parser.epilog = "example: " + os.linesep + "\tpython {} --clean " \
        "--qt5path ../../qtcreator_qt5 " \
        "--qt5_essentials7z http://it-dl241-hki.it.local/packages/qt/5.0.1-released/mac_cocoa_10.7/qt5_essentials.7z " \
        "--qt5_addons7z http://it-dl241-hki.it.local/packages/qt/5.0.1-released/mac_cocoa_10.7/qt5_addons.7z " \
        "--installerbase7z http://hegel.it.local/projects/installerbase.7z " \
        "".format(os.path.basename(sys.argv[0]))
else:
    parser.epilog = "example: " + os.linesep + "\tpython {} --clean " \
        "--qt5path ../../qtcreator_qt5 " \
        "--qt5_essentials7z http://it-dl241-hki.it.local/packages/qt/5.0.1-released/linux_gcc_64_ubuntu1110/qt5_essentials.7z " \
        "--qt5_addons7z http://it-dl241-hki.it.local/packages/qt/5.0.1-released/linux_gcc_64_ubuntu1110/qt5_addons.7z " \
        "--icu7z http://it-dl241-hki.it.local/packages/qt/5.0.1-released/linux_gcc_64_ubuntu1110/libicu_x86_64_ubuntu1110.7z " \
        "".format(os.path.basename(sys.argv[0]))

# general arguments
parser.add_argument('--clean', help="clean up everything from old builds", action='store_true', default=False)
parser.add_argument('--qt5path', help="here it expects a compiled Qt5", required=True)
parser.add_argument('--buildcommand', help="this means usually make", default="make")
parser.add_argument('--installcommand', help="this means usually make", default="make")
parser.add_argument('--debug', help="use debug builds", action='store_true', default=False)
parser.add_argument('--qt5_essentials7z', help="a file or url where it get the built qt5 essential content as 7z")
parser.add_argument('--qt5_addons7z', help="a file or url where it get the built qt5 essential content as 7z")
if (sys.platform != "darwin"):
    parser.add_argument('--icu7z', help="a file or url where it get icu libs as 7z", required=True)

# if we are on windows, maybe we want some other arguments
if os.name == 'nt':
    parser.add_argument('--d3dcompiler7z', help="a file or url where it get d3dcompiler lib")
    parser.add_argument('--environment_batch', help="batch file that sets up environment")
    parser.add_argument('--environment_batch_argument', help="if the batch file needs an argument just add it with this argument")
    parser.add_argument('--sevenzippath', help="path where the 7zip binary is located")
    parser.add_argument('--gitpath', help="path where the git binary is located")

if sys.platform == "darwin":
    parser.add_argument('--installerbase7z', help="a file or url where it get installerbase binary as 7z")

callerArguments = parser.parse_args()

# cleanup some values inside the callerArguments object
stripVars(callerArguments, "\"")
if callerArguments.qt5path != os.path.abspath(callerArguments.qt5path):
    print("changing the value of --qt5path from {} to {}".format(callerArguments.qt5path,
        os.path.abspath(callerArguments.qt5path)))
    callerArguments.qt5path = os.path.abspath(callerArguments.qt5path)

qtCreatorSourceDirectory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'qt-creator'))
qtCreatorBuildDirectory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..',
    os.path.split(qtCreatorSourceDirectory)[1] + '_build'))
qtCreatorInstallDirectory = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..',
    os.path.split(qtCreatorSourceDirectory)[1] + '_install'))

tempPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'temp'))

### clean step
if callerArguments.clean:
    print("##### {} #####".format("clean old builds"))
    removeDir(callerArguments.qt5path, raiseNoException = True)
    removeDir(qtCreatorBuildDirectory, raiseNoException = True)
    removeDir(qtCreatorInstallDirectory, raiseNoException = True)
    removeDir(tempPath, raiseNoException = True)

if not os.path.lexists(callerArguments.qt5path) and not all(
    (callerArguments.qt5_essentials7z, callerArguments.qt5_addons7z)):
    parser.print_help()
    print(("error: Please add the missing qt5_essentials7z and qt5_addons7z arguments if the {} does not exist"
        + os.linesep + os.linesep).format(callerArguments.qt5path))
    sys.exit(1)

qmakeBinary = os.path.abspath(os.path.join(callerArguments.qt5path, 'bin', 'qmake'))

if not os.path.lexists(callerArguments.qt5path):

    myGetQtBinaryWork = ThreadedWork("get and extract Qt 5 binary")
### add get Qt essentials task
    myGetQtBinaryWork.addTaskObject(
        createDownloadExtract7zTask(callerArguments.qt5_essentials7z, callerArguments.qt5path, tempPath, callerArguments))

### add get Qt addons task
    myGetQtBinaryWork.addTaskObject(
        createDownloadExtract7zTask(callerArguments.qt5_addons7z, callerArguments.qt5path, tempPath, callerArguments))

### add get icu and d3dcompiler lib task
    if os.name == 'nt':
        targetPath = os.path.join(callerArguments.qt5path, 'bin')
    else:
        targetPath = os.path.join(callerArguments.qt5path, 'lib')

    if not sys.platform == "darwin":
        myGetQtBinaryWork.addTaskObject(
            createDownloadExtract7zTask(callerArguments.icu7z, targetPath, tempPath, callerArguments))

    if os.name == 'nt':
        targetPath = os.path.join(callerArguments.qt5path, 'bin')
        myGetQtBinaryWork.addTaskObject(
            createDownloadExtract7zTask(callerArguments.d3dcompiler7z, targetPath, tempPath, callerArguments))
    if sys.platform == "darwin":
        myGetQtBinaryWork.addTaskObject(
            createDownloadExtract7zTask(callerArguments.installerbase7z, tempPath, tempPath, callerArguments))
### run get Qt 5 tasks
    myGetQtBinaryWork.run()

    print("##### {} #####".format("patch Qt"))
    if sys.platform == "darwin":
        installerbasePath = os.path.join(tempPath, 'installerbase.app/Contents/MacOS/installerbase')
        os.chmod(installerbasePath, 0777)
        runCommand(installerbasePath + " -v --runoperation QtPatch mac " + callerArguments.qt5path  + " 5",
            qtCreatorBuildDirectory, callerArguments)
    else: # don't use qt.conf file, it has a bug on macos QTBUG-29979
        qtConfFile = open(os.path.join(callerArguments.qt5path, 'bin', 'qt.conf'), "w")
        qtConfFile.write("[Paths]" + os.linesep)
        qtConfFile.write("Prefix=.." + os.linesep)
        qtConfFile.close()
    print("##### {} ##### ... done".format("patch Qt"))
    runCommand(qmakeBinary + " -query", qtCreatorBuildDirectory, callerArguments)
### lets start building
pathKey='PATH'
if os.name == 'nt':
    pathKey='Path'

# prepare the environment for example setting LD_LIBRARY_PATH
# or adding qmake path into the Path environment variable (Qt deployment step)
pathKeyList = []
qtBinPath = os.path.abspath(os.path.join(callerArguments.qt5path, 'bin'))
pathKeyList.append(qtBinPath)
pythonExecutablePath = os.path.dirname(sys.executable)
pathKeyList.append(pythonExecutablePath)
if hasattr(callerArguments, 'sevenzippath') and callerArguments.sevenzippath:
    pathKeyList.append(callerArguments.sevenzippath)
if hasattr(callerArguments, 'gitpath') and callerArguments.gitpath:
    pathKeyList.append(callerArguments.gitpath)

environment = {pathKey: os.pathsep.join(pathKeyList)}
if sys.platform.startswith('linux'):
    environment["LD_LIBRARY_PATH"] = os.path.join(callerArguments.qt5path, 'lib')
    environment["QMAKESPEC"] = "linux-g++"

if sys.platform == "darwin":
    environment["DYLD_FRAMEWORK_PATH"] = os.path.join(callerArguments.qt5path, 'lib')

if os.name != 'nt':
    environment["MAKEFLAGS"] = "-j" + str(multiprocessing.cpu_count() + 1)

if callerArguments.debug:
    buildType = 'debug'
else:
    buildType = 'release'
buildGitSHA = gitSHA(qtCreatorSourceDirectory, callerArguments)
qtCreatorProFile = os.path.join(qtCreatorSourceDirectory, 'qtcreator.pro')

qmakeCommandArguments = "-r {} QTC_PREFIX={} DEFINES+=IDE_REVISION={} CONFIG+={}".format(
    qtCreatorProFile, qtCreatorInstallDirectory, buildGitSHA, buildType)
runCommand("{} {}".format(qmakeBinary, qmakeCommandArguments), qtCreatorBuildDirectory,
    callerArguments = callerArguments, init_environment = environment)

runBuildCommand(currentWorkingDirectory = qtCreatorBuildDirectory, callerArguments = callerArguments,
    init_environment = environment)

# on windows the install command is usual nmake so single threaded
# because docs is creating same directory at the same time sometimes
runInstallCommand("docs", currentWorkingDirectory = qtCreatorBuildDirectory, callerArguments = callerArguments,
    init_environment = environment)

runInstallCommand('install install_docs deployqt', currentWorkingDirectory = qtCreatorBuildDirectory,
    callerArguments = callerArguments, init_environment = environment)

if os.name == 'nt':
    runInstallCommand('deployartifacts', qtCreatorBuildDirectory,
        callerArguments = callerArguments, init_environment = environment)

# instead of using bindist which compress it in a creator_install directory we are using something different
#runInstallCommand('bindist', qtCreatorBuildDirectory, callerArguments = callerArguments,
#    init_environment = environment)

compress(qtCreatorInstallDirectory, "QtCreator", "qtcreator.7z", callerArguments)
