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
import re
import shutil
import subprocess
from subprocess import PIPE, STDOUT
import sys
import urllib
import fileinput
import bldinstallercommon
import patch_qmake_qt_key

SCRIPT_ROOT_DIR                     = os.getcwd()
WORK_DIR_NAME                       = 'qt5_workdir'
WORK_DIR                            = SCRIPT_ROOT_DIR + os.sep + WORK_DIR_NAME
QT_SRC_PACKAGE_URL                  = ''
QT_PACKAGE_SAVE_AS_TEMP             = ''
QT_SOURCE_DIR                       = WORK_DIR + os.sep + 'w'
MAKE_INSTALL_ROOT_DIR_NAME          = 'qt5_install_root'
MAKE_INSTALL_ROOT_DIR               = WORK_DIR + os.sep + MAKE_INSTALL_ROOT_DIR_NAME #main dir for submodule installations
MISSING_MODULES_FILE                = WORK_DIR + os.sep + 'missing_modules.txt'
CONFIGURE_CMD                       = ''
MAKE_CMD                            = ''
MAKE_THREAD_COUNT                   = '8' # some initial default value
MAKE_INSTALL_CMD                    = ''
MODULE_ARCHIVE_DIR_NAME             = 'module_archives'
MODULE_ARCHIVE_DIR                  = SCRIPT_ROOT_DIR + os.sep + MODULE_ARCHIVE_DIR_NAME
MAIN_INSTALL_DIR_NAME               = 'main_install'
SUBMODULE_INSTALL_BASE_DIR_NAME     = "submodule_install_"
#list of modules, only a backup list, this list will be updated during script execution
QT5_MODULES_LIST                    = [ 'qt3d', 'qlalr', 'qtactiveqt', 'qtbase',     \
                                        'qtconnectivity', 'qtdeclarative', 'qtdoc', \
                                        'qtfeedback', 'qtgraphicaleffects', \
                                        'qtimageformats', 'qtjsbackend', \
                                        'qtlocation', 'qtmultimedia', 'qtpim', \
                                        'qtqa', 'qtquick1', 'qtrepotools', 'qtscript', \
                                        'qtsensors', 'qtsvg', 'qtsystems', 'qttools', \
                                        'qttranslations', 'qtwayland', 'webkit', \
                                        'qtwebkit-examples-and-demos', 'qtxmlpatterns']
QT5_MODULES_IGNORE_LIST             = []
CONFIGURE_OPTIONS                   = '-opensource -debug-and-release -release -nomake tests -confirm-license'
DEVEL_MODE                          = False
FORCE_MAKE                          = False
ORIGINAL_QMAKE_QT_PRFXPATH          = ''
SILENT_BUILD                        = False
STRICT_MODE                         = True
PADDING                             = "______________________________PADDING______________________________"
FILES_TO_REMOVE_LIST                = ['Makefile', 'Makefile.Release', 'Makefile.Debug', \
                                       '.o', '.moc', '.init-repository', \
                                       '.gitignore', '.obj']
IGNORE_PATCH_LIST                   = ['.png', '.jpg', '.gif', '.bmp', '.exe', '.dll', '.lib', '.pdb', '.qph']


###############################
# function
###############################
def print_wrap(text):
    print 'QT5BLD: ' + text


