#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#############################################################################
#
# Copyright (C) 2022 The Qt Company Ltd.
# Contact: https://www.qt.io/licensing/
#
# This file is part of the release tools of the Qt Toolkit.
#
# $QT_BEGIN_LICENSE:GPL-EXCEPT$
# Commercial License Usage
# Licensees holding valid commercial Qt licenses may use this file in
# accordance with the commercial license agreement provided with the
# Software or, alternatively, in accordance with the terms contained in
# a written agreement between you and The Qt Company. For licensing terms
# and conditions see https://www.qt.io/terms-conditions. For further
# information use the contact form at https://www.qt.io/contact-us.
#
# GNU General Public License Usage
# Alternatively, this file may be used under the terms of the GNU
# General Public License version 3 as published by the Free Software
# Foundation with exceptions as appearing in the file LICENSE.GPL3-EXCEPT
# included in the packaging of this file. Please review the following
# information to ensure the GNU General Public License requirements will
# be met: https://www.gnu.org/licenses/gpl-3.0.html.
#
# $QT_END_LICENSE$
#
#############################################################################

"""Scripts to generate SDK installer based on open source InstallerFramework"""

import os
import re
import shutil
import sys
from argparse import ArgumentParser, ArgumentTypeError
from configparser import ConfigParser, ExtendedInterpolation
from dataclasses import dataclass, field
from multiprocessing import cpu_count
from pathlib import Path
from time import gmtime, strftime
from typing import Any, Generator, List, Optional

import pkg_constants
from archiveresolver import ArchiveLocationResolver
from bld_utils import download, is_linux, is_macos, is_windows
from bldinstallercommon import (
    copy_tree,
    extract_file,
    handle_component_rpath,
    is_content_url_valid,
    locate_executable,
    locate_path,
    locate_paths,
    remove_one_tree_level,
    remove_tree,
    replace_in_files,
    retrieve_url,
    safe_config_key_fetch,
)
from installer_utils import PackagingError
from logging_util import init_logger
from patch_qt import patch_files, patch_qt_edition
from pkg_constants import INSTALLER_OUTPUT_DIR_NAME
from runner import run_cmd
from sdkcomponent import SdkComponent
from threadedwork import ThreadedWork

if is_windows():
    import win32api  # type: ignore # pylint: disable=E0401

log = init_logger(__name__, debug_mode=False)

# ----------------------------------------------------------------------
TARGET_INSTALL_DIR_NAME_TAG = '%TARGET_INSTALL_DIR%'
ARCHIVES_EXTRACT_DIR_NAME_TAG = '%ARCHIVES_EXTRACT_DIR%'
PACKAGE_DEFAULT_TAG = '%PACKAGE_DEFAULT_TAG%'
UPDATE_REPOSITORY_URL_TAG = '%UPDATE_REPOSITORY_URL%'
PACKAGE_CREATION_DATE_TAG = '%PACKAGE_CREATION_DATE%'
INSTALL_PRIORITY_TAG = '%INSTALL_PRIORITY%'
SORTING_PRIORITY_TAG = '%SORTING_PRIORITY%'
VERSION_NUMBER_AUTO_INCREASE_TAG = '%VERSION_NUMBER_AUTO_INCREASE%'
COMPONENT_SHA1_TAG = '%COMPONENT_SHA1%'


class CreateInstallerError(Exception):
    pass


##############################################################
# Check that valid tools are present in the build environment
##############################################################
def check_required_tools() -> None:
    """Check that valid tools are present in the build environment."""
    if not shutil.which("7z"):
        raise CreateInstallerError("7z tool not found in the PATH")


##############################################################
# Cleanup
##############################################################
def clean_work_dirs(task: Any) -> None:
    """Clean working directories."""
    log.info("Cleaning work environment")
    for item in [task.packages_full_path_dst, task.repo_output_dir, task.config_dir_dst]:
        if os.path.exists(item):
            remove_tree(item)
            log.debug("Deleted directory: %s", item)


##############################################################
# Set the config directory
##############################################################
def set_config_directory(task: Any) -> None:
    """Copy config directory into correct place."""
    log.info("Set config directory")
    config_dir_template = task.config.get('ConfigDir', 'template_name')
    config_template_src = os.path.normpath(os.path.join(task.configurations_dir, config_dir_template))
    if not os.path.exists(config_template_src):
        raise CreateInstallerError(f"No such 'config' template directory: '{config_template_src}'")

    Path(task.config_dir_dst).mkdir(parents=True, exist_ok=True)
    copy_tree(config_template_src, task.config_dir_dst)
    log.info("Copied: '%s' into: '%s'", config_template_src, task.config_dir_dst)


