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
import fileinput

# own imports
from threadedwork import Task, ThreadedWork
from bld_utils import runCommand, stripVars
import bldinstallercommon

SCRIPT_ROOT_DIR             = os.path.dirname(os.path.realpath(__file__))
MODULE_SRC_DIR_NAME         = 'module_src'
MODULE_SRC_DIR              = os.path.join(SCRIPT_ROOT_DIR, MODULE_SRC_DIR_NAME)
bldinstallercommon.init_common_module(os.getcwd())

###############################
# function
###############################
def patch_archive(base_dir, search_string, qt_install_prefix):
    erase_qmake_prl_build_dir(base_dir)
    patch_build_time_paths(base_dir, search_string, qt_install_prefix)

###############################
# function
###############################
def get_qt_install_prefix(qt_path):
    qmake_executable = 'qmake'
    qt_install_prefix = ''
    if os.name == 'nt':
        qmake_executable += '.exe'
    qmake_executable = bldinstallercommon.locate_file(qt_path, qmake_executable)
    if not os.path.isfile(qmake_executable):
        print('*** Unable to locate qmake executable from: {0}'.format(qt_path))
        sys.exit(-1)
    cmd_args = [qmake_executable, '-query']
    qmakePath = os.path.abspath(os.path.join(callerArguments.qt5path, 'bin'))
    dummy, output = bldinstallercommon.do_execute_sub_process(cmd_args, qmakePath, get_output=True)
    # read output line by line
    lines = output.splitlines(True)
    for line in lines:
        if 'QT_INSTALL_PREFIX' in line:
            # save qt_install_prefix
            qt_install_prefix = line[line.index(':') + 1:]
            break

    return qt_install_prefix

###############################
# function
###############################
def erase_qmake_prl_build_dir(search_path):
    print('--- Fix .prl files ---')
    # fetch all .prl files
    file_list = bldinstallercommon.make_files_list(search_path, '\\.prl')
    # erase lines starting with 'QMAKE_PRL_BUILD_DIR' from .prl files
    for item in file_list:
        found = False
        for line in fileinput.FileInput(item, inplace = 1):
            if line.startswith('QMAKE_PRL_BUILD_DIR'):
                found = True
                print(''.rstrip('\n'))
            else:
                print(line.rstrip('\n'))
        if found:
            print('Erased \'QMAKE_PRL_BUILD_DIR\' from: ' + item)

###############################
# function
###############################
def patch_build_time_paths(search_path, search_string, qt_install_prefix):
    extension_list = ['*.prl', '*.pri', '*.pc', '*.la']
    file_list = bldinstallercommon.search_for_files(search_path, extension_list, search_string)

    for item in file_list:
        print('Replacing \'{0}\' paths from file: {1}'.format(search_string, item))
        for line in fileinput.FileInput(item, inplace = 1):
            if not search_string in line:
                print(line.rstrip('\n'))
                continue
            patched_line = line.replace(search_string, qt_install_prefix.rstrip('\n'))
            print(patched_line.rstrip('\n'))

###############################
# function
###############################
def locate_pro(directory):
    print('Trying to locate module .pro file file from: {0}'.format(directory))
    for root, dummy, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, '*.pro'):
                filename = os.path.join(root, basename)
                print('-> .pro file found: {0}'.format(filename))
                return filename
    print('*** Warning! Unable to locate any .pro file from: {0}'.format(directory))
    return ''

# install an argument parser
parser = argparse.ArgumentParser(prog = os.path.basename(sys.argv[0]),
    add_help=True, description="build Qt 5 based Qt Module", formatter_class=argparse.RawTextHelpFormatter)
if os.name == 'nt':
    parser.epilog = "example on windows: " + os.linesep + "\tpython {0} --clean " \
        "--buildcommand C:\\bin\\ibjom.cmd" \
        "--qt5_module_url <uri to qt5_essentials.7z> " \
        "--qt5_module_url <uri to qt5_addons.7z> " \
        "--qt5_module_url <uri to qt5_webengine.7z> " \
        "--module_url <url into module repository>" \
        "--module_branch <module branch>" \
        "--module_dir <Local copy of module>" \
        "".format(os.path.basename(sys.argv[0]))
