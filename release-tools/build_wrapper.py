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
## ensure the GNU General Public Lhttps://www.google.fi/icense version 3.0 requirements will be
## met: http://www.gnu.org/copyleft/gpl.html.
##
##
## $QT_END_LICENSE$
##
#############################################################################

"""Scripts to generate SDK installer based on open source InstallerFramework"""

# import the print function which is used in python 3.x
from __future__ import print_function
import ConfigParser
import os
import shutil
import sys
from time import gmtime, strftime
import urllib
from optparse import OptionParser, Option, OptionValueError


import bldinstallercommon
import bld_ifw_tools
from bld_ifw_tools import IfwOptions
import release_build_handler


# ----------------------------------------------------------------------
BUILD_TIMESTAMP             = strftime('%Y-%m-%d', gmtime())
SCRIPT_ROOT_DIR             = os.path.dirname(os.path.realpath(__file__))
REPO_OUTPUT_DIR             = os.path.normpath(SCRIPT_ROOT_DIR + os.sep + 'repository')
WORK_DIR                    = os.environ['PKG_NODE_ROOT'] + os.sep + 'build'
#WORK_DIR                    = os.environ['PKG_NODE_ROOT']
COMMAND                     =''
LICENSE                     =''
QT_VERSION                  =''
QT_VERSION_TAG              =''
QT_FULL_VERSION             =''
TIME_STAMP                  =''
BUILD_NUMBER                =''
SERVER                      ='QT@qt-rnd.it.local'
PATH                        ='/data/www/packages/jenkins'
TARGET_ENV                  =''
ICU_LIBS                    ='http://download.qt-project.org/development_releases/prebuilt/icu/src/icu4c-51_1-src.tgz'
SRC_URL_PREFIX              ='http://qt-rnd.it.local/packages/jenkins'
SRC_URL                     =''
SSH_COMMAND                 ='ssh'
SSH_COMMAND_WIN             ='%SSH%'
SCP_COMMAND                 ='scp'
SCP_COMMAND_WIN             ='%SCP%'
PLATFORM                    =''
LICENSE_DIRS                = \
{'opensource': 'opensource'\
,'commercial': 'enterprise'}
SRC_DEST_DIRS               = \
['src','src/submodules_tar','src/submodules_zip'\
,'src/submodules','src/examples_injection','src/licheck',]
# TODO: target directories hard coded, should be figured out from somewhere!
BIN_TARGET_DIRS             = \
{'linux-g++-Ubuntu11.10-x86_Android-armv5':'android_armv5/linux_x86'\
,'linux-g++-Ubuntu11.10-x64_Android-armv5':'android_armv5/linux_x64'\
,'win-MinGW4.8-Windows7-x86_Android-armv5':'android_armv5/mingw_x86'\
,'linux-g++-Ubuntu11.10-x86_Android-armv7':'android_armv7/linux_x86'\
,'linux-g++-Ubuntu11.10-x64_Android-armv7':'android_armv7/linux_x64'\
,'win-MinGW4.8-Windows7-x86_Android-armv7':'android_armv7/mingw_x86'\
,'linux-g++-Ubuntu11.10-x86_Android-mips':'android_mips/linux_x86'\
,'linux-g++-Ubuntu11.10-x64_Android-mips':'android_mips/linux_x64'\
,'win-MinGW4.8-Windows7-x86_Android-mips':'android_mips/mingw_x86'\
,'linux-g++-Ubuntu11.10-x86_Android-x86':'android_x86/linux_x86'\
,'linux-g++-Ubuntu11.10-x64_Android-x86':'android_x86/linux_x64'\
,'win-MinGW4.8-Windows7-x86_Android-x86':'android_x86/mingw_x86'\
,'linux-g++-Ubuntu11.10-x86':'linux_gcc_32_ubuntu1110'\
,'linux-g++-Ubuntu11.10-x64':'linux_gcc_64_ubuntu1110'\
,'linux-g++-Ubuntu_11.10_x86':'linux_gcc_32_ubuntu1110'\
,'linux-g++-Ubuntu_11.10_x64':'linux_gcc_64_ubuntu1110'\
,'mac-clang-OSX_10.7_x64':'mac_cocoa_10.7'\
,'win-MinGW4.8-Windows7-x86_OpenGL':'windows_mingw'\
,'win-msvc2010-Windows7-x86_ANGLE':'windows_vs2010_32'\
,'win-msvc2010-Windows7-x86_OpenGL':'windows_vs2010_32_opengl'\
,'win-msvc2012-Windows8-x86_ANGLE':'windows_vs2012_32'\
,'win-msvc2012-Windows8-x64_ANGLE':'windows_vs2012_64'\
,'win-msvc2012-Windows8-x64_OpenGL':'windows_vs2012_64_opengl'\
,'win32-msvc2010_Windows_7':'windows_vs2010_32'\
,'win64-msvc2012_Windows_8':'windows_vs2012_64'\
,'macx-clang_OSX_10.7':'mac_cocoa_10.7'\
,'pkg-osx107-x64-01':'mac_cocoa_10.7'\
,'mac-clang-10.7-x64':'mac_cocoa_10.7'\
,'pkg-win7-x86-01':'windows_vs2010_32'}
REMOTE_DIR                  =''
LATEST_DIR                  =''
EXTRA_ENV                   = dict(os.environ)

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
# init_qt_build_cycle
###############################
def init_qt_build_cycle():
    # create dir structures in network drive
    # TODO: Figure out correct path + check parameters!
    for dir_name in SRC_DEST_DIRS:
        if dir_name != 'src/licheck':
            dir_path = REMOTE_DIR + '/' + dir_name
            create_remote_dirs(SERVER, dir_path)
        elif LICENSE == 'commercial':
            dir_path = REMOTE_DIR + '/' + dir_name
            create_remote_dirs(SERVER, dir_path)

    # Create directories for targets
    # for dir_name in BIN_TARGET_DIRS:
    #    dir_path = REMOTE_DIR + os.sep + dir_name
    #    create_remote_dirs(SERVER, dir_path)

    # Update latest link
    if bldinstallercommon.is_win_platform():
        cmd_args =[SSH_COMMAND_WIN,SERVER,'ln -sfn',REMOTE_DIR,LATEST_DIR]
    else:
        cmd_args =[SSH_COMMAND,SERVER,'ln -sfn',REMOTE_DIR,LATEST_DIR]
    bldinstallercommon.do_execute_sub_process(cmd_args,SCRIPT_ROOT_DIR, True)

    # QT Creator directory
    dir_path = PATH + '/' + LICENSE_DIRS[LICENSE] + '/' + 'qtcreator'
    create_remote_dirs(SERVER, dir_path + '/' + TIME_STAMP + '-' + BUILD_NUMBER)

    ssh_cmd = SSH_COMMAND
    if bldinstallercommon.is_win_platform():
        ssh_cmd = SSH_COMMAND_WIN
    cmd_args =[ssh_cmd, SERVER, 'ln -sfn', dir_path + '/' + TIME_STAMP + '-' + BUILD_NUMBER, dir_path + '/' + 'latest']
    bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR,True)



