
#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2014 Digia Plc and/or its subsidiary(-ies).
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
import bld_icu_tools
import multiprocessing
import patch_qmake_qt_key
from optparse import OptionParser, Option
import fnmatch
import shlex

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
ESSENTIALS_INSTALL_DIR_NAME         = 'essentials'
ADDONS_INSTALL_DIR_NAME             = 'addons'
SINGLE_INSTALL_DIR_NAME             = 'single'
#list of modules, only a backup list, this list will be updated during script execution
QT5_MODULES_LIST                    = [ 'qt3d', 'qtactiveqt', 'qtandroidextras', \
                                        'qtbase', 'qtconnectivity', 'qtdeclarative', \
                                        'qtdoc', 'qtenginio', 'qtfeedback', 'qtgraphicaleffects', \
                                        'qtimageformats', 'qtlocation', 'qtmacextras', \
                                        'qtmultimedia', 'qtpim', 'qtqa', 'qtquick1', \
                                        'qtquickcontrols', 'qtrepotools', 'qtscript', \
                                        'qtsensors', 'qtserialport', 'qtsvg', 'qtsystems', \
                                        'qttools', 'qttranslations', 'qtwayland', \
                                        'qtwebkit', 'qtwebkit-examples', 'qtwebsockets', \
                                        'qtwinextras', 'qtxmlpatterns', 'qtx11extras', \
                                        'qtwebengine', 'qtwebchannel' ]
QT5_ESSENTIALS                      = [ 'qtbase', 'qtdeclarative', 'qtdoc', \
                                        'qtmultimedia', 'qtquick1', 'qtquickcontrols', \
                                        'qtscript', 'qttools', 'qtwebkit', \
                                        'qtwebkit-examples', 'qtxmlpatterns' ]
# Modules not to be included in final package
QT5_MODULE_INSTALL_EXCLUDE_LIST     = ['qtwebkit-examples']
# Modules to be put in separate archive
QT5_MODULE_INSTALL_SEPARATE_LIST    = ['qtwebengine']

ORIGINAL_QMAKE_QT_PRFXPATH          = ''
FILES_TO_REMOVE_LIST                = ['Makefile', 'Makefile.Release', 'Makefile.Debug', \
                                       '.o', '.obj', '.moc', \
                                       '.qhp', \
                                       '.init-repository', '.gitignore']
IGNORE_PATCH_LIST                   = ['.png', '.jpg', '.gif', '.bmp', '.exe', '.dll', '.lib', '.qph']
INSTALL_PREFIX                      = ''
#Commandline options
OPTION_PARSER                       = 0
MAKE_INSTALL_CMD                    = ''
CONFIGURE_OPTIONS                   = '-confirm-license -debug-and-release -release -nomake tests -nomake examples -qt-zlib -qt-libjpeg -qt-libpng'
ANDROID_BUILD                       = False
QT_BUILD_OPTIONS                    = 0
DESKTOP_BUILD                       = True
QNX_BUILD                           = False

# init
bldinstallercommon.init_common_module(SCRIPT_ROOT_DIR)