elif sys.platform == "darwin":
    parser.epilog = "example: " + os.linesep + "\tpython {0} --clean " \
        "--qt5_module_url <uri to qt5_essentials.7z> " \
        "--qt5_module_url <uri to qt5_addons.7z> " \
        "--qt5_module_url <uri to qt5_webengine.7z> " \
        "--module_url <url into module repository>" \
        "--module_branch <module branch>" \
        "--module_dir <Local copy of module>" \
        "".format(os.path.basename(sys.argv[0]))
else:
    parser.epilog = "example: " + os.linesep + "\tpython {0} --clean " \
        "--qt5_module_url <uri to qt5_essentials.7z> " \
        "--qt5_module_url <uri to qt5_addons.7z> " \
        "--qt5_module_url <uri to qt5_webengine.7z> " \
        "--module_url <url into module repository>" \
        "--module_branch <module branch>" \
        "--module_dir <Local copy of module>" \
        "".format(os.path.basename(sys.argv[0]))

# general arguments
parser.add_argument('--clean', help="clean up everything from old builds", action='store_true', default=False)
parser.add_argument('--qt5path', help="here it expects a compiled Qt5", required=True)
parser.add_argument('--buildcommand', help="this means usually make", default="make")
parser.add_argument('--installcommand', help="this means usually make", default="make")
parser.add_argument('--debug', help="use debug builds", action='store_true', default=False)
parser.add_argument('--qt5_module_url', help="a file or url where to get a qt5 module's binary content that is needed for the build as 7z",
    dest='qt5_module_urls', action='append')
parser.add_argument('--module_url', help="Git URL for Qt Module", required=False, default='')
parser.add_argument('--module_branch', help="Git branch for Qt Module", required=False, default='')
parser.add_argument('--module_dir', help="Local copy of Qt Module", required=False, default='')
parser.add_argument('--module7z', help="a file or url where it get the module source", required=False, default='')
parser.add_argument('--makeDocs', help="Should the docs be built for this component?", required=False, action='store_true', default=False)
parser.add_argument('--collectDocs', help="Should the docs be collected for this component?", required=False, action='store_true', default=False)


if (sys.platform != "darwin"):
    parser.add_argument('--icu7z', help="a file or url where it get icu libs as 7z", required=False, default='')

callerArguments = parser.parse_args()

# cleanup some values inside the callerArguments object
stripVars(callerArguments, "\"")
if callerArguments.qt5path != os.path.abspath(callerArguments.qt5path):
    print("changing the value of --qt5path from {0} to {1}".format(callerArguments.qt5path,
        os.path.abspath(callerArguments.qt5path)))
    callerArguments.qt5path = os.path.abspath(callerArguments.qt5path)



tempPath = os.path.abspath(os.path.join(os.path.dirname(__file__), 'temp'))

# clone module repo
if callerArguments.module_url != '':
    bldinstallercommon.init_common_module(os.getcwd())
    bldinstallercommon.create_dirs(MODULE_SRC_DIR)
    bldinstallercommon.clone_repository(callerArguments.module_url, callerArguments.module_branch, os.path.join(os.path.dirname(__file__), MODULE_SRC_DIR_NAME))
    qtModuleSourceDirectory = MODULE_SRC_DIR
elif callerArguments.module7z != '':
    bldinstallercommon.create_dirs(MODULE_SRC_DIR)
    myGetQtModule = ThreadedWork("get and extract module src")
    myGetQtModule.addTaskObject(bldinstallercommon.create_download_extract_task(callerArguments.module7z, MODULE_SRC_DIR, tempPath, callerArguments))
    myGetQtModule.run()
    qtModuleSourceDirectory = MODULE_SRC_DIR
