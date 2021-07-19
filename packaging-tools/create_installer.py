#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2021 The Qt Company Ltd.
## Contact: https://www.qt.io/licensing/
##
## This file is part of the release tools of the Qt Toolkit.
##
## $QT_BEGIN_LICENSE:GPL-EXCEPT$
## Commercial License Usage
## Licensees holding valid commercial Qt licenses may use this file in
## accordance with the commercial license agreement provided with the
## Software or, alternatively, in accordance with the terms contained in
## a written agreement between you and The Qt Company. For licensing terms
## and conditions see https://www.qt.io/terms-conditions. For further
## information use the contact form at https://www.qt.io/contact-us.
##
## GNU General Public License Usage
## Alternatively, this file may be used under the terms of the GNU
## General Public License version 3 as published by the Free Software
## Foundation with exceptions as appearing in the file LICENSE.GPL3-EXCEPT
## included in the packaging of this file. Please review the following
## information to ensure the GNU General Public License requirements will
## be met: https://www.gnu.org/licenses/gpl-3.0.html.
##
## $QT_END_LICENSE$
##
#############################################################################

"""Scripts to generate SDK installer based on open source InstallerFramework"""

import configparser
import os
import shutil
import sys
import re
import subprocess
from time import gmtime, strftime
import argparse
import multiprocessing # to get the cpu core count
import platform
if platform.system().lower().startswith('win'):
    import win32api

from threadedwork import ThreadedWork
import bld_utils
import bldinstallercommon
import pkg_constants
from archiveresolver import ArchiveLocationResolver
from sdkcomponent import SdkComponent
from patch_qt import patchFiles, patchQtEdition
import logging

log = logging.getLogger("create_installer")
log.setLevel("INFO")

# ----------------------------------------------------------------------
TARGET_INSTALL_DIR_NAME_TAG         = '%TARGET_INSTALL_DIR%'
ARCHIVES_EXTRACT_DIR_NAME_TAG       = '%ARCHIVES_EXTRACT_DIR%'
PACKAGE_DEFAULT_TAG                 = '%PACKAGE_DEFAULT_TAG%'
UPDATE_REPOSITORY_URL_TAG           = '%UPDATE_REPOSITORY_URL%'
PACKAGE_CREATION_DATE_TAG           = '%PACKAGE_CREATION_DATE%'
INSTALL_PRIORITY_TAG                = '%INSTALL_PRIORITY%'
SORTING_PRIORITY_TAG                = '%SORTING_PRIORITY%'
VERSION_NUMBER_AUTO_INCREASE_TAG    = '%VERSION_NUMBER_AUTO_INCREASE%'
COMPONENT_SHA1_TAG                  = '%COMPONENT_SHA1%'


class CreateInstallerError(Exception):
    pass

##############################################################
# Check that valid tools are present in the build environment
##############################################################
def check_required_tools():
    """Check that valid tools are present in the build environment."""
    from distutils.spawn import find_executable
    if not find_executable('7z'):
        raise EnvironmentError("7z tool not found in the PATH")


##############################################################
# Cleanup
##############################################################
def clean_work_dirs(task):
    """Clean working directories."""
    log.info("Cleaning environment")

    # delete "/packages"
    if os.path.exists(task.packages_full_path_dst):
        bldinstallercommon.remove_tree(task.packages_full_path_dst)
        log.debug("Deleted directory: {0}".format(task.packages_full_path_dst))
    # delete "/repositories"
    if os.path.exists(task.repo_output_dir):
        bldinstallercommon.remove_tree(task.repo_output_dir)
        log.debug("Deleted directory: {0}".format(task.repo_output_dir))
    # delete "/config"
    if os.path.exists(task.config_dir_dst):
        bldinstallercommon.remove_tree(task.config_dir_dst)
        log.debug("Deleted directory: {0}".format(task.config_dir_dst))


##############################################################
# Set the config directory
##############################################################
def set_config_directory(task):
    """Copy config directory into correct place."""
    log.info("Set config directory")
    # ConfigDirLgpl is optional field so it can be ignored
    include_filter = ''
    try:
        include_filter = task.config.get('ConfigDirLgpl', 'include_filter')
    except Exception:
        pass
    if include_filter and include_filter in task.license_type:
        config_dir_template = task.config.get('ConfigDirLgpl', 'template_name')
    else:
        config_dir_template = task.config.get('ConfigDir', 'template_name')

    config_dir_template = os.path.normpath(task.configurations_dir + os.sep + config_dir_template)

    bldinstallercommon.create_dirs(task.config_dir_dst)
    bldinstallercommon.copy_tree(config_dir_template, task.config_dir_dst)
    log.info("Copied: '{0}' into: {1}".format(config_dir_template, task.config_dir_dst))


##############################################################
# Set the config.xml
##############################################################
def set_config_xml(task):
    """Copy config.xml template into correct place."""
    log.info("Set config.xml")

    configxml_filename = task.config.get('ConfigXml', 'template_name')
    config_template_source = task.configurations_dir + os.sep + task.platform_identifier + os.sep + configxml_filename
    # if no config.xml template, we assume the "config" template dir already contains it
    if not os.path.exists(config_template_source):
        raise CreateInstallerError("Given config.xml template does not exist: {0}".format(config_template_source))

    # name has to be config.xml for installer-framework
    config_template_dest_dir = task.config_dir_dst
    config_template_dest = config_template_dest_dir + os.sep + 'config.xml'

    if os.path.exists(config_template_dest):
        os.remove(config_template_dest)
        log.debug("Deleted old existing config.xml: {0}".format(config_template_dest))
    bldinstallercommon.create_dirs(config_template_dest_dir)
    shutil.copy(config_template_source, config_template_dest)
    log.info("Copied '{0}' into: '{1}'".format(config_template_source, config_template_dest))

    update_repository_url = bldinstallercommon.safe_config_key_fetch(task.config, 'SdkUpdateRepository', 'repository_url_release')

    fileslist = [config_template_dest]
    bldinstallercommon.replace_in_files(fileslist, UPDATE_REPOSITORY_URL_TAG, update_repository_url)
    # substitute values also from global substitution list
    for item in task.substitution_list:
        bldinstallercommon.replace_in_files(fileslist, item[0], item[1])
    return config_template_dest


