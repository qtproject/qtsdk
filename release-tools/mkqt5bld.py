
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
from optparse import OptionParser, Option, OptionValueError

SCRIPT_ROOT_DIR                     = os.getcwd()
WORK_DIR_NAME                       = 'qt5_workdir'
WORK_DIR                            = SCRIPT_ROOT_DIR + os.sep + WORK_DIR_NAME
QT_PACKAGE_SAVE_AS_TEMP             = ''
QT_SOURCE_DIR_NAME                  = 'w'
QT_SOURCE_DIR                       = WORK_DIR + os.sep + QT_SOURCE_DIR_NAME
QT_PACKAGE_SHORT_NAME               = 's'
MAKE_INSTALL_ROOT_DIR_NAME          = 'qt5_install_root'
MAKE_INSTALL_ROOT_DIR               = WORK_DIR + os.sep + MAKE_INSTALL_ROOT_DIR_NAME #main dir for submodule installations
MISSING_MODULES_FILE                = WORK_DIR + os.sep + 'missing_modules.txt'
CONFIGURE_CMD                       = ''
MODULE_ARCHIVE_DIR_NAME             = 'module_archives'
MODULE_ARCHIVE_DIR                  = SCRIPT_ROOT_DIR + os.sep + MODULE_ARCHIVE_DIR_NAME
SUBMODULE_INSTALL_BASE_DIR_NAME     = "submodule_install_"
ESSENTIALS_INSTALL_DIR_NAME         = SUBMODULE_INSTALL_BASE_DIR_NAME + 'essentials'
ADDONS_INSTALL_DIR_NAME             = SUBMODULE_INSTALL_BASE_DIR_NAME + 'addons'
#list of modules, only a backup list, this list will be updated during script execution
QT5_MODULES_LIST                    = [ 'qt3d', 'qlalr', 'qtactiveqt', 'qtbase',     \
                                        'qtconnectivity', 'qtdeclarative', 'qtdoc', \
                                        'qtfeedback', 'qtgraphicaleffects', \
                                        'qtimageformats', 'qtjsbackend', \
                                        'qtlocation', 'qtmultimedia', 'qtpim', \
                                        'qtqa', 'qtquick1', 'qtrepotools', 'qtscript', \
                                        'qtsensors', 'qtsvg', 'qtsystems', 'qttools', \
                                        'qttranslations', 'qtwayland', 'qtwebkit', \
                                        'qtwebkit-examples-and-demos', 'qtxmlpatterns']
QT5_ESSENTIALS                      = [ 'qtbase', 'qtdeclarative', 'qtdoc', \
                                        'qtjsbackend', 'qtquick1', 'qtscript', \
                                        'qttools', 'qtwebkit', 'qtxmlpatterns', \
                                        'qtmultimedia', 'qtwebkit-examples-and-demos']
ORIGINAL_QMAKE_QT_PRFXPATH          = ''
PADDING                             = '______________________________PADDING______________________________'
FILES_TO_REMOVE_LIST                = ['Makefile', 'Makefile.Release', 'Makefile.Debug', \
                                       '.o', '.moc', '.init-repository', \
                                       '.gitignore', '.obj']
IGNORE_PATCH_LIST                   = ['.png', '.jpg', '.gif', '.bmp', '.exe', '.dll', '.lib', '.qph']
INSTALL_PREFIX                      = ''
#Commandline options
OPTION_PARSER                       = 0
QT_SRC_PACKAGE_URL                  = ''
SILENT_BUILD                        = False
STRICT_MODE                         = True
QT5_MODULES_IGNORE_LIST             = []
MAKE_CMD                            = ''
MAKE_THREAD_COUNT                   = '8' # some initial default value
MAKE_INSTALL_CMD                    = ''
CONFIGURE_OPTIONS                   = '-confirm-license -debug-and-release -release -nomake tests -nomake examples -qt-zlib -qt-libjpeg -qt-libpng'