else:
    print(("Using local copy of {0}").format(os.environ['MODULE_NAME']))
    qtModuleSourceDirectory = callerArguments.module_dir

qtModuleProFile = locate_pro(MODULE_SRC_DIR)
# rip out drive letter from path on Windows
pro_file_base_path = os.path.split(qtModuleProFile)[0]

qtModuleBuildDirectory = MODULE_SRC_DIR + '_build'
if bldinstallercommon.is_win_platform():
    qtModuleBuildDirectory = pro_file_base_path
qtModuleInstallDirectory = MODULE_SRC_DIR + '_install'
if os.name == 'nt':
    qtModuleInstallDirectory = qtModuleInstallDirectory[2:]

    # check whether this is a QNX build
    if any('qnx' in qt5_url.lower() for qt5_url in callerArguments.qt5_module_urls):
        # apply the workaround from QTBUG-38555
        qtModuleInstallDirectory = qtModuleInstallDirectory.replace('\\','/').replace('/', '\\', 1)


### clean step
if callerArguments.clean:
    print("##### {0} #####".format("clean old builds"))
    bldinstallercommon.remove_tree(callerArguments.qt5path)
    bldinstallercommon.remove_tree(qtModuleInstallDirectory)
    bldinstallercommon.remove_tree(tempPath)

if not os.path.lexists(callerArguments.qt5path) and not callerArguments.qt5_module_urls:
    parser.print_help()
    print(("error: Please add the missing qt5_module_url arguments if the {0} does not exist"
        + os.linesep + os.linesep).format(callerArguments.qt5path))
    sys.exit(1)

qmakeBinary = os.path.abspath(os.path.join(callerArguments.qt5path, 'bin', 'qmake'))

if not os.path.lexists(callerArguments.qt5path):
    # get Qt
    myGetQtBinaryWork = ThreadedWork("get and extract Qt 5 binary")
    bldinstallercommon.add_qt_download(myGetQtBinaryWork, callerArguments.qt5_module_urls,
                                       callerArguments.qt5path, tempPath, callerArguments)
    myGetQtBinaryWork.run()

    # Save QT_INSTALL_PREFIX
    qt_install_prefix = get_qt_install_prefix(callerArguments.qt5path)

    # "install" Qt
    bldinstallercommon.patch_qt(callerArguments.qt5path)

### lets start building

# prepare the environment for example setting LD_LIBRARY_PATH
# or adding qmake path into the Path environment variable (Qt deployment step)
pathKeyList = []
qtBinPath = os.path.abspath(os.path.join(callerArguments.qt5path, 'bin'))
pathKeyList.append(qtBinPath)
pythonExecutablePath = os.path.dirname(sys.executable)
pathKeyList.append(pythonExecutablePath)

environment = {'PATH': os.pathsep.join(pathKeyList)}

if sys.platform.startswith('linux'):
    environment["LD_LIBRARY_PATH"] = os.pathsep.join([os.path.join(callerArguments.qt5path, 'lib')]
+ os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep))
    environment["QMAKESPEC"] = "linux-g++"

if sys.platform == "darwin":
    environment["DYLD_FRAMEWORK_PATH"] = os.path.join(callerArguments.qt5path, 'lib')

if os.name != 'nt':
    environment["MAKEFLAGS"] = "-j" + str(multiprocessing.cpu_count() + 1)

if callerArguments.debug:
    buildType = 'debug'
else:
    buildType = 'release'

qmakeCommandArguments = [qmakeBinary]
if os.environ.get('EXTRA_QMAKE_ARGS'):
    qmakeCommandArguments += [os.environ["EXTRA_QMAKE_ARGS"]]
qmakeCommandArguments += ["{0}".format(qtModuleProFile)]
bldinstallercommon.runCommand(qmakeCommandArguments, qtModuleBuildDirectory)

makeCommand = 'make'
if os.name == 'nt' or sys.platform == "darwin":
    makeCommand = callerArguments.buildcommand
