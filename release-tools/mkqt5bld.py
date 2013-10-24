
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
import sys
import urllib
import fileinput
import bldinstallercommon
import multiprocessing
import patch_qmake_qt_key
from optparse import OptionParser, Option
import fnmatch

SCRIPT_ROOT_DIR                     = os.getcwd()
WORK_DIR_NAME                       = 'qt5_workdir'
WORK_DIR                            = SCRIPT_ROOT_DIR + os.sep + WORK_DIR_NAME
QT_CREATOR_SRC_DIR                  = ''
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
SINGLE_INSTALL_DIR_NAME             = SUBMODULE_INSTALL_BASE_DIR_NAME + 'single'
#list of modules, only a backup list, this list will be updated during script execution
QT5_MODULES_LIST                    = [ 'qt3d', 'qlalr', 'qtactiveqt', 'qtandroidextras', \
                                        'qtbase', 'qtconnectivity', 'qtdeclarative', \
                                        'qtdoc', 'qtfeedback', 'qtgraphicaleffects', \
                                        'qtimageformats', 'qtlocation', 'qtmacextras', \
                                        'qtmultimedia', 'qtpim', 'qtqa', 'qtquick1', \
                                        'qtquickcontrols', 'qtrepotools', 'qtscript', \
                                        'qtsensors', 'qtserialport', 'qtsvg', 'qtsystems', \
                                        'qttools', 'qttranslations', 'qtwayland', \
                                        'qtwebkit', 'qtwebkit-examples', 'qtwinextras', \
                                        'qtxmlpatterns', 'qtx11extras' ]
QT5_ESSENTIALS                      = [ 'qtbase', 'qtdeclarative', 'qtdoc', \
                                        'qtmultimedia', 'qtquick1', 'qtquickcontrols', \
                                        'qtscript', 'qttools', 'qtwebkit', \
                                        'qtwebkit-examples', 'qtxmlpatterns' ]
ORIGINAL_QMAKE_QT_PRFXPATH          = ''
PADDING                             = '______________________________PADDING______________________________'
FILES_TO_REMOVE_LIST                = ['Makefile', 'Makefile.Release', 'Makefile.Debug', \
                                       '.o', '.obj', '.moc', \
                                       '.init-repository', '.gitignore', \
                                       'libQt5Bootstrap.a', 'qt_lib_bootstrap.pri']