class MultipleOption(Option):
    ACTIONS = Option.ACTIONS + ("extend",)
    STORE_ACTIONS = Option.STORE_ACTIONS + ("extend",)
    TYPED_ACTIONS = Option.TYPED_ACTIONS + ("extend",)
    ALWAYS_TYPED_ACTIONS = Option.ALWAYS_TYPED_ACTIONS + ("extend",)

    def take_action(self, action, dest, opt, value, values, parser):
        if action == "extend":
            values.ensure_value(dest, []).append(value)
        else:
            Option.take_action(self, action, dest, opt, value, values, parser)


###############################
# function
###############################
def print_wrap(text):
    print 'QT5BLD: ' + text



###############################
# function
###############################
def exit_script():
    print_wrap(' *** Exiting...')
    sys.exit(-1)

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
    global INSTALL_PREFIX

    print_wrap('---------------- Initializing build --------------------------------')
    #do not edit configure options, if configure options are overridden from commandline options
    if bldinstallercommon.is_unix_platform():
        CONFIGURE_CMD = './'

    if SILENT_BUILD and not bldinstallercommon.is_win_platform():
        CONFIGURE_OPTIONS += ' -silent'


    CONFIGURE_CMD += 'configure'

    # make cmd
    if MAKE_CMD == '':  #if not given in commandline param, use nmake or make according to the os
        if bldinstallercommon.is_win_platform():        #win
            MAKE_CMD = 'nmake'
            MAKE_INSTALL_CMD = 'nmake'
            if SILENT_BUILD:
                MAKE_CMD += ' /s'
                MAKE_INSTALL_CMD += ' /s'
            MAKE_INSTALL_CMD += ' install'
        elif bldinstallercommon.is_unix_platform():    #linux & mac
            MAKE_CMD = 'make'
            MAKE_INSTALL_CMD = 'make'
            if SILENT_BUILD:
                MAKE_CMD += ' -s'
                MAKE_INSTALL_CMD += ' -s'
            MAKE_INSTALL_CMD += ' install'
    else:
        if MAKE_CMD == 'jom':
            MAKE_INSTALL_CMD = 'jom -j1 install'
            if SILENT_BUILD:
                MAKE_INSTALL_CMD += ' /s'

    #remove old working dirs
    if os.path.exists(WORK_DIR):
        print_wrap('    Removing old work dir ' + WORK_DIR)
        bldinstallercommon.remove_tree(WORK_DIR)
    if os.path.exists(MODULE_ARCHIVE_DIR):
        print_wrap('    Removing old module archive dir ' + MODULE_ARCHIVE_DIR)
        bldinstallercommon.remove_tree(MODULE_ARCHIVE_DIR)

    print_wrap('  Build    : ' + MAKE_CMD)
    print_wrap('  Install  : ' + MAKE_INSTALL_CMD)
    print_wrap('  Configure: ' + CONFIGURE_OPTIONS)

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
        shorter_dir_path = QT_SOURCE_DIR + os.sep + QT_PACKAGE_SHORT_NAME
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
def configure_qt():
    print_wrap('---------------- Configuring Qt ------------------------------------')
    cmd_args = CONFIGURE_CMD + ' ' + CONFIGURE_OPTIONS
    print_wrap('    Configure line: ' + cmd_args)
    if os.path.exists(QT_SOURCE_DIR + os.sep + CONFIGURE_CMD):
        print_wrap(' configure found from ' + QT_SOURCE_DIR)
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR, True)
    else:
        print_wrap(' configure found from ' + QT_SOURCE_DIR + os.sep + 'qtbase')
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR + os.sep + 'qtbase', True)

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def save_install_prefix():
    print_wrap('---------------- Saving install prefix -----------------------------')
    global INSTALL_PREFIX

    qmake_executable_path = bldinstallercommon.locate_executable(QT_SOURCE_DIR, 'qmake' + bldinstallercommon.get_executable_suffix())
    if not qmake_executable_path:
        print_wrap('*** Error! qmake executable not found? Looks like the build has failed in previous step?')
        exit_script()

    query_args = qmake_executable_path + ' -query'
    return_code, output = bldinstallercommon.do_execute_sub_process(query_args.split(' '), '.', True, True)
    data = output.split('\n')

    for line in data:
        if 'QT_INSTALL_PREFIX' in line:
            splitted = line.split(':')
            #windows has different syntax in qmake -query
            if bldinstallercommon.is_win_platform():
                INSTALL_PREFIX = splitted[2]
            else:
                INSTALL_PREFIX = splitted[1]
            INSTALL_PREFIX = INSTALL_PREFIX.strip()
            print_wrap('INSTALL_PREFIX = ' + INSTALL_PREFIX)
            break

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def create_submodule_list():
    global QT5_MODULES_LIST
    print_wrap('-------- Creating ordered list of submodules -----------------------')

    #create list of modules in default make order
    regex = re.compile('^make_first:.*') #search line starting with 'make_first:'
    submodule_list = []
    modules_found = 0
    if os.path.exists(QT_SOURCE_DIR + os.sep + 'Makefile'):
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

        if modules_found == 1:
            QT5_MODULES_LIST = submodule_list
            print_wrap('    Modules list updated, modules are now in default build order.')
        else:
            print_wrap('    Warning! Could not extract module build order from ' + QT_SOURCE_DIR + os.sep + 'Makefile. Using default (non-ordered) list.')
    else:
        print_wrap('*** Error! Main Makefile not found. Build failed!')
        sys.exit(-1)

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def build_qt():
    print_wrap('---------------- Building Qt ---------------------------------------')
    #remove if old dir exists
    if os.path.exists(MAKE_INSTALL_ROOT_DIR):
        shutil.rmtree(MAKE_INSTALL_ROOT_DIR)
    #create install dirs
    bldinstallercommon.create_dirs(MAKE_INSTALL_ROOT_DIR)

    cmd_args = MAKE_CMD
    if bldinstallercommon.is_unix_platform():
        cmd_args += ' -j' + str(MAKE_THREAD_COUNT)
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR, STRICT_MODE)

    print_wrap('--------------------------------------------------------------------')

