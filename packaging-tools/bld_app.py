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
import sys
import fnmatch
import shutil
from urlparse import urlparse

# own imports
from threadedwork import Task, ThreadedWork
from bld_utils import download, removeDir, runCommand, stripVars
import bldinstallercommon

SCRIPT_ROOT_DIR             = os.path.dirname(os.path.realpath(__file__))
APPLICATION_SRC_DIR_NAME    = 'application_src'
APPLICATION_SRC_DIR         = os.path.join(SCRIPT_ROOT_DIR, APPLICATION_SRC_DIR_NAME)
bldinstallercommon.init_common_module(os.getcwd())

def createDownloadExtractTask(url, target_path, temp_path, caller_arguments):
    fileNameFromUrl = os.path.basename(urlparse(url).path)
    sevenzipFile = os.path.join(temp_path, fileNameFromUrl)
    downloadExtractTask = Task("download {0} to {1} and extract it to {2}".format(url, sevenzipFile, target_path))

    downloadExtractTask.addFunction(download, url, sevenzipFile)
    if fileNameFromUrl.endswith('tar.gz'):
        bldinstallercommon.create_dirs(temp_path)
        downloadExtractTask.addFunction(runCommand, "tar zxf {0} -C {1}".format(
            sevenzipFile, target_path), temp_path, caller_arguments)
    else:
        downloadExtractTask.addFunction(runCommand, "7z x -y {0} -o{1}".format(
            sevenzipFile, target_path), temp_path, caller_arguments)
    return downloadExtractTask

def locate_pro(directory):
    print('Trying to locate application .pro file file from: {0}'.format(directory))
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, '*.pro'):
                filename = os.path.join(root, basename)
                print('-> .pro file found: {0}'.format(filename))
                return filename
    print('*** Warning! Unable to locate any .pro file from: {0}'.format(directory))
    return ''

# install an argument parser
parser = argparse.ArgumentParser(prog = os.path.basename(sys.argv[0]),
    add_help=True, description="build Qt 5 based Qt Application", formatter_class=argparse.RawTextHelpFormatter)
if os.name == 'nt':
    parser.epilog = "example on windows: " + os.linesep + "\tpython {0} --clean " \
        "--buildcommand C:\\bin\\ibjom.cmd --installcommand nmake --qt5path ..\\..\\qtapplication_qt5 " \
        "--qt5_essentials7z <uri to qt5_essentials.7z> " \
        "--qt5_addons7z <uri to qt5_addons.7z> " \
        "--application_url <url into application repository>" \
        "--application_branch <application branch>" \
        "--application_dir <Local copy of application>" \
        "--sevenzippath \"C:\\Program Files\\7-Zip\" " \
        "--gitpath \"C:\\Program Files (x86)\\Git\\cmd\" "\
        "".format(os.path.basename(sys.argv[0]))
elif sys.platform == "darwin":
    parser.epilog = "example: " + os.linesep + "\tpython {0} --clean " \
        "--qt5path ../../qtapplication_qt5 " \
        "--qt5_essentials7z <uri to qt5_essentials.7z> " \
        "--qt5_addons7z <uri to qt5_addons.7z> " \
        "--installerbase7z <uri into installer base>" \
        "--application_url <url into application repository>" \
        "--application_branch <application branch>" \
        "--application_dir <Local copy of application>" \
        "--keychain_unlock_script $HOME/unlock-keychain.sh" \
        "".format(os.path.basename(sys.argv[0]))
else:
    parser.epilog = "example: " + os.linesep + "\tpython {0} --clean " \
        "--qt5path ../../qtapplication_qt5 " \
        "--qt5_essentials7z <uri to qt5_essentials.7z> " \
        "--qt5_addons7z <uri to qt5_addons.7z> " \
        "--application_url <url into application repository>" \
        "--application_branch <application branch>" \
        "--application_dir <Local copy of application>" \
        "".format(os.path.basename(sys.argv[0]))