##############################################################
# Substitute common version numbers etc., match against tags
##############################################################
def substitute_global_tags(task):
    """ Substitute common version numbers etc., match against tags """
    log.info("Substituting global tags:")
    log.info("%PACKAGE_CREATION_DATE% = {0}".format(task.build_timestamp))
    log.info("%VERSION_NUMBER_AUTO_INCREASE% = {0}".format(task.version_number_auto_increase_value))
    for item in task.substitution_list:
        log.info("{0} = {1}".format(item[0], item[1]))

    # initialize the file list
    fileslist = []
    for directory in task.directories_for_substitutions:
        for root, _, files in os.walk(directory):
            for name in files:
                path = os.path.join(root, name)
                fileslist.append(path)

    bldinstallercommon.replace_in_files(fileslist, PACKAGE_CREATION_DATE_TAG, task.build_timestamp)
    if task.force_version_number_increase:
        bldinstallercommon.replace_in_files(fileslist, VERSION_NUMBER_AUTO_INCREASE_TAG, task.version_number_auto_increase_value)
    for item in task.substitution_list:
        bldinstallercommon.replace_in_files(fileslist, item[0], item[1])


##############################################################
# Substitute component specifig tags
##############################################################
def substitute_component_tags(tag_pair_list, meta_dir_dest):
    """ Substitute component specific tags """
    if len(tag_pair_list) == 0:
        return
    log.info("Substituting component specific tags")
    # initialize the file list
    fileslist = []

    for root, _, files in os.walk(meta_dir_dest):
        for name in files:
            path = os.path.join(root, name)
            fileslist.append(path)

    for pair in tag_pair_list:
        tag = pair[0]
        value = pair[1]
        if tag and value:
            log.info("Matching '{0}' and '{1}' in files list".format(tag, value))
            bldinstallercommon.replace_in_files(fileslist, tag, value)
        else:
            log.warning("Ignoring incomplete tag pair: {0} = {1}".format(tag, value))

##############################################################
# Parse SDK components
##############################################################
def parse_component_data(task, configuration_file, configurations_base_path):
    """Parse SDK component data"""
    file_full_path = configuration_file
    if not os.path.isfile(file_full_path):
        file_full_path = bldinstallercommon.locate_file(configurations_base_path, configuration_file)
    if not file_full_path:
        # check the 'all-os' directory
        allos_conf_file_dir = os.path.normpath(task.configurations_dir + os.sep + 'all-os')
        file_full_path = bldinstallercommon.locate_file(allos_conf_file_dir, configuration_file)
    if not file_full_path:
        raise ValueError('*** Aborting, unable to locate the specified file. Check the configuration files for possible error(s).')
    log.info("Reading target configuration file: {0}".format(file_full_path))
    configuration = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
    configuration.readfp(open(file_full_path))

    # parse package ignore list first
    sdk_component_exclude_list = bldinstallercommon.safe_config_key_fetch(configuration, 'PackageIgnoreList', 'packages')
    if sdk_component_exclude_list:
        sdk_component_exclude_list = sdk_component_exclude_list.replace(' ', '')
        pkg_list = sdk_component_exclude_list.split(',')
        for item in pkg_list:
            task.sdk_component_ignore_list.append(item)
    # parse sdk components
    for section in configuration.sections():
        sectionNameSpace = section.split(".")[0]
        if sectionNameSpace in task.package_namespace:
            if section not in task.sdk_component_ignore_list:
                sdk_component = SdkComponent(section, configuration, task.packages_dir_name_list,
                                             task.archive_location_resolver, task.substitution_list, task.offline_installer)
                if task.dry_run:
                    sdk_component.setArchiveSkip(True)
                # validate component
                sdk_component.validate()
                if sdk_component.is_valid():
                    # if include filter defined for component it is included only if LICENSE_TYPE matches to include_filter
                    # same configuration file can contain components that are included only to either edition
                    if sdk_component.include_filter and sdk_component.include_filter in task.license_type:
                        task.sdk_component_list.append(sdk_component)
                    # components without include_filter definition are added by default
                    elif not sdk_component.include_filter:
                        task.sdk_component_list.append(sdk_component)
                else:
                    if task.offline_installer and sdk_component.optional_for_offline_installer():
                        log.warning("The [{0}] was not valid but it was marked optional for offline installers so skipping it.".format(sdk_component.package_name))
                    else:
                        if task.strict_mode:
                            log.info("{0}".format(sdk_component.error_msg()))
                            raise ValueError()
                        else:
                            log.warning("Ignored component in non-strict mode (missing archive data or metadata?): {0}".format(section))
                            task.sdk_component_list_skipped.append(sdk_component)
    # check for extra configuration files if defined
    extra_conf_list = bldinstallercommon.safe_config_key_fetch(configuration, 'PackageConfigurationFiles', 'file_list')
    if extra_conf_list:
        extra_conf_list = extra_conf_list.rstrip(',\n')
        file_list = extra_conf_list.split(',')
        for extra_conf_file in file_list:
            extra_conf_file = extra_conf_file.strip()
            # recursive call
            parse_component_data(task, extra_conf_file, configurations_base_path)


##############################################################
# Parse SDK components
##############################################################
def parse_components(task):
    """Parse SDK all components"""
    log.info("Parse target configuration files")
    conf_base_path = task.configurations_dir + os.sep + task.platform_identifier + os.sep
    main_conf_file = task.configuration_file
    parse_component_data(task, main_conf_file, conf_base_path)
    return

def create_metadata_map(sdk_component):
    """create lists for component specific tag substitutions"""
    component_metadata_tag_pair_list = []
    # version tag substitution if exists
    if sdk_component.version_tag or sdk_component.version:
        component_metadata_tag_pair_list.append([sdk_component.version_tag, sdk_component.version])
    # default package info substitution if exists
    if sdk_component.package_default:
        component_metadata_tag_pair_list.append([PACKAGE_DEFAULT_TAG, sdk_component.package_default])
    # install priority info substitution if exists
    if sdk_component.install_priority:
        component_metadata_tag_pair_list.append([INSTALL_PRIORITY_TAG, sdk_component.install_priority])
    # install priority info substitution if exists
    if sdk_component.sorting_priority:
        component_metadata_tag_pair_list.append([SORTING_PRIORITY_TAG, sdk_component.sorting_priority])
    # target install dir substitution
    if sdk_component.target_install_base:
        component_metadata_tag_pair_list.append([TARGET_INSTALL_DIR_NAME_TAG, sdk_component.target_install_base])
    # archives extract dir substitution
    if sdk_component.archives_extract_dir:
        component_metadata_tag_pair_list.append([ARCHIVES_EXTRACT_DIR_NAME_TAG, sdk_component.archives_extract_dir])
    # component sha1 substitution
    if sdk_component.component_sha1:
        component_metadata_tag_pair_list.append([COMPONENT_SHA1_TAG, sdk_component.component_sha1])

    return component_metadata_tag_pair_list