###############################
# function
###############################
def build_qmlpuppets():
    if not QT_CREATOR_SRC_DIR:
        return
    print_wrap('---------------- Building QML Puppets -------------------------------')

    qmake_executable_path = bldinstallercommon.locate_executable(QT_SOURCE_DIR, 'qmake' + bldinstallercommon.get_executable_suffix())
    if not qmake_executable_path:
        print_wrap('*** Error! qmake executable not found? Looks like the build has failed in previous step?')
        exit_script()

    cmd_args = MAKE_CMD
    if bldinstallercommon.is_unix_platform():
        cmd_args += ' -j' + str(MAKE_THREAD_COUNT)

    shutil.copy(os.path.join(QT_SOURCE_DIR, ".qmake.super"),
                QT_CREATOR_SRC_DIR)

    qmlpuppet_dir = os.path.join(QT_CREATOR_SRC_DIR, 'share', 'qtcreator', 'qml', 'qmlpuppet', 'qml2puppet')
    bldinstallercommon.do_execute_sub_process(qmake_executable_path, qmlpuppet_dir, STRICT_MODE)
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), qmlpuppet_dir, STRICT_MODE)

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def install_qt():
    print_wrap('---------------- Installing Qt -------------------------------------')

    #make install for each module with INSTALL_ROOT
    print_wrap('    Install modules to separate INSTALL_ROOT')
    for module_name in QT5_MODULES_LIST:
        install_dir = ''
        if module_name in QT5_ESSENTIALS:
            install_dir = ESSENTIALS_INSTALL_DIR_NAME
        else:
            install_dir = ADDONS_INSTALL_DIR_NAME
        install_root_path = MAKE_INSTALL_ROOT_DIR + os.sep + install_dir
        if bldinstallercommon.is_win_platform():
            install_root_path = install_root_path[2:]
            print_wrap('    Using install root path: ' + install_root_path)
        submodule_dir_name = QT_SOURCE_DIR + os.sep + module_name
        cmd_args = MAKE_INSTALL_CMD + ' ' + 'INSTALL_ROOT=' + install_root_path
        print_wrap('    Installing module: ' + module_name)
        print_wrap('          -> cmd args: ' + cmd_args)
        print_wrap('                -> in: ' + submodule_dir_name)
        return_code, output = bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), submodule_dir_name, STRICT_MODE)
        if return_code >= 0:
            file_handle = open(MISSING_MODULES_FILE, 'a')
            file_handle.write('\nFailed to build ' + module_name)
            file_handle.close()

    print_wrap('--------------------------------------------------------------------')