###############################
# Class MultipleOption
###############################
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
# Qt5 build options class
###############################
class MkQtBuildOptions:
    def __init__(self):
        self.src_url                = ''
        self.qt_creator_src_dir     = ''
        self.configure_options      = ''
        self.add_configure_option   = ''
        self.make_cmd               = ''
        self.make_thread_count      = multiprocessing.cpu_count()+1
        self.silent_build           = False
        self.module_ignore_list     = []
        self.strict_mode            = True
        self.replace_rpath          = False
        self.icu_uri                = ''
        self.runtime_path           = ''
        self.prefix                 = ''
        self.android_ndk_host       = ''
        self.android_api_version    = ''
        self.android_sdk_home       = ''
        self.android_ndk_home       = ''
        self.system_env             = dict(os.environ)

    def set_args(self, option_parser):
        if option_parser.src_url:
            self.src_url = option_parser.src_url
        if option_parser.qt_creator_src_dir:
            self.qt_creator_src_dir = option_parser.qt_creator_src_dir
        if option_parser.configure_options:
            self.configure_options      = option_parser.configure_options
        if option_parser.add_configure_option:
            self.add_configure_option   = option_parser.add_configure_option
        if option_parser.make_cmd:
            self.make_cmd               = option_parser.make_cmd
        if option_parser.make_thread_count:
            self.make_thread_count      = option_parser.make_thread_count
        if option_parser.silent_build:
            self.silent_build           = option_parser.silent_build
        if option_parser.module_ignore_list:
            self.module_ignore_list     = option_parser.module_ignore_list
        if option_parser.strict_mode:
            self.strict_mode            = option_parser.strict_mode
        if option_parser.replace_rpath:
            self.replace_rpath          = option_parser.replace_rpath
        if option_parser.icu_uri:
            self.icu_uri                = option_parser.icu_uri
        if option_parser.runtime_path:
            self.runtime_path           = option_parser.runtime_path
        if option_parser.prefix:
            self.prefix                 = option_parser.prefix
        if option_parser.android_ndk_host:
            self.android_ndk_host       = option_parser.android_ndk_host
        if option_parser.android_api_version:
            self.android_api_version    = option_parser.android_api_version
        if option_parser.android_sdk_home:
            self.android_sdk_home       = option_parser.android_sdk_home
        if option_parser.android_ndk_home:
            self.android_ndk_home       = option_parser.android_ndk_home


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
    global MAKE_INSTALL_CMD
    global QT_BUILD_OPTIONS

    print_wrap('---------------- Initializing build --------------------------------')
    #do not edit configure options, if configure options are overridden from commandline options
    if bldinstallercommon.is_unix_platform():
        CONFIGURE_CMD = './'
    if QT_BUILD_OPTIONS.silent_build and not bldinstallercommon.is_win_platform():
        CONFIGURE_OPTIONS += ' -silent'
    # add required configuration arguments if Android build
    if ANDROID_BUILD:
        CONFIGURE_OPTIONS += ' -android-ndk ' + QT_BUILD_OPTIONS.android_ndk_home
        CONFIGURE_OPTIONS += ' -android-sdk ' + QT_BUILD_OPTIONS.android_sdk_home
        QT_BUILD_OPTIONS.system_env['ANDROID_NDK_HOST'] = QT_BUILD_OPTIONS.android_ndk_host
        QT_BUILD_OPTIONS.system_env['ANDROID_API_VERSION'] = QT_BUILD_OPTIONS.android_api_version

    CONFIGURE_CMD += 'configure'

    # make cmd
    if QT_BUILD_OPTIONS.make_cmd == '':  #if not given in commandline param, use nmake or make according to the os
        if bldinstallercommon.is_win_platform():        #win
            QT_BUILD_OPTIONS.make_cmd = 'nmake'
            MAKE_INSTALL_CMD = 'nmake'
            if QT_BUILD_OPTIONS.silent_build:
                QT_BUILD_OPTIONS.make_cmd += ' /s'
                MAKE_INSTALL_CMD += ' /s'
            MAKE_INSTALL_CMD += ' install'
        elif bldinstallercommon.is_unix_platform():    #linux & mac
            QT_BUILD_OPTIONS.make_cmd = 'make'
            MAKE_INSTALL_CMD = 'make'
            if QT_BUILD_OPTIONS.silent_build:
                QT_BUILD_OPTIONS.make_cmd += ' -s'
                MAKE_INSTALL_CMD += ' -s'
            MAKE_INSTALL_CMD += ' install'
    else:
        if QT_BUILD_OPTIONS.make_cmd == 'jom':
            MAKE_INSTALL_CMD = 'jom -j1 install'
            if QT_BUILD_OPTIONS.silent_build:
                QT_BUILD_OPTIONS.make_cmd += ' -s -nologo'
                MAKE_INSTALL_CMD += ' -s -nologo'
        ## QTBUG-38555: make install INSTALL_ROOT=\some\path does not work on Windows
        # always use 'make' for 'make install', 'mingw32-make install' does not work atm
        elif QT_BUILD_OPTIONS.make_cmd == 'mingw32-make' and bldinstallercommon.is_win_platform() and QNX_BUILD:
            MAKE_INSTALL_CMD = 'make install'

    #remove old working dirs
    if os.path.exists(WORK_DIR):
        print_wrap('    Removing old work dir ' + WORK_DIR)
        bldinstallercommon.remove_tree(WORK_DIR)
    if os.path.exists(MODULE_ARCHIVE_DIR):
        print_wrap('    Removing old module archive dir ' + MODULE_ARCHIVE_DIR)
        bldinstallercommon.remove_tree(MODULE_ARCHIVE_DIR)

    print_wrap('  Build    : ' + QT_BUILD_OPTIONS.make_cmd)
    print_wrap('  Install  : ' + MAKE_INSTALL_CMD)
    print_wrap('  Configure: ' + CONFIGURE_OPTIONS)
    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def fetch_src_package():
    global QT_PACKAGE_SAVE_AS_TEMP
    QT_PACKAGE_SAVE_AS_TEMP = os.path.normpath(WORK_DIR + os.sep + os.path.basename(QT_BUILD_OPTIONS.src_url))
    print_wrap('---------------- Fetching Qt src package ---------------------------')
    # check first if package on local file system
    if not os.path.isfile(QT_PACKAGE_SAVE_AS_TEMP):
        if not bldinstallercommon.is_content_url_valid(QT_BUILD_OPTIONS.src_url):
            print_wrap('*** Qt src package url: [' + QT_BUILD_OPTIONS.src_url + '] is invalid! Abort!')
            sys.exit(-1)
        print_wrap('     Downloading:        ' + QT_BUILD_OPTIONS.src_url)
        print_wrap('            into:        ' + QT_PACKAGE_SAVE_AS_TEMP)
        # start download
        urllib.urlretrieve(QT_BUILD_OPTIONS.src_url, QT_PACKAGE_SAVE_AS_TEMP, reporthook=bldinstallercommon.dlProgress)
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
    for ignore in QT_BUILD_OPTIONS.module_ignore_list:
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
    # shlex does not like backslashes
    cmd_args = cmd_args.replace('\\', '/')
    print_wrap('    Configure line: ' + cmd_args)
    if os.path.exists(QT_SOURCE_DIR + os.sep + CONFIGURE_CMD):
        print_wrap(' configure found from ' + QT_SOURCE_DIR)
        bldinstallercommon.do_execute_sub_process(shlex.split(cmd_args), QT_SOURCE_DIR, True, False, QT_BUILD_OPTIONS.system_env)
    else:
        print_wrap(' configure found from ' + QT_SOURCE_DIR + os.sep + 'qtbase')
        bldinstallercommon.do_execute_sub_process(shlex.split(cmd_args), QT_SOURCE_DIR + os.sep + 'qtbase', True, False, QT_BUILD_OPTIONS.system_env)
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

    cmd_args = QT_BUILD_OPTIONS.make_cmd
    if bldinstallercommon.is_unix_platform():
        cmd_args += ' -j' + str(QT_BUILD_OPTIONS.make_thread_count)
    elif bldinstallercommon.is_win_platform() and 'mingw32-make' in QT_BUILD_OPTIONS.make_cmd:
        cmd_args += ' -j' + str(QT_BUILD_OPTIONS.make_thread_count)
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR, QT_BUILD_OPTIONS.strict_mode, False, QT_BUILD_OPTIONS.system_env)
    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def build_qmlpuppets():
    if not QT_BUILD_OPTIONS.qt_creator_src_dir:
        return
    print_wrap('---------------- Building QML Puppets -------------------------------')
    qmake_executable_path = bldinstallercommon.locate_executable(QT_SOURCE_DIR, 'qmake' + bldinstallercommon.get_executable_suffix())
    if not qmake_executable_path:
        print_wrap('*** Error! qmake executable not found? Looks like the build has failed in previous step?')
        exit_script()

    cmd_args = QT_BUILD_OPTIONS.make_cmd
    if bldinstallercommon.is_unix_platform():
        cmd_args += ' -j' + str(QT_BUILD_OPTIONS.make_thread_count)

    shutil.copy(os.path.join(QT_SOURCE_DIR, ".qmake.super"),
                QT_BUILD_OPTIONS.qt_creator_src_dir)

    qmlpuppet_dir = os.path.join(QT_BUILD_OPTIONS.qt_creator_src_dir, 'src', 'tools', 'qml2puppet', 'qml2puppet')

    # override DESTDIR because DESTDIR in qml2puppet.pro doesn't handle that Qt is not installed in
    # QT_INSTALL_BINS, but within a INSTALL_ROOT
    prfx_path = ORIGINAL_QMAKE_QT_PRFXPATH
    if bldinstallercommon.is_win_platform():
        prfx_path = prfx_path[2:].replace('/', '\\')
    install_root_path = MAKE_INSTALL_ROOT_DIR + os.sep + ESSENTIALS_INSTALL_DIR_NAME + prfx_path
    qmake_executable_path = [qmake_executable_path, '-after', 'DESTDIR=' + os.path.join(install_root_path, 'bin')]

    bldinstallercommon.do_execute_sub_process(qmake_executable_path, qmlpuppet_dir, QT_BUILD_OPTIONS.strict_mode, False, QT_BUILD_OPTIONS.system_env)
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), qmlpuppet_dir, QT_BUILD_OPTIONS.strict_mode, False, QT_BUILD_OPTIONS.system_env)
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
        return_code, output = bldinstallercommon.do_execute_sub_process(cmd_args.split(' '),
            QT_SOURCE_DIR, QT_BUILD_OPTIONS.strict_mode, False, QT_BUILD_OPTIONS.system_env)
        return

    if QNX_BUILD:
        install_root_path = MAKE_INSTALL_ROOT_DIR + os.sep + SINGLE_INSTALL_DIR_NAME
        if bldinstallercommon.is_win_platform():
            # do not use drive letter when running make install [because of c:$(INSTALL_ROOT)/$(PREFIX)]
            install_root_path = install_root_path[2:]
            # apply the workaround from QTBUG-38555
            install_root_path = install_root_path.replace('\\','/').replace('/', '\\', 1)
        cmd_args = MAKE_INSTALL_CMD + ' ' + 'INSTALL_ROOT=' + install_root_path
        print_wrap('Installing module: Qt top level')
        return_code, output = bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR, QT_BUILD_OPTIONS.strict_mode,
                False, QT_BUILD_OPTIONS.system_env)
        return

    #make install for each module with INSTALL_ROOT
    print_wrap('Install modules to separate INSTALL_ROOT')
    for module_name in QT5_MODULES_LIST:
        # we do not provide pre-built examples
        if module_name in QT5_MODULE_INSTALL_EXCLUDE_LIST:
            print_wrap('Qt5 module excluded from make install: ' + module_name)
            continue
        # determine into which final archive this module belongs into
        install_dir = ''
        if module_name in QT5_MODULE_INSTALL_SEPARATE_LIST:
            install_dir = module_name
        elif module_name in QT5_ESSENTIALS:
            install_dir = ESSENTIALS_INSTALL_DIR_NAME
        else:
            install_dir = ADDONS_INSTALL_DIR_NAME
        install_root_path = MAKE_INSTALL_ROOT_DIR + os.path.sep + install_dir
        if bldinstallercommon.is_win_platform():
            install_root_path = install_root_path[2:]
            print_wrap('Using install root path: ' + install_root_path)
        submodule_dir_name = QT_SOURCE_DIR + os.sep + module_name
        cmd_args = MAKE_INSTALL_CMD + ' ' + 'INSTALL_ROOT=' + install_root_path
        print_wrap('Installing module: ' + module_name)
        return_code, output = bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), submodule_dir_name, QT_BUILD_OPTIONS.strict_mode,
            False, QT_BUILD_OPTIONS.system_env)
        if return_code >= 0:
            file_handle = open(MISSING_MODULES_FILE, 'a')
            file_handle.write('\nFailed to install ' + module_name)
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
    qconfig_file_path = bldinstallercommon.locate_file(MAKE_INSTALL_ROOT_DIR, 'qconfig.pri')
    print_wrap('------------ Replacing system paths in ' + qconfig_file_path + ' ----------------')
    for line in fileinput.FileInput(qconfig_file_path, inplace=1):
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
def clean_up():
    print_wrap('---------------- Cleaning unnecessary files from ' + MAKE_INSTALL_ROOT_DIR + '----------')
    # remove examples from binary packages
    bldinstallercommon.remove_directories_by_type(MAKE_INSTALL_ROOT_DIR, 'examples')
    # all platforms
    for root, dirs, files in os.walk(MAKE_INSTALL_ROOT_DIR):
        for name in files:
            if (any(name.endswith(to_remove) for to_remove in FILES_TO_REMOVE_LIST)):
                path = os.path.join(root, name)
                print_wrap('    ---> Deleting file: ' + name)
                os.remove(path)
    # on windows remove redundant .dll files from \lib
    if bldinstallercommon.is_win_platform():
        for name in os.listdir(MAKE_INSTALL_ROOT_DIR):
            dir_name = os.path.join(MAKE_INSTALL_ROOT_DIR, name)
            lib_path = bldinstallercommon.locate_directory(dir_name, 'lib')
            if lib_path:
                bldinstallercommon.delete_files_by_type_recursive(lib_path, '\\.dll')
    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def build_docs():
    print_wrap('------------------------- Building documentation -------------------')

    print_wrap('    Running \'make qmake_all\' ...')
    cmd_args = QT_BUILD_OPTIONS.make_cmd + ' qmake_all'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR, False, False, QT_BUILD_OPTIONS.system_env)

    #first we need to do make install for the sources
    print_wrap('    Running make install...')
    install_args = MAKE_INSTALL_CMD
    bldinstallercommon.do_execute_sub_process(install_args.split(' '), QT_SOURCE_DIR, False, False, QT_BUILD_OPTIONS.system_env)

    cmd_args = QT_BUILD_OPTIONS.make_cmd + ' docs'
    print_wrap('    Running make docs in ' + QT_SOURCE_DIR)
    #do not abort on fail, if the doc build fails, we still want to get the binary package
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), QT_SOURCE_DIR, False, False, QT_BUILD_OPTIONS.system_env)

    print_wrap('    Running make install_docs in ' + QT_SOURCE_DIR)
    make_cmd = QT_BUILD_OPTIONS.make_cmd
    install_root_path = MAKE_INSTALL_ROOT_DIR + os.sep + ESSENTIALS_INSTALL_DIR_NAME
    if bldinstallercommon.is_win_platform():
        install_root_path = install_root_path[2:]
    doc_install_args = make_cmd + ' -j1 install_docs INSTALL_ROOT=' + install_root_path
    #do not abort on fail, if the doc build fails, we still want to get the binary package
    bldinstallercommon.do_execute_sub_process(doc_install_args.split(' '), QT_SOURCE_DIR, False, False, QT_BUILD_OPTIONS.system_env)

    # Also archive docs in a separate qt5_docs.7z file
    print_wrap('    Archiving qt5_docs.7z')
    cmd_args = '7z a ' + MODULE_ARCHIVE_DIR + os.sep + 'qt5_docs' + '.7z *'
    run_in = os.path.normpath(MAKE_INSTALL_ROOT_DIR + os.sep + ESSENTIALS_INSTALL_DIR_NAME + os.sep + INSTALL_PREFIX + os.sep + 'doc')
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), run_in, True, True)

    print_wrap('--------------------------------------------------------------------')