IGNORE_PATCH_LIST                   = ['.png', '.jpg', '.gif', '.bmp', '.exe', '.dll', '.lib', '.qph']
INSTALL_PREFIX                      = ''
#Commandline options
OPTION_PARSER                       = 0
QT_SRC_PACKAGE_URL                  = ''
SILENT_BUILD                        = False
STRICT_MODE                         = True
QT5_MODULES_IGNORE_LIST             = []
MAKE_CMD                            = ''
MAKE_THREAD_COUNT                   = ''
MAKE_INSTALL_CMD                    = ''
CONFIGURE_OPTIONS                   = '-confirm-license -debug-and-release -release -nomake tests -nomake examples -qt-zlib -qt-libjpeg -qt-libpng'
ANDROID_NDK_HOST                    = ''
ANDROID_API_VERSION                 = 'android-10'
ANDROID_SDK_HOME                    = ''
ANDROID_NDK_HOME                    = ''
ANDROID_BUILD                       = False
EXTRA_ENV                           = dict(os.environ)
REPLACE_RPATH                       = False
CUSTOM_ICU_URI                      = ''


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
    global EXTRA_ENV

    print_wrap('---------------- Initializing build --------------------------------')
    #do not edit configure options, if configure options are overridden from commandline options
    if bldinstallercommon.is_unix_platform():
        CONFIGURE_CMD = './'

    if SILENT_BUILD and not bldinstallercommon.is_win_platform():
        CONFIGURE_OPTIONS += ' -silent'
    # add required configuration arguments if Android build
    if ANDROID_BUILD:
        CONFIGURE_OPTIONS += ' -android-ndk ' + ANDROID_NDK_HOME
        CONFIGURE_OPTIONS += ' -android-sdk ' + ANDROID_SDK_HOME
        EXTRA_ENV['ANDROID_NDK_HOST'] = ANDROID_NDK_HOST
        EXTRA_ENV['ANDROID_API_VERSION'] = ANDROID_API_VERSION

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
                MAKE_CMD += ' -s -nologo'
                MAKE_INSTALL_CMD += ' -s -nologo'

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
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR, True, False, EXTRA_ENV)
    else:
        print_wrap(' configure found from ' + QT_SOURCE_DIR + os.sep + 'qtbase')
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR + os.sep + 'qtbase', True, False, EXTRA_ENV)

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
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR, STRICT_MODE, False, EXTRA_ENV)

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

    if bldinstallercommon.is_mac_platform():
        # make install INSTALL_ROOT= doesn't work on the mac, set DESTDIR instead
        install_root_path = os.path.join(MAKE_INSTALL_ROOT_DIR, ESSENTIALS_INSTALL_DIR_NAME, ORIGINAL_QMAKE_QT_PRFXPATH)
        qmake_executable_path = [qmake_executable_path, '-after', 'DESTDIR=' + os.path.join(install_root_path, 'bin')]

    bldinstallercommon.do_execute_sub_process(qmake_executable_path, qmlpuppet_dir, STRICT_MODE)
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), qmlpuppet_dir, STRICT_MODE)

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def install_qt():
    print_wrap('---------------- Installing Qt -------------------------------------')

    # temporary solution for installing cross compiled Qt for Android on Windows host
    if ANDROID_BUILD and bldinstallercommon.is_win_platform():
        install_root_path = MAKE_INSTALL_ROOT_DIR + os.sep + SINGLE_INSTALL_DIR_NAME
        # do not use drive letter when running make install
        install_root_path = install_root_path[2:]
        cmd_args = MAKE_INSTALL_CMD + ' ' + 'INSTALL_ROOT=' + install_root_path
        print_wrap('    Installing module: Qt top level')
        print_wrap('          -> cmd args: ' + cmd_args)
        print_wrap('                -> in: ' + QT_SOURCE_DIR)
        return_code, output = bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR, STRICT_MODE)
        return

    #make install for each module with INSTALL_ROOT
    print_wrap('    Install modules to separate INSTALL_ROOT')
    for module_name in QT5_MODULES_LIST:
        # we do not provide pre-built examples
        if 'qtwebkit-examples' in module_name:
            continue
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
                    readlines = open(path,'r').read()
                    if pattern.search(readlines):
                        print_wrap('---> Regexp match: ' + path)
                        if bldinstallercommon.is_text_file(path):
                            print_wrap('---> Replacing build path in: ' + path)
                            print_wrap('--->         String to match: ' + QT_SOURCE_DIR)
                            print_wrap('--->         String to match: ' + qt_source_dir_delimeter_2)
                            print_wrap('--->             Replacement: ' + ORIGINAL_QMAKE_QT_PRFXPATH)
                            for line in fileinput.FileInput(path, inplace=1):
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
def replace_system_paths():
    qconfig_path = MAKE_INSTALL_ROOT_DIR + os.sep + ESSENTIALS_INSTALL_DIR_NAME \
                   + os.sep + INSTALL_PREFIX + os.sep + 'mkspecs' + os.sep + 'qconfig.pri'
    print_wrap('------------ Replacing system paths in ' + qconfig_path + ' ----------------')
    for line in fileinput.FileInput(qconfig_path, inplace=1):
        if 'QMAKE_DEFAULT_LIBDIRS' in line:
            libdirs = line.split('=')[0]
            print libdirs + ' = '
        elif 'QMAKE_DEFAULT_INCDIRS' in line:
            incdirs = line.split('=')[0]
            print incdirs + ' = '
        else:
            print line,
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
        bldinstallercommon.remove_tree(os.path.normpath(examples_path_addons))
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
def replace_rpath():
    if not bldinstallercommon.is_linux_platform():
        print_wrap('*** Warning! RPath patching enabled only for Linux platforms')
        return
    dest_path_lib = bldinstallercommon.locate_directory(os.path.join(MAKE_INSTALL_ROOT_DIR, ESSENTIALS_INSTALL_DIR_NAME), 'lib')
    component_root_path = os.path.dirname(dest_path_lib)
    bldinstallercommon.handle_component_rpath(component_root_path, '/lib')