# general arguments
parser.add_argument('--clean', help="clean up everything from old builds", action='store_true', default=False)
parser.add_argument('--qt5path', help="here it expects a compiled Qt5", required=True)
parser.add_argument('--buildcommand', help="this means usually make", default="make")
parser.add_argument('--installcommand', help="this means usually make", default="make")
parser.add_argument('--debug', help="use debug builds", action='store_true', default=False)
parser.add_argument('--qt5_essentials7z', help="a file or url where it get the built qt5 essential content as 7z")
parser.add_argument('--qt5_addons7z', help="a file or url where it get the built qt5 addons content as 7z", required=False, default='')
parser.add_argument('--application_url', help="Git URL for Qt Application", required=False, default='')
parser.add_argument('--application_branch', help="Git branch for Qt Application", required=False, default='')
parser.add_argument('--application_dir', help="Local copy of Qt Application", required=False, default='')
parser.add_argument('--application7z', help="a file or url where it get the application source", required=False, default='')
parser.add_argument('--makeDocs', help="Should the docs be built for this component?", required=False, action='store_true', default=False)
parser.add_argument('--collectDocs', help="Should the docs be collected for this component?", required=False, action='store_true', default=False)


if (sys.platform != "darwin"):
    parser.add_argument('--icu7z', help="a file or url where it get icu libs as 7z", required=False, default='')

# if we are on windows, maybe we want some other arguments
if os.name == 'nt':
    parser.add_argument('--sevenzippath', help="path where the 7zip binary is located", required=False, default='')
    parser.add_argument('--gitpath', help="path where the git binary is located", required=False, default='')

if sys.platform == "darwin":
    parser.add_argument('--installerbase7z', help="a file or url where it get installerbase binary as 7z")
    parser.add_argument('--keychain_unlock_script', help="script for unlocking the keychain used for signing")
callerArguments = parser.parse_args()

# cleanup some values inside the callerArguments object
stripVars(callerArguments, "\"")
if callerArguments.qt5path != os.path.abspath(callerArguments.qt5path):
    print("changing the value of --qt5path from {0} to {1}".format(callerArguments.qt5path,
        os.path.abspath(callerArguments.qt5path)))
    callerArguments.qt5path = os.path.abspath(callerArguments.qt5path)



tempPath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'temp'))

# clone application repo
if callerArguments.application_url != '':
    bldinstallercommon.init_common_module(os.getcwd())
    bldinstallercommon.create_dirs(APPLICATION_SRC_DIR)
    bldinstallercommon.clone_repository(callerArguments.application_url, callerArguments.application_branch, os.path.join(os.path.dirname(__file__), APPLICATION_SRC_DIR_NAME))
    qtApplicationSourceDirectory = APPLICATION_SRC_DIR
elif callerArguments.application7z != '':
    bldinstallercommon.create_dirs(APPLICATION_SRC_DIR)
    myGetQtApp = ThreadedWork("get and extract application src")
    myGetQtApp.addTaskObject(createDownloadExtractTask(callerArguments.application7z, APPLICATION_SRC_DIR, tempPath, callerArguments))
    myGetQtApp.run()
    qtApplicationSourceDirectory = APPLICATION_SRC_DIR
else:
    print(("Using local copy of {0}").format(os.environ['APPLICATION_NAME']))
    qtApplicationSourceDirectory = callerArguments.application_dir

qtApplicationProFile = locate_pro(APPLICATION_SRC_DIR)
# rip out drive letter from path on Windows
#if bldinstallercommon.is_win_platform():
#    qtApplicationProFile = qtApplicationProFile[2:]
pro_file_base_path = os.path.split(qtApplicationProFile)[0]

qtApplicationBuildDirectory = APPLICATION_SRC_DIR + '_build'
if bldinstallercommon.is_win_platform():
    qtApplicationBuildDirectory = pro_file_base_path
qtApplicationInstallDirectory = APPLICATION_SRC_DIR + '_install'
if os.name == 'nt':
    qtApplicationInstallDirectory = qtApplicationInstallDirectory[2:]