###############################
# function
###############################
def replace_rpath():
    if not bldinstallercommon.is_linux_platform() or not DESKTOP_BUILD:
        print_wrap('*** Warning! RPath patching enabled only for Linux platforms and Desktop builds')
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

    if QNX_BUILD:
        print_wrap('---------- Archiving Qt modules')
        install_path = MAKE_INSTALL_ROOT_DIR + os.sep + SINGLE_INSTALL_DIR_NAME
        if bldinstallercommon.is_win_platform():
            install_path = 'C' + install_path[1:]
        if os.path.exists(install_path):
            cmd_args = '7z a ' + MODULE_ARCHIVE_DIR + os.sep + 'qt5_essentials' + '.7z *'
            run_in = os.path.normpath(install_path + os.sep + INSTALL_PREFIX)
            bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), run_in, True, True)
        else:
            print_wrap(install_path + os.sep + SINGLE_INSTALL_DIR_NAME + ' DIRECTORY NOT FOUND\n      -> Qt not archived!')
        return

    file_list = os.listdir(MAKE_INSTALL_ROOT_DIR)
    for item in file_list:
        print_wrap('---------- Archiving: ' + item)
        cmd_args = ['7z', 'a', MODULE_ARCHIVE_DIR + os.sep + 'qt5_' + item, '.7z' , '*']
        run_in = os.path.normpath(MAKE_INSTALL_ROOT_DIR + os.sep + item + os.sep + INSTALL_PREFIX)
        bldinstallercommon.do_execute_sub_process(cmd_args, run_in, True, True)
    return


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
                # let's replace the ' .*libgcc.a' string
                regex = re.compile(' .*libgcc.a')
                for prl_name in prl_files:
                    # let's just remove the undesired string for QMAKE_PRL_LIBS
                    prl_name_path = os.path.join(lib_path_final, prl_name)
                    print_wrap('---> Replacing regex .*libgcc.a in file: ' + prl_name_path)
                    if os.path.isfile(prl_name_path):
                        for line in fileinput.FileInput(prl_name_path, inplace=1):
                            if line.startswith('QMAKE_PRL_LIBS'):
                                line = regex.sub('', line)
                            print line,
                    else:
                        print_wrap('*** Warning! The file : ' + prl_name_path + ' does not exist')
            else:
                print_wrap('*** Warning! Unable to locate ' + lib_path_final + ' directory')