def get_component_sha1_file(sdk_component, sha1_file_dest):
    """download component sha1 file"""
    bld_utils.download(sdk_component.component_sha1_uri, sha1_file_dest)

    # read sha1 from the file
    with open(sha1_file_dest, "r") as sha1_file:
        sdk_component.component_sha1 = sha1_file.read().strip()

def get_component_data(task, sdk_component, archive, install_dir, data_dir_dest, compress_content_dir):
    """download and create data for a component"""
    package_raw_name = os.path.basename(archive.archive_uri)

    # if no data to be installed, then just continue
    if not package_raw_name:
        return
    if not archive.package_strip_dirs:
        archive.package_strip_dirs = '0'

    if package_raw_name.endswith('.7z') \
       and archive.package_strip_dirs == '0' \
       and not archive.package_finalize_items \
       and not archive.archive_action \
       and not archive.rpath_target \
       and sdk_component.target_install_base == '/' \
       and not archive.target_install_dir:
        log.info("No repackaging actions required for the package, just download it directly to data directory")
        downloadedArchive = os.path.normpath(data_dir_dest + os.sep + archive.archive_name)
        # start download
        bld_utils.download(archive.archive_uri, downloadedArchive)
        return

    downloadedArchive = os.path.normpath(install_dir + os.sep + package_raw_name)
    # start download
    bld_utils.download(archive.archive_uri, downloadedArchive)

    # repackage content so that correct dir structure will get into the package

    if not archive.extract_archive:
        archive.extract_archive = 'yes'

    # extract contents
    if archive.extract_archive == 'yes':
        extracted = bldinstallercommon.extract_file(downloadedArchive, install_dir)
        # remove old package
        if extracted:
            os.remove(downloadedArchive)
        else:
            # ok we could not extract the file, so propably not even archived file,
            # check the case if we downloaded a text file, must ensure proper file endings
            if bldinstallercommon.is_text_file(downloadedArchive):
                bldinstallercommon.ensure_text_file_endings(downloadedArchive)

        # perform custom action script for the extracted archive
        if archive.archive_action:
            script_file, script_args = archive.archive_action.split(",")
            script_args = script_args or ""
            script_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), script_file)
            if not os.path.exists(script_path):
                raise Exception("Unable to locate custom archive action script: " + script_path)
            subprocess.check_call([script_path, '--input-dir=' + install_dir, script_args.strip()])

        # strip out unnecessary folder structure based on the configuration
        count = 0
        iterations = int(archive.package_strip_dirs)
        while(count < iterations):
            count = count + 1
            bldinstallercommon.remove_one_tree_level(install_dir)
        # perform package finalization tasks for the given archive
        if 'delete_doc_directory' in archive.package_finalize_items:
            doc_dir = bldinstallercommon.locate_directory(install_dir, 'doc')
            if os.path.exists(doc_dir):
                log.info("Erasing doc: {0}".format(doc_dir))
                shutil.rmtree(doc_dir)
        if 'cleanup_doc_directory' in archive.package_finalize_items:
            cleanup_docs(install_dir)
        if 'qml_examples_only' in archive.package_finalize_items:
            examples_dir = bldinstallercommon.locate_directory(install_dir, 'examples')
            qml_examples_only(examples_dir)
        if 'patch_qt' in archive.package_finalize_items:
            patchFiles(install_dir, product='qt_framework')
        if 'set_executable' in archive.package_finalize_items:
            handle_set_executable(install_dir, archive.package_finalize_items)
        if 'set_licheck' in archive.package_finalize_items:
            handle_set_licheck(task, install_dir, archive.package_finalize_items)

    # remove debug information files when explicitly defined so
    if not task.remove_pdb_files or not task.remove_debug_information_files:
        # don't remove debug information files from debug information archives
        if not archive.archive_name.endswith('debug-symbols.7z'):
            # Check if debug information file types are defined
            if task.remove_pdb_files or task.remove_debug_information_files:
                # Remove debug information files according to host platform defaults
                remove_all_debug_information_files(install_dir)

    # remove debug libraries
    if task.remove_debug_libraries:
        remove_all_debug_libraries(install_dir)

    if archive.rpath_target:
        if not archive.rpath_target.startswith(os.sep):
            archive.rpath_target = os.sep + archive.rpath_target
        if bldinstallercommon.is_linux_platform() or bldinstallercommon.is_solaris_platform():
            bldinstallercommon.handle_component_rpath(install_dir, archive.rpath_target)

    if archive.component_sha1_file:
        # read sha1 from the file
        sha1_file_path = install_dir + os.sep + archive.component_sha1_file
        if os.path.exists(sha1_file_path):
            with open(sha1_file_path, "r") as sha1_file:
                sdk_component.component_sha1 = sha1_file.read().strip()
        else:
            raise ValueError('Component SHA1 file "{0}" not found'.format(archive.component_sha1_file))

    # lastly compress the component back to .7z archive
    content_list = os.listdir(compress_content_dir)
    #adding compress_content_dir in front of every item
    content_list = [(compress_content_dir + os.sep + x) for x in content_list]

    saveas = os.path.normpath(data_dir_dest + os.sep + archive.archive_name)
    cmd_args = [ task.archivegen_tool, saveas] + content_list
    bldinstallercommon.do_execute_sub_process(cmd_args, data_dir_dest)


def handle_set_executable(baseDir, packageFinalizeItems):
    for item in parsePackageFinalizeItems(packageFinalizeItems, 'set_executable'):
        expectedPath = os.path.join(baseDir, item)
        if not os.path.exists(expectedPath):
            raise ValueError('Can not set executable bit as path not found: "{0}"'.format(expectedPath))
        os.chmod(expectedPath, 0o755)
        log.info("Executable bit set for: {0}".format(expectedPath))


def handle_set_licheck(task, baseDir, packageFinalizeItems):
    for licheckFileName in parsePackageFinalizeItems(packageFinalizeItems, 'set_licheck'):
        licheckFilePath = os.path.join(baseDir, licheckFileName)
        if not os.path.exists(licheckFilePath):
            raise ValueError('Can not set licheck as path not found: "{0}"'.format(licheckFilePath))
        patchQtEdition(baseDir, licheckFileName, task.build_timestamp)
        log.info("Licheck set for: {0}".format(licheckFilePath))
        break


def parsePackageFinalizeItems(packageFinalizeItems, itemCategory):
    for item in packageFinalizeItems.split(","):
        if itemCategory not in item:
            continue
        parts = item.split("=")
        yield parts[-1].strip()


##############################################################
# Substitute pkg template directory names
##############################################################
def substitute_package_name(task, package_name):
    for item in task.substitution_list:
        package_name = package_name.replace(item[0], item[1])

    return package_name

