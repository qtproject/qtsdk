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
import argparse
from time import gmtime, strftime
import bldinstallercommon

TIMESTAMP           = strftime('%Y-%m-%d-%H-%M', gmtime())
ROOT_DIR            = os.path.dirname(os.path.realpath(__file__))
REPOGEN_TOOL        = 'repogen'
REPOGEN_TOOLS_DIR   = os.path.join(ROOT_DIR, 'repogen_tools')

UPDATE_NEW_COMPONENTS_ONLY = False  # default to update all (given) components


###############################
# Setup argument parser
###############################
def setup_argument_parser():
    parser = argparse.ArgumentParser(prog=os.path.basename(sys.argv[0]),
                                     add_help=True, description="Update online repository",
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('--repogen_tools', help="Where to fetch repogen tools (.7z, .zip, .tar.gz)", required=True, default="")
    parser.add_argument('--target_repo', help="Repository to be updated", required=True, default="")
    parser.add_argument('--source_repo', help="New repository source. Used only if target repository does not exits i.e. first time usage", required=False, default="")
    parser.add_argument('--source_pkg', help="pkg folder containing updates", required=True, default="")
    parser.add_argument('--source_config_xml', help="Path to config.xml file", required=False, default="")
    parser.add_argument('--components_to_update', help="Comma separated list of component to update", required=False, default="")
    parser.add_argument('--backup_base_dir', help="Backup directory, if given a backup will be taken from the repo when making updates", required=False, default="")
    parser.add_argument('--update_new_components_only', help="Update component(s) only if version number increase", required=False, action='store_true', default=False)
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
            print('Found existing repogen tool: {0}'.format(REPOGEN_TOOL))
            return
        else:
            # remove the bogus directory
            bldinstallercommon.remove_tree(REPOGEN_TOOLS_DIR)

    # create dirs
    bldinstallercommon.create_dirs(REPOGEN_TOOLS_DIR)
    # fetch
    print('Fetch repogen tools')
    if bldinstallercommon.is_content_url_valid(tools_uri):
        package_save_as_temp = os.path.normpath(os.path.join(ROOT_DIR, os.path.basename(tools_uri)))
        bldinstallercommon.retrieve_url(tools_uri, package_save_as_temp)
        bldinstallercommon.extract_file(package_save_as_temp, REPOGEN_TOOLS_DIR)
        print('Trying to locate repogen tool: {0}'.format(REPOGEN_TOOL + executable_suffix))
        tool = bldinstallercommon.locate_executable(REPOGEN_TOOLS_DIR, REPOGEN_TOOL + executable_suffix)
        if not os.path.isfile(tool):
            raise IOError('Unable to locate repogen tool [%s] under directory: %s' % (REPOGEN_TOOL + executable_suffix, REPOGEN_TOOLS_DIR))
        else:
            REPOGEN_TOOL = tool
    else:
        raise IOError('Invalid url: %s' % tools_uri)

    # found the tool
    print('Using repogen tool: {0}'.format(REPOGEN_TOOL))


###############################
# Function
###############################
def update_repository(source_pkg, target_repo, components_to_update):
    print('Updating repository')
    print('  Target repository: {0}'.format(target_repo))
    print('  Source pkg:        {0}'.format(source_pkg))
    print('  Components:        {0}'.format(components_to_update))
    print()
    if not len(components_to_update):
        raise RuntimeError('*** You asked me to update nothing?')
    if not os.path.exists(source_pkg):
        raise IOError('*** Source pkg does not exist: %s' % source_pkg)
    if not os.path.exists(target_repo):
        raise IOError('*** Target repository does not exist: %s' % target_repo)
    # do we update new components only or all given components no matter
    # what the version numbers are
    repogen_update_cmd = '--update'
    if UPDATE_NEW_COMPONENTS_ONLY:
        repogen_update_cmd = '--update-new-components'
    cmd_args = [REPOGEN_TOOL, repogen_update_cmd, '-p', source_pkg]
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
    source_pkg_path = os.path.join(source_pkg, 'online_repository')
    for name in os.listdir(source_pkg_path):
        temp = os.path.join(source_pkg_path, name)
        if os.path.isdir(temp):
            source_packages.append(name)
    for item in component_list:
        orig_item = item
        if item == '*':
            break
        if '*' in item:
            left, dummy = item.split('*')
            item = left.rstrip('.')
        if item not in source_packages:
            print('*** Sanity check fail!')
            print('*** Can not update component: [{0}] as it does not exist under: {1}'.format(orig_item, source_pkg_path))
            raise RuntimeError()


###############################
# Function
###############################
def expand_wildcard(selection, component_list):
    expanded_list = []
    left, dummy = selection.split('*')
    component = left.rstrip('.')
    for dummy, item in enumerate(component_list):
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
            print('{0} {1} {2}'.format(counter, marker, item))
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
        print('  {0}'.format(item))
    print()
    var = raw_input("Is the above selection correct? y/n ")
    if var not in ['y', 'Y']:
        print('*** Aborting...')
        raise RuntimeError()

    # return the components to be updated
    return component_list


###############################
# Function
###############################
def backup_repo(backup_base_dir, directory_to_be_backed_up):
    backup_full_path = os.path.join(backup_base_dir, TIMESTAMP)
    # create dirs
    bldinstallercommon.create_dirs(backup_full_path)
    # backup
    bldinstallercommon.copy_tree(directory_to_be_backed_up, backup_full_path)
    print('Created backup of repository:')
    print('Source:      {0}'.format(directory_to_be_backed_up))
    print('Destination: {0}'.format(backup_full_path))


###############################
# Function
###############################
def parse_components_from_argument(caller_arguments):
    global UPDATE_NEW_COMPONENTS_ONLY
    if caller_arguments.update_new_components_only:
        UPDATE_NEW_COMPONENTS_ONLY = True

    components_to_update_list = caller_arguments.components_to_update
    components_to_update_list = components_to_update_list.replace(" ", "")
    split_components = caller_arguments.components_to_update.split(',')
    return_list = []
    # parse all possible components in source repo
    full_component_listing = []
    source_pkg_path = os.path.join(caller_arguments.source_pkg, 'pkg')
    for name in os.listdir(source_pkg_path):
        temp = os.path.join(source_pkg_path, name)
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
    PARSER = setup_argument_parser()
    # parse args
    CALLER_ARGUMENTS = PARSER.parse_args()
    # check if first time usage!
    # 1) target repository directory must be empty i.e. we initialize things for the first time
    # 2) copy the source repository as target repository 1:1 and nothing else
    if CALLER_ARGUMENTS.source_repo:
        source_repo = os.path.join(CALLER_ARGUMENTS.source_repo, 'online_repository')
        if not os.path.isdir(source_repo) or not os.path.isfile(os.path.join(source_repo, 'Updates.xml')):
            print('*** The given source directory does not seem to be proper repository? Abort!')
            print('Given source repository: {0}'.format(source_repo))
            raise RuntimeError()
        if os.path.isfile(os.path.join(CALLER_ARGUMENTS.target_repo, 'Updates.xml')):
            print('The given destination directory already contains a repository.')
            print('We just update the existing repository:')
            print('Given target repository: {0}'.format(CALLER_ARGUMENTS.target_repo))
        else:
            print('Initializing the repository for the first time!')
            # create dirs
            bldinstallercommon.create_dirs(CALLER_ARGUMENTS.target_repo)
            # copy repository
            bldinstallercommon.copy_tree(source_repo, CALLER_ARGUMENTS.target_repo)
            # everything done now!
            print('Repository initialized:')
            print('Source:      {0}'.format(source_repo))
            print('Destination: {0}'.format(CALLER_ARGUMENTS.target_repo))
            sys.exit()
    # fetch tools
    fetch_repogen_tools(CALLER_ARGUMENTS.repogen_tools)
    # components to update
    COMPONENTS_TO_UPDATE = []
    if not CALLER_ARGUMENTS.components_to_update or CALLER_ARGUMENTS.components_to_update == '':
        # ask user which components to update
        COMPONENTS_TO_UPDATE = ask_for_components(CALLER_ARGUMENTS.source_pkg)
    else:
        COMPONENTS_TO_UPDATE = parse_components_from_argument(CALLER_ARGUMENTS)
    # sanity check
    source_pkg_path = os.path.join(CALLER_ARGUMENTS.source_pkg, 'pkg')
    sanity_check(COMPONENTS_TO_UPDATE, CALLER_ARGUMENTS.source_pkg)
    # backup current repo
    if CALLER_ARGUMENTS.backup_base_dir:
        backup_repo(CALLER_ARGUMENTS.backup_base_dir, CALLER_ARGUMENTS.target_repo)
    # update repo
    update_repository(source_pkg_path, CALLER_ARGUMENTS.target_repo, COMPONENTS_TO_UPDATE)
    print('\nRepository updated successfully!')

