### check mac setup
if sys.platform == "darwin":
    if callerArguments.keychain_unlock_script:
        if not os.environ['SIGNING_IDENTITY']:
            print('error: Environment variable SIGNING_IDENTITY not set')
            sys.exit(1)

### clean step
if callerArguments.clean:
    print("##### {0} #####".format("clean old builds"))
    removeDir(callerArguments.qt5path, raiseNoException = True)
    #removeDir(qtApplicationBuildDirectory, raiseNoException = True)
    removeDir(qtApplicationInstallDirectory, raiseNoException = True)
    removeDir(tempPath, raiseNoException = True)

if not os.path.lexists(callerArguments.qt5path) and not (callerArguments.qt5_essentials7z):
    parser.print_help()
    print(("error: Please add the missing qt5_essentials7z argument if the {0} does not exist"
        + os.linesep + os.linesep).format(callerArguments.qt5path))
    sys.exit(1)

qmakeBinary = os.path.abspath(os.path.join(callerArguments.qt5path, 'bin', 'qmake'))

if not os.path.lexists(callerArguments.qt5path):
    myGetQtBinaryWork = ThreadedWork("get and extract Qt 5 binary")
### add get Qt essentials task
    myGetQtBinaryWork.addTaskObject(
        createDownloadExtractTask(callerArguments.qt5_essentials7z, callerArguments.qt5path, tempPath, callerArguments))

    ### add get Qt addons task
    if callerArguments.qt5_addons7z:
        myGetQtBinaryWork.addTaskObject(
            createDownloadExtractTask(callerArguments.qt5_addons7z, callerArguments.qt5path, tempPath, callerArguments))

        if os.name == 'nt':
            targetPath = os.path.join(callerArguments.qt5path, 'bin')
        else:
            targetPath = os.path.join(callerArguments.qt5path, 'lib')

    ### add get icu lib task
    if not bldinstallercommon.is_mac_platform():
        if callerArguments.icu7z:
            if os.name == 'nt':
                targetPath = os.path.join(callerArguments.qt5path, 'bin')
            else:
                targetPath = os.path.join(callerArguments.qt5path, 'lib')

            if not sys.platform == "darwin":
                myGetQtBinaryWork.addTaskObject(
                    createDownloadExtractTask(callerArguments.icu7z, targetPath, tempPath, callerArguments))

    if sys.platform == "darwin":
        myGetQtBinaryWork.addTaskObject(
            createDownloadExtractTask(callerArguments.installerbase7z, tempPath, tempPath, callerArguments))
### run get Qt 5 tasks
    myGetQtBinaryWork.run()

    print("##### {0} #####".format("patch Qt"))
    if sys.platform == "darwin":
        installerbasePath = os.path.join(tempPath, 'ifw-bld/bin/installerbase')
        os.chmod(installerbasePath, 0777)
        runCommand(installerbasePath + " -v --runoperation QtPatch mac " + callerArguments.qt5path  + " qt5",
            qtApplicationBuildDirectory, callerArguments)
    else: # don't use qt.conf file, it has a bug on macos QTBUG-29979
        qtConfFile = open(os.path.join(callerArguments.qt5path, 'bin', 'qt.conf'), "w")
        qtConfFile.write("[Paths]" + os.linesep)
        qtConfFile.write("Prefix=.." + os.linesep)
        qtConfFile.close()
    if sys.platform.startswith('linux'):
        bldinstallercommon.handle_component_rpath(callerArguments.qt5path, 'lib')
    print("##### {0} ##### ... done".format("patch Qt"))
    runCommand(qmakeBinary + " -query", qtApplicationBuildDirectory, callerArguments)


### lets start building

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

environment = {'PATH': os.pathsep.join(pathKeyList)}

environment["INSTALLER_ARCHIVE"] = os.environ['APPLICATION_NAME'] + '.7z'

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

#qtApplicationProFile = locate_pro(APPLICATION_SRC_DIR)
# rip out drive letter from path on Windows
#if bldinstallercommon.is_win_platform():
#    qtApplicationProFile = qtApplicationProFile[2:]