###############################
# handle_ifw_build()
###############################
def handle_ifw_build():
    os.chdir(WORK_DIR+'/qtsdk/release-tools')
    if bldinstallercommon.is_win_platform():
        if LICENSE == 'commercial':
            cmd_args = ['python','-u','bld_ifw_tools.py','--license='+LICENSE,'--qt_archive_uri=http://download.qt-project.org/development_releases/prebuilt/qt-src-for-ifw/qt_4.8.4_ifw_prepared.zip','--ifw_url=git://gitorious.org/installer-framework/installer-framework.git','--ifw_branch=1.4','--product_key_checker_url='+WORK_DIR+'/qtsdk-enterprise/productkeycheck/qt_product_key_checker.pri']
        else:
            cmd_args = ['python','-u','bld_ifw_tools.py','--license='+LICENSE,'--qt_archive_uri=http://download.qt-project.org/development_releases/prebuilt/qt-src-for-ifw/qt_4.8.4_ifw_prepared.zip','--ifw_url=git://gitorious.org/installer-framework/installer-framework.git','--ifw_branch=1.4']
    else:
        if LICENSE == 'commercial':
            cmd_args = ['python','-u','bld_ifw_tools.py','--license='+LICENSE,'--qt_archive_uri=http://download.qt-project.org/development_releases/prebuilt/qt-src-for-ifw/qt_4.8.4_ifw_prepared.tar.gz','--ifw_url=git://gitorious.org/installer-framework/installer-framework.git','--ifw_branch=1.4','--product_key_checker_url='+WORK_DIR+'/qtsdk-enterprise/productkeycheck/qt_product_key_checker.pri']
        else:
            cmd_args = ['python','-u','bld_ifw_tools.py','--license='+LICENSE,'--qt_archive_uri=http://download.qt-project.org/development_releases/prebuilt/qt-src-for-ifw/qt_4.8.4_ifw_prepared.tar.gz','--ifw_url=git://gitorious.org/installer-framework/installer-framework.git','--ifw_branch=1.4']


    bldinstallercommon.do_execute_sub_process(cmd_args,'/work/build/qtsdk/release-tools',True)

    #create destination dirs
    create_remote_dirs(SERVER,PATH + '/' + LICENSE_DIRS[LICENSE] + '/ifw/1.4');

    if bldinstallercommon.is_win_platform():
        file_list = os.listdir(SCRIPT_ROOT_DIR+'/build_artefacts')
        for file_name in file_list:
            if file_name.endswith(".7z"):
                cmd_args = [SCP_COMMAND_WIN,file_name,SERVER + ':' + PATH + '/' + LICENSE_DIRS[LICENSE] + '/ifw/1.4/']
                bldinstallercommon.do_execute_sub_process(cmd_args,SCRIPT_ROOT_DIR+'/build_artefacts',True)
    else:
        cmd_args = ['rsync','-r','./',SERVER + ':' + PATH + '/' + LICENSE_DIRS[LICENSE] + '/ifw/1.4/']
        bldinstallercommon.do_execute_sub_process(cmd_args,SCRIPT_ROOT_DIR+'/build_artefacts',True)


###############################
# handle_qt_src_package_build
###############################
def handle_qt_src_package_build():
    global COMMAND
    global LICENSE
    global QT_VERSION
    global TIME_STAMP
    global BUILD_NUMBER
    global SERVER
    global PATH

    #cmd_args = ['./init-repository','-f']
    exec_path = WORK_DIR + os.sep + 'qt5'
    #bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    if LICENSE == 'commercial':
        cmd_args = ['../patches/apply.sh']
        bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)

    if LICENSE == 'commercial':
        copy_license_checkers()
    package_path = WORK_DIR + os.sep + 'src_pkg'
    bldinstallercommon.create_dirs(package_path)
    if QT_VERSION == '5.1.1':
        cmd_args = [WORK_DIR + os.sep + 'qtsdk/release-tools/mksrc.sh','-u',WORK_DIR + os.sep + 'qt5','-v',QT_FULL_VERSION,'-m','-N','-l',LICENSE_DIRS[LICENSE],'-i','qlalr','-i','qt3d','-i','qtconnectivity','-i','qtdocgallery','-i','qtfeedback','-i','qtjsondb','-i','qtlocation','-i','qtmacextras','-i','qtpim','-i','qtqa','-i','qtrepotools','-i','qtsystems','-i','qtwayland','-i','qtwinextras']
    else: # 5.2.0
        cmd_args = [WORK_DIR + os.sep + 'qtsdk/release-tools/mksrc.sh','-u',WORK_DIR + os.sep + 'qt5','-v',QT_FULL_VERSION,'-m','-N','-l',LICENSE_DIRS[LICENSE],'-i','qlalr','-i','qt3d','-i','qtdocgallery','-i','qtfeedback','-i','qtjsondb','-i','qtlocation','-i','qtmacextras','-i','qtpim','-i','qtqa','-i','qtrepotools','-i','qtsystems','-i','qtwayland']

    bldinstallercommon.do_execute_sub_process(cmd_args,package_path, True)

    # Example injection
    package_name = 'qt-everywhere-' + LICENSE_DIRS[LICENSE] + '-src-' + QT_FULL_VERSION

    cmd_args = ['tar','xzf','single/' + package_name + '.tar.gz']

    bldinstallercommon.do_execute_sub_process(cmd_args,package_path, True)
    essentials_path = WORK_DIR + os.sep + 'src_pkg' + os.sep + 'examples_essentials'
    bldinstallercommon.create_dirs(essentials_path)
    addons_path = WORK_DIR + os.sep + 'src_pkg' + os.sep + 'examples_addons'
    bldinstallercommon.create_dirs(addons_path)

    src_dirs = os.listdir(package_path + os.sep + package_name)
    current_path = os.getcwd()
    os.chdir(package_path + os.sep + package_name)
    for dir_name in src_dirs:
        if os.path.isdir(dir_name):
            module_dirs = os.listdir(dir_name)
            for example_dir in module_dirs:
                if example_dir == 'examples':
                    bldinstallercommon.copy_tree(package_path + os.sep + package_name + os.sep + dir_name + os.sep + example_dir, essentials_path)
    os.chdir(current_path)
    cmd_args = ['cp','-r',package_name + os.sep + 'qtbase' + os.sep + 'examples' + os.sep +'examples.pro', essentials_path]
    bldinstallercommon.do_execute_sub_process(cmd_args,package_path, True)

    # remove out of place top level files from qtdeclarative
    if os.path.exists(essentials_path + os.sep + 'HACKING'):
        os.remove(essentials_path + os.sep + 'HACKING')
    if os.path.exists(essentials_path + os.sep + 'README'):
        os.remove(essentials_path + os.sep + 'README')

    shutil.move(essentials_path + os.sep + 'activeqt', addons_path)
    shutil.move(essentials_path + os.sep +'svg', addons_path)

    cmd_args = ['7z','a','..' + os.sep + 'examples_essentials.7z','*']
    bldinstallercommon.do_execute_sub_process(cmd_args,essentials_path, True)
    cmd_args = [SCRIPT_ROOT_DIR + os.sep + 'winzipdir.sh', '..' + os.sep + 'examples_essentials.zip','.' ]
    bldinstallercommon.do_execute_sub_process(cmd_args,essentials_path, True)

    cmd_args = ['7z','a','..' + os.sep + 'examples_addons.7z','*']
    bldinstallercommon.do_execute_sub_process(cmd_args,addons_path, True)
    cmd_args = [SCRIPT_ROOT_DIR + os.sep + 'winzipdir.sh', '..' + os.sep + 'examples_addons.zip','.' ]
    bldinstallercommon.do_execute_sub_process(cmd_args,addons_path, True)


    # Upload packages
    exec_path = SCRIPT_ROOT_DIR
    cmd_args = ['rsync','-r','../../src_pkg/single/',SERVER + ':' + LATEST_DIR + os.sep + 'src' + os.sep + 'single' + os.sep]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = ['rsync','-r','../../src_pkg/submodules_tar/',SERVER + ':' + LATEST_DIR + os.sep + 'src' + os.sep + 'submodules' + os.sep]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = ['rsync','-r','../../src_pkg/submodules_zip/',SERVER + ':' + LATEST_DIR + os.sep + 'src' + os.sep + 'submodules' + os.sep]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)

    file_list = os.listdir(package_path)
    for file_name in file_list:
        if file_name.startswith("examples_addons."):
            cmd_args = ['scp',file_name,SERVER + ':' + LATEST_DIR + os.sep + 'src' + os.sep + 'examples_injection']
            bldinstallercommon.do_execute_sub_process(cmd_args,package_path, True)
        if file_name.startswith("examples_essentials."):
            cmd_args = ['scp',file_name,SERVER + ':' + LATEST_DIR + os.sep + 'src' + os.sep + 'examples_injection']
            bldinstallercommon.do_execute_sub_process(cmd_args,package_path, True)