##############################################################
# Remove debug information files
##############################################################
def remove_all_debug_information_files(install_dir):
    """Remove debug information files according to host machine."""
    if bldinstallercommon.is_win_platform():
        debug_information_file_ending = 'pdb'
    elif bldinstallercommon.is_linux_platform():
        debug_information_file_ending = 'debug'
    elif bldinstallercommon.is_mac_platform():
        debug_information_file_ending = 'dSYM'
    else:
        raise ValueError('Host is not identified as Windows, Linux or macOS')

    remove_debug_information_files_by_file_type(install_dir, debug_information_file_ending)


##############################################################
# Remove debug information files by file type
##############################################################
def remove_debug_information_files_by_file_type(install_dir, debug_information_file_ending):
    """Remove debug information files by file type"""
    for directory in ('bin', 'lib', 'qml', 'plugins'):
        debug_information_dir = bldinstallercommon.locate_directory(install_dir, directory)
        if os.path.exists(debug_information_dir):
            log.info("Removing debug information files from: {0}".format(debug_information_dir))
            if debug_information_file_ending == 'dSYM':
                # On macOS, debug symbols are in folder bundles instead of files. os.walk used by bldinstallercommon.py
                # helper functions doesn't directly support wildchars on path names so alternative approach for removing
                # dSYM folders is required compared to Linux and Windows debug information files.
                list_of_debug_information_files = []
                for root, dirs, files in os.walk(debug_information_dir): # pylint: disable=W0612
                    for d in dirs:
                        if d.endswith('dSYM'):
                            list_of_debug_information_files.append(os.path.join(root, d))
                for debug_information in list_of_debug_information_files:
                    bldinstallercommon.remove_tree(debug_information)
            else:
               # This will only take the text connected to the debug information file by grabbing all non-space characters (\S)
               bldinstallercommon.delete_files_by_type_recursive(debug_information_dir, '\S*\.' + debug_information_file_ending) # pylint: disable=W1401


##############################################################
# Remove debug libraries
##############################################################
def remove_all_debug_libraries(install_dir):
    """Remove debug libraries."""
    # at this point of packaging we don't necessarily have reliable source of library names
    # on Windows we trust debug library filenames to follow *d.dll | *d.lib industry standard naming convention
    # but we must consider that library filenames can end with letter 'd' in release build
    # and exclude those from removable items
    if bldinstallercommon.is_win_platform():
        for directory in ('bin', 'lib', 'qml', 'plugins'):
            windows_debug_library_dir = bldinstallercommon.locate_directory(install_dir, directory)
            log.info("Removing Windows debug libraries from: {0}".format(windows_debug_library_dir))
            # go through all library types and related qmake files
            debug_library_file_endings = ['dll', 'lib', 'prl']
            for debug_library_file_type in debug_library_file_endings:
                if os.path.exists(windows_debug_library_dir):
                    # make list of all debug library names
                    all_debug_files_list = bldinstallercommon.make_files_list(windows_debug_library_dir, '\S*d\.' + debug_library_file_type) # pylint: disable=W1401
                    # in case library name ends with 'd' we need to keep that and remove only library with double d at the end of file name
                    double_d_debug_files_list = bldinstallercommon.make_files_list(windows_debug_library_dir, '\S*dd\.' + debug_library_file_type) # pylint: disable=W1401
                    if double_d_debug_files_list:
                        # check intersection of all debug libraries and library names ending with letter 'd'
                        debug_files_list_intersection = set(all_debug_files_list).intersection(double_d_debug_files_list)
                        for debug_library_name in set(debug_files_list_intersection):
                            # remove one 'd' from library names ending letter 'd' also in release builds
                            # and exclude from removed libraries
                            altered_library_name = debug_library_name[:-5] + debug_library_name[-5+1:]
                            all_debug_files_list.remove(altered_library_name)
                            for item in all_debug_files_list:
                                if os.path.exists(item):
                                    os.remove(item)
                    else:
                        # there are no library names ending letter 'd' in this package
                        # we can remove all debug libraries with filenames ending *d.dll | *d.lib
                        if os.path.exists(windows_debug_library_dir):
                            bldinstallercommon.delete_files_by_type_recursive(windows_debug_library_dir, '\S*d\.' + debug_library_file_type) # pylint: disable=W1401
    # remove macOS debug libraries
    elif bldinstallercommon.is_mac_platform():
        for directory in ('bin', 'lib', 'qml', 'plugins'):
            macOS_debug_library_dir = bldinstallercommon.locate_directory(install_dir, directory)
            log.info("Removing macOS debug libraries from: {0}".format(macOS_debug_library_dir))
            debug_library_file_ending = '_debug\.*' # pylint: disable=W1401
            if os.path.exists(macOS_debug_library_dir):
                bldinstallercommon.delete_files_by_type_recursive(macOS_debug_library_dir, '\S*' + debug_library_file_ending) # pylint: disable=W1401
    else:
        log.info("Host was not Windows or macOS. For Linux and others we don\'t do anything at the moment")