##############################################################
# Set the config.xml
##############################################################
def set_config_xml(task: Any) -> Any:
    """Copy config.xml template into correct place."""
    log.info("Set config.xml")

    configxml_filename = task.config.get('ConfigXml', 'template_name')
    config_template_source = task.configurations_dir + os.sep + task.platform_identifier + os.sep + configxml_filename
    # if no config.xml template, we assume the "config" template dir already contains it
    if not os.path.exists(config_template_source):
        raise CreateInstallerError(f"Given config.xml template does not exist: {config_template_source}")

    # name has to be config.xml for installer-framework
    config_template_dest_dir = task.config_dir_dst
    config_template_dest = config_template_dest_dir + os.sep + 'config.xml'

    if os.path.exists(config_template_dest):
        os.remove(config_template_dest)
        log.debug("Deleted old existing config.xml: %s", config_template_dest)
    Path(config_template_dest_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy(config_template_source, config_template_dest)
    log.info("Copied '%s' into: '%s'", config_template_source, config_template_dest)

    update_repository_url = safe_config_key_fetch(task.config, 'SdkUpdateRepository', 'repository_url_release')

    fileslist = [config_template_dest]
    replace_in_files(fileslist, UPDATE_REPOSITORY_URL_TAG, update_repository_url)
    # substitute values also from global substitution list
    for item in task.substitutions:
        replace_in_files(fileslist, item[0], item[1])
    return config_template_dest


##############################################################
# Substitute common version numbers etc., match against tags
##############################################################
def substitute_global_tags(task: Any) -> None:
    """ Substitute common version numbers etc., match against tags """
    log.info("Substituting global tags:")
    log.info("%%PACKAGE_CREATION_DATE%% = %s", task.build_timestamp)
    log.info("%%VERSION_NUMBER_AUTO_INCREASE%% = %s", task.version_number_auto_increase_value)
    for item in task.substitutions:
        log.info("%s = %s", item[0], item[1])

    # initialize the file list
    fileslist = []
    for directory in task.directories_for_substitutions:
        for root, _, files in os.walk(directory):
            for name in files:
                if not name.endswith((".qs", ".xml", ".ui")):
                    continue
                path = os.path.join(root, name)
                fileslist.append(path)

    replace_in_files(fileslist, PACKAGE_CREATION_DATE_TAG, task.build_timestamp)
    if task.force_version_number_increase:
        replace_in_files(fileslist, VERSION_NUMBER_AUTO_INCREASE_TAG, task.version_number_auto_increase_value)
    for item in task.substitutions:
        replace_in_files(fileslist, item[0], item[1])


##############################################################
# Substitute component specifig tags
##############################################################
def substitute_component_tags(tag_pair_list: List[List[str]], meta_dir_dest: str) -> None:
    """ Substitute component specific tags """
    if len(tag_pair_list) == 0:
        return
    log.info("Substituting component specific tags")
    # initialize the file list
    fileslist = []

    for root, _, files in os.walk(meta_dir_dest):
        for name in files:
            if not name.endswith((".qs", ".xml", ".ui")):
                continue
            path = os.path.join(root, name)
            fileslist.append(path)

    for pair in tag_pair_list:
        tag = pair[0]
        value = pair[1]
        if tag and value:
            log.info("Matching '%s' and '%s' in files list", tag, value)
            replace_in_files(fileslist, tag, value)
        else:
            log.warning("Ignoring incomplete tag pair: %s = %s", tag, value)


##############################################################
# Parse SDK components
##############################################################
def parse_component_data(task: Any, configuration_file: str, configurations_base_path: str) -> None:
    """Parse SDK component data"""
    file_full_path = configuration_file
    if not os.path.isfile(file_full_path):
        try:
            file_full_path = locate_path(configurations_base_path, [configuration_file], filters=[os.path.isfile])
        except PackagingError:
            # check the 'all-os' directory
            allos_conf_file_dir = os.path.normpath(task.configurations_dir + os.sep + 'all-os')
            file_full_path = locate_path(allos_conf_file_dir, [configuration_file], filters=[os.path.isfile])
    log.info("Reading target configuration file: %s", file_full_path)
    configuration = ConfigParser(interpolation=ExtendedInterpolation())
    with open(file_full_path, encoding="utf-8") as cfgfile:
        configuration.read_file(cfgfile)

    # parse package ignore list first
    sdk_component_exclude_list = safe_config_key_fetch(configuration, 'PackageIgnoreList', 'packages')
    if sdk_component_exclude_list:
        sdk_component_exclude_list = sdk_component_exclude_list.replace(' ', '')
        pkg_list = sdk_component_exclude_list.split(',')
        for item in pkg_list:
            task.sdk_component_ignore_list.append(item)
    # parse sdk components
    for section in configuration.sections():
        section_namespace = section.split(".")[0]
        if section_namespace in task.package_namespace:
            if section not in task.sdk_component_ignore_list:
                sdk_component = SdkComponent(
                    section_name=section,
                    target_config=configuration,
                    packages_full_path_list=task.packages_dir_name_list,
                    archive_location_resolver=task.archive_location_resolver,
                    key_value_substitution_list=task.substitutions,
                )
                if task.dry_run:
                    sdk_component.set_archive_skip(True)
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
                    if task.strict_mode:
                        raise CreateInstallerError(f"{sdk_component.error_msg()}")
                    log.warning("Ignore invalid component (missing payload/metadata?): %s", section)
                    task.sdk_component_list_skipped.append(sdk_component)
    # check for extra configuration files if defined
    extra_conf_list = safe_config_key_fetch(configuration, 'PackageConfigurationFiles', 'file_list')
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
def parse_components(task: Any) -> None:
    """Parse SDK all components"""
    log.info("Parse target configuration files")
    conf_base_path = task.configurations_dir + os.sep + task.platform_identifier + os.sep
    main_conf_file = task.configuration_file
    parse_component_data(task, main_conf_file, conf_base_path)


def create_metadata_map(sdk_component: SdkComponent) -> List[List[str]]:
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


def get_component_sha1_file(sdk_component: SdkComponent, sha1_file_dest: str) -> None:
    """download component sha1 file"""
    download(sdk_component.component_sha1_uri, sha1_file_dest)

    # read sha1 from the file
    with open(sha1_file_dest, "r", encoding="utf-8") as sha1_file:
        sdk_component.component_sha1 = sha1_file.read().strip()


def get_component_data(
    task: Any,
    sdk_component: SdkComponent,
    archive: SdkComponent.DownloadableArchive,
    install_dir: str,
    data_dir_dest: str,
    compress_content_dir: str,
) -> None:
    """download and create data for a component"""
    package_raw_name = os.path.basename(archive.archive_uri)

    # if no data to be installed, then just continue
    if not package_raw_name:
        return
    if not archive.package_strip_dirs:
        archive.package_strip_dirs = '0'

    if package_raw_name.endswith(('.7z', '.tar.xz')) \
       and archive.package_strip_dirs == '0' \
       and not archive.package_finalize_items \
       and not archive.archive_action \
       and not archive.rpath_target \
       and sdk_component.target_install_base == '/' \
       and not archive.target_install_dir:
        log.info("No repackaging actions required for the package, just download it directly to data directory")
        downloaded_archive = os.path.normpath(data_dir_dest + os.sep + archive.archive_name)
        # start download
        download(archive.archive_uri, downloaded_archive)
        return

    downloaded_archive = os.path.normpath(install_dir + os.sep + package_raw_name)
    # start download
    download(archive.archive_uri, downloaded_archive)

    # repackage content so that correct dir structure will get into the package

    if not archive.extract_archive:
        archive.extract_archive = 'yes'

    # extract contents
    if archive.extract_archive == 'yes':
        extracted = extract_file(downloaded_archive, install_dir)
        # remove old package if extraction was successful, else keep it
        if extracted:
            os.remove(downloaded_archive)

        # perform custom action script for the extracted archive
        if archive.archive_action:
            script_file, script_args = archive.archive_action.split(",")
            script_args = script_args or ""
            script_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), script_file)
            if not os.path.exists(script_path):
                raise CreateInstallerError(f"Custom archive action script missing: {script_path}")
            cmd = [script_path, "--input-dir=" + install_dir, script_args.strip()]
            if script_path.endswith(".py"):
                cmd.insert(0, sys.executable)
            run_cmd(cmd)

        # strip out unnecessary folder structure based on the configuration
        count = 0
        iterations = int(archive.package_strip_dirs)
        while count < iterations:
            count = count + 1
            remove_one_tree_level(install_dir)
        # perform package finalization tasks for the given archive
        if 'delete_doc_directory' in archive.package_finalize_items:
            try:
                doc_dir = locate_path(install_dir, ["doc"], filters=[os.path.isdir])
                log.info("Erasing doc: %s", doc_dir)
                shutil.rmtree(doc_dir)
            except PackagingError:
                pass
        if 'cleanup_doc_directory' in archive.package_finalize_items:
            cleanup_docs(install_dir)
        if 'qml_examples_only' in archive.package_finalize_items:
            try:
                examples_dir = locate_path(install_dir, ["examples"], filters=[os.path.isdir])
                qml_examples_only(examples_dir)
            except PackagingError:
                pass
        if 'patch_qt' in archive.package_finalize_items:
            patch_files(install_dir, product='qt_framework')
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
        if is_linux():
            handle_component_rpath(install_dir, archive.rpath_target)

    if archive.component_sha1_file:
        # read sha1 from the file
        sha1_file_path = install_dir + os.sep + archive.component_sha1_file
        if os.path.exists(sha1_file_path):
            with open(sha1_file_path, "r", encoding="utf-8") as sha1_file:
                sdk_component.component_sha1 = sha1_file.read().strip()
        else:
            raise CreateInstallerError(f"Component SHA1 file '{archive.component_sha1_file}' not found")

    # lastly compress the component back to .7z archive
    content_list = os.listdir(compress_content_dir)
    # adding compress_content_dir in front of every item
    content_list = [(compress_content_dir + os.sep + x) for x in content_list]

    saveas = os.path.normpath(data_dir_dest + os.sep + archive.archive_name)
    run_cmd(cmd=[task.archivegen_tool, saveas] + content_list, cwd=data_dir_dest)


