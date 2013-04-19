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
import sys
import os
import platform
import argparse
import shutil
from time import gmtime, strftime
import bldinstallercommon

TIMESTAMP           = strftime('%Y-%m-%d-%H-%M', gmtime())
ROOT_DIR            = os.path.dirname(os.path.realpath(__file__))
REPOGEN_TOOL        = 'repogen'
REPOGEN_TOOLS_DIR   = ROOT_DIR + os.sep + 'repogen_tools'



###############################
# Setup argument parser
###############################
def setup_argument_parser():
    parser = argparse.ArgumentParser(prog = os.path.basename(sys.argv[0]),
              add_help=True, description="Update online repository",
               formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--repogen_tools', help="Where to fetch repogen tools (.7z, .zip, .tar.gz)", required=True, default="")
    parser.add_argument('--target_repo', help="Repository to be updated", required=True, default="")
    parser.add_argument('--source_repo', help="New repository source. Used only if target repository does not exits i.e. first time usage", required=False, default="")
    parser.add_argument('--source_pkg', help="pkg folder containing updates", required=True, default="")
    parser.add_argument('--source_config_xml', help="Path to config.xml file", required=True, default="")
    parser.add_argument('--components_to_update', help="Comma separated list of component to update", required=False, default="")
    parser.add_argument('--backup_base_dir', help="Backup directory, if given a backup will be taken from the repo when making updates", required=False, default="")
    return parser


###############################
# Function
###############################
def fetch_repogen_tools(tools_uri):
    global REPOGEN_TOOL
    executable_suffix = bldinstallercommon.get_executable_suffix()
    # first check if we have existing copy of the tool
    if os.path.exists(REPOGEN_TOOLS_DIR):
        tool = bldinstallercommon.locate_executable(REPOGEN_TOOLS_DIR, REPOGEN_TOOL + executable_suffix)
        if os.path.isfile(tool):
            REPOGEN_TOOL = tool
            print('Found existing repogen tool: {}'.format(REPOGEN_TOOL))
            return
        else:
            # remove the bogus directory
            bldinstallercommon.remove_tree(REPOGEN_TOOLS_DIR)

    # create dirs
    bldinstallercommon.create_dirs(REPOGEN_TOOLS_DIR)
    # fetch
    print('Fetch repogen tools')
    if bldinstallercommon.is_content_url_valid(tools_uri):
        package_save_as_temp = os.path.normpath(ROOT_DIR + os.sep + os.path.basename(tools_uri))
        bldinstallercommon.retrieve_url(tools_uri, package_save_as_temp)
        bldinstallercommon.extract_file(package_save_as_temp, REPOGEN_TOOLS_DIR)
        print('Trying to locate repogen tool: {}'.format(REPOGEN_TOOL + executable_suffix))
        tool = bldinstallercommon.locate_executable(REPOGEN_TOOLS_DIR, REPOGEN_TOOL + executable_suffix)
        if not os.path.isfile(tool):
            print('Unable to locate repogen tool [{}] under directory: {}'.format(REPOGEN_TOOL + executable_suffix, REPOGEN_TOOLS_DIR))
            print('*** Abort!')
            sys.exit(-1)
        else:
            REPOGEN_TOOL = tool
    else:
        print('Invalid url: {}'.format(tools_uri))
        print('*** Abort!')
        sys.exit(-1)

    # found the tool
    print('Using repogen tool: {}'.format(REPOGEN_TOOL))


###############################
# Function
###############################
def update_repository(source_pkg, target_repo, config_xml_file, components_to_update):
    print('Updating repository')
    print('  Target repository: {}'.format(target_repo))
    print('  Source pkg:        {}'.format(source_pkg))
    print('  Source config xml: {}'.format(config_xml_file))
    print('  Components:        {}'.format(components_to_update))
    print()
    if not len(components_to_update):
        print('*** You asked me to update nothing?')
        sys.exit(-1)
    if not os.path.exists(source_pkg):
        print('*** Source pkg does not exist: {}'.format(source_pkg))
        sys.exit(-1)
    if not os.path.exists(target_repo):
        print('*** Target repository does not exist: {}'.format(target_repo))
        sys.exit(-1)
    cmd_args = [REPOGEN_TOOL, '--update', '-p', source_pkg, '-c', config_xml_file]
    if components_to_update[0] and components_to_update[0] == '*':
        cmd_args += [target_repo]
    else:
        cmd_args += ['--include', ','.join(components_to_update), target_repo]
    bldinstallercommon.do_execute_sub_process(cmd_args, source_pkg, True)


###############################
# Function
###############################
def is_number(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


###############################
# Function
###############################
def sanity_check(component_list, source_pkg):
    source_packages = []
    for name in os.listdir(source_pkg):
        temp = os.path.join(source_pkg, name)
        if os.path.isdir(temp):
            source_packages.append(name)
    for item in component_list:
        orig_item = item
        if item == '*':
            break
        if '*' in item:
            left, right = item.split('*')
            item = left.rstrip('.')
        if item not in source_packages:
            print('*** Sanity check fail!')
            print('*** Can not update component: [{}] as it does not exist under: {}'.format(orig_item, source_pkg))
            sys.exit(-1)


###############################
# Function
###############################
def expand_wildcard(selection, component_list):
    expanded_list = []
    left, right = selection.split('*')
    component = left.rstrip('.')
    for counter, item in enumerate(component_list):
        # e.g. if 'qt.502.*' found in 'qt.502.gcc'
        if component in item:
            expanded_list.append(item)
    return expanded_list


###############################
# Function
###############################
def ask_for_components(source_pkg):
    components = []
    for name in os.listdir(source_pkg):
        temp = os.path.join(source_pkg, name)
        if os.path.isdir(temp):
            components.append(name)

    component_list = []
    selected_items = []
    var = ''
    count = len(components)
    while True:
        print()
        print('Which component you wish to update? Provide comma separated list:')
        for counter, item in enumerate(components):
            marker = '-'
            if counter in selected_items:
                marker = '+'
            print('{} {} {}'.format(counter, marker, item))
        print()
        print('a: Select all')
        print('c: Continue')
        print()
        var = raw_input("Enter item number: ")
        if var in ['c', 'C']:
            break
        if var in ['a', 'A']:
            for counter, item in enumerate(components):
                selected_items.append(counter)
                component_list.append(item)
            break
        if is_number(var) and int(var) not in selected_items and (0 <= int(var) < count):
            selected_items.append(int(var))
            component_list.append(components[int(var)])
        if '*' in var:
            expanded_components = expand_wildcard(var, components)
            component_list += expanded_components
            break
    print()
    print('You are about to update the following components:')
    print()
    for item in component_list:
        print('  {}'.format(item))
    print()
    var = raw_input("Is the above selection correct? y/n ")
    if var not in ['y', 'Y']:
        print('*** Aborting...')
        sys.exit(-1)

    # return the components to be updated
    return component_list


###############################
# Function
###############################
def backup_repo(backup_base_dir, directory_to_be_backed_up):
    backup_full_path = backup_base_dir + os.sep + TIMESTAMP
    # create dirs
    bldinstallercommon.create_dirs(backup_full_path)
    # backup
    bldinstallercommon.copy_tree(directory_to_be_backed_up, backup_full_path)
    print('Created backup of repository:')
    print('Source:      {}'.format(directory_to_be_backed_up))
    print('Destination: {}'.format(backup_full_path))


###############################
# Function
###############################
def parse_components_from_argument(caller_arguments):
    components_to_update_list = caller_arguments.components_to_update
    components_to_update_list = components_to_update_list.replace(" ", "")
    split_components = caller_arguments.components_to_update.split(',')
    return_list = []
    # parse all possible components in source repo
    full_component_listing = []
    for name in os.listdir(caller_arguments.source_pkg):
        temp = os.path.join(caller_arguments.source_pkg, name)
        if os.path.isdir(temp):
            full_component_listing.append(name)
    # figure out all components that should be updated
    for item in split_components:
        if '*' in item:
            expanded_items = expand_wildcard(item, full_component_listing)
            return_list += expanded_items
        else:
            return_list.append(item)
    # return list should contain all single items and items with wild mark
    return return_list


###############################
# Main
###############################
if __name__ == "__main__":
    # init things
    bldinstallercommon.init_common_module(ROOT_DIR)
    parser = setup_argument_parser()
    # parse args
    caller_arguments = parser.parse_args()
    # check if first time usage!
    # 1) target repository directory must be empty i.e. we initialize things for the first time
    # 2) copy the source repository as target repository 1:1 and nothing else
    if caller_arguments.source_repo:
        if not os.path.isdir(caller_arguments.source_repo) or not os.path.isfile(caller_arguments.source_repo + os.sep + 'Updates.xml'):
            print('*** The given source directory does not seem to be proper repository? Abort!')
            print('Given source repository: {}'.format(caller_arguments.source_repo))
            sys.exit(-1)
        if os.path.isfile(caller_arguments.target_repo + os.sep + 'Updates.xml'):
            print('The given destination directory already contains a repository.')
            print('We just update the existing repository:')
            print('Given target repository: {}'.format(caller_arguments.target_repo))
        else:
            print('Initializing the repository for the first time!')
            # create dirs
            bldinstallercommon.create_dirs(caller_arguments.target_repo)
            # copy repository
            bldinstallercommon.copy_tree(caller_arguments.source_repo, caller_arguments.target_repo)
            # everything done now!
            print('Repository initialized:')
            print('Source:      {}'.format(caller_arguments.source_repo))
            print('Destination: {}'.format(caller_arguments.target_repo))
            sys.exit()
    # fetch tools
    fetch_repogen_tools(caller_arguments.repogen_tools)
    # components to update
    components_to_update = []
    if not caller_arguments.components_to_update or caller_arguments.components_to_update == '':
        # ask user which components to update
        components_to_update = ask_for_components(caller_arguments.source_pkg)
    else:
        components_to_update = parse_components_from_argument(caller_arguments)
    # sanity check
    sanity_check(components_to_update, caller_arguments.source_pkg)
    # backup current repo
    if caller_arguments.backup_base_dir:
        backup_repo(caller_arguments.backup_base_dir, caller_arguments.target_repo)
    # update repo
    update_repository(caller_arguments.source_pkg, caller_arguments.target_repo, caller_arguments.source_config_xml, components_to_update)
    print('\nRepository updated successfully!')

