###############################
# function
###############################
def init_mkqt5bld():
    global CONFIGURE_CMD
    global CONFIGURE_OPTIONS
    global MAKE_CMD
    global MAKE_INSTALL_CMD
    global SUBMODULE_INSTALL_BASE_DIR_NAME
    global MAKE_INSTALL_ROOT_DIR

    print_wrap('---------------- Initializing build --------------------------------')
    if bldinstallercommon.is_linux_platform():          #linux
        CONFIGURE_CMD = './'
        CONFIGURE_OPTIONS += ' -no-gtkstyle'
    elif bldinstallercommon.is_mac_platform():          #mac
        CONFIGURE_CMD = './'
        #CONFIGURE_OPTIONS += ' -make libs -no-pch' <- not sure if these are needed,
        #Added -developer-build to get the sources built, should be removed later..?
        CONFIGURE_OPTIONS = '-developer-build -opensource -confirm-license -nomake tests -platform macx-clang -prefix $PWD/qtbase'

    #Add padding to original rpaths to make sure that original rpath is longer than the new
    if bldinstallercommon.is_linux_platform() or bldinstallercommon.is_solaris_platform():
        CONFIGURE_OPTIONS += ' -R ' + PADDING

    CONFIGURE_CMD += 'configure'

    # make cmd
    if MAKE_CMD == '':  #if not given in commandline param, use nmake or make according to the os
        if bldinstallercommon.is_win_platform():        #win
            MAKE_CMD = 'nmake'
            MAKE_INSTALL_CMD = 'nmake'
            if SILENT_BUILD:
                MAKE_CMD += ' /s'
                MAKE_INSTALL_CMD += ' /s'
            if FORCE_MAKE:
                MAKE_CMD += ' /l'
                MAKE_INSTALL_CMD += ' \l'
            MAKE_INSTALL_CMD += ' install'
        elif bldinstallercommon.is_linux_platform() or bldinstallercommon.is_mac_platform():    #linux & mac
            MAKE_CMD = 'make'
            MAKE_INSTALL_CMD = 'make'
            if SILENT_BUILD:
                MAKE_CMD += ' -s'
                MAKE_INSTALL_CMD += ' -s'
            if FORCE_MAKE:
                MAKE_CMD += ' -i'
                MAKE_INSTALL_CMD += ' -i'
            MAKE_INSTALL_CMD += ' install'

    #remove old working dirs
    if os.path.exists(WORK_DIR):
        print_wrap('    Removing old work dir ' + WORK_DIR)
        bldinstallercommon.remove_tree(WORK_DIR)
    if os.path.exists(MODULE_ARCHIVE_DIR):
        print_wrap('    Removing old module archive dir ' + MODULE_ARCHIVE_DIR)
        bldinstallercommon.remove_tree(MODULE_ARCHIVE_DIR)

    print_wrap('    Using ' + MAKE_CMD + ' for making and ' + MAKE_INSTALL_CMD + ' for installing')
    print_wrap('    Qt configure command set to: ' + CONFIGURE_CMD + ' ' + CONFIGURE_OPTIONS)
    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def fetch_src_package():
    global QT_PACKAGE_SAVE_AS_TEMP
    QT_PACKAGE_SAVE_AS_TEMP = os.path.normpath(WORK_DIR + os.sep + os.path.basename(QT_SRC_PACKAGE_URL))
    print_wrap('---------------- Fetching Qt src package ---------------------------')
    # check first if package on local file system
    if not os.path.isfile(QT_PACKAGE_SAVE_AS_TEMP):
        if not bldinstallercommon.is_content_url_valid(QT_SRC_PACKAGE_URL):
            print_wrap('*** Qt src package url: [' + QT_SRC_PACKAGE_URL + '] is invalid! Abort!')
            sys.exit(-1)
        print_wrap('     Downloading:        ' + QT_SRC_PACKAGE_URL)
        print_wrap('            into:        ' + QT_PACKAGE_SAVE_AS_TEMP)
        # start download
        urllib.urlretrieve(QT_SRC_PACKAGE_URL, QT_PACKAGE_SAVE_AS_TEMP, reporthook=bldinstallercommon.dlProgress)
    else:
        print_wrap('Found local package, using that: ' + QT_PACKAGE_SAVE_AS_TEMP)
    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def extract_src_package():
    global QT_SOURCE_DIR
    global CONFIGURE_CMD
    print_wrap('---------------- Extracting source package -------------------------')
    if os.path.exists(QT_SOURCE_DIR):
        print_wrap('Source dir ' + QT_SOURCE_DIR + ' already exists, using that (not re-extracting the archive!)')
    else:
        print_wrap('Extracting source package: ' + QT_PACKAGE_SAVE_AS_TEMP)
        print_wrap('Into:                      ' + QT_SOURCE_DIR)
        bldinstallercommon.create_dirs(QT_SOURCE_DIR)
        bldinstallercommon.extract_file(QT_PACKAGE_SAVE_AS_TEMP, QT_SOURCE_DIR)

    l = os.listdir(QT_SOURCE_DIR)
    items = len(l)
    if items == 1:
        print_wrap('    Replacing qt-everywhere-xxx-src-5.0.0 with shorter path names')
        shorter_dir_path = QT_SOURCE_DIR + os.sep + 's'
        os.rename(QT_SOURCE_DIR + os.sep + l[0], shorter_dir_path)
        print_wrap('    Old source dir: ' + QT_SOURCE_DIR)
        QT_SOURCE_DIR = shorter_dir_path
        print_wrap('    New source dir: ' + QT_SOURCE_DIR)
        #CONFIGURE_CMD = QT_SOURCE_DIR + os.sep + CONFIGURE_CMD   #is this needed in shadow build?
    else:
        print_wrap('*** Unsupported directory structure!!!')
        sys.exit(-1)

    #Remove the modules to be ignored
    for ignore in QT5_MODULES_IGNORE_LIST:
        if os.path.exists(QT_SOURCE_DIR + os.sep + ignore):
            print_wrap('    Removing ' + ignore)
            bldinstallercommon.remove_tree(QT_SOURCE_DIR + os.sep + ignore)

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def build_qt():
    global QT5_MODULES_LIST
    # configure
    print_wrap('---------------- Configuring Qt ------------------------------------')
    cmd_args = CONFIGURE_CMD + ' ' + CONFIGURE_OPTIONS
    print_wrap('    Configure line: ' + cmd_args)
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR, True)

    # build
    print_wrap('---------------- Building Qt ---------------------------------------')
    #create list of modules in default make order
    regex = re.compile('^make_first:.*') #search line starting with 'make_default:'
    submodule_list = []
    modules_found = 0
    if os.path.exists(QT_SOURCE_DIR + os.sep + 'Makefile'):
        print_wrap('    Generating ordered list of submodules from main Makefile')
        makefile = open(QT_SOURCE_DIR + os.sep + 'Makefile', 'r')
        for line in makefile:
            lines = regex.findall(line)
            for make_def_line in lines:
                #print_wrap(make_def_line)
                make_def_list = make_def_line.split(' ')
                #TODO: check if there is more than one line in Makefile
                #change 'module-qtbase-make_first' to 'qtbase'
                for item in make_def_list:
                    if item.startswith('module-'):
                        submodule_name = item[7:]   #7 <- module-
                        index = submodule_name.index('-make_first')
                        submodule_list.append(submodule_name[:index])
                        modules_found = 1
                    #webkit is listed with different syntax: sub-webkit-pri-make_first
                    elif item.startswith('sub-'):
                        submodule_name = item[4:]   #4 <- sub-
                        index = submodule_name.index('-pri-make_first')
                        submodule_list.append(submodule_name[:index])

        if modules_found == 1:
            QT5_MODULES_LIST = submodule_list
            print_wrap('    Modules list updated, modules list is now in default build order.')
        else:
            print_wrap('    Warning! Could not extract module build order from ' + QT_SOURCE_DIR + os.sep + 'Makefile. Using default (non-ordered) list.')
    else:
        print_wrap('*** Error! Main Makefile not found. Build failed!')
        sys.exit(-1)

    #remove if old dir exists
    if os.path.exists(MAKE_INSTALL_ROOT_DIR):
        shutil.rmtree(MAKE_INSTALL_ROOT_DIR)
    #create install dirs
    bldinstallercommon.create_dirs(MAKE_INSTALL_ROOT_DIR)

    #make each submodule
    for module_name in QT5_MODULES_LIST:
        print_wrap('    Building module ' + module_name)
        cmd_args = MAKE_CMD
        if bldinstallercommon.is_linux_platform():
            cmd_args += ' -j' + MAKE_THREAD_COUNT
        cmd_args += ' module-' + module_name
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR, STRICT_MODE)

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def install_qt():
    print_wrap('---------------- Installing Qt -------------------------------------')
    #make install to single install root
    cmd_args = ''
    install_root_path = MAKE_INSTALL_ROOT_DIR + os.sep + MAIN_INSTALL_DIR_NAME
    #TODO: there probably is a better way to fix the delimeters, but this is working atm
    if 'mingw' in MAKE_CMD:
        install_root_path = WORK_DIR + '/' + MAKE_INSTALL_ROOT_DIR_NAME + '/' + MAIN_INSTALL_DIR_NAME
    if bldinstallercommon.is_win_platform():
        install_root_path = install_root_path[3:]
        print_wrap('    On Windows, use install root path: ' + install_root_path)

    print_wrap('    Install modules to single INSTALL_ROOT')
    for module_name in QT5_MODULES_LIST:
        submodule_dir_name = QT_SOURCE_DIR + os.sep + module_name
        make_i_cmd = MAKE_INSTALL_CMD
        if module_name == 'qtwebkit':
            make_i_cmd = make_i_cmd + ' -f Makefile.WebKit install'
        cmd_args = ''
        cmd_args += make_i_cmd + ' ' + 'INSTALL_ROOT=' + install_root_path
        print_wrap('    Installing module: ' + module_name)
        print_wrap('          -> cmd args: ' + cmd_args)
        print_wrap('                -> in: ' + submodule_dir_name)
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), submodule_dir_name, STRICT_MODE)

    #make install for each module with INSTALL_ROOT
    print_wrap('    Install modules to separate INSTALL_ROOT')
    for module_name in QT5_MODULES_LIST:
        install_root_path = MAKE_INSTALL_ROOT_DIR + os.sep + SUBMODULE_INSTALL_BASE_DIR_NAME + module_name
        if 'mingw' in MAKE_CMD:
            install_root_path = WORK_DIR + '/' + MAKE_INSTALL_ROOT_DIR_NAME + '/' + SUBMODULE_INSTALL_BASE_DIR_NAME + module_name
        if bldinstallercommon.is_win_platform():
            install_root_path = install_root_path[3:]
            print_wrap('    Using install root path: ' + install_root_path)
        submodule_dir_name = QT_SOURCE_DIR + os.sep + module_name
        make_i_cmd = MAKE_INSTALL_CMD
        if module_name == 'qtwebkit':
            make_i_cmd = make_i_cmd + ' -f Makefile.WebKit install'
        cmd_args = ''
        cmd_args += make_i_cmd + ' ' + 'INSTALL_ROOT=' + install_root_path
        print_wrap('    Installing module: ' + module_name)
        print_wrap('          -> cmd args: ' + cmd_args)
        print_wrap('                -> in: ' + submodule_dir_name)
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), submodule_dir_name, STRICT_MODE)

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def save_original_qt_prfxpath():
    print_wrap('---------------- Saving original qt_prfxpath -----------------------')
    global ORIGINAL_QMAKE_QT_PRFXPATH
    qmake_executable_path = bldinstallercommon.locate_executable(QT_SOURCE_DIR, 'qmake' + bldinstallercommon.get_executable_suffix())
    if not qmake_executable_path:
        print_wrap('*** Error! qmake executable not found? Looks like the build has failed in previous step? Aborting..')
        sys.exit(-1)
    ORIGINAL_QMAKE_QT_PRFXPATH = patch_qmake_qt_key.fetch_key(os.path.normpath(qmake_executable_path), 'qt_prfxpath')
    print_wrap(' ===> Original qt_prfxpath: ' + ORIGINAL_QMAKE_QT_PRFXPATH)
    if not ORIGINAL_QMAKE_QT_PRFXPATH:
        print_wrap('*** Could not find original qt_prfxpath from qmake executable?!')
        print_wrap('*** Abort!')
        sys.exit(-1)
    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def replace_build_paths(path_to_checked):
    print_wrap('------------ Replacing build paths in ' + path_to_checked + '----------------')
    pattern = re.compile(WORK_DIR_NAME)
    qt_source_dir_delimeter_2 = QT_SOURCE_DIR.replace('/', os.sep)
    for root, dirs, files in os.walk(path_to_checked):
        for name in files:
            path = os.path.join(root, name)
            if not os.path.isdir(path) and not os.path.islink(path):
                if not (any(name.endswith(item) for item in IGNORE_PATCH_LIST)):
                    readlines=open(path,'r').read()
                    if pattern.search(readlines):
                        print_wrap('---> Regexp match: ' + path)
                        if bldinstallercommon.is_text_file(path):
                            print_wrap('---> Replacing build path in: ' + path)
                            print_wrap('--->         String to match: ' + QT_SOURCE_DIR)
                            print_wrap('--->         String to match: ' + qt_source_dir_delimeter_2)
                            print_wrap('--->             Replacement: ' + ORIGINAL_QMAKE_QT_PRFXPATH)
                            for line in fileinput.FileInput(path,inplace=1):
                                output1 = line.replace(QT_SOURCE_DIR, ORIGINAL_QMAKE_QT_PRFXPATH)
                                if line != output1:
                                    # we had a match
                                    print output1.rstrip('\n')
                                    continue
                                else:
                                    output2 = line.replace(qt_source_dir_delimeter_2, ORIGINAL_QMAKE_QT_PRFXPATH)
                                    if line != output2:
                                        # we had a match for the second replacement
                                        print output2.rstrip('\n')
                                        continue
                                # no match so write original line back to file
                                print line.rstrip('\n')
    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def clean_up(install_dir):
    print_wrap('---------------- Cleaning unnecessary files from ' + install_dir + '----------')
    # all platforms
    for root, dirs, files in os.walk(install_dir):
        for name in files:
            if (any(name.endswith(to_remove) for to_remove in FILES_TO_REMOVE_LIST)):
                path = os.path.join(root, name)
                print_wrap('    ---> Deleting file: ' + name)
                os.remove(path)
    # on windows remove redundant .dll files from \lib
    if bldinstallercommon.is_win_platform():
        # each submodule first
        for sub_dir in QT5_MODULES_LIST:
            base_path = MAKE_INSTALL_ROOT_DIR + os.sep + SUBMODULE_INSTALL_BASE_DIR_NAME + sub_dir
            lib_path = bldinstallercommon.locate_directory(base_path, 'lib')
            if lib_path:
                bldinstallercommon.delete_files_by_type_recursive(lib_path, '\\.dll')
            else:
                print_wrap('*** Warning! Unable to locate \\lib directory under: ' + base_path)
        # then the full install
        base_path_full_install = MAKE_INSTALL_ROOT_DIR + os.sep + MAIN_INSTALL_DIR_NAME
        if os.path.exists(base_path_full_install):
            full_install_lib_path = bldinstallercommon.locate_directory(base_path_full_install, 'lib')
            if full_install_lib_path:
                bldinstallercommon.delete_files_by_type_recursive(full_install_lib_path, '\\.dll')
            else:
                print_wrap('*** Warning! Unable to locate \\lib directory under: ' + full_install_lib_path)
    print_wrap('--------------------------------------------------------------------')