##############################################################
# Create target components
##############################################################
def create_target_components(task):
    """Create target components."""
    bldinstallercommon.create_dirs(task.packages_full_path_dst)

    log.info("Creating SDK components")
    # download and extract lrelease binary for creating translation binaries
    if task.create_repository and os.environ.get("LRELEASE_TOOL"):
        if not os.path.isfile(os.path.join(task.script_root_dir, "lrelease")):
            bld_utils.download(os.environ.get("LRELEASE_TOOL"), task.script_root_dir)
            bldinstallercommon.extract_file(os.path.basename(os.environ.get("LRELEASE_TOOL")), task.script_root_dir)
    getComponentDataWork = ThreadedWork("get components data")
    for sdk_component in task.sdk_component_list:
        sdk_component.print_component_data()
        # substitute pkg_template dir names and package_name
        package_name = substitute_package_name(task, sdk_component.package_name)
        dest_base = task.packages_full_path_dst + os.sep + package_name + os.sep
        meta_dir_dest = os.path.normpath(dest_base + 'meta')
        data_dir_dest = os.path.normpath(dest_base + 'data')
        temp_data_dir = os.path.normpath(dest_base + 'tmp')
        # save path for later substitute_component_tags call
        sdk_component.meta_dir_dest = meta_dir_dest
        # create meta destination folder
        bldinstallercommon.create_dirs(meta_dir_dest)
        # Copy Meta data
        metadata_content_source_root = os.path.normpath(sdk_component.pkg_template_dir + os.sep + 'meta')
        bldinstallercommon.copy_tree(metadata_content_source_root, meta_dir_dest)
        if os.path.isfile(os.path.join(task.script_root_dir, "lrelease")):
            # create translation binaries, files are created if translation source files exist for component
            subprocess.check_call([os.path.join(task.script_root_dir, "update_component_translations.sh"), "-r", os.path.join(task.script_root_dir, "lrelease"), dest_base])
        # add files into tag substitution
        task.directories_for_substitutions.append(meta_dir_dest)
        # handle archives
        if sdk_component.downloadable_archive_list:
            # save path for later substitute_component_tags call
            sdk_component.temp_data_dir = temp_data_dir
            # Copy archives into temporary build directory if exists
            for archive in sdk_component.downloadable_archive_list:
                # fetch packages only if offline installer or repo creation, for online installer just handle the metadata
                if task.offline_installer or task.create_repository:
                    # Create needed data dirs
                    compress_content_dir = os.path.normpath(temp_data_dir + os.sep + archive.archive_name)
                    install_dir = os.path.normpath(compress_content_dir + archive.get_archive_installation_directory())

                    if task.incremental and os.path.exists(os.path.join(data_dir_dest, archive.archive_name)):
                        continue
                    # adding get_component_data task to our work queue
                    # Create needed data dirs before the threads start to work
                    bldinstallercommon.create_dirs(install_dir)
                    bldinstallercommon.create_dirs(data_dir_dest)
                    if platform.system().lower().startswith('win'):
                        install_dir = win32api.GetShortPathName(install_dir)
                        data_dir_dest = win32api.GetShortPathName(data_dir_dest)
                    getComponentDataWork.addTask("adding {0} to {1}".format(archive.archive_name, sdk_component.package_name),
                                                 get_component_data, task, sdk_component, archive, install_dir, data_dir_dest, compress_content_dir)
        # handle component sha1 uri
        if sdk_component.component_sha1_uri:
            sha1_file_dest = os.path.normpath(dest_base + 'SHA1')
            getComponentDataWork.addTask("getting component sha1 file for {0}".format(sdk_component.package_name),
                                         get_component_sha1_file, sdk_component, sha1_file_dest)

        # maybe there is some static data
        data_content_source_root = os.path.normpath(sdk_component.pkg_template_dir + os.sep + 'data')
        if os.path.exists(data_content_source_root):
            bldinstallercommon.create_dirs(data_dir_dest)
            bldinstallercommon.copy_tree(data_content_source_root, data_dir_dest)

    if not task.dry_run:
        # start the work threaded, more than 8 parallel downloads are not so useful
        getComponentDataWork.run(min([task.max_cpu_count, multiprocessing.cpu_count()]))

    for sdk_component in task.sdk_component_list:
        # substitute tags
        substitute_component_tags(create_metadata_map(sdk_component), sdk_component.meta_dir_dest)
        if hasattr(sdk_component, 'temp_data_dir') and os.path.exists(sdk_component.temp_data_dir):
            # lastly remove temp dir after all data is prepared
            if not bldinstallercommon.remove_tree(sdk_component.temp_data_dir):
                raise IOError('Unable to remove directory: %s' % sdk_component.temp_data_dir)
            # substitute downloadable archive names in installscript.qs
            substitute_component_tags(sdk_component.generate_downloadable_archive_list(), sdk_component.meta_dir_dest)


##############################################################
# Cleanup examples
##############################################################
def qml_examples_only(examples_dir):
    if not os.path.isdir(examples_dir):
        log.error("Given examples directory is not valid path: {0}".format(examples_dir))
        log.error("Archive not cleaned!")
        return
    subdir_list = []
    regex = re.compile('^qml\S.*') # pylint: disable=W1401
    for root, dirs, _ in os.walk(examples_dir):
        for basename in dirs:
            if regex.search(basename):
                root_dir = root
                break
        else:
            continue
        break

    # populate subdirectory list from under examples
    for name in os.listdir(root_dir):
        dir_name = os.path.join(root_dir, name)
        if os.path.isdir(dir_name):
            subdir_list.append(name)

    for submodule in subdir_list:
        # remove unwanted subdirectories
        if regex.search(submodule):
            log.info("QML example package: {0}".format(submodule))
        else:
            delete_dir = os.path.join(root_dir, submodule)
            log.info("Delete non qml examples directory: {0}".format(delete_dir))
            shutil.rmtree(delete_dir)


##############################################################
# Cleanup unnecessary documentation files
##############################################################
def cleanup_docs(install_dir):
    if not os.path.isdir(install_dir):
        log.error("Given docs directory is not valid path: {0}".format(install_dir))
        log.error("Archive not cleaned!")
        return
    submodule_list = []
    # populate subdirectory list from under /doc
    for name in os.listdir(install_dir):
        dir_name = os.path.join(install_dir, name)
        if os.path.isdir(dir_name) and "global" not in dir_name:
            submodule_list.append(dir_name)
    # iterate list
    dirs_to_delete = ['images', 'scripts', 'style', 'template', 'externalsites']
    for submodule in submodule_list:
        # remove unnecessary subdirectories first
        for item in [os.path.join(submodule, i) for i in dirs_to_delete]:
            if os.path.isdir(item):
                log.info("Cleaning up -> deleting directory: {0}".format(item))
                shutil.rmtree(item, ignore_errors=True)
        # then remove unnecessary files
        for filename in os.listdir(submodule):
            if filename.endswith(('.qdocconf', '.sha1', '.html')):
                full_filename = os.path.join(submodule, filename)
                if os.path.isfile(full_filename):
                    log.info("Cleaning up -> deleting file: {0}".format(item))
                    os.remove(full_filename)