qmakeCommandArguments = [qmakeBinary]
if os.environ.get('EXTRA_QMAKE_ARGS'):
    qmakeCommandArguments += [os.environ["EXTRA_QMAKE_ARGS"]]
qmakeCommandArguments += ["{0}".format(qtApplicationProFile)]
bldinstallercommon.do_execute_sub_process(qmakeCommandArguments, qtApplicationBuildDirectory, True)

#runBuildCommand(currentWorkingDirectory = qtApplicationBuildDirectory, callerArguments = callerArguments,
#    init_environment = environment)
makeCommand = 'make'
if os.name == 'nt' or sys.platform == "darwin":
    makeCommand = callerArguments.buildcommand
#runCommand("{0}".format(makeCommand),currentWorkingDirectory = qtApplicationBuildDirectory, callerArguments = callerArguments, init_environment = environment)
runCommand("{0}".format(makeCommand), currentWorkingDirectory = qtApplicationBuildDirectory)

#runInstallCommand("docs", currentWorkingDirectory = qtApplicationBuildDirectory, callerArguments = callerArguments,
#    init_environment = environment)
makeCommandArguments = 'install INSTALL_ROOT=' + qtApplicationInstallDirectory
runCommand("{0} {1}".format(makeCommand, makeCommandArguments), currentWorkingDirectory = qtApplicationBuildDirectory,
        callerArguments = callerArguments, init_environment = environment)

# patch .so filenames on Windows/Android
if bldinstallercommon.is_win_platform() and os.environ.get('DO_PATCH_ANDROID_SONAME_FILES'):
    bldinstallercommon.rename_android_soname_files(qtApplicationInstallDirectory)

#charts doc collection
if callerArguments.collectDocs:
    doc_list = bldinstallercommon.make_files_list(qtApplicationSourceDirectory, '\\.qch')
    doc_install_dir = qtApplicationInstallDirectory + os.sep + 'doc'
    bldinstallercommon.create_dirs(doc_install_dir)
    for item in doc_list:
        shutil.copy(item, doc_install_dir)

# enginio etc. docs creation
if callerArguments.makeDocs:
    # build docs first
    makeCommandArguments = '-j1 docs'
    runCommand("{0} {1}".format(makeCommand, makeCommandArguments), currentWorkingDirectory = qtApplicationBuildDirectory, callerArguments = callerArguments, init_environment = environment)
    # then make install those
    makeCommandArguments = '-j1 install_docs INSTALL_ROOT=' + qtApplicationInstallDirectory
    runCommand("{0} {1}".format(makeCommand, makeCommandArguments), currentWorkingDirectory = qtApplicationBuildDirectory, callerArguments = callerArguments, init_environment = environment)
    # make separate "doc.7z" for later use if needed
    doc_dir = bldinstallercommon.locate_directory(qtApplicationInstallDirectory, 'doc')
    if doc_dir:
        archive_name = os.environ['APPLICATION_NAME'] + '-' + os.environ['LICENSE'] + '-doc-' + os.environ['APPLICATION_VERSION'] + '.7z'
        archive_cmd = '7z a ' + 'doc_archives' + os.sep + archive_name + ' ' + doc_dir
        runCommand("{0}".format(archive_cmd), currentWorkingDirectory = os.path.dirname(os.path.realpath(__file__)) )

# try to figure out where the actual exported content is
dir_to_archive = os.path.dirname(bldinstallercommon.locate_directory(qtApplicationInstallDirectory, 'qt5_package_dir'))

# create 7z archive
archive_cmd = '7z a ' + 'module_archives' + os.sep + 'qt5_' + os.environ['APPLICATION_NAME'] + '.7z' + ' ' + dir_to_archive + os.sep + 'qt5_package_dir'
runCommand("{0}".format(archive_cmd), currentWorkingDirectory = os.path.dirname(os.path.realpath(__file__)) )