###############################
# function
###############################
def patch_qnx6_files(dir_tofind, regex_filename, line_toreplace, regex_toreplace, replace_with=''):
    # remove references to absolute path of the SDP on the build machine
    if QNX_BUILD:
        install_path_final = MAKE_INSTALL_ROOT_DIR + os.sep + SINGLE_INSTALL_DIR_NAME
        if bldinstallercommon.is_win_platform():
            install_path_final = 'C' + install_path_final[1:]

        # find the 'dir_tofind' directory under the install directory
        path_final = bldinstallercommon.locate_directory(install_path_final, dir_tofind)

        # just list the files with a pattern matching 'expression'
        print_wrap('---------- Remove references to hard coded paths of the SDP under ' + path_final + ' ----------------')
        print_wrap('*** Replacing hard coded paths to SDP under : ' + path_final)
        files_to_patch = [f for f in os.listdir(path_final) if re.match(regex_filename, f)]
        # let's replace the 'regex_toreplace' string
        regex = re.compile(regex_toreplace)
        for name_to_patch in files_to_patch:
            # let's just replace the line containing the 'line_toreplace' string
            name_path = os.path.join(path_final, name_to_patch)
            for line in fileinput.FileInput(name_path, inplace=1):
                if line.startswith(line_toreplace):
                    line = regex.sub(replace_with, line)
                print line,