##############################################################
# Create the final installer binary
##############################################################
def create_installer_binary(task):
    """Create installer binary files using binarycreator tool."""
    log.info("Create installer binary")

    # naming scheme: qt-<platform>-<license>-<version>-<tag>-<compiler>-<target_arch>-<offline/online>.<extension>
    #    license is opensource or commercial
    #    extension is exe, dmg, or run
    #    tag is alpha1, beta2, rc1, etc (no tag for final).
    #    platform is win, linux, mac, etc.
    platform        = task.config.get('PlatformIdentifier', 'identifier')
    installer_type  = 'offline' if task.offline_installer else 'online'
    extension       = '.run' if bldinstallercommon.is_linux_platform() else ''

    if not task.installer_name:
        task.installer_name = task.installer_name + '-' + platform + '-' + task.license_type
        task.installer_name = task.installer_name + '-' + installer_type
    else:
        task.installer_name = task.installer_name
    task.installer_name += extension

    # if online installer only
    if task.online_installer:
        # binarycreator arguments
        cmd_args = [task.binarycreator_tool, '-t', task.installerbase_tool, '-v', '-p', task.packages_full_path_dst]
        cmd_args = cmd_args + ['--online-only', '-c', task.config_dir_dst + os.sep + 'config.xml', task.installer_name]

    # if offline-only installer
    if task.offline_installer:
        cmd_args = [task.binarycreator_tool, '--offline-only']
        cmd_args = cmd_args + ['-t', task.installerbase_tool, '-v', '-p', task.packages_full_path_dst]
        # check if package exclude list should be used for offline installer
        if task.config.has_option('OfflinePackageExcludeList', 'package_list'):
            package_exclude_list = task.config.get('OfflinePackageExcludeList', 'package_list')
            package_exclude_list = package_exclude_list.replace('\n', '')
            if package_exclude_list:
                cmd_args = cmd_args + ['-e', package_exclude_list]
        cmd_args = cmd_args + ['-c', task.config_dir_dst + os.sep + 'config.xml', task.installer_name]

    # use license resource file if given
    license_resource_file = os.path.join(task.config_dir_dst, 'license.qrc')
    if os.path.isfile(license_resource_file):
        cmd_args = cmd_args + ['-r', license_resource_file]

    # create installer binary
    bldinstallercommon.do_execute_sub_process(cmd_args, task.script_root_dir)

    # move results to dedicated directory
    output_dir = os.path.join(task.script_root_dir, pkg_constants.INSTALLER_OUTPUT_DIR_NAME)
    bldinstallercommon.create_dirs(output_dir)
    file_name = os.path.join(task.script_root_dir, task.installer_name)
    old_existing_file_name = os.path.join(output_dir, task.installer_name)
    if bldinstallercommon.is_mac_platform():
        file_name = file_name + '.app'
        old_existing_file_name = old_existing_file_name + '.app'
    if bldinstallercommon.is_win_platform():
        file_name = file_name + '.exe'
        old_existing_file_name = old_existing_file_name + '.exe'
    # remove old if exists
    if os.path.isfile(old_existing_file_name):
        log.info("Deleting old existing file: {0}".format(old_existing_file_name))
        os.remove(old_existing_file_name)
    log.info("Moving '{0}' into '{1}'".format(file_name, output_dir))
    shutil.move(file_name, output_dir)


##############################################################
# Create the repository
##############################################################
def create_online_repository(task):
    """Create online repository using repogen tool."""
    log.info("Create online repository")

    # handle special case if MaintenanceTool repository build and
    # update.rcc update requeste
    if task.create_maintenance_tool_resource_file:
        create_maintenance_tool_resource_file(task, task.substitution_list)

    # repogen arguments
    if task.create_repository:
        log.info("Creating online repository:")
        log.info("Destination dir: {0}".format(task.repo_output_dir))
        log.info("Input data dir: {0}".format(task.packages_full_path_dst))
        repogen_args = [task.repogen_tool]
        if os.environ.get('IFW_UNITE_METADATA'):
            repogen_args += ['--unite-metadata']
        repogen_args += ['-p', task.packages_full_path_dst, task.repo_output_dir]
        # create repository
        bldinstallercommon.do_execute_sub_process(repogen_args, task.script_root_dir)
        if not os.path.exists(task.repo_output_dir):
            raise IOError('*** Fatal error! Unable to create repository directory: ' + task.repo_output_dir)


##############################################################
# Create MaintenanceTool resource file
##############################################################
def create_maintenance_tool_resource_file(task):
    """Create MaintenanceTool resource file."""
    log.info("Create MaintenanceTool resource file")
    set_config_directory(task)
    config_xml = set_config_xml(task)
    cmd_args = [task.binarycreator_tool, '--online-only', '-p', task.packages_full_path_dst, '-c', config_xml, '-rcc']
    bldinstallercommon.do_execute_sub_process(cmd_args, task.script_root_dir)
    # archive
    resource_file = os.path.join(task.script_root_dir, 'update.rcc')
    installer_base_archive = bldinstallercommon.locate_file(task.packages_full_path_dst, '*installer-framework*')
    if not os.path.isfile(installer_base_archive):
        log.error("Unable to locate installerbase archive from: {0}".format(task.packages_full_path_dst))
        log.error("The update.rcc will not be included in the MaintenanceTool repository!")
        return
    # inject the resource file to the same archive where installerbase is
    inject_update_rcc_to_archive(installer_base_archive, resource_file)


###############################
# function
###############################
def inject_update_rcc_to_archive(archive_file_path, file_to_be_injected):
    log.info("Injecting file [{0}] into [{1}]".format(file_to_be_injected, archive_file_path))
    if not os.path.isfile(file_to_be_injected):
        log.error("*** Unable to locate file: {0}".format(file_to_be_injected))
    if not os.path.isfile(archive_file_path):
        log.error('*** Unable to locate file: {0}'.format(archive_file_path))
    archive_file_name = os.path.basename(archive_file_path)
    # copy to tmp location
    tmp_dir = os.path.join(os.path.dirname(archive_file_path), '_tmp')
    bldinstallercommon.create_dirs(tmp_dir)
    shutil.copy(archive_file_path, tmp_dir)
    # extract
    copied_archive_file = os.path.join(tmp_dir, archive_file_name)
    bldinstallercommon.extract_file(copied_archive_file, tmp_dir)
    os.remove(copied_archive_file)
    # add file
    shutil.copy(file_to_be_injected, tmp_dir)
    # re-compress
    cmd_args_archive = ['7z', 'a', archive_file_name, '*']
    bldinstallercommon.do_execute_sub_process(cmd_args_archive, tmp_dir)
    # delete original
    os.remove(archive_file_path)
    # copy re-compressed package to correct location
    shutil.copy(os.path.join(tmp_dir, archive_file_name), os.path.dirname(archive_file_path))
    # delete tmp location
    bldinstallercommon.shutil.rmtree(tmp_dir)


##############################################################
# Create the final installer binary
##############################################################
def create_mac_disk_image(task):
    """Create Apple disk image."""
    log.info("Create Apple disk image")

    # create disk image
    cmd_args = ['hdiutil', 'create', '-srcfolder', \
                os.path.join(task.script_root_dir, pkg_constants.INSTALLER_OUTPUT_DIR_NAME, task.installer_name + '.app'), \
                '-volname', task.installer_name, \
                '-format', 'UDBZ', \
                os.path.join(task.script_root_dir, pkg_constants.INSTALLER_OUTPUT_DIR_NAME, task.installer_name + '.dmg'), \
                '-ov', '-scrub', '-size', '4g']
    bldinstallercommon.do_execute_sub_process(cmd_args, task.script_root_dir)