###############################
# function
###############################
def archive_submodules():
    print_wrap('---------------- Archiving submodules ------------------------------')
    bldinstallercommon.create_dirs(MODULE_ARCHIVE_DIR)

    # temporary solution for Android on Windows compilations
    if ANDROID_BUILD and bldinstallercommon.is_win_platform():
        print_wrap('---------- Archiving Qt modules')
        install_path = MAKE_INSTALL_ROOT_DIR + os.sep + SINGLE_INSTALL_DIR_NAME
        install_path = 'C' + install_path[1:]
        if os.path.exists(install_path):
            cmd_args = '7z a ' + MODULE_ARCHIVE_DIR + os.sep + 'qt5_essentials' + '.7z *'
            run_in = os.path.normpath(install_path + os.sep + INSTALL_PREFIX)
            bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), run_in, True, True)
        else:
            print_wrap(install_path + os.sep + SINGLE_INSTALL_DIR_NAME + ' DIRECTORY NOT FOUND\n      -> Qt not archived!')
        return

    # Essentials
    print_wrap('---------- Archiving essential modules')
    if os.path.exists(MAKE_INSTALL_ROOT_DIR + os.sep + ESSENTIALS_INSTALL_DIR_NAME):
        # Archive the essential modules first
        cmd_args = '7z a ' + MODULE_ARCHIVE_DIR + os.sep + 'qt5_essentials' + '.7z *'
        run_in = os.path.normpath(MAKE_INSTALL_ROOT_DIR + os.sep + ESSENTIALS_INSTALL_DIR_NAME + os.sep + INSTALL_PREFIX)
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), run_in, True, True)

        # Also archive docs in a separated qt5_docs.7z file
        cmd_args = '7z a ' + MODULE_ARCHIVE_DIR + os.sep + 'qt5_docs' + '.7z *'
        run_in = os.path.normpath(MAKE_INSTALL_ROOT_DIR + os.sep + ESSENTIALS_INSTALL_DIR_NAME + os.sep + INSTALL_PREFIX + os.sep + 'doc')
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
def rename_android_soname_files():
    ## QTBUG-33793
    # temporary solution for Android on Windows compilations
    if ANDROID_BUILD and bldinstallercommon.is_win_platform():
        install_path = MAKE_INSTALL_ROOT_DIR + os.sep + SINGLE_INSTALL_DIR_NAME
        install_path = 'C' + install_path[1:]

        ## rename the .so files for Android on Windows
        # find the lib directory under the install directory for essentials
        lib_path_essentials = os.path.normpath(install_path + os.sep + INSTALL_PREFIX + os.sep + 'lib')
        print_wrap('---------- Renaming .so name files in ' + lib_path_essentials + ' ----------------')
        # regex for Qt version, eg. 5.2.0
        # assuming that Qt version will always have one digit, eg, 5.2.0
        p = re.compile('\d\.\d\.\d')
        if os.path.exists(lib_path_essentials):
            # just list the files with a pattern like 'libQt5Core.so.5.2.0'
            files = [f for f in os.listdir(lib_path_essentials) if re.match(r'libQt5.*\.so\..*', f)]
            for name in files:
                # if name is something like 'libQt5Core.so.5.2.0' then
                # filename, so, version = ['libQt5Core', 'so', '5.2.0']
                filename, so, version = name.split(os.extsep, 2)
                # let's just rename the appropriate files
                if filename.startswith('libQt5') and so == 'so' and p.match(version) != None:
                    old_filepath = os.path.join(lib_path_essentials, name)
                    new_filepath = os.path.join(lib_path_essentials, filename + '.so')
                    os.rename(old_filepath, new_filepath)
                    print_wrap('--->            Old file name : ' + old_filepath)
                    print_wrap('--->            New file name : ' + new_filepath)
                else:
                    print_wrap('*** Warning! The file : ' + filename + " does not match the pattern 'libQt5.*\.so\..*'")
        else:
            print_wrap('*** Warning! Unable to locate \\lib directory under: ' + install_path + os.sep + INSTALL_PREFIX)