def handle_set_executable(base_dir: str, package_finalize_items: str) -> None:
    for item in parse_package_finalize_items(package_finalize_items, 'set_executable'):
        expected_path = os.path.join(base_dir, item)
        if not os.path.exists(expected_path):
            raise CreateInstallerError(f'Can not set executable bit as path not found: "{expected_path}"')
        os.chmod(expected_path, 0o755)
        log.info("Executable bit set for: %s", expected_path)


def handle_set_licheck(task: Any, base_dir: str, package_finalize_items: str) -> None:
    for licheck_file_name in parse_package_finalize_items(package_finalize_items, 'set_licheck'):
        licheck_file_path = os.path.join(base_dir, licheck_file_name)
        if not os.path.exists(licheck_file_path):
            raise CreateInstallerError(f'Can not set licheck as path not found: "{licheck_file_path}"')
        patch_qt_edition(base_dir, licheck_file_name, task.build_timestamp)
        log.info("Licheck set for: %s", licheck_file_path)
        break


def parse_package_finalize_items(package_finalize_items: str, item_category: str) -> Generator[Any, Any, Any]:
    for item in package_finalize_items.split(","):
        if item_category not in item:
            continue
        parts = item.split("=")
        yield parts[-1].strip()


##############################################################
# Substitute pkg template directory names
##############################################################
def substitute_package_name(task: Any, package_name: str) -> str:
    for item in task.substitutions:
        package_name = package_name.replace(item[0], item[1])

    return package_name