###############################
# function
###############################
def install_qmlpuppets():
    if not QT_CREATOR_SRC_DIR:
        return
    print_wrap('---------------- Installing qmlpuppets------------------------------')

    #make install for each module with INSTALL_ROOT
    install_dir = ESSENTIALS_INSTALL_DIR_NAME
    prfx_path = ORIGINAL_QMAKE_QT_PRFXPATH
    if bldinstallercommon.is_win_platform():
        prfx_path = prfx_path[2:].replace('/', '\\')
    install_root_path = MAKE_INSTALL_ROOT_DIR + os.sep + install_dir + prfx_path
    if bldinstallercommon.is_win_platform():
        install_root_path = install_root_path[3:]
    print_wrap('    Using install root path: ' + install_root_path)
    qmlpuppet_dir = os.path.join(QT_CREATOR_SRC_DIR, 'share', 'qtcreator', 'qml', 'qmlpuppet', 'qml2puppet')

    cmd_args = MAKE_INSTALL_CMD + ' ' + 'INSTALL_ROOT=' + install_root_path
    print_wrap('    Installing qmlpuppet')
    print_wrap('          -> cmd args: ' + cmd_args)
    print_wrap('                -> in: ' + qmlpuppet_dir)
    return_code, output = bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), qmlpuppet_dir, STRICT_MODE)
    if return_code >= 0:
        file_handle = open(MISSING_MODULES_FILE, 'a')
        file_handle.write('\nFailed to build qmlpuppet')
        file_handle.close()

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

    base_path_essentials = MAKE_INSTALL_ROOT_DIR + os.sep + ESSENTIALS_INSTALL_DIR_NAME + os.sep + INSTALL_PREFIX
    base_path_addon = MAKE_INSTALL_ROOT_DIR + os.sep + ADDONS_INSTALL_DIR_NAME + os.sep + INSTALL_PREFIX
    # on windows remove redundant .dll files from \lib
    if bldinstallercommon.is_win_platform():
        lib_path_essentials = bldinstallercommon.locate_directory(base_path_essentials, 'lib')
        if lib_path_essentials:
            bldinstallercommon.delete_files_by_type_recursive(lib_path_essentials, '\\.dll')
        else:
            print_wrap('*** Warning! Unable to locate \\lib directory under: ' + base_path_essentials)

        lib_path_addon = bldinstallercommon.locate_directory(base_path_addon, 'lib')
        if lib_path_addon:
            bldinstallercommon.delete_files_by_type_recursive(lib_path_addon, '\\.dll')
        else:
            print_wrap('*** Warning! Unable to locate \\lib directory under: ' + base_path_addon)

    # ensure that we do not ship prebuilt examples in binary packages
    # essentials install
    examples_path_essentials = bldinstallercommon.locate_directory(base_path_essentials, 'examples')
    if examples_path_essentials:
        bldinstallercommon.remove_tree(os.path.normpath(examples_path_essentials))
    else:
        print_wrap('*** Warning! Unable to locate examples directory under: ' + examples_path_essentials)
    # addons install
    examples_path_addons = bldinstallercommon.locate_directory(base_path_addon, 'examples')
    if examples_path_addons:
        bldinstallercommon.remove_tree(os.path.normpathexamples_path_addons))
    else:
        print_wrap('*** Warning! Unable to locate examples directory under: ' + examples_path_addons)
    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def build_docs():
    print_wrap('------------------------- Building documentation -------------------')

    #first we need to do make install for the sources
    print_wrap('    Running make install...')
    install_args = MAKE_INSTALL_CMD
    bldinstallercommon.do_execute_sub_process(install_args.split(' '), QT_SOURCE_DIR, False, False)

    cmd_args = MAKE_CMD + ' docs'
    print_wrap('    Running make docs in ' + QT_SOURCE_DIR)
    #do not abort on fail, if the doc build fails, we still want to get the binary package
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR, False)

    print_wrap('    Running make install_docs in ' + QT_SOURCE_DIR)
    make_cmd = MAKE_CMD
    install_root_path = MAKE_INSTALL_ROOT_DIR + os.sep + ESSENTIALS_INSTALL_DIR_NAME
    if bldinstallercommon.is_win_platform():
        install_root_path = install_root_path[2:]
    doc_install_args = make_cmd + ' -j1 install_docs INSTALL_ROOT=' + install_root_path
    #do not abort on fail, if the doc build fails, we still want to get the binary package
    bldinstallercommon.do_execute_sub_process(doc_install_args.split(' '), QT_SOURCE_DIR, False)

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def archive_submodules():
    print_wrap('---------------- Archiving submodules ------------------------------')
    bldinstallercommon.create_dirs(MODULE_ARCHIVE_DIR)

    # Essentials
    print_wrap('---------- Archiving essential modules')
    if os.path.exists(MAKE_INSTALL_ROOT_DIR + os.sep + ESSENTIALS_INSTALL_DIR_NAME):
        cmd_args = '7z a ' + MODULE_ARCHIVE_DIR + os.sep + 'qt5_essentials' + '.7z *'
        run_in = os.path.normpath(MAKE_INSTALL_ROOT_DIR + os.sep + ESSENTIALS_INSTALL_DIR_NAME + os.sep + INSTALL_PREFIX)
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), run_in, True, True)
    else:
        print_wrap(MAKE_INSTALL_ROOT_DIR + os.sep + ESSENTIALS_INSTALL_DIR_NAME + ' DIRECTORY NOT FOUND\n      -> essentials not archived!')

    # Add-ons
    print_wrap('---------- Archiving add-on modules')
    if os.path.exists(MAKE_INSTALL_ROOT_DIR + os.sep + ADDONS_INSTALL_DIR_NAME):
        cmd_args = '7z a ' + MODULE_ARCHIVE_DIR + os.sep + 'qt5_addons' + '.7z *'
        run_in = os.path.normpath(MAKE_INSTALL_ROOT_DIR + os.sep + ADDONS_INSTALL_DIR_NAME + os.sep + INSTALL_PREFIX)
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), run_in, True, True)
    else:
        print_wrap(MAKE_INSTALL_ROOT_DIR + os.sep + ADDONS_INSTALL_DIR_NAME + ' DIRECTORY NOT FOUND\n      -> add-ons not archived!')

    print_wrap('---------------------------------------------------------------------')