ret = runCommand("{0}".format(makeCommand), currentWorkingDirectory = qtModuleBuildDirectory)
if ret:
    sys.exit('Failure running the last command: %i' % ret)

installCommand = 'make'
if os.name == 'nt' or sys.platform == "darwin":
    installCommand = callerArguments.installcommand

installCommandArguments = 'install INSTALL_ROOT=' + qtModuleInstallDirectory
ret = runCommand("{0} {1}".format(installCommand, installCommandArguments), currentWorkingDirectory = qtModuleBuildDirectory,
        callerArguments = callerArguments, init_environment = environment)
if ret:
    sys.exit('Failure running the last command: %i' % ret)

# patch .so filenames on Windows/Android
if bldinstallercommon.is_win_platform() and os.environ.get('DO_PATCH_ANDROID_SONAME_FILES'):
    bldinstallercommon.rename_android_soname_files(qtModuleInstallDirectory)

#doc collection
if callerArguments.collectDocs:
    doc_list = bldinstallercommon.make_files_list(qtModuleSourceDirectory, '\\.qch')
    doc_install_dir = qtModuleInstallDirectory + os.sep + 'doc'
    bldinstallercommon.create_dirs(doc_install_dir)
    for item in doc_list:
        shutil.copy(item, doc_install_dir)

# enginio etc. docs creation
if callerArguments.makeDocs:
    # build docs first
    makeCommandArguments = '-j1 docs'
    ret = runCommand("{0} {1}".format(makeCommand, makeCommandArguments), currentWorkingDirectory = qtModuleBuildDirectory, callerArguments = callerArguments, init_environment = environment)
    if ret:
        sys.exit('Failure running the last command: %i' % ret)
    # then make install those
    installCommandArguments = '-j1 install_docs INSTALL_ROOT=' + qtModuleInstallDirectory
    ret = runCommand("{0} {1}".format(installCommand, installCommandArguments), currentWorkingDirectory = qtModuleBuildDirectory, callerArguments = callerArguments, init_environment = environment)
    if ret:
        sys.exit('Failure running the last command: %i' % ret)
    # make separate "doc.7z" for later use if needed
    doc_dir = bldinstallercommon.locate_directory(qtModuleInstallDirectory, 'doc')
    if doc_dir:
        archive_name = os.environ['MODULE_NAME'] + '-' + os.environ['LICENSE'] + '-doc-' + os.environ['MODULE_VERSION'] + '.7z'
        archive_cmd = '7z a ' + 'doc_archives' + os.sep + archive_name + ' ' + doc_dir
        ret = runCommand("{0}".format(archive_cmd), currentWorkingDirectory = os.path.dirname(os.path.realpath(__file__)) )
        if ret:
            sys.exit('Failure running the last command: %i' % ret)

# try to figure out where the actual exported content is
dir_to_archive = os.path.dirname(bldinstallercommon.locate_directory(qtModuleInstallDirectory, 'qt5_package_dir'))

# if .tag file exists in the source package (sha1) then copy it into the binary archive
tag_file = bldinstallercommon.locate_file(MODULE_SRC_DIR, '.tag')
if tag_file:
    shutil.copy2(tag_file, dir_to_archive + os.sep + 'qt5_package_dir')

# Pre-patch the package for IFW to patch it correctly during installation
basedir = dir_to_archive + os.sep + 'qt5_package_dir'
patch_archive(basedir, callerArguments.qt5path, qt_install_prefix)

# create 7z archive
archive_cmd = '7z a ' + 'module_archives' + os.sep + 'qt5_' + os.environ['MODULE_NAME'] + '.7z' + ' ' + dir_to_archive + os.sep + 'qt5_package_dir'
ret = runCommand("{0}".format(archive_cmd), currentWorkingDirectory = os.path.dirname(os.path.realpath(__file__)) )
if ret:
    sys.exit('Failure running the last command: %i' % ret)