##############################################################
# Remove debug information files
##############################################################
def remove_all_debug_information_files(install_dir: str) -> None:
    """Remove debug information files according to host machine."""
    if is_windows():
        debug_information_file_ending = 'pdb'
    elif is_linux():
        debug_information_file_ending = 'debug'
    elif is_macos():
        debug_information_file_ending = 'dSYM'
    else:
        raise CreateInstallerError('Host is not identified as Windows, Linux or macOS')

    remove_debug_information_files_by_file_type(install_dir, debug_information_file_ending)


##############################################################
# Remove debug information files by file type
##############################################################
def remove_debug_information_files_by_file_type(install_dir: str, dbg_file_suffix: str) -> None:
    """Remove debug information files by file type"""
    dirs = locate_paths(install_dir, ['bin', 'lib', 'qml', 'plugins'], filters=[os.path.isdir])
    for dbg_info_dir in dirs:
        log.info("Removing debug information files from: %s", dbg_info_dir)
        if dbg_file_suffix == 'dSYM':
            # On macOS, debug symbols are in dSYM folder bundles instead of files.
            dbg_file_list = locate_paths(dbg_info_dir, ["*dSYM"], [os.path.isdir])
            for debug_information in dbg_file_list:
                remove_tree(debug_information)
        else:
            for path in locate_paths(dbg_info_dir, ["*." + dbg_file_suffix], [os.path.isfile]):
                Path(path).unlink()


##############################################################
# Remove debug libraries
##############################################################
def remove_all_debug_libraries(install_dir: str) -> None:
    """Remove debug libraries."""
    # at this point of packaging we don't necessarily have reliable source of library names
    # on Windows we trust debug library filenames to follow *d.dll | *d.lib industry standard naming convention
    # but we must consider that library filenames can end with letter 'd' in release build
    # and exclude those from removable items
    if is_windows():
        for directory in ('bin', 'lib', 'qml', 'plugins'):
            windows_debug_library_dir = locate_path(install_dir, [directory], filters=[os.path.isdir])
            log.info("Removing Windows debug libraries from: %s", windows_debug_library_dir)
            # go through all library types and related qmake files
            debug_library_file_endings = ['dll', 'lib', 'prl']
            for debug_library_file_type in debug_library_file_endings:
                # make list of all debug library names
                all_debug_files_list = locate_paths(windows_debug_library_dir, ['*d.' + debug_library_file_type], filters=[os.path.isfile])
                # in case library name ends with 'd' we need to keep that and remove only library with double d at the end of file name
                double_d_debug_files_list = locate_paths(windows_debug_library_dir, ['*dd.' + debug_library_file_type], filters=[os.path.isfile])
                if double_d_debug_files_list:
                    # check intersection of all debug libraries and library names ending with letter 'd'
                    debug_files_list_intersection = set(all_debug_files_list).intersection(double_d_debug_files_list)
                    for debug_library_name in set(debug_files_list_intersection):
                        # remove one 'd' from library names ending letter 'd' also in release builds
                        # and exclude from removed libraries
                        altered_library_name = debug_library_name[:-5] + debug_library_name[-5 + 1:]
                        all_debug_files_list.remove(altered_library_name)
                # remove all debug libraries with filenames ending *d.dll | *d.lib
                for item in all_debug_files_list:
                    Path(item).unlink()
    # remove macOS debug libraries
    elif is_macos():
        for debug_library_dir in locate_paths(install_dir, ['bin', 'lib', 'qml', 'plugins'], filters=[os.path.isdir]):
            log.info("Removing macOS debug libraries from: %s", debug_library_dir)
            debug_library_file_ending = '_debug.*'
            if os.path.exists(debug_library_dir):
                for item in locate_paths(debug_library_dir, ['*' + debug_library_file_ending]):
                    Path(item).unlink()
    else:
        log.info("Host was not Windows or macOS. For Linux and others we don\'t do anything at the moment")