###############################
# function
###############################
def patch_build():
    # replace build directory paths in install_root locations
    replace_build_paths(MAKE_INSTALL_ROOT_DIR)
    # remove system specific paths from qconfig.pri
    if not ANDROID_BUILD and not QNX_BUILD:
        replace_system_paths()
    # fix qmake prl build fir references
    erase_qmake_prl_build_dir()
    if ANDROID_BUILD:
        if bldinstallercommon.is_win_platform():
            install_path = MAKE_INSTALL_ROOT_DIR + os.sep + SINGLE_INSTALL_DIR_NAME
            install_path = 'C' + install_path[1:]
            lib_path_essentials = os.path.normpath(install_path + os.sep + INSTALL_PREFIX + os.sep)
            bldinstallercommon.rename_android_soname_files(lib_path_essentials)
        patch_android_prl_files()
    if QNX_BUILD:
        patch_qnx6_files('lib', 'libQt5.*\.prl', 'QMAKE_PRL_LIBS', '-L[^ ]* ')
        patch_qnx6_files('lib', 'libQt5.*\.la', 'dependency_libs', '-L[^ ]* ')
        # QT-701: internal qnx bug report
        patch_qnx6_files('common', 'qcc-base-qnx\.conf', 'QMAKE_LFLAGS ', '\n', ' -Wl,-rpath-link,$$[QT_INSTALL_LIBS]')
        patch_qnx6_files('pkgconfig', 'Qt5.*\.pc', 'Libs.private', '-L[^ ]* ')
    # patch RPath if requested
    if QT_BUILD_OPTIONS.replace_rpath:
        replace_rpath()
    # patch icu_install paths from files
    if bldinstallercommon.is_linux_platform():
        bld_icu_tools.patch_icu_paths(MAKE_INSTALL_ROOT_DIR)


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
    if os.path.isdir(QT_BUILD_OPTIONS.icu_uri):
        return QT_BUILD_OPTIONS.icu_uri
    package_raw_name = os.path.basename(QT_BUILD_OPTIONS.icu_uri)
    icu_extract_path = os.path.join(SCRIPT_ROOT_DIR, 'icu_saveas')
    if os.path.isdir(icu_extract_path):
        bldinstallercommon.remove_tree(icu_extract_path)
    bldinstallercommon.create_dirs(icu_extract_path)
    icu_extract_saveas = os.path.join(icu_extract_path, package_raw_name)
    if os.path.isfile(QT_BUILD_OPTIONS.icu_uri):
        bldinstallercommon.extract_file(QT_BUILD_OPTIONS.icu_uri, icu_extract_path)
    if bldinstallercommon.is_content_url_valid(QT_BUILD_OPTIONS.icu_uri):
        bldinstallercommon.retrieve_url(QT_BUILD_OPTIONS.icu_uri, icu_extract_saveas)
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
    global QT_BUILD_OPTIONS
    setup_option_parser()
    arg_count = len(sys.argv)
    if arg_count < 2:
        OPTION_PARSER.print_help()
        sys.exit(-1)
    (options, args) = OPTION_PARSER.parse_args()
    QT_BUILD_OPTIONS = MkQtBuildOptions()
    QT_BUILD_OPTIONS.set_args(options)
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
                      action="store", type="string", dest="android_api_version", default="",
                      help="API version for the Android.")
    OPTION_PARSER.add_option("--android-sdk-home",
                      action="store", type="string", dest="android_sdk_home", default="",
                      help="Path to Android SDK home.")
    OPTION_PARSER.add_option("--android-ndk-home",
                      action="store", type="string", dest="android_ndk_home", default="",
                      help="Path to Android NDK home.")
    print_wrap('---------------------------------------------------------------------')


