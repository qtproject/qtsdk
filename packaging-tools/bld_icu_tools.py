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
import os
import sys
import multiprocessing
import shutil
import platform
import fileinput
from optparse import OptionParser, Option
import bldinstallercommon
from pkg_constants import ICU_BUILD_OUTPUT_DIR
from pkg_constants import ICU_INSTALL_DIR_NAME

SCRIPT_ROOT_DIR            = os.path.dirname(os.path.realpath(__file__))
ICU_SRC_DIR_NAME           = 'icu-src'
QT5_FILES_TO_PATCH_LIST    = ['*.prl', '*.pri', '*.pc', '*.la']
DEFAULT_ICU_SRC_PKG        = 'http://download.qt-project.org/development_releases/prebuilt/icu/src/icu4c-53_1-src.tgz'


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

class ICUConfiguration:
    def __init__(self):
        self.environment             = {}
        self.icu_include_path        = ''
        self.icu_lib_path            = ''
        self.qt_configure_extra_args = ''


###############################
# handle_icu_build
###############################
def build_icu_linux(environment, icu_src_base_dir, archive_icu):
    bldinstallercommon.create_dirs(os.path.join(SCRIPT_ROOT_DIR, ICU_INSTALL_DIR_NAME))
    exec_path = icu_src_base_dir
    # configure
    environment['LFLAGS'] = '-Wl,-rpath,\$ORIGIN'
    cmd_args = ['./runConfigureICU', 'Linux', '--enable-rpath', '--prefix=' + os.path.join(SCRIPT_ROOT_DIR, ICU_INSTALL_DIR_NAME)]
    exec_path = os.path.dirname(bldinstallercommon.locate_file(os.path.join(SCRIPT_ROOT_DIR, ICU_SRC_DIR_NAME), 'configure'))
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True, environment)
    # build
    cmd_args = ['make', '-j' + str(multiprocessing.cpu_count() + 1)]
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True, environment)
    cmd_args = ['make', 'install']
    bldinstallercommon.do_execute_sub_process(cmd_args, exec_path, True, environment)
    # patch RPath
    exec_path = os.path.join(SCRIPT_ROOT_DIR, ICU_INSTALL_DIR_NAME, 'lib')
    files = bldinstallercommon.make_files_list(exec_path, '.so$')
    for item in files:
        cmd_args = 'chrpath -r $ORIGIN ' + item
        bldinstallercommon.do_execute_sub_process(cmd_args.split(' '), exec_path, True, environment)
    icu_configuration = ICUConfiguration
    search_path = os.path.join(SCRIPT_ROOT_DIR, ICU_INSTALL_DIR_NAME)
    icu_configuration.icu_include_path = bldinstallercommon.locate_directory(search_path, 'include')
    icu_configuration.icu_lib_path = bldinstallercommon.locate_directory(search_path, 'lib')
    # archvive icu build artifacts if requested
    if archive_icu:
        archive_build_artifacts(search_path)
    return icu_configuration


###############################
# Archive ICU build artifacts
###############################
def archive_build_artifacts(base_path):
    # archive naming
    archive_name_base = 'icu'
    if os.environ.get('cfg'):
        archive_name_base += '-' + os.environ.get('cfg')
    elif os.environ.get('TARGET_ENV'):
        archive_name_base += '-' + os.environ.get('TARGET_ENV')
    # build artifacts output dir
    output_dir = os.path.join(SCRIPT_ROOT_DIR, ICU_BUILD_OUTPUT_DIR)
    if os.path.exists(output_dir):
        bldinstallercommon.remove_tree(output_dir)
    bldinstallercommon.create_dirs(output_dir)
    # devel package
    archive_name = archive_name_base + '-devel.7z'
    if os.path.isfile(archive_name):
        os.remove(archive_name)
    cmd_args = ['7z', 'a', archive_name, '*']
    bldinstallercommon.do_execute_sub_process(cmd_args, base_path, True)
    shutil.move(os.path.join(base_path, archive_name), output_dir)
    # lib package
    archive_name = archive_name_base + '.7z'
    if os.path.isfile(archive_name):
        os.remove(archive_name)
    lib_path = bldinstallercommon.locate_directory(base_path, 'lib')
    clean_icu_lib(lib_path)
    cmd_args = ['7z', 'a', archive_name, '*']
    bldinstallercommon.do_execute_sub_process(cmd_args, lib_path, True)
    shutil.move(os.path.join(lib_path, archive_name), output_dir)