###############################
# handle_icu_build
###############################
def handle_icu_build():
    global EXTRA_ENV
    dir_list = os.listdir(WORK_DIR)
    for file_name in dir_list:
        if file_name.startswith("icu"):
                cmd_args = 'rm -rf ' + file_name
                bldinstallercommon.do_execute_sub_process(cmd_args.split(' '),WORK_DIR, True)

    cmd_args = 'rm -rf icu*'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '),WORK_DIR, True)
    bldinstallercommon.create_dirs(WORK_DIR+ os.sep + 'icu_install')
    exec_path = WORK_DIR
    cmd_args = ['wget',ICU_LIBS]
    bldinstallercommon.do_execute_sub_process(cmd_args,exec_path, True)
    dir_list = os.listdir(WORK_DIR)
    for file_name in dir_list:
        if file_name.startswith("icu4c"):
            cmd_args = ['tar','xvzf',file_name]
            bldinstallercommon.do_execute_sub_process(cmd_args,exec_path, True)
    EXTRA_ENV['LFLAGS']='-Wl,-rpath,\$ORIGIN'
    cmd_args = ['./runConfigureICU','Linux','--enable-rpath','--prefix='+WORK_DIR + os.sep + 'icu_install']
    exec_path = WORK_DIR+os.sep+'icu'+os.sep+'source'
    bldinstallercommon.do_execute_sub_process(cmd_args,exec_path, True,EXTRA_ENV)
    cmd_args = ['make','-j6']
    bldinstallercommon.do_execute_sub_process(cmd_args,exec_path, True,EXTRA_ENV)
    cmd_args = ['make','install']
    bldinstallercommon.do_execute_sub_process(cmd_args,exec_path, True,EXTRA_ENV)

    cmd_args = 'chrpath -r $ORIGIN libicuuc.so'
    exec_path = WORK_DIR+os.sep+'icu_install'+os.sep+'lib'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), exec_path, True, EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libicui18n.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '),exec_path, True,EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libicudata.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '),exec_path, True,EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libicuio.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '),exec_path, True,EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libicule.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '),exec_path, True,EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libiculx.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '),exec_path, True,EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libicutest.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '),exec_path, True,EXTRA_ENV)
    cmd_args = 'chrpath -r \$ORIGIN libicutu.so'
    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '),exec_path, True,EXTRA_ENV)

    dir_list = os.listdir(WORK_DIR)
    for file_name in dir_list:
        if file_name.startswith("icu"):
            if file_name != 'icu_install':
                    cmd_args = 'rm -rf ' + file_name
                    bldinstallercommon.do_execute_sub_process(cmd_args.split(' '),WORK_DIR, True)