###############################
# function
###############################
def parse_cmd_line():
    print_wrap('---------------- Parsing commandline arguments ---------------------')
    global QT_SRC_PACKAGE_URL
    global MAKE_CMD
    global MAKE_THREAD_COUNT
    global MAKE_INSTALL_CMD
    global SILENT_BUILD
    global QT5_MODULES_IGNORE_LIST
    global STRICT_MODE
    global CONFIGURE_OPTIONS
    global CONFIGURE_OVERRIDE
    global QT_CREATOR_SRC_DIR

    setup_option_parser()

    arg_count = len(sys.argv)
    if arg_count < 2:
        OPTION_PARSER.print_help()
        sys.exit(-1)

    (options, args) = OPTION_PARSER.parse_args()

    QT_SRC_PACKAGE_URL      = options.src_url
    if options.make_cmd:
        MAKE_CMD            = options.make_cmd
    MAKE_THREAD_COUNT       = options.make_thread_count
    MAKE_INSTALL_CMD        = MAKE_CMD + ' install'
    SILENT_BUILD            = options.silent_build
    if options.module_ignore_list:
        QT5_MODULES_IGNORE_LIST = options.module_ignore_list
    STRICT_MODE             = options.strict_mode
    QT_CREATOR_SRC_DIR      = options.qt_creator_src_dir

    if options.configure_options:
        if os.path.isfile(options.configure_options):
            configure_file = open(options.configure_options, 'r')
            CONFIGURE_OPTIONS = configure_file.readline().rstrip('\r\n')
            configure_file.close()
        else:
            print_wrap(' *** Error! Could not find file ' + options.configure_options)
            exit_script()
    else:
        print_wrap(' *** Error! No configure options given!')
        exit_script()

    if options.add_configure_option:
        CONFIGURE_OPTIONS += ' ' + options.add_configure_option

    if QT_CREATOR_SRC_DIR and not os.path.isdir(QT_CREATOR_SRC_DIR):
        print_wrap(' *** Error! Could not find directory ' + QTCREATOR_SRC_DIR)
        exit_script()


    print_wrap('---------------------------------------------------------------------')
    return True