##############################################################
# Create target components
##############################################################
def create_target_components(task: Any) -> None:
    """Create target components."""
    Path(task.packages_full_path_dst).mkdir(parents=True, exist_ok=True)

    log.info("Creating SDK components")
    # download and extract lrelease binary for creating translation binaries
    if task.create_repository and os.environ.get("LRELEASE_TOOL"):
        if not os.path.isfile(os.path.join(task.script_root_dir, "lrelease")):
            download(os.environ.get("LRELEASE_TOOL", ""), task.script_root_dir)
            extract_file(os.path.basename(os.environ.get("LRELEASE_TOOL", "")), task.script_root_dir)
    get_component_data_work = ThreadedWork("get components data")
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
        Path(meta_dir_dest).mkdir(parents=True, exist_ok=True)
        # Copy Meta data
        metadata_content_source_root = os.path.normpath(sdk_component.pkg_template_dir + os.sep + 'meta')
        copy_tree(metadata_content_source_root, meta_dir_dest)
        if os.path.isfile(os.path.join(task.script_root_dir, "lrelease")):
            # create translation binaries if translation source files exist for component
            update_script = os.path.join(task.script_root_dir, "update_component_translations.sh")
            lrelease_tool = os.path.join(task.script_root_dir, "lrelease")
            run_cmd(cmd=[update_script, "-r", lrelease_tool, dest_base])
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
                    # adding get_component_data task to our work queue
                    # Create needed data dirs before the threads start to work
                    Path(install_dir).mkdir(parents=True, exist_ok=True)
                    Path(data_dir_dest).mkdir(parents=True, exist_ok=True)
                    if is_windows():
                        install_dir = win32api.GetShortPathName(install_dir)
                        data_dir_dest = win32api.GetShortPathName(data_dir_dest)
                    get_component_data_work.add_task(f"adding {archive.archive_name} to {sdk_component.package_name}",
                                                     get_component_data, task, sdk_component, archive, install_dir, data_dir_dest, compress_content_dir)
        # handle component sha1 uri
        if sdk_component.component_sha1_uri:
            sha1_file_dest = os.path.normpath(dest_base + 'SHA1')
            get_component_data_work.add_task(f"getting component sha1 file for {sdk_component.package_name}",
                                             get_component_sha1_file, sdk_component, sha1_file_dest)

        # maybe there is some static data
        data_content_source_root = os.path.normpath(sdk_component.pkg_template_dir + os.sep + 'data')
        if os.path.exists(data_content_source_root):
            Path(data_dir_dest).mkdir(parents=True, exist_ok=True)
            copy_tree(data_content_source_root, data_dir_dest)

    if not task.dry_run:
        # start the work threaded, more than 8 parallel downloads are not so useful
        get_component_data_work.run(min([task.max_cpu_count, cpu_count()]))

    for sdk_component in task.sdk_component_list:
        # substitute tags
        substitute_component_tags(create_metadata_map(sdk_component), sdk_component.meta_dir_dest)
        if hasattr(sdk_component, 'temp_data_dir') and os.path.exists(sdk_component.temp_data_dir):
            # lastly remove temp dir after all data is prepared
            if not remove_tree(sdk_component.temp_data_dir):
                raise CreateInstallerError(f"Unable to remove directory: {sdk_component.temp_data_dir}")
            # substitute downloadable archive names in installscript.qs
            substitute_component_tags(sdk_component.generate_downloadable_archive_list(), sdk_component.meta_dir_dest)


##############################################################
# Cleanup examples
##############################################################
def qml_examples_only(examples_dir: str) -> None:
    if not os.path.isdir(examples_dir):
        log.error("Given examples directory is not valid path: %s", examples_dir)
        log.error("Archive not cleaned!")
        return
    subdir_list = []
    regex = re.compile(r'^qml\S.*')
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
            log.info("QML example package: %s", submodule)
        else:
            delete_dir = os.path.join(root_dir, submodule)
            log.info("Delete non qml examples directory: %s", delete_dir)
            shutil.rmtree(delete_dir)


##############################################################
# Cleanup unnecessary documentation files
##############################################################
def cleanup_docs(install_dir: str) -> None:
    if not os.path.isdir(install_dir):
        log.error("Given docs directory is not valid path: %s", install_dir)
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
                log.info("Cleaning up -> deleting directory: %s", item)
                shutil.rmtree(item, ignore_errors=True)
        # then remove unnecessary files
        for filename in os.listdir(submodule):
            if filename.endswith(('.qdocconf', '.sha1', '.html')):
                full_filename = os.path.join(submodule, filename)
                if os.path.isfile(full_filename):
                    log.info("Cleaning up -> deleting file: %s", full_filename)
                    os.remove(full_filename)