###############################
# handle_qt_android_release_build
###############################
def handle_qt_android_release_build():
    configure_extra_options = ''
    if LICENSE == 'enterprise':
        if bldinstallercommon.is_win_platform():
            configure_extra_options += '-D QT_EVAL'
        else:
            configure_extra_options += '-DQT_EVAL'
    global EXTRA_ENV
    cmd_args = ''
    script_path = 'qtsdk' + os.sep + 'release-tools' + os.sep + 'mkqt5bld.py'
    source_url = SRC_URL+'/single/qt-everywhere-' + LICENSE_DIRS[LICENSE] + '-src-' + QT_FULL_VERSION
    configure_files_path = os.path.join(WORK_DIR, 'qtsdk', 'release-tools', 'bld_config' + os.sep)
    if bldinstallercommon.is_linux_platform():
        if TARGET_ENV.find("x64") >= 1:
            if TARGET_ENV.find("armv7") >= 1:
                cmd_args = ['python','-u',script_path,'-u',source_url + '.tar.gz','-c',configure_files_path + 'configure_android_armv7_' + LICENSE,'-a','-prefix ' +WORK_DIR + os.sep + '______________________________PADDING______________________________' + ' -android-toolchain-version 4.8','--android-ndk-host=linux-x86_64','--android-api-version=android-10','--android-sdk-home=/opt/android/sdk','--android-ndk-home=/opt/android/ndk','--replace-rpath']
            else:
                cmd_args = ['python','-u',script_path,'-u',source_url + '.tar.gz','-c',configure_files_path + 'configure_android_x86_' + LICENSE,'-a','-prefix ' +WORK_DIR + os.sep + '______________________________PADDING______________________________' + ' -android-toolchain-version 4.8','--android-ndk-host=linux-x86_64','--android-api-version=android-10','--android-sdk-home=/opt/android/sdk','--android-ndk-home=/opt/android/ndk','--replace-rpath']
        else:
            if TARGET_ENV.find("armv7") >= 1:
                cmd_args = ['python','-u',script_path,'-u',source_url + '.tar.gz','-c',configure_files_path + 'configure_android_armv7_' + LICENSE,'-a','-prefix ' +WORK_DIR + os.sep + '______________________________PADDING______________________________' + ' -android-toolchain-version 4.8','--android-ndk-host=linux-x86','--android-api-version=android-10','--android-sdk-home=/opt/android/sdk','--android-ndk-home=/opt/android/ndk','--replace-rpath']
            else:
                cmd_args = ['python','-u',script_path,'-u',source_url + '.tar.gz','-c',configure_files_path + 'configure_android_x86_' + LICENSE,'-a','-prefix ' +WORK_DIR + os.sep + '______________________________PADDING______________________________' + ' -android-toolchain-version 4.8','--android-ndk-host=linux-x86','--android-api-version=android-10','--android-sdk-home=/opt/android/sdk','--android-ndk-home=/opt/android/ndk','--replace-rpath']
        bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR, True)
    elif bldinstallercommon.is_win_platform():
        os.chdir('/')
        exec_dir=os.getcwd()
        if TARGET_ENV.find("armv7") >= 1:
            EXTRA_ENV['ANDROID_TARGET_ARCH'] = 'armeabi-v7a'
            EXTRA_ENV['QTDIR'] = ''
            cmd_args = ['python','-u',script_path,'-u',source_url + '.zip','-m','mingw32-make','-c',configure_files_path + 'configure_android_armv7_' + LICENSE,'-a','-prefix ' +WORK_DIR + os.sep + 'PADDING' + ' -android-toolchain-version 4.8','--android-ndk-host=windows','--android-api-version=android-10','--android-sdk-home=C:'+os.sep+'Utils'+os.sep+'android'+os.sep+'sdk'+os.sep+'sdk','--android-ndk-home=C:'+os.sep+'Utils'+os.sep+'android'+os.sep+'ndk']
        else:
            EXTRA_ENV['ANDROID_TARGET_ARCH'] = 'x86'
            EXTRA_ENV['QTDIR'] = ''
            cmd_args = ['python','-u',script_path,'-u',source_url + '.zip','-m','mingw32-make','-c',configure_files_path + 'configure_android_x86_' + LICENSE,'-a','-prefix ' +WORK_DIR + os.sep + 'PADDING' + ' -android-toolchain-version 4.8','--android-ndk-host=windows','--android-api-version=android-10','--android-sdk-home=C:'+os.sep+'Utils'+os.sep+'android'+os.sep+'sdk'+os.sep+'sdk','--android-ndk-home=C:'+os.sep+'Utils'+os.sep+'android'+os.sep+'ndk']
        bldinstallercommon.do_execute_sub_process(cmd_args,exec_dir, True)

###############################
# handle_qt_release_build
###############################
def handle_qt_release_build():
    # Handle Android build
    if TARGET_ENV.find("Android") >= 1:
        handle_qt_android_release_build()
    else:
        # download pre-compiled ICU
        global EXTRA_ENV
        icu_lib_path = ''
        icu_include_path = ''
        if ICU_LIBS !='':
            handle_icu_build()
#        cmd_args = ['wget',ICU_LIBS]
#        bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR, True)