##############################################################
# Setup Option Parser
##############################################################
def setup_option_parser():
    print_wrap('------------------- Setup option parser -----------------------------')
    global OPTION_PARSER
    OPTION_PARSER = OptionParser(option_class=MultipleOption)

    OPTION_PARSER.add_option("-u", "--src-url",
                      action="store", type="string", dest="src_url", default="",
                      help="the url where to fetch the source package")
    OPTION_PARSER.add_option("-m", "--make_cmd",
                      action="store", type="string", dest="make_cmd", default="",
                      help="make command (e.g. mingw32-make). On linux defaults to make and on win nmake.")
    OPTION_PARSER.add_option("-j", "--jobs",
                      action="store", type="int", dest="make_thread_count", default=8,
                      help="make job count")
    OPTION_PARSER.add_option("-q", "--silent-build",
                      action="store_true", dest="silent_build", default=False,
                      help="supress command output, show only errors")
    OPTION_PARSER.add_option("-i", "--ignore",
                      action="extend", type="string", dest="module_ignore_list",
                      help="do not build module")
    OPTION_PARSER.add_option("-S", "--non-strict-mode",
                      action="store_false", dest="strict_mode", default=True,
                      help="exit on error, defaults to true.")
    OPTION_PARSER.add_option("-c", "--configure",
                      action="store", type="string", dest="configure_options", default="",
                      help="options for configure command. In addition option -a can be used to give extra parameters.")
    OPTION_PARSER.add_option("-a", "--add-configure-option",
                      action="store", type="string", dest="add_configure_option", default="",
                      help="options to be added to default configure options. For example, if -prefix or -R are needed but not defined in configure options file given with -c, those can be passed with this option, e.g. -a \"-prefix /home/user/my/path/here -R /home/user/my/path/here\"")
    OPTION_PARSER.add_option("--creator-dir",
                      action="store", type="string", dest="qt_creator_src_dir", default="",
                      help="path to Qt Creator sources. If given, the Qt Quick Designer processes (qmlpuppet, qml2puppet) will be built and packaged.")
    print_wrap('---------------------------------------------------------------------')


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
    # configure
    configure_qt()
    # save used install prefix
    save_install_prefix()
    # create submodule list
    create_submodule_list()
    # build
    build_qt()
    # build qmlpuppets
    build_qmlpuppets()
    # save original qt_prfxpath in qmake executable
    save_original_qt_prfxpath()
    # install
    install_qt()
    # install qmlpuppets
    install_qmlpuppets()
    #cleanup files that are not needed in binary packages
    clean_up(MAKE_INSTALL_ROOT_DIR)
    # build docs and copy to essentials install dir
    build_docs()
    # replace build directory paths in install_root locations
    replace_build_paths(MAKE_INSTALL_ROOT_DIR)
    # archive each submodule
    archive_submodules()


###############################
# function
###############################
main()