##############################################################
# Create the final installer binary
##############################################################
def create_installer_binary(task: Any) -> None:
    """Create installer binary files using binarycreator tool."""
    log.info("Create installer binary")

    # naming scheme: qt-<platform>-<license>-<version>-<tag>-<compiler>-<target_arch>-<offline/online>.<extension>
    #    license is opensource or commercial
    #    extension is exe, dmg, or run
    #    tag is alpha1, beta2, rc1, etc (no tag for final).
    #    platform is win, linux, mac, etc.
    platform = task.config.get('PlatformIdentifier', 'identifier')
    installer_type = 'offline' if task.offline_installer else 'online'
    extension = '.run' if is_linux() else ''

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
    run_cmd(cmd=cmd_args, cwd=task.script_root_dir)

    # move results to dedicated directory
    output_dir = os.path.join(task.script_root_dir, INSTALLER_OUTPUT_DIR_NAME)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    file_name = os.path.join(task.script_root_dir, task.installer_name)
    old_existing_file_name = os.path.join(output_dir, task.installer_name)
    if is_macos():
        file_name = file_name + '.app'
        old_existing_file_name = old_existing_file_name + '.app'
    if is_windows():
        file_name = file_name + '.exe'
        old_existing_file_name = old_existing_file_name + '.exe'
    # remove old if exists
    if os.path.isfile(old_existing_file_name):
        log.info("Deleting old existing file: %s", old_existing_file_name)
        os.remove(old_existing_file_name)
    log.info("Moving '%s' into '%s'", file_name, output_dir)
    shutil.move(file_name, output_dir)


##############################################################
# Create the repository
##############################################################
def create_online_repository(task: Any) -> None:
    """Create online repository using repogen tool."""
    log.info("Create online repository")

    # handle special case if MaintenanceTool repository build and
    # update.rcc update requeste
    if task.create_maintenance_tool_resource_file:
        create_maintenance_tool_resource_file(task)

    # repogen arguments
    if task.create_repository:
        log.info("Creating online repository:")
        log.info("Destination dir: %s", task.repo_output_dir)
        log.info("Input data dir: %s", task.packages_full_path_dst)
        repogen_args = [task.repogen_tool]
        if os.environ.get('IFW_UNITE_METADATA'):
            repogen_args += ['--unite-metadata']
        repogen_args += ['-p', task.packages_full_path_dst, task.repo_output_dir]
        # create repository
        run_cmd(cmd=repogen_args, cwd=task.script_root_dir)
        if not os.path.exists(task.repo_output_dir):
            raise CreateInstallerError(f"Unable to create repository directory: {task.repo_output_dir}")


##############################################################
# Create MaintenanceTool resource file
##############################################################
def create_maintenance_tool_resource_file(task: Any) -> None:
    """Create MaintenanceTool resource file."""
    log.info("Create MaintenanceTool resource file")
    set_config_directory(task)
    config_xml = set_config_xml(task)
    pkg_dir = task.packages_full_path_dst
    cmd_args = [task.binarycreator_tool, '--online-only', '-p', pkg_dir, '-c', config_xml, '-rcc']
    run_cmd(cmd=cmd_args, cwd=task.script_root_dir)
    # archive
    resource_file = os.path.join(task.script_root_dir, 'update.rcc')
    try:
        installer_base_archive = locate_path(task.packages_full_path_dst, ["*installer-framework*"], filters=[os.path.isfile])
        # inject the resource file to the same archive where installerbase is
        inject_update_rcc_to_archive(installer_base_archive, resource_file)
    except PackagingError:
        log.error("Unable to locate installerbase archive from: %s", task.packages_full_path_dst)
        log.error("The update.rcc will not be included in the MaintenanceTool repository!")


###############################
# function
###############################
def inject_update_rcc_to_archive(archive_file_path: str, file_to_be_injected: str) -> None:
    log.info("Injecting file [%s] into [%s]", file_to_be_injected, archive_file_path)
    if not os.path.isfile(file_to_be_injected):
        log.error("Unable to locate file: %s", file_to_be_injected)
    if not os.path.isfile(archive_file_path):
        log.error("Unable to locate file: %s", archive_file_path)
    archive_file_name = os.path.basename(archive_file_path)
    # copy to tmp location
    tmp_dir = os.path.join(os.path.dirname(archive_file_path), '_tmp')
    Path(tmp_dir).mkdir(parents=True, exist_ok=True)
    shutil.copy(archive_file_path, tmp_dir)
    # extract
    copied_archive_file = os.path.join(tmp_dir, archive_file_name)
    extract_file(copied_archive_file, tmp_dir)
    os.remove(copied_archive_file)
    # add file
    shutil.copy(file_to_be_injected, tmp_dir)
    # re-compress
    cmd_args_archive = ["7z", "a", archive_file_name, "*"]
    run_cmd(cmd=cmd_args_archive, cwd=tmp_dir)
    # delete original
    os.remove(archive_file_path)
    # copy re-compressed package to correct location
    shutil.copy(os.path.join(tmp_dir, archive_file_name), os.path.dirname(archive_file_path))
    # delete tmp location
    shutil.rmtree(tmp_dir)