#        dir_list = os.listdir(WORK_DIR)
#        for file_name in dir_list:
#            if file_name.startswith("icu_"):
#                cmd_args = ['7z','x',file_name]
#                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR, True)

    # del os.environ['QTDIR']
        if ICU_LIBS !='':
            dir_list = os.listdir(WORK_DIR)
            print(dir_list)
            for file_name in dir_list:
                print(file_name)
                if file_name.startswith("icu"):
                    print(file_name)
                    if os.path.isdir(WORK_DIR+ os.sep + file_name):
                        icu_lib_path = WORK_DIR + os.sep + file_name + os.sep + 'lib'
                        icu_include_path = WORK_DIR + os.sep + file_name + os.sep + 'include'
                        EXTRA_ENV['LD_LIBRARY_PATH'] = icu_lib_path
        script_path = 'qtsdk' + os.sep + 'release-tools' + os.sep + 'mkqt5bld.py'
        source_url = SRC_URL+'/single/qt-everywhere-' + LICENSE_DIRS[LICENSE] + '-src-' + QT_FULL_VERSION
        configure_files_path = os.path.join(WORK_DIR, 'qtsdk', 'release-tools', 'bld_config' + os.sep)
        if bldinstallercommon.is_linux_platform():
            if LICENSE == 'commercial':
                cmd_args = ['python','-u',script_path,'-u',source_url + '.tar.gz','--creator-dir=' + WORK_DIR + os.sep + 'qt-creator','-c',configure_files_path + 'configure_linux_' + LICENSE,'-a','-DQT_EVAL -L '+icu_lib_path + ' -I ' + icu_include_path + ' -prefix ' +WORK_DIR + os.sep + '______________________________PADDING______________________________' + ' -R ' + WORK_DIR + os.sep + '______________________________PADDING______________________________']
            else:
                cmd_args = ['python','-u',script_path,'-u',source_url + '.tar.gz','--creator-dir=' + WORK_DIR + os.sep + 'qt-creator','-c',configure_files_path + 'configure_linux_' + LICENSE,'-a','-L '+icu_lib_path + ' -I ' + icu_include_path + ' -prefix ' +WORK_DIR + os.sep + '______________________________PADDING______________________________' + ' -R ' + WORK_DIR + os.sep + '______________________________PADDING______________________________']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR, True,EXTRA_ENV)
        elif bldinstallercommon.is_win_platform():
            exec_path = os.getcwd()
            if LICENSE == 'commercial':
                if TARGET_ENV.find('opengl') >= 1 or TARGET_ENV.find('OpenGL') >= 1:
                    cmd_args = ['python','-u',script_path,'-u',source_url + '.zip','--creator-dir=' + WORK_DIR + os.sep + 'qt-creator','-m','jom','-c',configure_files_path + 'configure_win_opengl_' + LICENSE,'-a','-D QT_EVAL' + ' -prefix ' + WORK_DIR + os.sep + 'PADDING']
                elif TARGET_ENV.find('msvc2012') >= 1 and TARGET_ENV.find('x86') >= 1:
                    cmd_args = ['python','-u',script_path,'-u',source_url + '.zip','-m','jom','-c',configure_files_path + 'configure_win_' + LICENSE,'-a','-D QT_EVAL -no-vcproj' + ' -prefix ' + WORK_DIR + os.sep + 'PADDING']
                else:
                    cmd_args = ['python','-u',script_path,'-u',source_url + '.zip','--creator-dir=' + WORK_DIR + os.sep + 'qt-creator','-m','jom','-c',configure_files_path + 'configure_win_' + LICENSE,'-a','-D QT_EVAL' + ' -prefix ' + WORK_DIR + os.sep + 'PADDING']
            else:
                if TARGET_ENV.find('opengl') >=1 or TARGET_ENV.find('OpenGL') >= 1:
                    cmd_args = ['python','-u',script_path,'-u',source_url + '.zip','--creator-dir=' + WORK_DIR + os.sep + 'qt-creator','-m','jom','-c',configure_files_path + 'configure_win_opengl_' + LICENSE,'-a','-prefix ' + WORK_DIR + os.sep + 'PADDING']
                elif TARGET_ENV.find('msvc2012') >= 1 and TARGET_ENV.find('x86') >= 1:
                    cmd_args = ['python','-u',script_path,'-u',source_url + '.zip','--creator-dir=' + WORK_DIR + os.sep + 'qt-creator','-m','jom','-c',configure_files_path + 'configure_win_' + LICENSE,'-a','-prefix ' + WORK_DIR + os.sep + 'PADDING']
                else:
                    cmd_args = ['python','-u',script_path,'-u',source_url + '.zip','--creator-dir=' + WORK_DIR + os.sep + 'qt-creator','-m','jom','-c',configure_files_path + 'configure_win_' + LICENSE,'-a','-prefix ' + WORK_DIR + os.sep + 'PADDING']
            bldinstallercommon.do_execute_sub_process(cmd_args,exec_path, True)
        elif bldinstallercommon.is_mac_platform():
            cmd_args = ['python','-u',script_path,'-u',source_url + '.tar.gz','--creator-dir=' + WORK_DIR + os.sep + 'qt-creator','-c',configure_files_path + 'configure_mac_' + LICENSE,'-a','-prefix ' + WORK_DIR + os.sep + '______________________________PADDING______________________________']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR, True)

    # Inject examples
    if TARGET_ENV.find('Android') <= 0:
        if bldinstallercommon.is_linux_platform():
            cmd_args = ['wget', SRC_URL + '/examples_injection/examples_essentials.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + '/module_archives', True)
            cmd_args = ['wget', SRC_URL + '/examples_injection/examples_addons.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + '/module_archives', True)
        elif bldinstallercommon.is_mac_platform():
            cmd_args = ['curl','-O',SRC_URL + '/examples_injection/examples_essentials.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
            cmd_args = ['curl','-O',SRC_URL + '/examples_injection/examples_addons.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
        else:
            if TARGET_ENV.find('x86') >=1:
                cmd_args = ['C:\Program Files\Git\\bin\curl','-O',SRC_URL + '/examples_injection/examples_essentials.7z']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
                cmd_args = ['C:\Program Files\Git\\bin\curl','-O',SRC_URL + '/examples_injection/examples_addons.7z']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
            else:
                cmd_args = ['C:\Program Files (x86)\Git\\bin\curl','-O',SRC_URL + '/examples_injection/examples_essentials.7z']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
                cmd_args = ['C:\Program Files (x86)\Git\\bin\curl','-O',SRC_URL + '/examples_injection/examples_addons.7z']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)

        bldinstallercommon.create_dirs(WORK_DIR+'module_archives' +os.sep+ 'essentials')
        bldinstallercommon.create_dirs(WORK_DIR+'module_archives' +os.sep + 'addons')

        if bldinstallercommon.is_win_platform():
            if TARGET_ENV.find('x86') >= 1:
                cmd_args = ['7z','x','qt5_essentials.7z','-oessentials']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
                cmd_args = ['7z','x','examples_essentials.7z','-oessentials'+os.sep+'examples','-y']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)

                cmd_args = ['C:\Program Files\Git\\bin\\rm','qt5_essentials.7z']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
                cmd_args = ['C:\Program Files\Git\\bin\\rm','examples_essentials.7z']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)

                cmd_args = ['7z','a','..'+os.sep+'qt5_essentials.7z','*']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives/essentials', True)

                cmd_args = ['7z','x','qt5_addons.7z','-oaddons']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
                cmd_args = ['7z','x','examples_addons.7z','-oaddons'+os.sep+'examples','-y']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)

                cmd_args = ['C:\Program Files\Git\\bin\\rm','qt5_addons.7z']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
                cmd_args = ['C:\Program Files\Git\\bin\\rm','examples_addons.7z']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)

                cmd_args = ['7z','a','..'+os.sep+'qt5_addons.7z','*']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives/addons',True)
            else:
                cmd_args = ['7z','x','qt5_essentials.7z','-oessentials']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
                cmd_args = ['7z','x','examples_essentials.7z','-oessentials'+os.sep+'examples','-y']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)

                cmd_args = ['C:\Program Files (x86)\Git\\bin\\rm','qt5_essentials.7z']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
                cmd_args = ['C:\Program Files (x86)\Git\\bin\\rm','examples_essentials.7z']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)

                cmd_args = ['7z','a','..'+os.sep+'qt5_essentials.7z','*']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives/essentials', True)

                cmd_args = ['7z','x','qt5_addons.7z','-oaddons']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
                cmd_args = ['7z','x','examples_addons.7z','-oaddons'+os.sep+'examples','-y']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)

                cmd_args = ['C:\Program Files (x86)\Git\\bin\\rm','qt5_addons.7z']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
                cmd_args = ['C:\Program Files (x86)\Git\\bin\\rm','examples_addons.7z']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)

                cmd_args = ['7z','a','..'+os.sep+'qt5_addons.7z','*']
                bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives/addons',True)
        else:
            cmd_args = ['7z','x','qt5_essentials.7z','-oessentials']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
            cmd_args = ['7z','x','examples_essentials.7z','-oessentials'+os.sep+'examples','-y']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)

            cmd_args = ['rm','qt5_essentials.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
            cmd_args = ['rm','examples_essentials.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)

            cmd_args = ['7z','a','..'+os.sep+'qt5_essentials.7z','*']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives/essentials', True)

            cmd_args = ['7z','x','qt5_addons.7z','-oaddons']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
            cmd_args = ['7z','x','examples_addons.7z','-oaddons'+os.sep+'examples','-y']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)

            cmd_args = ['rm','qt5_addons.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)
            cmd_args = ['rm','examples_addons.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives', True)

            cmd_args = ['7z','a','..'+os.sep+'qt5_addons.7z','*']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives/addons',True)

    # Create target directory
    create_remote_dirs(SERVER,LATEST_DIR+'/'+BIN_TARGET_DIRS[TARGET_ENV]);

    dir_list = os.listdir(WORK_DIR + os.sep + 'module_archives')
    print(dir_list)
    for file_name in dir_list:
        print(file_name)
        if file_name.endswith(".7z"):
            print(file_name)
            if bldinstallercommon.is_linux_platform():
                cmd_args = [SCP_COMMAND,WORK_DIR + os.sep + 'module_archives' + os.sep + file_name,SERVER + ':' + LATEST_DIR + '/' + BIN_TARGET_DIRS[TARGET_ENV]]
            elif bldinstallercommon.is_win_platform():
                cmd_args = [SCP_COMMAND_WIN,file_name,SERVER + ':' + LATEST_DIR + '/' + BIN_TARGET_DIRS[TARGET_ENV] + '/']
            else:
                cmd_args = ['rsync',WORK_DIR + os.sep + 'module_archives' + os.sep + file_name,SERVER + ':' + LATEST_DIR + '/' + BIN_TARGET_DIRS[TARGET_ENV]]
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR + os.sep + 'module_archives',True)

    # TODO: Missing_modules.txt upload

###############################
# handle_qt_creator_build
###############################
def handle_qt_creator_build():

    dir_path = PATH + LICENSE_DIRS[LICENSE] + '/qtcreator/latest'

    if bldinstallercommon.is_linux_platform():
        if LICENSE == 'opensource':
            cmd_args=['python','./bld_qtcreator.py','--clean','--qt5path','../../qt5_install_dir','--qt5_essentials7z',SRC_URL+BIN_TARGET_DIRS[TARGET_ENV]+'/qt5_essentials.7z','--qt5_addons7z',SRC_URL+BIN_TARGET_DIRS[TARGET_ENV]+'/qt5_addons.7z','--icu7z',ICU_LIBS,'--versiondescription','""']
        else:
            cmd_args=['python','./bld_qtcreator.py','--clean','--qt5path','../../qt5_install_dir','--qt5_essentials7z',SRC_URL+BIN_TARGET_DIRS[TARGET_ENV]+'/qt5_essentials.7z','--qt5_addons7z',SRC_URL+BIN_TARGET_DIRS[TARGET_ENV]+'/qt5_addons.7z','--icu7z',ICU_LIBS,'--versiondescription','""','--additional_plugin',WORK_DIR + '/qmlprofiler','--additional_plugin',WORK_DIR + '/qtquickdesigner']
        bldinstallercommon.do_execute_sub_process(cmd_args,SCRIPT_ROOT_DIR,True)
    elif bldinstallercommon.is_mac_platform():
        if LICENSE == 'opensource':
            cmd_args=['python','-u','./bld_qtcreator.py','--clean','--installcommand','make -j1','--qt5path','../../qt5_install_dir','--qt5_essentials7z',SRC_URL+BIN_TARGET_DIRS[TARGET_ENV]+'/qt5_essentials.7z','--qt5_addons7z',SRC_URL+BIN_TARGET_DIRS[TARGET_ENV]+'/qt5_addons.7z','--installerbase7z','http://it-dl241-hki/packages/jenkins/opensource/ifw/1.4/installer-framework-build-mac-x64.7z','--versiondescription','""','--keychain_unlock_script','/Users/qt/unlock-keychain.sh']
        else:
            cmd_args=['python','-u','./bld_qtcreator.py','--clean','--installcommand','make -j1','--qt5path','../../qt5_install_dir','--qt5_essentials7z',SRC_URL+BIN_TARGET_DIRS[TARGET_ENV]+'/qt5_essentials.7z','--qt5_addons7z',SRC_URL+BIN_TARGET_DIRS[TARGET_ENV]+'/qt5_addons.7z','--installerbase7z','http://it-dl241-hki/packages/jenkins/opensource/ifw/1.4/installer-framework-build-mac-x64.7z','--versiondescription','""','--additional_plugin',WORK_DIR + '/qmlprofiler','--additional_plugin',WORK_DIR + '/qtquickdesigner','--keychain_unlock_script','/Users/qt/unlock-keychain.sh']
        bldinstallercommon.do_execute_sub_process(cmd_args,SCRIPT_ROOT_DIR,True)
        cmd_args = ['security','lock-keychain','Developer_ID_Digia.keychain']
        bldinstallercommon.do_execute_sub_process(cmd_args,SCRIPT_ROOT_DIR,True)
    else:
        if LICENSE == 'opensource':
            cmd_args=['python','-u','bld_qtcreator.py','--clean','--buildcommand','C:\Utils\jom\jom.exe','--installcommand','c:\Program Files\Microsoft Visual Studio 10.0\VC\\bin\\nmake.exe','--qt5path','..\..\qt5_install_dir','--qt5_essentials7z',SRC_URL+BIN_TARGET_DIRS[TARGET_ENV]+'/qt5_essentials.7z','--qt5_addons7z',SRC_URL+BIN_TARGET_DIRS[TARGET_ENV]+'/qt5_addons.7z','--icu7z',ICU_LIBS,'--sevenzippath','C:\Utils\\sevenzip','--gitpath','C:\Program Files\Git\\bin','--d3dcompiler7z','http://download.qt-project.org/development_releases/prebuilt/d3dcompiler/msvc2010/D3DCompiler_43-x86.dll.7z','--environment_batch','"C:\Program Files\Microsoft Visual Studio 10.0\VC\\vcvarsall.bat"','--environment_batch_argument','x86','--versiondescription','""']
        else:
            cmd_args=['python','-u','bld_qtcreator.py','--clean','--buildcommand','C:\Utils\jom\jom.exe','--installcommand','c:\Program Files\Microsoft Visual Studio 10.0\VC\\bin\\nmake.exe','--qt5path','..\..\qt5_install_dir','--qt5_essentials7z',SRC_URL+BIN_TARGET_DIRS[TARGET_ENV]+'/qt5_essentials.7z','--qt5_addons7z',SRC_URL+BIN_TARGET_DIRS[TARGET_ENV]+'/qt5_addons.7z','--icu7z',ICU_LIBS,'--sevenzippath','C:\\Utils\\sevenzip','--gitpath','C:\Program Files\Git\\bin','--d3dcompiler7z','http://download.qt-project.org/development_releases/prebuilt/d3dcompiler/msvc2010/D3DCompiler_43-x86.dll.7z','--versiondescription','""','--additional_plugin',WORK_DIR + '/qmlprofiler','--additional_plugin',WORK_DIR + '/qtquickdesigner','--environment_batch','"C:\Program Files\Microsoft Visual Studio 10.0\VC\\vcvarsall.bat"','--environment_batch_argument','x86']
        bldinstallercommon.do_execute_sub_process(cmd_args,SCRIPT_ROOT_DIR,True)

    if bldinstallercommon.is_linux_platform():
        if TARGET_ENV.find('64') != -1:
            cmd_args = [SCP_COMMAND,'qt-creator_build/qtcreator.7z',SERVER + ':' + dir_path + '/qtcreator_linux_gcc_64_ubuntu1110.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR,True)
        else:
            cmd_args = [SCP_COMMAND,'qt-creator_build/qtcreator.7z',SERVER + ':' + dir_path + '/qtcreator_linux_gcc_32_ubuntu1110.7z']
            bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR,True)
    elif bldinstallercommon.is_mac_platform():
        cmd_args = [SCP_COMMAND,'qt-creator_build/qtcreator.7z',SERVER + ':' + dir_path + '/qtcreator_mac_cocoa_10_7.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR,True)
    else:
        cmd_args = [SCP_COMMAND_WIN,'qt-creator_build/qtcreator.7z',SERVER + ':' + dir_path + '/qtcreator_windows_vs2010_32.7z']
        bldinstallercommon.do_execute_sub_process(cmd_args,WORK_DIR,True)

    #TODO: Check qt-creator checkout!


###############################
# handle_offline_installer_build
###############################
def handle_offline_installer_build():

    conf_file_base_path = WORK_DIR + os.sep + 'qtsdk' + os.sep + 'release-tools' + os.sep + 'releases'
    conf_file = conf_file_base_path + os.sep + os.environ['RELEASE_BUILD_CONF_FILE']
    license = LICENSE
    branch = 'release' # TODO
    platform = PLATFORM
    if TARGET_ENV.find('64') != -1:
        arch = 'x64'
    else:
        arch = 'x86'
    packages_base_url = SERVER # os.environ['PKG_SERVER_URL'] 'http://it-dl241-hki/packages/jenkins'

    # create all offline installers for this host
    release_build_handler.handle_offline_installer_build(conf_file, license, branch, platform, arch, packages_base_url)
    # copy all offline installers from /qtsdk/release-tools/installer_output/
    # into network disk

    # Crete remote directories
    dest_dir = PATH + '/sdk_qt5_offline_' + LICENSE_DIRS[LICENSE] + '/' + QT_VERSION + '-offline'
    create_remote_dirs('QT@qt-rnd.it.local', dest_dir)

    installer_name = ''
    installer_name_base = ''
    dir_list = os.listdir(WORK_DIR + os.sep + 'qtsdk' + os.sep + 'release-tools' + os.sep + 'installer_output')
    if bldinstallercommon.is_linux_platform():
        for file_name in dir_list:
            if file_name.endswith(".run"):
                installer_name = file_name
                installer_name_base = os.path.splitext(file_name)[0]
                cmd_args = ['rsync', installer_name, 'QT@qt-rnd.it.local:' + dest_dir + '/' + installer_name_base + '_' + TIME_STAMP + '.run']
                bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR + os.sep + 'installer_output', True)
    elif bldinstallercommon.is_mac_platform():
        for file_name in dir_list:
            if file_name.endswith(".dmg"):
                installer_name = file_name
                installer_name_base = os.path.splitext(file_name)[0]
                cmd_args = ['/Users/qt/unlock-keychain.py']
                bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR + os.sep + 'installer_output', True)
                s_arg = 'Developer ID Application: Digia Plc'
                cmd_args = ['codesign', '-r', '/Users/qt/csreq.txt', '-s', s_arg, installer_name_base + '.app']
                bldinstallercommon.do_execute_sub_process(cmd_args,  SCRIPT_ROOT_DIR + os.sep + 'installer_output', True)
                cmd_args = ['security','lock-keychain','Developer_ID_Digia.keychain']
                bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR + os.sep + 'installer_output', True)
                cmd_args = ['hdiutil', 'create', '-srcfolder', WORK_DIR + '/qtsdk/release-tools/installer_output/' + installer_name_base + '.app', '-volname', installer_name_base, '-format', 'UDBZ', WORK_DIR + '/qtsdk/release-tools/installer_output/'  + installer_name_base + '.dmg', '-ov', '-scrub']
                bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR + os.sep + 'installer_output', True)
                cmd_args = ['rsync', installer_name, 'QT@qt-rnd.it.local:' + dest_dir + '/' + installer_name_base + '_' + TIME_STAMP + '.dmg']
                bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR + os.sep + 'installer_output', True)
    else:
        for file_name in dir_list:
            if file_name.endswith(".exe"):
                installer_name = file_name
                installer_name_base = os.path.splitext(file_name)[0]
                if LICENSE == 'opensource':
                    cmd_args = ['C:\Utils\sign\signtool.exe', 'sign /v /du' + os.environ[SIGNING_SERVER], '/p' + os.environ[SIGNING_PASSWORD], '/t http://timestamp.verisign.com/scripts/timestamp.dll', '/f "C:\utils\sign\keys.pfx"' + installer_name]
                else:
                    cmd_args = ['C:\Utils\sign\signtool.exe', 'sign /v /du' + os.environ[SIGNING_SERVER], '/p' + os.environ[SIGNING_PASSWORD], '/t http://timestamp.verisign.com/scripts/timestamp.dll', '/f "C:\utils\sign\keys.pfx"' + installer_name]
                bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR + os.sep + 'installer_output', True)
                cmd_args = [SCP_COMMAND_WIN, installer_name, 'QT@qt-rnd.it.local:' + dest_dir + '/' + installer_name_base + '_' + TIME_STAMP + '.exe']
                bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR + os.sep + 'installer_output', True)