###############################
# Archive ICU build artifacts
###############################
def clean_icu_lib(lib_path):
    plat = platform.system().lower()
    if plat.startswith('linux'):
        libs_to_save = ['libicudata', 'libicui18n', 'libicuuc']
        file_list = os.listdir(lib_path)
        for item in file_list:
            item_path = os.path.join(lib_path, item)
            if os.path.isdir(item_path):
                bldinstallercommon.remove_tree(item_path)
            elif (item.count('.') > 1) and any(item[:item.index('.')] in s for s in libs_to_save):
                continue
            else:
                os.remove(item_path)
    elif plat.startswith('win'):
        libs_to_save = ['icudt', 'icuin', 'icuuc']
        file_list = os.listdir(lib_path)
        for item in file_list:
            item_path = os.path.join(lib_path, item)
            if os.path.isdir(item_path):
                bldinstallercommon.remove_tree(item_path)
            elif any(item[:item.index('.')] in s for s in libs_to_save) and item.endswith('.dll'):
                continue
            else:
                os.remove(item_path)
    else:
        print('*** Platform not supported: {0}'.format(plat))
        sys.exit(-1)


###############################
# Add ICU to environment
###############################
def get_icu_env(icu_lib_path, icu_include_path):
    if not os.path.isdir(icu_lib_path) or not os.path.isdir(icu_include_path):
        return
    icu_environment = dict()
    if bldinstallercommon.is_linux_platform():
        icu_environment['LD_LIBRARY_PATH'] = icu_lib_path
        icu_environment['LIBRARY_PATH'] = icu_lib_path
        icu_environment['CPLUS_INCLUDE_PATH'] = icu_include_path
    elif bldinstallercommon.is_mac_platform():
        print('*** ICU build for Mac not implemented yet!')
    elif bldinstallercommon.is_win_platform():
        print('*** ICU build for Win not implemented yet!')
    else:
        print('*** Unsupported platform')

    return icu_environment


###############################
# function
###############################
def patch_icu_paths(search_path):
    extension_list = ['*.prl', '*.pri', '*.pc', '*.la']
    search_string = ICU_INSTALL_DIR_NAME
    file_list = bldinstallercommon.search_for_files(search_path, extension_list, search_string)

    for item in file_list:
        print('Erasing \'{0}\' paths from file: {1}'.format(search_string, item))
        for line in fileinput.FileInput(item, inplace = 1):
            if not search_string in line:
                print(line.rstrip('\n'))
                continue
            if is_quoted_line(line):
                patched_line = patch_quoted_line(line, search_string)
            else:
                patched_line = patch_line(line, search_string)

            print(patched_line.rstrip('\n'))


###############################
# function
###############################
def is_quoted_line(line):
    if line.rstrip(' \t\n\r').endswith(('\'', '\"')):
        index = line.index('=')
        if index:
            tmp = line[index + 1:].lstrip(' \t\n\r')
            return tmp.startswith(('-L\"', '\'-L'))
    return False


###############################
# function
###############################
def patch_line(line, search_string):
    line_items = line.split(' ')
    line_items[:] = [x for x in line_items if not (search_string in x)]
    return ' '.join(line_items)


###############################
# function
###############################
def patch_quoted_line(line, search_string):
    index_character = line.rstrip(' \t\n\r')[-1:]
    string_begin_index = line.index(index_character)
    string_end_index = line.rindex(index_character)
    string_to_patch = line[string_begin_index + 1:string_end_index]
    patched_substring = patch_line(string_to_patch, search_string)
    if not patched_substring.strip(' \t\n\r'):
        patched_line = line[:line.index('=') + 1]
    else:
        patched_line = line[:string_begin_index + 1] + patched_substring + line[string_end_index:]
    return patched_line