###############################
# function
###############################
def patch_android_prl_files():
    ## QTBUG-33660
    # remove references to absolute path of the NDK on the build machine
    if ANDROID_BUILD:
        install_path_essent = MAKE_INSTALL_ROOT_DIR + os.sep + ESSENTIALS_INSTALL_DIR_NAME
        install_path_addons = MAKE_INSTALL_ROOT_DIR + os.sep + ADDONS_INSTALL_DIR_NAME
        # temporary solution for Android on Windows compilations
        if bldinstallercommon.is_win_platform():
            install_path_essent = MAKE_INSTALL_ROOT_DIR + os.sep + SINGLE_INSTALL_DIR_NAME
            install_path_essent = 'C' + install_path_essent[1:]

        # find the lib directory under the install directory for essentials and addons
        lib_path_essent = os.path.normpath(install_path_essent + os.sep + INSTALL_PREFIX + os.sep + 'lib')
        lib_path_addons = os.path.normpath(install_path_addons + os.sep + INSTALL_PREFIX + os.sep + 'lib')

        # just list the files with a pattern like 'libQt5Core.prl'
        for lib_path_final in [lib_path_essent, lib_path_addons]:
            print_wrap('---------- Remove references to a static library in the NDK under ' + lib_path_final + ' ----------------')
            if os.path.exists(lib_path_final):
                prl_files = [f for f in os.listdir(lib_path_final) if re.match(r'libQt5.*\.prl', f)]
                for prl_name in prl_files:
                    # let's just remove the undesired string for QMAKE_PRL_LIBS
                    prl_name_path = os.path.join(lib_path_final, prl_name)
                    if os.path.isfile(prl_name_path):
                        for line in fileinput.FileInput(prl_name_path, inplace=1):
                            if line.startswith('QMAKE_PRL_LIBS'):
                                line = line.replace(' /opt/android/ndk/toolchains/arm-linux-androideabi-4.8/prebuilt/linux-x86/bin/../lib/gcc/arm-linux-androideabi/4.8/libgcc.a', '')
                                line = line.replace(' /opt/android/ndk/toolchains/arm-linux-androideabi-4.8/prebuilt/linux-x86_64/bin/../lib/gcc/arm-linux-androideabi/4.8/libgcc.a', '')
                                line = line.replace(' /opt/android/ndk/toolchains/arm-linux-androideabi-4.8/prebuilt/darwin-x86_64/bin/../lib/gcc/arm-linux-androideabi/4.8/libgcc.a', '')
                                line = line.replace(' c:/utils/android/ndk/toolchains/arm-linux-androideabi-4.8/prebuilt/windows/bin/../lib/gcc/arm-linux-androideabi/4.8/libgcc.a', '')
                                print line,
                            else:
                                print line,
                    else:
                        print_wrap('*** Warning! The file : ' + prl_name_path + ' does not exist')
            else:
                print_wrap('*** Warning! Unable to locate ' + lib_path_final + ' directory')
        print_wrap('--->            String to remove : /opt/android/ndk/toolchains/arm-linux-androideabi-4.8/prebuilt/linux-x86/bin/../lib/gcc/arm-linux-androideabi/4.8/libgcc.a')
        print_wrap('--->            String to remove : /opt/android/ndk/toolchains/arm-linux-androideabi-4.8/prebuilt/linux-x86_64/bin/../lib/gcc/arm-linux-androideabi/4.8/libgcc.a')
        print_wrap('--->            String to remove : /opt/android/ndk/toolchains/arm-linux-androideabi-4.8/prebuilt/darwin-x86_64/bin/../lib/gcc/arm-linux-androideabi/4.8/libgcc.a')
        print_wrap('--->            String to remove : c:/utils/android/ndk/toolchains/arm-linux-androideabi-4.8/prebuilt/windows/bin/../lib/gcc/arm-linux-androideabi/4.8/libgcc.a')


###############################
# function
###############################
def patch_build():
    # replace build directory paths in install_root locations
    replace_build_paths(MAKE_INSTALL_ROOT_DIR)
    # remove system specific paths from qconfig.pri
    if not ANDROID_BUILD:
        replace_system_paths()
    # fix qmake prl build fir references
    erase_qmake_prl_build_dir()
    if ANDROID_BUILD:
        rename_android_soname_files()
        patch_android_prl_files()
    # patch RPath if requested
    if REPLACE_RPATH:
        replace_rpath()
    # patch icu_install paths from files
    if bldinstallercommon.is_linux_platform():
        patch_icu_paths(MAKE_INSTALL_ROOT_DIR)