##############################################################
# Create the final installer binary
##############################################################
def create_mac_disk_image(task: Any) -> None:
    """Create Apple disk image."""
    log.info("Create Apple disk image")
    output_dir = INSTALLER_OUTPUT_DIR_NAME
    source_dir = os.path.join(task.script_root_dir, output_dir, task.installer_name + '.app')
    dmg_path = os.path.join(task.script_root_dir, output_dir, task.installer_name + '.dmg')
    cmd_args = ['hdiutil', 'create', '-srcfolder', source_dir, '-volname', task.installer_name]
    cmd_args += ['-format', 'UDBZ', dmg_path, '-ov', '-scrub', '-size', '4g']
    run_cmd(cmd=cmd_args, cwd=task.script_root_dir)


##############################################################
# All main build steps
##############################################################
def create_installer(task: Any) -> None:
    """Installer creation main steps."""
    log.info("Creating Qt Installer Framework based installer/online repository")
    # check required tools
    check_required_tools()
    # clean env before starting
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
        if is_macos():
            create_mac_disk_image(task)
    if task.create_repository:
        create_online_repository(task)


def str2bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    if value.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    if value.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    raise ArgumentTypeError('Boolean value expected.')


@dataclass
class QtInstallerTask:
    """QtInstallerTask dataclass"""

    config = ConfigParser(interpolation=ExtendedInterpolation())
    configurations_dir: str = "configurations"
    configuration_file: str = ""
    script_root_dir: str = os.path.dirname(os.path.realpath(__file__))
    ifw_tools_uri: str = ""
    ifw_tools_dir: str = os.path.join(script_root_dir, "ifwt")
    archivegen_tool: str = ""
    binarycreator_tool: str = ""
    installerbase_tool: str = ""
    repogen_tool: str = ""
    config_dir_dst: str = os.path.join(script_root_dir, "config")
    packages_full_path_dst: str = os.path.join(script_root_dir, "pkg")
    repo_output_dir: str = os.path.join(script_root_dir, "online_repository")
    package_namespace: List[str] = field(default_factory=list)
    platform_identifier: str = ""
    installer_name: str = ""
    packages_dir_name_list: List[str] = field(default_factory=list)
    substitutions: List[List[str]] = field(default_factory=list)
    directories_for_substitutions: List[str] = field(default_factory=list)
    sdk_component_list: List[SdkComponent] = field(default_factory=list)
    sdk_component_list_skipped: List[SdkComponent] = field(default_factory=list)
    sdk_component_ignore_list: List[str] = field(default_factory=list)
    archive_location_resolver: Optional[ArchiveLocationResolver] = None
    archive_base_url: str = ""
    remove_debug_information_files: bool = False
    remove_debug_libraries: bool = False
    remove_pdb_files: bool = False
    offline_installer: bool = False
    online_installer: bool = False
    create_repository: bool = False
    strict_mode: bool = True
    dry_run: Optional[str] = None
    license_type: str = "opensource"
    build_timestamp: str = strftime("%Y-%m-%d", gmtime())
    force_version_number_increase: bool = False
    version_number_auto_increase_value: str = "-" + strftime("%Y%m%d%H%M", gmtime())
    max_cpu_count: int = 8
    create_maintenance_tool_resource_file: bool = bool(
        os.environ.get("CREATE_MAINTENANCE_TOOL_RESOURCE_FILE")
    )
    substitution_list: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        log.info("Parsing: %s", self.configuration_file)
        with open(self.configuration_file, encoding="utf-8") as cfgfile:
            self.config.read_file(cfgfile)
        package_namespace = self.config.get("PackageNamespace", "name").replace(" ", "")
        self.package_namespace: List[str] = package_namespace.split(",")
        self.platform_identifier = self.config.get("PlatformIdentifier", "identifier")
        self.packages_dir_name_list = self.parse_ifw_pkg_template_dirs(
            self.config.get("PackageTemplates", "template_dirs"), self.configurations_dir
        )
        self._parse_substitutions()
        if self.archive_location_resolver is None:
            self.archive_location_resolver = ArchiveLocationResolver(
                self.config, self.archive_base_url, self.configurations_dir, self.substitutions
            )

    def __str__(self) -> str:
        return f"""Installer task:
  IFW tools: {self.ifw_tools_uri}
  Archivegen: {self.archivegen_tool}
  Binarycreator: {self.binarycreator_tool}
  Installerbase: {self.installerbase_tool}
  Repogen: {self.repogen_tool}
  Working config dir: {self.config_dir_dst}
  Working pkg dir: {self.packages_full_path_dst}
  Package namespace: {self.package_namespace}
  Platform identifier: {self.platform_identifier}
  Installer name: {self.installer_name}
  IFW pkg templates: {self.packages_dir_name_list}
  Substitutions: {self.substitutions}
  Remove debug information files: {self.remove_debug_information_files}
  Remove debug libraries: {self.remove_debug_libraries}
  Remove pdb files: {self.remove_pdb_files}
  Online installer: {self.online_installer}
  Offline installer: {self.offline_installer}
  Create repository: {self.create_repository}
  License: {self.license_type}
  Build timestamp: {self.build_timestamp}
  Force version number increase: {self.force_version_number_increase}
  Version number auto increase value: {self.version_number_auto_increase_value}
  Mac cpu count: {self.max_cpu_count}
  Create MaintenanceTool resource file: {self.create_maintenance_tool_resource_file}"""

    def _parse_substitutions(self) -> None:
        for item in self.substitution_list:  # pylint: disable=not-an-iterable
            key, value = item.split("=", maxsplit=1)
            if not value:
                log.warning("Empty value for substitution string given, substituting anyway: %s", item)
            self.substitutions.append([key, value])  # pylint: disable=no-member
        self.substitutions.append(['%LICENSE%', self.license_type])  # pylint: disable=no-member

    def parse_ifw_pkg_template_dirs(self, template_list: str, configurations_dir: str) -> List[str]:
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

    def install_ifw_tools(self) -> None:
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
    def set_ifw_tools(self) -> None:
        executable_suffix = ".exe" if is_windows() else ""
        installerbase_filename = "installerbase_unsigned" if is_windows() else "installerbase"
        self.archivegen_tool = locate_executable(self.ifw_tools_dir, ['archivegen' + executable_suffix])
        self.binarycreator_tool = locate_executable(self.ifw_tools_dir, ['binarycreator' + executable_suffix])
        self.installerbase_tool = locate_executable(self.ifw_tools_dir, [installerbase_filename + executable_suffix])
        self.repogen_tool = locate_executable(self.ifw_tools_dir, ['repogen' + executable_suffix])
        # check
        assert os.path.isfile(self.archivegen_tool), f"Archivegen tool not found: {self.archivegen_tool}"
        assert os.path.isfile(self.binarycreator_tool), f"Binary creator tool not found: {self.binarycreator_tool}"
        assert os.path.isfile(self.installerbase_tool), f"Installerbase not found: {self.installerbase_tool}"
        assert os.path.isfile(self.repogen_tool), f"Repogen tool not found: {self.repogen_tool}"
        log.info("Archive generator tool: %s", self.archivegen_tool)
        log.info("Binary creator tool: %s", self.binarycreator_tool)
        log.info("Repogen tool: %s", self.repogen_tool)
        log.info("Installerbase: %s", self.installerbase_tool)

    def download_and_extract_ifw_tools(self) -> None:
        package_save_as_temp = os.path.join(self.ifw_tools_dir, os.path.basename(self.ifw_tools_uri))
        package_save_as_temp = os.path.normpath(package_save_as_temp)
        # download ifw archive if not present on disk
        if not os.path.exists(package_save_as_temp):
            # create needed dirs
            Path(self.ifw_tools_dir).mkdir(parents=True, exist_ok=True)
            log.info("Downloading: %s", self.ifw_tools_uri)
            if not is_content_url_valid(self.ifw_tools_uri):
                raise CreateInstallerError(f"Package URL is invalid: {self.ifw_tools_uri}")
            retrieve_url(self.ifw_tools_uri, package_save_as_temp)
            if not os.path.isfile(package_save_as_temp):
                raise CreateInstallerError("Downloading failed! Aborting!")
        # extract ifw archive
        extract_file(package_save_as_temp, self.ifw_tools_dir)
        log.info("IFW tools extracted into: %s", self.ifw_tools_dir)