##############################################################
# Cleanup
##############################################################
def cleanup_icu():
    bldinstallercommon.remove_tree(os.path.join(SCRIPT_ROOT_DIR, ICU_SRC_DIR_NAME))
    bldinstallercommon.remove_tree(os.path.join(SCRIPT_ROOT_DIR, ICU_INSTALL_DIR_NAME))


##############################################################
# Execute task(s)
##############################################################
def init_build_icu(icu_src, icu_version = '', environment = dict(os.environ), archive_icu = False):
    # clean up first
    cleanup_icu()
    icu_src_dir = os.path.join(SCRIPT_ROOT_DIR, ICU_SRC_DIR_NAME)
    # what to do
    if not icu_src:
        print('*** Error! You asked to build the ICU but did not tell from where to find the sources?')
        sys.exit(-1)
    if icu_src.endswith('git'):
        if not icu_version:
            print('*** Error! You asked to clone ICU sources from git repository but did not tell from which branch/tag/sha?')
            sys.exit(-1)
        bldinstallercommon.clone_repository(icu_src, icu_version, icu_src_dir)
    else:
        if not bldinstallercommon.is_content_url_valid(icu_src):
            print('*** Error! The given URL for ICU sources is not valid: {0}'.format(icu_src))
            sys.exit(-1)
        package_save_as_temp = os.path.join(SCRIPT_ROOT_DIR, os.path.basename(icu_src))
        bldinstallercommon.create_dirs(icu_src_dir)
        print('Downloading ICU src package: ' + icu_src)
        bldinstallercommon.retrieve_url(icu_src, package_save_as_temp)
        bldinstallercommon.extract_file(package_save_as_temp, icu_src_dir)
    # now build the icu
    icu_configuration = None
    if bldinstallercommon.is_linux_platform():
        icu_configuration = build_icu_linux(environment, os.path.join(SCRIPT_ROOT_DIR, icu_src_dir), archive_icu)
    elif bldinstallercommon.is_mac_platform():
        print('*** ICU build for Mac not implemented yet!')
    elif bldinstallercommon.is_win_platform():
        print('*** ICU build for Win not implemented yet!')
    else:
        print('*** Unsupported platform')
    # set options for Qt5 build
    extra_qt_configure_args = ' -L' + icu_configuration.icu_lib_path
    extra_qt_configure_args += ' -I' + icu_configuration.icu_include_path
    icu_configuration.qt_configure_extra_args = extra_qt_configure_args
    icu_configuration.environment = get_icu_env(icu_configuration.icu_lib_path, icu_configuration.icu_include_path)
    return icu_configuration


##############################################################
# Setup Option Parser
##############################################################
def setup_option_parser():
    parser = OptionParser(option_class=MultipleOption)
    parser.add_option("--build-icu",
                      action="store_true", dest="build_icu", default=False,
                      help="Build ICU. Give ICU source separately.")
    parser.add_option("--icu-src",
                      action="store",  type="string", dest="icu_src",
                      default=DEFAULT_ICU_SRC_PKG,
                      help="URL for ICU git repository or URL for ICU src package.")
    parser.add_option("--icu-version",
                      action="store",  type="string", dest="icu_version", default="",
                      help="E.g. git branch or tag.")
    return parser


###############################
# parse_cmd_line
###############################
def parse_cmd_line():
    parser = setup_option_parser()
    arg_count = len(sys.argv)
    if arg_count < 2:
        parser.print_help()
        sys.exit(-1)

    (options, args) = parser.parse_args()
    return options


###############################
# Main
###############################
def main():
    bldinstallercommon.init_common_module(SCRIPT_ROOT_DIR)
    options = parse_cmd_line()
    if options.build_icu:
        init_build_icu(options.icu_src, options.icu_version, True)
    else:
        print('You asked me to do nothing?')

if __name__ == "__main__":
    main()