###############################
# function
###############################
def patch_icu_paths(search_path):
    extension_list = ['*.prl', '*.pri', '*.pc', '*.la']
    pattern = re.compile('icu_install')
    file_list = []
    for root, dirnames, filenames in os.walk(search_path):
        for extensions in extension_list:
            for filename in fnmatch.filter(filenames, extensions):
                path = os.path.join(root, filename)
                readlines = open(path,'r').read()
                if pattern.search(readlines):
                    file_list.append(path)

    for item in file_list:
        print_wrap('Erasing \'icu_install\' paths from file: ' + item)
        match = 0
        for line in fileinput.FileInput(item, inplace = 1):
            keep_going = True
            formatted_line = ''
            while keep_going:
                formatted_line = re.sub('-[I|L](.*?icu_install)(.*?)[\" $]', '', line)
                if formatted_line == line:
                    keep_going = False
                else:
                    match = match + 1
                    line = formatted_line
            print formatted_line.rstrip('\n')
        if match:
            print_wrap('Items erased: ' + str(match))


###############################
# function
###############################
def erase_qmake_prl_build_dir():
    print_wrap('--- Fix .prl files ---')
    # fetch all .prl files
    file_list = bldinstallercommon.make_files_list(MAKE_INSTALL_ROOT_DIR, '\\.prl')
    # erase lines starting with 'QMAKE_PRL_BUILD_DIR' from .prl files
    for item in file_list:
        found = False
        for line in fileinput.FileInput(item, inplace = 1):
            if line.startswith('QMAKE_PRL_BUILD_DIR'):
                found = True
                print ''
            else:
                print line,
        if found:
            print_wrap('Erased \'QMAKE_PRL_BUILD_DIR\' from: ' + item)