###############################
# function
###############################
def archive_submodules():
    print_wrap('---------------- Archiving submodules ------------------------------')
    bldinstallercommon.create_dirs(MODULE_ARCHIVE_DIR)
    # submodules
    for sub_dir in QT5_MODULES_LIST:
        print_wrap('---------- Archiving ' + sub_dir)
        if os.path.exists(MAKE_INSTALL_ROOT_DIR + os.sep + SUBMODULE_INSTALL_BASE_DIR_NAME + sub_dir):
            cmd_args = '7z a ' + MODULE_ARCHIVE_DIR + os.sep + sub_dir + '.7z ' + SUBMODULE_INSTALL_BASE_DIR_NAME + sub_dir
            bldinstallercommon.do_execute_sub_process_get_std_out(cmd_args.split(' '), MAKE_INSTALL_ROOT_DIR, True, True)
        else:
            print_wrap(MAKE_INSTALL_ROOT_DIR + os.sep + SUBMODULE_INSTALL_BASE_DIR_NAME + sub_dir + ' DIRECTORY NOT FOUND\n      -> ' + sub_dir + ' not archived!')
            file_handle = open(MISSING_MODULES_FILE, 'a')
            file_handle.write('\nFailed to build ' + sub_dir)
            file_handle.close()
    # one chunk
    if os.path.exists(MAKE_INSTALL_ROOT_DIR + os.sep + MAIN_INSTALL_DIR_NAME):
        print_wrap('    Archiving all modules to archive qt5_all.7z')
        cmd_args = '7z a ' + MODULE_ARCHIVE_DIR + os.sep + 'qt5_all' + '.7z ' + MAIN_INSTALL_DIR_NAME
        bldinstallercommon.do_execute_sub_process_get_std_out(cmd_args.split(' '), MAKE_INSTALL_ROOT_DIR, True, True)

    print_wrap('---------------------------------------------------------------------')