def main() -> None:
    """Main"""
    parser = ArgumentParser(prog="Script to create Qt Installer Framework based installers.")
    parser.add_argument("-c", "--configurations-dir", dest="configurations_dir", type=str, default="configurations",
                        help="define configurations directory where to read installer configuration files")
    parser.add_argument("-f", "--configuration-file", dest="configuration_file", type=str,
                        help="define configuration file for installer content")
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
                        help="Task include filters per section name in the --config file to match with "
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

    task: QtInstallerTask = QtInstallerTask(
        configurations_dir=args.configurations_dir,
        configuration_file=args.configuration_file,
        offline_installer=args.offline_installer,
        online_installer=args.online_installer,
        create_repository=args.create_repository,
        strict_mode=args.strict_mode,
        dry_run=args.dry_run,
        archive_base_url=args.archive_base_url,
        ifw_tools_uri=args.ifw_tools_uri,
        license_type=args.license_type,
        installer_name=args.preferred_installer_name,
        substitution_list=args.substitution_list,
        build_timestamp=args.build_timestamp,
        force_version_number_increase=args.force_version_number_increase,
        version_number_auto_increase_value=args.version_number_auto_increase_value,
        remove_debug_information_files=args.remove_debug_information_files,
        remove_debug_libraries=args.remove_debug_libraries,
        remove_pdb_files=args.remove_pdb_files,
        max_cpu_count=args.max_cpu_count,
        create_maintenance_tool_resource_file=args.create_maintenance_tool_resource_file,
    )
    log.info(str(task))
    create_installer(task)


if __name__ == "__main__":
    main()