#def handle_online_installer_build(license, ....):

#def handle_online_repository_build(license, ....):

###############################
# copy_license_checkers
###############################
def copy_license_checkers():
    exec_path = WORK_DIR + os.sep + 'qt5' + os.sep + 'qtbase' + os.sep + 'bin'
    cmd_args = [SCP_COMMAND,SERVER + ':' + LATEST_DIR +os.sep +'src' +os.sep +'licheck' + os.sep + 'licheck.exe','.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = [SCP_COMMAND,SERVER + ':' + LATEST_DIR +os.sep +'src' +os.sep +'licheck' + os.sep + 'licheck32','.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = [SCP_COMMAND,SERVER + ':' + LATEST_DIR +os.sep +'src' +os.sep +'licheck' + os.sep + 'licheck64','.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = [SCP_COMMAND,SERVER + ':' + LATEST_DIR +os.sep +'src' +os.sep +'licheck' + os.sep + 'licheck_mac','.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    #change permissions
    os.chdir(WORK_DIR + os.sep + 'qt5' + os.sep + 'qtbase' + os.sep + 'bin')
    os.system('chmod u+x licheck32')
    os.system('chmod u+x licheck64')
    os.system('chmod u+x licheck_mac')

    cmd_args = ['git','add','.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = ['git','commit','-m','"Add license checkers into commercial source package"']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    exec_path = WORK_DIR + os.sep + 'qt5'
    cmd_args = ['git','add','.']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)
    cmd_args = ['git','commit','-m','"Add license checkers into commercial source package"']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True)

    os.chdir(SCRIPT_ROOT_DIR)

###############################
# create_remote_dirs
###############################
def create_remote_dirs(server, dir_path):
    if bldinstallercommon.is_win_platform():
        cmd_args = [SSH_COMMAND_WIN, '-t', '-t', server, 'mkdir -p' ,dir_path]
    else:
        cmd_args = [SSH_COMMAND, '-t', '-t', server, 'mkdir -p' ,dir_path]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)

