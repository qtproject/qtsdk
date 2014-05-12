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

# import the print function which is used in python 3.x
from __future__ import print_function
import sys
import os
import argparse
import difflib
import binascii
import shutil
import bldinstallercommon

QT_SDK_REPOSITORY_NAME = 'qtsdkrepository'

###############################
# Helper class
###############################
class SwapOperation:
    def __init__(self):
        self.componen_name   = ''
        self.source_dir      = ''
        self.destination_dir = ''


###############################
# Helper class
###############################
def generate_random_string():
    return binascii.b2a_hex(os.urandom(15))


###############################
# function
###############################
def parse_cmd_line_args():
    parser = argparse.ArgumentParser(prog = os.path.basename(sys.argv[0]),
        add_help=True, description="Swap online repositories", formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--component', help="What directory (repository) to swap", required=True)
    parser.add_argument('--source', help="Source base directory", required=True)
    parser.add_argument('--destination', help="Destination base directory", required=True)
    return parser.parse_args()


###############################
# function
###############################
def get_directory_list(base_dir, search_match):
    matches = []
    for root, dirs, files in os.walk(base_dir):
        for basename in dirs:
            if basename == search_match:
                fulldirname = os.path.join(root, basename)
                matches.append(fulldirname)
    return matches


###############################
# function
###############################
def determine_dest_dir(item, destination_base_dir):
    start_index = item.index(QT_SDK_REPOSITORY_NAME)
    remainder = item[start_index:]
    dest_start_index = destination_base_dir.index(QT_SDK_REPOSITORY_NAME)
    dest_path_start = destination_base_dir[:dest_start_index]
    return dest_path_start + remainder


###############################
# function
###############################
def is_platform_match(source_item, dest_item):
    temp_index = source_item.index(QT_SDK_REPOSITORY_NAME)
    temp_index += len(QT_SDK_REPOSITORY_NAME) + 1
    chopped_source_item = source_item[temp_index:]
    delimeter_index = chopped_source_item.index(os.path.sep)
    platform = chopped_source_item[:delimeter_index]
    if platform in dest_item:
        return True
    return False


###############################
# function
###############################
def generate_match_list(source_match_list, dest_match_list, component_name, destination_base_dir):
    match_list = []
    for item in source_match_list:
        matches = difflib.get_close_matches(item, dest_match_list)
        dest_dir = ''
        if not matches or \
           not os.path.isdir(matches[0]) or \
           not matches[0].endswith(component_name) or \
           not is_platform_match(item, matches[0]):
            print('*** No match found? Is this the first time the repo is being copied?')
            dest_dir = determine_dest_dir(item, destination_base_dir)
        else:
            dest_dir = matches[0]
        swap_operation = SwapOperation()
        swap_operation.componen_name = component_name
        swap_operation.source_dir = item
        swap_operation.destination_dir = dest_dir
        match_list.append(swap_operation)
    return match_list


###############################
# function
###############################
def swap_repository(parser_args):
    if not parser_args:
        print('*** No options available to swap online reposities')
        sys.exit(1)

    source_match_list = get_directory_list(parser_args.source, parser_args.component)
    if not source_match_list:
        print('*** Nothing to update? Did not find any component named: {0}'.format(parser_args.component))
        sys.exit(1)
    dest_match_list = get_directory_list(parser_args.destination, parser_args.component)

    match_list = generate_match_list(source_match_list, dest_match_list, parser_args.component, parser_args.destination)
    for swap_option in match_list:
        print()
        print('###################################################')
        print('Replacing: {0}'.format(swap_option.destination_dir))
        print('With:      {0}'.format(swap_option.source_dir))
        print()
        print('y: Yes')
        print('n: No (abort)')
        print()
        keep_asking = True
        while (keep_asking):
            var = raw_input("Proceed? ")
            if var in ['n', 'N']:
                keep_asking = False
                break
            if var in ['y', 'Y']:
                keep_asking = False
                print()
                # if the repo exists, take backup
                if os.path.exists(swap_option.destination_dir):
                    backup_dir = swap_option.destination_dir + '_old_' + generate_random_string()
                    bldinstallercommon.create_dirs(backup_dir)
                    bldinstallercommon.copy_tree(swap_option.destination_dir, backup_dir)
                    print('Backup taken into: {0}'.format(backup_dir))
                    shutil.rmtree(swap_option.destination_dir)
                bldinstallercommon.create_dirs(swap_option.destination_dir)
                bldinstallercommon.copy_tree(swap_option.source_dir, swap_option.destination_dir)
                print('Repository updated: {0}'.format(swap_option.destination_dir))


###############################
# function
###############################
if __name__ == "__main__":
    parser_args = parse_cmd_line_args()
    swap_repository(parser_args)