###############################
# function
###############################
def print_help():
    print_wrap('*** Error! Insufficient arguments given!')
    print_wrap('')
    print_wrap('Example: python -u mkqt5bld.py src_url=qt-everywhere-opensource-src-5.0.0.zip force_make [make_cmd=mingw32-make]')
    print_wrap('')
    print_wrap('Available options:')
    print_wrap('')
    print_wrap('  src_url=[url where to fetch src package]')
    print_wrap('  devel_mode')
    print_wrap('  use_prefix=[prefix used for configure options]')
    print_wrap('  force_make')
    print_wrap('  make_cmd=[custom make tool]')
    print_wrap('  make_thread_count=[number of threads]')
    print_wrap('  ignore=[module_to_ignore]')
    print_wrap('  strict_mode=true/false')
    print_wrap('')


###############################
# function
###############################
def parse_cmd_line():
    global CONFIGURE_OPTIONS
    global QT_SRC_PACKAGE_URL
    global DEVEL_MODE
    global FORCE_MAKE
    global MAKE_CMD
    global MAKE_THREAD_COUNT
    global MAKE_INSTALL_CMD
    global SILENT_BUILD
    global QT5_MODULES_IGNORE_LIST
    global STRICT_MODE

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
            QT_SRC_PACKAGE_URL = values[1]
            print_wrap('        Qt source dir set to: ' + QT_SRC_PACKAGE_URL)
        #is using development mode
        if item.find('devel_mode') >= 0:
            DEVEL_MODE = True
            CONFIGURE_OPTIONS += ' -nomake examples'
            print_wrap('        devel mode set to true.')
        #prefix for configure
        if item.find('use_prefix') >= 0:
            values = item.split('=')
            CONFIGURE_OPTIONS += ' -prefix ' + values[1]
            print_wrap('        -prefix added to configure line.')
        #set force make (-i option for make)
        if item.find('force_make') >= 0:
            FORCE_MAKE = True
            print_wrap('        using force make (ignoring errors).')
        #set make command, if not set make/nmake is used
        if item.find('make_cmd') >= 0:
            values = item.split('=')
            if values[1] != '':
                MAKE_CMD = values[1]
                MAKE_INSTALL_CMD = values[1] + ' install'
            print_wrap('        using command: ' + MAKE_CMD + ' for making and ' + MAKE_INSTALL_CMD + ' for installing')
        #how many threads to be used for building
        if item.find('make_thread_count') >= 0:
            values = item.split('=')
            if values[1] != '':
                MAKE_THREAD_COUNT = values[1]
            print_wrap('        threads used for building: ' + MAKE_THREAD_COUNT)
        #set SILENT_BUILD to true, defaults to false
        if item.find('silent_build') >= 0:
            SILENT_BUILD = True
            print_wrap('        doing silent build.')
        # add modules to ignore list
        if item.find('ignore') >= 0:
            values = item.split('=')
            if values[1] != '':
                QT5_MODULES_IGNORE_LIST.append(values[1])
        # set strict mode on/off
        if item.find('strict_mode') >= 0:
            values = item.split('=')
            if values[1] == 'false':
                STRICT_MODE = False

    if len(QT5_MODULES_IGNORE_LIST) > 0:
        print_wrap('        ignoring modules:')
        for ignore in QT5_MODULES_IGNORE_LIST:
            print_wrap('        - ' + ignore)

    print_wrap('---------------------------------------------------------------------')
    return True


###############################
# function
###############################
def main():
    # init
    bldinstallercommon.init_common_module(SCRIPT_ROOT_DIR)
    # parse cmd line
    parse_cmd_line()
    # init
    init_mkqt5bld()
    # create work dir
    bldinstallercommon.create_dirs(WORK_DIR)
    # fetch src package (or create?)
    fetch_src_package()
    # extract src package
    extract_src_package()
    # build
    build_qt()
    # save original qt_prfxpath in qmake executable
    save_original_qt_prfxpath()
    # install
    install_qt()
    #cleanup files that are not needed in binary packages
    clean_up(MAKE_INSTALL_ROOT_DIR)
    # replace build directory paths in install_root locations
    replace_build_paths(MAKE_INSTALL_ROOT_DIR)
    # archive each submodule
    archive_submodules()

###############################
# function
###############################
main()