###############################
# parse_cmd_line
###############################
def parse_cmd_line():
    global COMMAND
    global LICENSE
    global QT_VERSION
    global TIME_STAMP
    global BUILD_NUMBER
    global SERVER
    global PATH
    global TARGET_ENV
    global ICU_LIBS
    global SRC_URL
    global REMOTE_DIR
    global LATEST_DIR
    global PLATFORM
    global QT_VERSION_TAG
    global QT_FULL_VERSION

    setup_option_parser()

    arg_count = len(sys.argv)
    if arg_count < 2:
        OPTION_PARSER.print_help()
        sys.exit(-1)

    (options, args) = OPTION_PARSER.parse_args()

    COMMAND                 = options.command
    if options.command == 'init' or options.command == 'build_src' or options.command == 'build_bin' or options.command == 'offline_installer' or options.command == 'ifw' or options.command == 'build_creator':
        if arg_count < 15:
            OPTION_PARSER.print_help()
            sys.exit(-1)
        else:
            COMMAND         = options.command
            LICENSE         = options.license
            QT_VERSION      = options.qt_version
            TIME_STAMP      = options.time_stamp
            BUILD_NUMBER    = options.build_number
            SERVER          = options.server
            PATH            = options.path
            TARGET_ENV      = options.target_env
            ICU_LIBS        = options.icu_libs
            SRC_URL         = options.src_url
            QT_VERSION_TAG  = options.version_tag
            QT_FULL_VERSION = QT_VERSION
            if QT_VERSION_TAG:
                QT_FULL_VERSION += '-' + QT_VERSION_TAG
            REMOTE_DIR      = PATH + '/' + LICENSE_DIRS[LICENSE] + '/' + 'qt' + '/' + QT_VERSION + '/' + TIME_STAMP + '-' + BUILD_NUMBER
            LATEST_DIR      = PATH + '/' + LICENSE_DIRS[LICENSE] + '/' + 'qt' + '/' + QT_VERSION + '/' + 'latest'
    else:
        OPTION_PARSER.print_help()
        sys.exit(-1)
    if bldinstallercommon.is_linux_platform():
        PLATFORM = 'linux'
    elif bldinstallercommon.is_mac_platform():
        PLATFORM = 'mac'
    else:
        PLATFORM = 'windows'

    return True