##############################################################
# All main build steps
##############################################################
def create_installer(task):
    """Installer creation main steps."""
    log.info("Creating Qt Installer Framework based installer/online repository")
    # init
    bldinstallercommon.init_common_module(task.script_root_dir)
    # check required tools
    check_required_tools()
    # clean env before starting
    if not task.incremental:
        clean_work_dirs(task)
    # set config templates
    if task.online_installer or task.offline_installer:
        set_config_directory(task)
        set_config_xml(task)
    # install Installer Framework tools
    task.install_ifw_tools()
    # parse SDK components
    parse_components(task)
    # create components
    create_target_components(task)
    # substitute global tags
    substitute_global_tags(task)
    # create the installer binary
    if task.online_installer or task.offline_installer:
        create_installer_binary(task)
        # for mac we need some extra work
        if bldinstallercommon.is_mac_platform():
            create_mac_disk_image(task)
    if task.create_repository:
        create_online_repository(task)


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')


class QtInstallerTask:

    def __init__(self, args):
        log.info("Parsing: {0}".format(args.configuration_file))
        self.config = configparser.ConfigParser(interpolation=configparser.ExtendedInterpolation())
        self.config.readfp(open(args.configuration_file))
        self.configurations_dir = args.configurations_dir
        self.configuration_file = args.configuration_file

        self.script_root_dir = os.path.dirname(os.path.realpath(__file__))
        self.ifw_tools_uri = args.ifw_tools_uri
        self.ifw_tools_dir = os.path.join(self.script_root_dir, "ifwt")
        self.archivegen_tool = None
        self.binarycreator_tool = None
        self.installerbase_tool = None
        self.repogen_tool = None
        self.config_dir_dst = os.path.join(self.script_root_dir, "config")
        self.packages_full_path_dst = os.path.join(self.script_root_dir, "pkg")

        self.repo_output_dir = os.path.join(self.script_root_dir, 'online_repository')

        self.package_namespace = self.config.get('PackageNamespace', 'name').replace(" ", "").split(",")
        self.platform_identifier = self.config.get('PlatformIdentifier', 'identifier')
        self.installer_name = args.preferred_installer_name
        self.packages_dir_name_list = self.parse_ifw_pkg_template_dirs(self.config.get('PackageTemplates', 'template_dirs'),
                                                                       args.configurations_dir)

        self.substitution_list = self.parse_substitutions(args)
        self.directories_for_substitutions = []
        self.sdk_component_list = []
        self.sdk_component_list_skipped = []
        self.sdk_component_ignore_list = []

        self.archive_location_resolver = ArchiveLocationResolver(self.config, args.archive_base_url, args.configurations_dir,
                                                                 self.substitution_list)

        self.remove_debug_information_files = args.remove_debug_information_files
        self.remove_debug_libraries = args.remove_debug_libraries
        self.remove_pdb_files = args.remove_pdb_files

        self.incremental = args.incremental
        self.offline_installer = args.offline_installer
        self.online_installer = args.online_installer
        self.create_repository = args.create_repository
        self.strict_mode = args.strict_mode
        self.dry_run = args.dry_run
        self.license_type = args.license_type
        self.build_timestamp = args.build_timestamp
        self.force_version_number_increase = args.force_version_number_increase
        self.version_number_auto_increase_value = args.version_number_auto_increase_value
        self.max_cpu_count = args.max_cpu_count
        self.create_maintenance_tool_resource_file = args.create_maintenance_tool_resource_file

    def verbose(self):
        log.info("Installer task:")
        log.info("  IFW tools: {0}".format(self.ifw_tools_uri))
        log.info("  Archivegen: {0}".format(self.archivegen_tool))
        log.info("  Binarycreator: {0}".format(self.binarycreator_tool))
        log.info("  Installerbase: {0}".format(self.installerbase_tool))
        log.info("  Repogen: {0}".format(self.repogen_tool))
        log.info("  Working config dir: {0}".format(self.config_dir_dst))
        log.info("  Working pkg dir: {0}".format(self.packages_full_path_dst))
        log.info("  Package namespace: {0}".format(self.package_namespace))
        log.info("  Platform identifier: {0}".format(self.platform_identifier))
        log.info("  Installer name: {0}".format(self.installer_name))
        log.info("  IFW pkg templates: {0}".format(self.packages_dir_name_list))
        log.info("  Substitutions: {0}".format(self.substitution_list))
        log.info("  Remove debug information files: {0}".format(self.remove_debug_information_files))
        log.info("  Remove debug libraries: {0}".format(self.remove_debug_libraries))
        log.info("  Remove pdb files: {0}".format(self.remove_pdb_files))
        log.info("  Online installer: {0}".format(self.online_installer))
        log.info("  Offline installer: {0}".format(self.offline_installer))
        log.info("  Create repository: {0}".format(self.create_repository))
        log.info("  License: {0}".format(self.license_type))
        log.info("  Build timestamp: {0}".format(self.build_timestamp))
        log.info("  Force version number increase: {0}".format(self.force_version_number_increase))
        log.info("  Version number autom increase value: {0}".format(self.version_number_auto_increase_value))
        log.info("  Mac cpu count: {0}".format(self.max_cpu_count))
        log.info("  Create MaintenanceTool resource file: {0}".format(self.create_maintenance_tool_resource_file))

    def parse_substitutions(self, args):
        substitution_list = []
        for item in args.substitution_list:
            key, value = item.split("=")
            if value:
                substitution_list.append([key, value])
            else:
                raise CreateInstallerError("Invalid substition string given: '{0}'".format(item))

        substitution_list.append(['%LICENSE%', args.license_type])
        return substitution_list

    def parse_ifw_pkg_template_dirs(self, template_list, configurations_dir):
        ret = []
        packages_list_raw = template_list.replace(' ', '')
        for package_template_dir in packages_list_raw.split(','):
            package_template_dir = os.path.normpath(package_template_dir)
            # if the packages directory name is absolute path, then the packages templates (or static packages)
            # can reside outside the "<script_root_dir>/configurations" folder
            # otherwise the packages templates must be under "/configurations"
            if os.path.isabs(package_template_dir):
                ret.append(package_template_dir)
            else:
                # first check if the pkg templates are under assumed "/configurations/pkg_templates" directory
                pkg_template_dir = os.path.join(configurations_dir, pkg_constants.PKG_TEMPLATE_BASE_DIR_NAME,
                                                package_template_dir)
                if os.path.exists(pkg_template_dir):
                    ret.append(pkg_template_dir)
                # if not then assume the old directory layout is being used
                else:
                    ret.append(os.path.join(configurations_dir, package_template_dir))
        return ret

    def install_ifw_tools(self):
        """Setup Installer-Framework tools."""
        log.info("Install Installer Framework tools")

        # check if the ifw tools is already extracted on disk to save time
        if not os.path.exists(self.ifw_tools_dir):
            self.download_and_extract_ifw_tools()

        try:
            self.set_ifw_tools()
        except Exception:
            # try to download and set from scratch if the ifw archive on disk was corrupted
            self.download_and_extract_ifw_tools()
            self.set_ifw_tools()

    ##############################################################
    # Install Installer-Framework tools
    ##############################################################
    def set_ifw_tools(self):
        executable_suffix = bldinstallercommon.get_executable_suffix()
        self.archivegen_tool = bldinstallercommon.locate_executable(self.ifw_tools_dir, 'archivegen' + executable_suffix)
        self.binarycreator_tool = bldinstallercommon.locate_executable(self.ifw_tools_dir, 'binarycreator' + executable_suffix)
        self.installerbase_tool = bldinstallercommon.locate_executable(self.ifw_tools_dir, 'installerbase' + executable_suffix)
        self.repogen_tool = bldinstallercommon.locate_executable(self.ifw_tools_dir, 'repogen' + executable_suffix)
        # check
        assert os.path.isfile(self.archivegen_tool), "Archivegen tool not found: {0}".format(self.archivegen_tool)
        assert os.path.isfile(self.binarycreator_tool), "Binary creator tool not found: {0}".format(self.binarycreator_tool)
        assert os.path.isfile(self.installerbase_tool), "Installerbase not found: {0}".format(self.installerbase_tool)
        assert os.path.isfile(self.repogen_tool), "Repogen tool not found: {0}".format(self.repogen_tool)
        log.info("Archive generator tool: ".format(self.archivegen_tool))
        log.info("Binary creator tool: ".format(self.binarycreator_tool))
        log.info("Repogen tool: ".format(self.repogen_tool))
        log.info("Installerbase: ".format(self.installerbase_tool))


    def download_and_extract_ifw_tools(self):
        package_save_as_temp = os.path.join(self.ifw_tools_dir, os.path.basename(self.ifw_tools_uri))
        package_save_as_temp = os.path.normpath(package_save_as_temp)
        # download ifw archive if not present on disk
        if not os.path.exists(package_save_as_temp):
            # create needed dirs
            bldinstallercommon.create_dirs(self.ifw_tools_dir)
            log.info("Downloading: {0}".format(self.ifw_tools_uri))
            if not bldinstallercommon.is_content_url_valid(self.ifw_tools_uri):
                raise Exception("Package URL is invalid: [" + self.ifw_tools_uri + "]")
            bldinstallercommon.retrieve_url(self.ifw_tools_uri, package_save_as_temp)
            if not (os.path.isfile(package_save_as_temp)):
                raise Exception("Downloading failed! Aborting!")
        # extract ifw archive
        bldinstallercommon.extract_file(package_save_as_temp, self.ifw_tools_dir)
        log.info("IFW tools extracted into: {0}".format(self.ifw_tools_dir))