##############################################################
# main_call_parameters
##############################################################
def main_call_parameters():
    global MAKE_INSTALL_CMD
    global CONFIGURE_OPTIONS
    global ANDROID_BUILD
    global EXTRA_ENV
    global DESKTOP_BUILD
    global QNX_BUILD

    if QT_BUILD_OPTIONS.make_cmd:
        MAKE_INSTALL_CMD    = QT_BUILD_OPTIONS.make_cmd + ' install'
    if not QT_BUILD_OPTIONS.make_thread_count:
        QT_BUILD_OPTIONS.make_thread_count = multiprocessing.cpu_count()+1

    if QT_BUILD_OPTIONS.configure_options:
        if os.path.isfile(QT_BUILD_OPTIONS.configure_options):
            configure_file = open(QT_BUILD_OPTIONS.configure_options, 'r')
            CONFIGURE_OPTIONS = configure_file.readline().rstrip('\r\n')
            configure_file.close()
        else:
            print_wrap(' *** Error! Could not find file ' + QT_BUILD_OPTIONS.configure_options)
            exit_script()
    else:
        print_wrap(' *** Error! No configure options given!')
        exit_script()

    if QT_BUILD_OPTIONS.add_configure_option:
        CONFIGURE_OPTIONS += ' ' + QT_BUILD_OPTIONS.add_configure_option

    if QT_BUILD_OPTIONS.qt_creator_src_dir and not os.path.isdir(QT_BUILD_OPTIONS.qt_creator_src_dir):
        print_wrap(' *** Error! Could not find directory ' + QT_BUILD_OPTIONS.qt_creator_src_dir)
        exit_script()

    #TODO: android options to global variables (all). Check that paths exists, also other values
    if QT_BUILD_OPTIONS.android_ndk_host:
        ANDROID_BUILD        = True
    if QT_BUILD_OPTIONS.android_sdk_home and os.path.isdir(QT_BUILD_OPTIONS.android_sdk_home):
        ANDROID_BUILD        = True
    if QT_BUILD_OPTIONS.android_ndk_home and os.path.isdir(QT_BUILD_OPTIONS.android_ndk_home):
        ANDROID_BUILD        = True
    # All or none Android specific arguments must be preset
    if ANDROID_BUILD and '' in [QT_BUILD_OPTIONS.android_ndk_host, QT_BUILD_OPTIONS.android_sdk_home, QT_BUILD_OPTIONS.android_ndk_home]:
        print_wrap('*** Invalid arguments for Android build. Please check them.')
        sys.exit(-1)

    # check whether this is a QNX build
    if 'qnx' in CONFIGURE_OPTIONS.lower():
        QNX_BUILD = True

    if QT_BUILD_OPTIONS.icu_uri:
        icu_install_base_path = use_custom_icu()
        print_wrap('Using custom ICU from path: ' + icu_install_base_path)
        icu_path_lib = os.path.join(icu_install_base_path, 'lib')
        icu_path_inc = os.path.join(icu_install_base_path, 'include')
        if bldinstallercommon.is_win_platform():
            env = EXTRA_ENV['LIB']
            if env:
                env = ';' + env
            EXTRA_ENV['LIB'] = icu_path_lib + env
    if QT_BUILD_OPTIONS.prefix:
        CONFIGURE_OPTIONS += ' ' + '-prefix' + ' ' + QT_BUILD_OPTIONS.prefix
    if QT_BUILD_OPTIONS.runtime_path:
        CONFIGURE_OPTIONS += ' ' + '-R' + ' ' + QT_BUILD_OPTIONS.runtime_path

    if ANDROID_BUILD or QNX_BUILD or any(substr in CONFIGURE_OPTIONS.lower() for substr in ['ios', 'winrt', 'winphone']):
        DESKTOP_BUILD = False

    CONFIGURE_OPTIONS = CONFIGURE_OPTIONS.replace('  ', ' ')
    # Starting the build
    run_build()


###############################
# run_build()
###############################
def run_build():
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
    # install
    install_qt()
    # build qmlpuppets into Qt install
    if DESKTOP_BUILD:
        build_qmlpuppets()
    # build docs and copy to essentials install dir
    if not ANDROID_BUILD and not QNX_BUILD:
        build_docs()
    #cleanup files that are not needed in binary packages
    clean_up()
    # patch files after build
    patch_build()
    # archive each submodule
    archive_submodules()


###############################
# execute_build
###############################
def execute_build():
    # parse cmd line
    parse_cmd_line()
    # Start the build
    main_call_parameters()


###############################
# function
###############################
if __name__ == "__main__":
    execute_build()