###############################
# function
###############################
def use_custom_icu():
    if os.path.isdir(CUSTOM_ICU_URI):
        return CUSTOM_ICU_URI
    package_raw_name = os.path.basename(CUSTOM_ICU_URI)
    icu_extract_path = os.path.join(SCRIPT_ROOT_DIR, 'icu_saveas')
    if os.path.isdir(icu_extract_path):
        bldinstallercommon.remove_tree(icu_extract_path)
    bldinstallercommon.create_dirs(icu_extract_path)
    icu_extract_saveas = os.path.join(icu_extract_path, package_raw_name)
    if os.path.isfile(CUSTOM_ICU_URI):
        bldinstallercommon.extract_file(CUSTOM_ICU_URI, icu_extract_path)
    if bldinstallercommon.is_content_url_valid(CUSTOM_ICU_URI):
        bldinstallercommon.retrieve_url(CUSTOM_ICU_URI, icu_extract_saveas)
        bldinstallercommon.extract_file(icu_extract_saveas, icu_extract_path)
    lib_path = bldinstallercommon.locate_directory(icu_extract_path, 'lib')
    if not lib_path:
        return icu_extract_path
    if (lib_path.endswith('/')):
        lib_path = lib_path[:len(lib_path) - 1]
    return os.path.dirname(lib_path)


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
    global QT_CREATOR_SRC_DIR
    global ANDROID_NDK_HOST
    global ANDROID_API_VERSION
    global ANDROID_SDK_HOME
    global ANDROID_NDK_HOME
    global ANDROID_BUILD
    global REPLACE_RPATH
    global CUSTOM_ICU_URI
    global EXTRA_ENV

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
    REPLACE_RPATH           = options.replace_rpath

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
        print_wrap(' *** Error! Could not find directory ' + QT_CREATOR_SRC_DIR)
        exit_script()

    #TODO: android options to global variables (all). Check that paths exists, also other values
    if options.android_ndk_host:
        ANDROID_NDK_HOST     = options.android_ndk_host
        ANDROID_BUILD        = True
    if options.android_api_version:
        ANDROID_API_VERSION  = options.android_api_version
    if options.android_sdk_home and os.path.isdir(options.android_sdk_home):
        ANDROID_SDK_HOME     = options.android_sdk_home
        ANDROID_BUILD        = True
    if options.android_ndk_home and os.path.isdir(options.android_ndk_home):
        ANDROID_NDK_HOME     = options.android_ndk_home
        ANDROID_BUILD        = True
    # All or none Android specific arguments must be preset
    if ANDROID_BUILD and '' in [ANDROID_NDK_HOST, ANDROID_SDK_HOME, ANDROID_NDK_HOME]:
        print_wrap('*** Invalid arguments for Android build. Please check them.')
        sys.exit(-1)

    if options.icu_uri:
        CUSTOM_ICU_URI = options.icu_uri
        icu_install_base_path = use_custom_icu()
        print_wrap('Using custom ICU from path: ' + icu_install_base_path)
        icu_path_lib = os.path.join(icu_install_base_path, 'lib')
        icu_path_inc = os.path.join(icu_install_base_path, 'include')
        CONFIGURE_OPTIONS += ' ' + '-L' + ' ' + icu_path_lib
        CONFIGURE_OPTIONS += ' ' + '-I' + ' ' + icu_path_inc
        if bldinstallercommon.is_linux_platform():
            env = EXTRA_ENV['LD_LIBRARY_PATH']
            if env:
                env = ':' + env
            EXTRA_ENV['LD_LIBRARY_PATH'] = icu_path_lib + env
        if bldinstallercommon.is_win_platform():
            env = EXTRA_ENV['LIB']
            if env:
                env = ';' + env
            EXTRA_ENV['LIB'] = icu_path_lib + env
    if options.prefix:
        CONFIGURE_OPTIONS += ' ' + '-prefix' + ' ' + options.prefix
    if options.runtime_path:
        CONFIGURE_OPTIONS += ' ' + '-R' + ' ' + options.runtime_path

    CONFIGURE_OPTIONS = CONFIGURE_OPTIONS.replace('  ', ' ')
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
                      action="store", type="int", dest="make_thread_count", default=multiprocessing.cpu_count()+1,
                      help="make job count, uses the number of available processors plus one by default.")
    OPTION_PARSER.add_option("-q", "--silent-build",
                      action="store_true", dest="silent_build", default=False,
                      help="suppress command output, show only errors")
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
                      help="options to be added to configure options not defined in configure options file given with -c, e.g. -a \"-<configure_option> <value>\"")
    OPTION_PARSER.add_option("--creator-dir",
                      action="store", type="string", dest="qt_creator_src_dir", default="",
                      help="path to Qt Creator sources. If given, the Qt Quick Designer processes (qmlpuppet, qml2puppet) will be built and packaged.")
    OPTION_PARSER.add_option("--replace-rpath",
                      action="store_true", dest="replace_rpath", default=False,
                      help="patch RPath with relative paths pointing to /lib")
    OPTION_PARSER.add_option("--icu",
                      action="store", type="string", dest="icu_uri", default="",
                      help="use the given icu for qt5 build, e.g. --icu=http://master.qt-project.org/development_releases/prebuilt/icu/prebuilt/ubuntu1110/icu_51_1_ubuntu_11_10_64_devel.7z")
    OPTION_PARSER.add_option("--runtime-path",
                      action="store", type="string", dest="runtime_path", default="",
                      help="use the given dynamic runtime path for qt5 build (-R for configure), e.g. --runtime-path=/home/user/my/path/here")
    OPTION_PARSER.add_option("--prefix",
                      action="store", type="string", dest="prefix", default="",
                      help="use the given prefix for qt5 build (-prefix for configure)")
    # for Android cross compilations
    OPTION_PARSER.add_option("--android-ndk-host",
                      action="store", type="string", dest="android_ndk_host", default="",
                      help="E.g. linux-x86")
    OPTION_PARSER.add_option("--android-api-version",
                      action="store", type="string", dest="android_api_version", default="android-10",
                      help="API version for the Android.")
    OPTION_PARSER.add_option("--android-sdk-home",
                      action="store", type="string", dest="android_sdk_home", default="",
                      help="Path to Android SDK home.")
    OPTION_PARSER.add_option("--android-ndk-home",
                      action="store", type="string", dest="android_ndk_home", default="",
                      help="Path to Android NDK home.")
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
    # save original qt_prfxpath in qmake executable
    save_original_qt_prfxpath()
    # build qmlpuppets
    if not ANDROID_BUILD:
        build_qmlpuppets()
    # install
    install_qt()
    # install qmlpuppets
    if not ANDROID_BUILD:
        install_qmlpuppets()
    #cleanup files that are not needed in binary packages
    clean_up(MAKE_INSTALL_ROOT_DIR)
    # build docs and copy to essentials install dir
    if not ANDROID_BUILD:
        build_docs()
    # patch files after build
    patch_build()
    # archive each submodule
    archive_submodules()


###############################
# function
###############################
main()