if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Script to create Qt Installer Framework based installers.")
    parser.add_argument("-c", "--configurations-dir", dest="configurations_dir", type=str, default="configurations",
                        help="define configurations directory where to read installer configuration files")
    parser.add_argument("-f", "--configuration-file", dest="configuration_file", type=str,
                        help="define configuration file for installer content")
    parser.add_argument("-i", "--incremental", dest="incremental", action='store_true', default=False,
                        help="Enable incremental development mode")
    parser.add_argument("-o", "--offline", dest="offline_installer", action='store_true', default=False,
                        help="Create online installer")
    parser.add_argument("-O", "--online", dest="online_installer", action='store_true', default=False,
                        help="Create online installer")
    parser.add_argument("-r", "--create-repo", dest="create_repository", action='store_true', default=False,
                        help="Create online repository")
    parser.add_argument("-s", "--strict", dest="strict_mode", action='store_true', default=True,
                        help="Use strict mode, abort on any error")
    parser.add_argument("-S", "--non-strict", dest="strict_mode", action='store_true', default=False,
                        help="Non strict mode, try to keep on going despite of errors")
    parser.add_argument("--dry-run", dest="dry_run", action='store_true', default=False,
                        help="For testing purposes (faster testing), skip downloading archives")

    parser.add_argument("-u", "--archive-base-url", dest="archive_base_url", type=str,
                        help="Define server base url where to look for archives (.7z)")
    parser.add_argument("--ifw-tools", dest="ifw_tools_uri", type=str,
                        help="Define location where to fetch prebuilt Installer-Framework tools (.7z)")

    parser.add_argument("-l", "--license-type", dest="license_type", type=str, default="opensource",
                        help="Installer file name scheme: define license type")
    parser.add_argument("--preferred-installer-name", dest="preferred_installer_name", type=str,
                        help="Define the full installer name excluding the extension (.run, .exe, .app)")

    parser.add_argument("--add-substitution", dest="substitution_list", action='append',
                        default=[],
                        help="Task include filters per section name in the --config file to match with " \
                        "the section name, e.g. 'offline', 'repository', ...")

    parser.add_argument("--build-timestamp", dest="build_timestamp", type=str,
                        default=strftime('%Y-%m-%d', gmtime()),
                        help="Build timestamp")
    parser.add_argument("--force-version-number-increase", dest="force_version_number_increase", action='store_true',
                        default=False, help="Auto increment %VERSION_NUMBER_AUTO_INCREASE% tag in package.xml file(s)")
    parser.add_argument("--version-number-auto-increase-value", dest="version_number_auto_increase_value", type=str,
                        default='-' + strftime('%Y%m%d%H%M', gmtime()),
                        help="Value for the %VERSION_NUMBER_AUTO_INCREASE%")

    parser.add_argument("--remove-debug-information-files", dest="remove_debug_information_files", action='store_true',
                        default=False,
                        help="Removes debug information files. Besides 'True' and 'False' values accepts also debug file type as parameter")
    parser.add_argument("--remove-debug-libraries", dest="remove_debug_libraries", action='store_true',
                        default=False, help="Removes libraries debug versions")
    parser.add_argument("--remove-pdb-files", dest="remove_pdb_files", action='store_true',
                        default=False, help="(Obsolete) Windows only: Removes Windows pdb files")

    parser.add_argument("--max-cpu-count", dest="max_cpu_count", type=int, default=8,
                        help="Set maximum number of CPU's used on packaging")

    parser.add_argument("--create-maintenance-tool-resource-file", type=str2bool, nargs='?',
                        const=True, dest="create_maintenance_tool_resource_file",
                        default=os.environ.get('CREATE_MAINTENANCE_TOOL_RESOURCE_FILE'),
                        help="Create resource file for Maintenance Tool")
    args = parser.parse_args(sys.argv[1:])

    task = QtInstallerTask(args)
    task.verbose()
    create_installer(task)