##############################################################
# Setup Option Parser
##############################################################
def setup_option_parser():
    global OPTION_PARSER
    OPTION_PARSER = OptionParser(option_class=MultipleOption)

    OPTION_PARSER.add_option("-c", "--command",
                      action="store", type="string", dest="command", default="",
                      help="command to be executed: e.g. -c init")
    OPTION_PARSER.add_option("-l", "--license",
                      action="store", type="string", dest="license", default="",
                      help="license type: commercial or opensource")
    OPTION_PARSER.add_option("-v", "--qt_version",
                      action="store", type="string", dest="qt_version", default="",
                      help="Qt version e.g. 5.0.2")
    OPTION_PARSER.add_option("-t", "--time_stamp",
                      action="store", type="string", dest="time_stamp", default="",
                      help="Jenkins build time stamp")
    OPTION_PARSER.add_option("-b", "--build_number",
                      action="store", type="string", dest="build_number", default="",
                      help="Jenkins build number")
    OPTION_PARSER.add_option("-s", "--server",
                      action="store", type="string", dest="server", default="",
                      help="Upload server e.g. <user>@<host>")
    OPTION_PARSER.add_option("-p", "--path",
                      action="store", type="string", dest="path", default="",
                      help="Path on server")
    OPTION_PARSER.add_option("-e", "--target_env",
                      action="store", type="string", dest="target_env", default="",
                      help="Target environment: Linux, Linux_64, mac, win")
    OPTION_PARSER.add_option("-i", "--icu_libs",
                      action="store", type="string", dest="icu_libs", default="",
                      help="Url for pre-compiled icu libraries")
    OPTION_PARSER.add_option("-u", "--src_url",
                      action="store", type="string", dest="src_url", default="",
                      help="Url for source code")
    OPTION_PARSER.add_option("--version-tag",
                      action="store", type="string", dest="version_tag", default="",
                      help="Version tag e.g. alpha, beta, rc1")


###############################
# Main
###############################
def main():
    bldinstallercommon.init_common_module(SCRIPT_ROOT_DIR)

    parse_cmd_line()
    if COMMAND == 'init':
        init_qt_build_cycle()
    elif COMMAND == 'build_src':
        if LICENSE == 'opensource':
            init_qt_build_cycle()
        handle_qt_src_package_build()
    elif COMMAND == 'build_bin':
        handle_qt_release_build()
    elif COMMAND == 'offline_installer':
        handle_offline_installer_build()
    elif COMMAND == 'ifw':
        handle_ifw_build()
    elif COMMAND == 'build_creator':
        handle_qt_creator_build()
    else:
        print('Unsupported command')

if __name__ == "__main__":
    main()

