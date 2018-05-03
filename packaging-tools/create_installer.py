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

"""Scripts to generate SDK installer based on open source InstallerFramework"""

import ConfigParser
import os
import shutil
import sys
import re
import glob
from time import gmtime, strftime
from optparse import OptionParser, Option
import multiprocessing # to get the cpu core count
import platform
if platform.system().lower().startswith('win'):
    import win32api

from threadedwork import ThreadedWork
import bld_utils
import bldinstallercommon
import pkg_constants
import bld_ifw_tools
from bld_ifw_tools import IfwOptions
from archiveresolver import ArchiveLocationResolver
from sdkcomponent import SdkComponent

# ----------------------------------------------------------------------
BUILD_TIMESTAMP             = strftime('%Y-%m-%d', gmtime())
CONFIG_PARSER_COMMON        = 0
CONFIG_PARSER_TARGET        = 0
OPTION_PARSER               = 0
PLATFORM_IDENTIFIER         = ''
MAIN_CONFIG_NAME            = ''
SCRIPT_ROOT_DIR             = os.path.dirname(os.path.realpath(__file__))
GENERAL_TAG_SUBST_LIST      = []
CONFIGURATIONS_DIR          = 'configurations'
CONFIG_DIR_DST              = 'config'
COMMON_CONFIG_NAME          = 'common'
COMMON_CONFIG_DIR_NAME      = 'all-os'
REPO_OUTPUT_DIR             = os.path.normpath(SCRIPT_ROOT_DIR + os.sep + 'repository')
PACKAGES_DIR_NAME_LIST      = []
PACKAGES_FULL_PATH_DST      = 'pkg'
ROOT_COMPONENT_NAME         = ''
PACKAGE_NAMESPACE           = None
IFW_TOOLS_DIR               = ''
ARCHIVEGEN_TOOL             = ''
BINARYCREATOR_TOOL          = ''
INSTALLERBASE_TOOL          = ''
REPOGEN_TOOL                = ''
SDK_NAME_ROOT               = ''
SDK_NAME                    = ''
DEBUG_RPATH                 = False
DUMP_CONFIG                 = False
INCREMENTAL_MODE            = False
ARCHIVE_DOWNLOAD_SKIP       = False
CREATE_ONLINE_INSTALLER     = False
CREATE_OFFLINE_INSTALLER    = False
CREATE_REPOSITORY           = False
ARCHIVE_LOCATION_RESOLVER   = None
SDK_COMPONENT_LIST          = []
SDK_COMPONENT_LIST_SKIPPED  = []
SDK_COMPONENT_IGNORE_LIST   = []
STRICT_MODE                 = True
ARCHIVE_SERVER_BASE_URL     = ''
INSTALLER_FRAMEWORK_TOOLS   = ''
IFW_TOOLS_DIR_NAME          = 'ifwt'
CREATE_MAINTENANCE_TOOL_RESOURCE_FILE = False

LICENSE_TYPE                        = ''

TARGET_INSTALL_DIR_NAME_TAG         = '%TARGET_INSTALL_DIR%'
PACKAGE_DEFAULT_TAG                 = '%PACKAGE_DEFAULT_TAG%'
SDK_VERSION_NUM_TAG                 = '%SDK_VERSION_NUM%'
UPDATE_REPOSITORY_URL_TAG           = '%UPDATE_REPOSITORY_URL%'
PACKAGE_CREATION_DATE_TAG           = '%PACKAGE_CREATION_DATE%'
INSTALL_PRIORITY_TAG                = '%INSTALL_PRIORITY%'
SORTING_PRIORITY_TAG                = '%SORTING_PRIORITY%'
VERSION_NUMBER_AUTO_INCREASE_TAG    = '%VERSION_NUMBER_AUTO_INCREASE%'
VERSION_NUMBER_AUTO_INCREASE_VALUE  = ''
REMOVE_PDB_FILES                    = 'False'
REMOVE_WINDOWS_DEBUG_LIBRARIES      = 'False'
REMOVE_DEBUG_INFORMATION_FILES      = 'False'
REMOVE_DEBUG_LIBRARIES              = 'False'

KEY_SUBSTITUTION_LIST               = []
PREFERRED_INSTALLER_NAME            = ''


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


##############################################################
# Start
##############################################################
def main():
    """ Start """
    if parse_cmd_line():
        create_installer()
    else:
        raise ValueError("Insufficient command line arguments given")


##############################################################
# Check that valid tools are present in the build environment
##############################################################
def check_required_tools():
    """Check that valid tools are present in the build environment."""
    print(sys.path)
    from distutils.spawn import find_executable
    print(find_executable('7z'))
    if not find_executable('7z'):
        raise EnvironmentError("7z tool not found in the PATH")


##############################################################
# Check if valid platform identifier
##############################################################
def check_platform_identifier(platform_identifier):
    """Check if given platform identifier is valid."""
    path_to_be_checked = CONFIGURATIONS_DIR + os.sep + platform_identifier
    if os.path.exists(path_to_be_checked):
        return
    sys.stderr.write('*** Unsupported platform identifier given: ' + platform_identifier)
    sys.stderr.write('*** Following directory can not be found:   ' + path_to_be_checked)
    raise ValueError()


##############################################################
# Setup Option Parser
##############################################################
def setup_option_parser():
    """ Set up Option Parser """
    global OPTION_PARSER
    OPTION_PARSER = OptionParser(option_class=MultipleOption)
    OPTION_PARSER.add_option("-c", "--configurations-dir",
                             action="store", type="string", dest="configurations_dir", default="configurations",
                             help="define configurations directory where to read installer configuration files")
    OPTION_PARSER.add_option("-f", "--configuration-file",
                             action="store", type="string", dest="configuration_file", default="",
                             help="define configurations directory where to read installer configuration files")

    OPTION_PARSER.add_option("-i", "--incremental",
                             action="store_true", dest="incremental", default=False,
                             help="enable incremental development mode")
    OPTION_PARSER.add_option("-o", "--offline",
                             action="store_true", dest="offline_installer", default=False,
                             help="create offline installer")
    OPTION_PARSER.add_option("-O", "--online",
                             action="store_true", dest="online_installer", default=False,
                             help="create online installer")
    OPTION_PARSER.add_option("-r", "--create-repo",
                             action="store_true", dest="create_repository", default=False,
                             help="create offline repository")
    OPTION_PARSER.add_option("-s", "--strict",
                             action="store_true", dest="strict_mode", default=True,
                             help="use strict mode, abort on any error")
    OPTION_PARSER.add_option("-S", "--non-strict",
                             action="store_false", dest="strict_mode", default=True,
                             help="non strict mode, try to keep on going despite of errors")
    OPTION_PARSER.add_option("--archive-skip",
                             action="store_true", dest="archive_skip", default=False,
                             help="for testing purposes (faster testing), skip downloading archives")
    # optional override
    OPTION_PARSER.add_option("-u", "--archive-base-url",
                             action="store", dest="archive_base_url", default="",
                             help="define alternative server base url where to look for archives (.7z)")
    OPTION_PARSER.add_option("--ifw-tools",
                             action="store", dest="ifw_tools_uri", default="",
                             help="define alternative location where to fetch prebuilt Installer-Framework tools (.7z)")
    # installer naming scheme options, affects only the filename of the installer executable
    OPTION_PARSER.add_option("-l", "--license-type",
                             action="store", type="string", dest="license_type", default="opensource",
                             help="installer file name scheme: define license type")
    OPTION_PARSER.add_option("--preferred-installer-name",
                             action="store", type="string", dest="preferred_installer_name", default="",
                             help="alternatively define the full installer name excluding the extension (.run, .exe, .app)")
    # global key-value substitution
    OPTION_PARSER.add_option("--add-substitution",
                             action="extend", type="string", dest="global_key_value_substitution_list",
                             help="E.g. $LICENSE$=opensource -> will replace all occurrences in configuration files.")
    # forced version number bump for components
    OPTION_PARSER.add_option("--force-version-number-increase",
                             action="store_true", dest="force_version_number_increase", default=False,
                             help="If you wish to enable forced version number bump for components that have %VERSION_NUMBER_AUTO_INCREASE% tag in package.xml file(s)")
    # enable debug information files removal
    OPTION_PARSER.add_option("--remove-debug-information-files",
                             action="store_true", dest="remove_debug_information_files", default="False",
                             help="Removes debug information files. Besides 'True' and 'False' values accepts also debug file type as parameter")
    # enable debug libraries removal
    OPTION_PARSER.add_option("--remove-debug-libraries",
                             action="store_true", dest="remove_debug_libraries", default="False",
                             help="Removes libraries debug versions")
    # enable pdb files removal
    OPTION_PARSER.add_option("--remove-pdb-files",
                             action="store_true", dest="remove_pdb_files", default="False",
                             help="(Obsolete) Windows only: Removes Windows pdb files")
    # enable Windows debug libraries removal
    OPTION_PARSER.add_option("--remove-windows-debug-libraries",
                             action="store_true", dest="remove_windows_debug_libraries", default="False",
                             help="(Obsolete) Windows only: Removes Windows debug libraries")


##############################################################
# Print options
##############################################################
def print_options():
    """Print given command options."""
    print
    print '----------------------------------------'
    print ' Installer creation options'
    print '----------------------------------------'
    if ARCHIVE_SERVER_BASE_URL:
        print "Archive URL override:        " + ARCHIVE_SERVER_BASE_URL
    if INSTALLER_FRAMEWORK_TOOLS:
        print "IFW tools override:          " + INSTALLER_FRAMEWORK_TOOLS
    print "Configurations directory:    " + CONFIGURATIONS_DIR
    print "Configuration file:          " + MAIN_CONFIG_NAME
    print "Create online installer:     %r" % (CREATE_ONLINE_INSTALLER)
    print "Create offline installer:    %r" % (CREATE_OFFLINE_INSTALLER)
    print "Create repository:           %r" % (CREATE_REPOSITORY)
    print "MaintenanceTool rcc:         %r" % (CREATE_MAINTENANCE_TOOL_RESOURCE_FILE)
    print "Incremental mode:            %r" % (INCREMENTAL_MODE)
    print "Archive skip:                %r" % (ARCHIVE_DOWNLOAD_SKIP)
    print "Strict mode:                 %r" % (STRICT_MODE)
    print "Remove debug information files: %r" % (REMOVE_DEBUG_INFORMATION_FILES)
    print "Remove debug libraries:      %r" % (REMOVE_DEBUG_LIBRARIES)
    print "(Obsolete) Remove pdb files: %r" % (REMOVE_PDB_FILES)
    print "(Obsolete) Remove Windows debug libraries: %r" % (REMOVE_WINDOWS_DEBUG_LIBRARIES)
    print
    print "Installer naming scheme options:\n"
    print "License type:                " + LICENSE_TYPE
    print "Key-Value substitution list: "
    print KEY_SUBSTITUTION_LIST


##############################################################
# Parse command line arguments
##############################################################
def parse_cmd_line():
    """Parse command line arguments."""
    arg_count = len(sys.argv)
    if arg_count < 2:
        return False
    setup_option_parser()
    (options, dummy) = OPTION_PARSER.parse_args()

    global MAIN_CONFIG_NAME
    global INCREMENTAL_MODE
    global ARCHIVE_DOWNLOAD_SKIP
    global CREATE_ONLINE_INSTALLER
    global CREATE_OFFLINE_INSTALLER
    global CREATE_REPOSITORY
    global CREATE_MAINTENANCE_TOOL_RESOURCE_FILE
    global LICENSE_TYPE
    global CONFIGURATIONS_DIR
    global STRICT_MODE
    global ARCHIVE_SERVER_BASE_URL
    global INSTALLER_FRAMEWORK_TOOLS

    global KEY_SUBSTITUTION_LIST
    global PREFERRED_INSTALLER_NAME
    global VERSION_NUMBER_AUTO_INCREASE_VALUE
    global REMOVE_PDB_FILES
    global REMOVE_WINDOWS_DEBUG_LIBRARIES
    global REMOVE_DEBUG_INFORMATION_FILES
    global REMOVE_DEBUG_LIBRARIES

    CONFIGURATIONS_DIR                  = options.configurations_dir
    MAIN_CONFIG_NAME                    = options.configuration_file
    LICENSE_TYPE                        = options.license_type
    INCREMENTAL_MODE                    = options.incremental
    ARCHIVE_DOWNLOAD_SKIP               = options.archive_skip
    CREATE_ONLINE_INSTALLER             = options.online_installer
    CREATE_OFFLINE_INSTALLER            = options.offline_installer
    CREATE_REPOSITORY                   = options.create_repository
    STRICT_MODE                         = options.strict_mode
    ARCHIVE_SERVER_BASE_URL             = options.archive_base_url
    INSTALLER_FRAMEWORK_TOOLS           = options.ifw_tools_uri
    REMOVE_DEBUG_INFORMATION_FILES      = options.remove_debug_information_files
    REMOVE_DEBUG_LIBRARIES              = options.remove_debug_libraries
    REMOVE_PDB_FILES                    = options.remove_pdb_files
    REMOVE_WINDOWS_DEBUG_LIBRARIES      = options.remove_windows_debug_libraries

    if os.environ.get('CREATE_MAINTENANCE_TOOL_RESOURCE_FILE') in ['yes', 'true', '1']:
        CREATE_MAINTENANCE_TOOL_RESOURCE_FILE = True

    PREFERRED_INSTALLER_NAME                        = options.preferred_installer_name

    if options.force_version_number_increase:
        VERSION_NUMBER_AUTO_INCREASE_VALUE = '-' + strftime('%Y%m%d%H%M', gmtime())

    # key value substitution list init
    delimeter = '='
    if options.global_key_value_substitution_list:
        for item in options.global_key_value_substitution_list:
            if delimeter in item:
                key, value = item.split(delimeter)
                if key == "%REMOVE_PDB_FILES%":
                    REMOVE_PDB_FILES = value
                if key == "%REMOVE_WINDOWS_DEBUG_LIBRARIES%":
                    REMOVE_WINDOWS_DEBUG_LIBRARIES = value
                if key == "%REMOVE_DEBUG_INFORMATION_FILES%":
                    REMOVE_DEBUG_INFORMATION_FILES = value
                if key == "%REMOVE_DEBUG_LIBRARIES%":
                    REMOVE_DEBUG_LIBRARIES = value
                KEY_SUBSTITUTION_LIST.append([key, value])
    KEY_SUBSTITUTION_LIST.append(['%LICENSE%', LICENSE_TYPE])

    if CREATE_ONLINE_INSTALLER and CREATE_OFFLINE_INSTALLER:
        sys.stderr.write('*** Error! This script does not support (yet) creating offline and online installers at the same time!')
        sys.stderr.write('*** Choose either offline or online!')
        raise ValueError()
    if CREATE_ONLINE_INSTALLER and CREATE_REPOSITORY:
        sys.stderr.write('*** Error! This script does not support (yet) creating online installer and repository at the same time!')
        sys.stderr.write('*** Choose either online installer or repository creation!')
        raise ValueError()

    # check that given main configuration root dir exists
    if not os.path.isdir(CONFIGURATIONS_DIR):
        temp = CONFIGURATIONS_DIR = SCRIPT_ROOT_DIR + os.sep + CONFIGURATIONS_DIR
        if os.path.isdir(temp):
            CONFIGURATIONS_DIR = temp
        else:
            print '*** Unable to find given configurations root dir: ' + CONFIGURATIONS_DIR
    # check that given main configuration exits
    if not os.path.isfile(MAIN_CONFIG_NAME):
        temp = CONFIGURATIONS_DIR + os.sep + MAIN_CONFIG_NAME
        if os.path.isfile(temp):
            MAIN_CONFIG_NAME = temp
        else:
            print '*** Unable to find given main configuration file: ' + MAIN_CONFIG_NAME

    # print given options
    print_options()
    return True


##############################################################
# Initialize config parsers
##############################################################
def init_data():
    """Init data based on configuration files."""
    print '----------------------------------------'
    print ' Init Data'
    global CONFIG_PARSER_COMMON
    global CONFIG_PARSER_TARGET
    global PACKAGES_DIR_NAME_LIST
    global SDK_NAME
    global LICENSE_TYPE
    global SDK_NAME_ROOT
    global PACKAGE_NAMESPACE
    global PACKAGES_FULL_PATH_DST
    global IFW_TOOLS_DIR
    global ARCHIVE_LOCATION_RESOLVER
    global CONFIG_DIR_DST
    global PLATFORM_IDENTIFIER

    common_conf_path = CONFIGURATIONS_DIR + os.sep + COMMON_CONFIG_DIR_NAME + os.sep + COMMON_CONFIG_NAME
    target_conf_path = MAIN_CONFIG_NAME
    CONFIG_PARSER_COMMON = ConfigParser.ConfigParser()
    print ' Parsing: ' + common_conf_path
    CONFIG_PARSER_COMMON.readfp(open(common_conf_path))
    CONFIG_PARSER_TARGET = ConfigParser.ConfigParser()
    print ' Parsing: ' + target_conf_path
    CONFIG_PARSER_TARGET.readfp(open(target_conf_path))

    PLATFORM_IDENTIFIER = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'PlatformIdentifier')['identifier']
    check_platform_identifier(PLATFORM_IDENTIFIER)
    CONFIG_DIR_DST      = os.path.normpath(SCRIPT_ROOT_DIR + os.sep + 'config')
    SDK_NAME            = bldinstallercommon.config_section_map(CONFIG_PARSER_COMMON,'SdkCommon')['name']
    if not LICENSE_TYPE:
        LICENSE_TYPE        = bldinstallercommon.config_section_map(CONFIG_PARSER_COMMON,'SdkCommon')['license']
    SDK_NAME_ROOT       = SDK_NAME
    PACKAGE_NAMESPACE   = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'PackageNamespace')['name'].replace(" ", "").split(",")

    PACKAGES_FULL_PATH_DST = os.path.normpath(SCRIPT_ROOT_DIR + os.sep + PACKAGES_FULL_PATH_DST)
    packages_list_raw      = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'PackageTemplates')['template_dirs']
    packages_list_raw      = packages_list_raw.replace(' ', '')
    packages_list          = packages_list_raw.split(',')
    for package_template_dir in packages_list:
        package_template_dir = os.path.normpath(package_template_dir)
        # if the packages directory name is absolute path, then the packages templates (or static packages)
        # can reside outside the "<script_root_dir>/configurations" folder
        # otherwise the packages templates must be under "/configurations"
        if os.path.isabs(package_template_dir):
            PACKAGES_DIR_NAME_LIST.append(package_template_dir)
        else:
            # first check if the pkg templates are under assumed "/configurations/pkg_templates" directory
            pkg_template_dir = os.path.join(CONFIGURATIONS_DIR, pkg_constants.PKG_TEMPLATE_BASE_DIR_NAME, package_template_dir)
            if os.path.exists(pkg_template_dir):
                PACKAGES_DIR_NAME_LIST.append(pkg_template_dir)
            # if not then assume the old directory layout is being used
            else:
                PACKAGES_DIR_NAME_LIST.append(os.path.join(CONFIGURATIONS_DIR, package_template_dir))

    tools_dir_name = IFW_TOOLS_DIR_NAME
    IFW_TOOLS_DIR = SCRIPT_ROOT_DIR + os.sep + tools_dir_name
    IFW_TOOLS_DIR = os.path.normpath(IFW_TOOLS_DIR)

    # init data for archive locator
    ARCHIVE_LOCATION_RESOLVER = ArchiveLocationResolver(CONFIG_PARSER_TARGET, ARCHIVE_SERVER_BASE_URL, CONFIGURATIONS_DIR, KEY_SUBSTITUTION_LIST)
    ARCHIVE_LOCATION_RESOLVER.print_server_list()

    if DUMP_CONFIG:
        bldinstallercommon.dump_config(CONFIG_PARSER_COMMON, COMMON_CONFIG_NAME)
        bldinstallercommon.dump_config(CONFIG_PARSER_TARGET, MAIN_CONFIG_NAME)


##############################################################
# Cleanup
##############################################################
def clean_work_dirs():
    """Clean working directories."""
    print '----------------------------------------'
    print ' Cleaning environment'

    # delete "/packages"
    if os.path.exists(PACKAGES_FULL_PATH_DST):
        bldinstallercommon.remove_tree(PACKAGES_FULL_PATH_DST)
        print ' -> deleted old existing directory: ' + PACKAGES_FULL_PATH_DST
    # delete "/repositories"
    if os.path.exists(REPO_OUTPUT_DIR):
        bldinstallercommon.remove_tree(REPO_OUTPUT_DIR)
        print ' -> deleted old existing directory: ' + REPO_OUTPUT_DIR
    # delete "/config"
    if os.path.exists(CONFIG_DIR_DST):
        bldinstallercommon.remove_tree(CONFIG_DIR_DST)
        print ' -> deleted old existing directory: ' + CONFIG_DIR_DST


##############################################################
# Set the config directory
##############################################################
def set_config_directory():
    """Copy config directory into correct place."""
    print '----------------------------------------'
    print ' Set config directory'
    config_dir_template = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'ConfigDir')['template_name']
    config_dir_template = os.path.normpath(CONFIGURATIONS_DIR + os.sep + config_dir_template)

    if not os.path.exists(CONFIG_DIR_DST):
        bldinstallercommon.create_dirs(CONFIG_DIR_DST)
    bldinstallercommon.copy_tree(config_dir_template, CONFIG_DIR_DST)
    print ' -> copied [' + config_dir_template + '] into [' + CONFIG_DIR_DST + ']'


##############################################################
# Set the config.xml
##############################################################
def set_config_xml():
    """Copy config.xml template into correct place."""
    print '----------------------------------------'
    print ' Set config.xml'

    configxml_filename = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'ConfigXml')['template_name']
    config_template_source = CONFIGURATIONS_DIR + os.sep + PLATFORM_IDENTIFIER + os.sep + configxml_filename
    # if no config.xml template, we assume the "config" template dir already contains it
    if not os.path.exists(config_template_source):
        sys.stderr.write('*** Error!')
        sys.stderr.write('*** Given config.xml template does not exist: ' + config_template_source)
        sys.stderr.write('*** Abort!')
        raise ValueError()

    # name has to be config.xml for installer-framework
    config_template_dest_dir = CONFIG_DIR_DST
    config_template_dest = config_template_dest_dir + os.sep + 'config.xml'

    if os.path.exists(config_template_dest):
        os.remove(config_template_dest)
        print ' -> deleted old existing config.xml: ' + config_template_dest
    if not os.path.exists(config_template_dest_dir):
        bldinstallercommon.create_dirs(config_template_dest_dir)
    shutil.copy(config_template_source, config_template_dest)
    print ' -> copied [' + config_template_source + '] into [' + config_template_dest + ']'

    update_repository_url = bldinstallercommon.safe_config_key_fetch(CONFIG_PARSER_TARGET, 'SdkUpdateRepository', 'repository_url_release')

    fileslist = [config_template_dest]
    bldinstallercommon.replace_in_files(fileslist, UPDATE_REPOSITORY_URL_TAG, update_repository_url)
    # substitute values also from global substitution list
    for item in KEY_SUBSTITUTION_LIST:
        bldinstallercommon.replace_in_files(fileslist, item[0], item[1])
    return config_template_dest


##############################################################
# Substitute common version numbers etc., match against tags
##############################################################
def substitute_global_tags():
    """ Substitute common version numbers etc., match against tags """
    print '----------------------------------------'
    print 'Substituting global tags:'
    print '%PACKAGE_CREATION_DATE%        = ' + BUILD_TIMESTAMP
    print '%VERSION_NUMBER_AUTO_INCREASE% = ' + VERSION_NUMBER_AUTO_INCREASE_VALUE
    for item in KEY_SUBSTITUTION_LIST:
        print item[0] + ' = ' + item[1]

    # initialize the file list
    fileslist = []
    for directory in GENERAL_TAG_SUBST_LIST:
        for root, dummy, files in os.walk(directory):
            for name in files:
                path = os.path.join(root, name)
                fileslist.append(path)

    bldinstallercommon.replace_in_files(fileslist, PACKAGE_CREATION_DATE_TAG, BUILD_TIMESTAMP)
    bldinstallercommon.replace_in_files(fileslist, VERSION_NUMBER_AUTO_INCREASE_TAG, VERSION_NUMBER_AUTO_INCREASE_VALUE)
    for item in KEY_SUBSTITUTION_LIST:
        bldinstallercommon.replace_in_files(fileslist, item[0], item[1])


##############################################################
# Substitute component specifig tags
##############################################################
def substitute_component_tags(tag_pair_list, meta_dir_dest):
    """ Substitute component specific tags """
    if len(tag_pair_list) == 0:
        return
    print '   ----------------------------------------'
    print '   Substituting component specific tags'
    # initialize the file list
    fileslist = []

    for root, dummy, files in os.walk(meta_dir_dest):
        for name in files:
            path = os.path.join(root, name)
            fileslist.append(path)

    for pair in tag_pair_list:
        tag = pair[0]
        value = pair[1]
        if tag and value:
            print '    Matching [ ' + tag + ' ] and [ ' + value + ' ] in files list'
            bldinstallercommon.replace_in_files(fileslist, tag, value)
        else:
            print '    Warning! Ignoring incomplete tag pair [ ' + tag + ' ] for [ ' + value + ' ] pair'

##############################################################
# Create offline static component
##############################################################
def create_offline_static_component(target_config, section, static_package_src):
    """Create installable offline target component from static data."""
    print '--------------------------------------------------------------------------------'
    print ' Static package: [' + section + ']'
    # Create needed dirs
    package_dest_dir = os.path.normpath(PACKAGES_FULL_PATH_DST + os.sep + section)
    bldinstallercommon.create_dirs(package_dest_dir)
    # copy static content, assumption is that content is on local machine or on
    # accessible network share
    print '      Copying static package: '   + section
    print '              Package source: '   + static_package_src
    print '              Package dest:   '   + package_dest_dir
    bldinstallercommon.copy_tree(static_package_src, package_dest_dir)
    print '      Copying static package: Done!'
    print '--------------------------------------------------------------------------------'

##############################################################
# Parse SDK components
##############################################################
def parse_component_data(configuration_file, configurations_base_path):
    """Parse SDK component data"""
    global SDK_COMPONENT_LIST
    global SDK_COMPONENT_LIST_SKIPPED
    global SDK_COMPONENT_IGNORE_LIST
    file_full_path = configuration_file
    if not os.path.isfile(file_full_path):
        file_full_path = bldinstallercommon.locate_file(configurations_base_path, configuration_file)
    if not file_full_path:
        # check the 'all-os' directory
        allos_conf_file_dir = os.path.normpath(CONFIGURATIONS_DIR + os.sep + COMMON_CONFIG_DIR_NAME)
        file_full_path = bldinstallercommon.locate_file(allos_conf_file_dir, configuration_file)
    if not file_full_path:
        raise ValueError('*** Aborting, unable to locate the specified file. Check the configuration files for possible error(s).')
    print ' -> Reading target configuration file: ' + file_full_path
    configuration = ConfigParser.ConfigParser()
    configuration.readfp(open(file_full_path))

    # parse package ignore list first
    sdk_component_exclude_list = bldinstallercommon.safe_config_key_fetch(configuration, 'PackageIgnoreList', 'packages')
    if sdk_component_exclude_list:
        sdk_component_exclude_list = sdk_component_exclude_list.replace(' ', '')
        pkg_list = sdk_component_exclude_list.split(',')
        for item in pkg_list:
            SDK_COMPONENT_IGNORE_LIST.append(item)
    # parse sdk components
    for section in configuration.sections():
        sectionNameSpace = section.split(".")[0]
        if sectionNameSpace in PACKAGE_NAMESPACE:
            if section not in SDK_COMPONENT_IGNORE_LIST:
                sdk_component = SdkComponent(section, configuration, PACKAGES_DIR_NAME_LIST, ARCHIVE_LOCATION_RESOLVER, KEY_SUBSTITUTION_LIST, CREATE_OFFLINE_INSTALLER)
                if ARCHIVE_DOWNLOAD_SKIP:
                    sdk_component.setArchiveSkip(True)
                # validate component
                sdk_component.validate()
                if sdk_component.is_valid():
                    SDK_COMPONENT_LIST.append(sdk_component)
                else:
                    if CREATE_OFFLINE_INSTALLER and sdk_component.optional_for_offline_installer():
                        print('*** Warning! The [{0}] was not valid but it was marked optional for offline installers so skipping it.'.format(sdk_component.package_name))
                    else:
                        if STRICT_MODE:
                            print sdk_component.error_msg()
                            raise ValueError()
                        else:
                            print '!!! Ignored component in non-strict mode (missing archive data or metadata?): ' + section
                            SDK_COMPONENT_LIST_SKIPPED.append(sdk_component)
    # check for extra configuration files if defined
    extra_conf_list = bldinstallercommon.safe_config_key_fetch(configuration, 'PackageConfigurationFiles', 'file_list')
    if extra_conf_list:
        extra_conf_list = extra_conf_list.rstrip(',\n')
        file_list = extra_conf_list.split(',')
        for extra_conf_file in file_list:
            extra_conf_file = extra_conf_file.strip()
            # recursive call
            parse_component_data(extra_conf_file, configurations_base_path)


##############################################################
# Parse SDK components
##############################################################
def parse_components(target_config):
    """Parse SDK all components"""
    print '----------------------------------------'
    print ' Parse target configuration files'
    conf_base_path = CONFIGURATIONS_DIR + os.sep + PLATFORM_IDENTIFIER + os.sep
    main_conf_file = MAIN_CONFIG_NAME
    parse_component_data(main_conf_file, conf_base_path)
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

    return component_metadata_tag_pair_list

def get_component_data(sdk_component, archive, install_dir, data_dir_dest, compress_content_dir):
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
       and not archive.rpath_target \
       and sdk_component.target_install_base == '/' \
       and package_raw_name == archive.archive_name:
        print '     No repackaging actions required for the package, just download it directly to data directory'
        downloadedArchive = os.path.normpath(data_dir_dest + os.sep + package_raw_name)
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
                print 'Erasing doc: ' + doc_dir
                shutil.rmtree(doc_dir)
        if 'cleanup_doc_directory' in archive.package_finalize_items:
            cleanup_docs(install_dir)
        if 'qml_examples_only' in archive.package_finalize_items:
            examples_dir = bldinstallercommon.locate_directory(install_dir, 'examples')
            qml_examples_only(examples_dir)

    # remove debug information files when explicitly defined so
    if REMOVE_PDB_FILES.lower() != "false" or REMOVE_DEBUG_INFORMATION_FILES.lower() != "false":
        # don't remove debug information files from debug information archives
        if not archive.archive_name.endswith('debug-symbols.7z'):
            # Check if debug information file types are defined
            if REMOVE_PDB_FILES.lower() == "true" or REMOVE_DEBUG_INFORMATION_FILES.lower() == "true":
                # Remove debug information files according to host platform defaults
                remove_all_debug_information_files(install_dir)
            # Debug information file type is given as parameter
            else:
                # Remove debug information files regardless of host platform
                remove_debug_information_files_by_file_type(install_dir, REMOVE_DEBUG_INFORMATION_FILES.lower())

    # remove debug libraries
    if REMOVE_WINDOWS_DEBUG_LIBRARIES.lower() == "true" or REMOVE_DEBUG_LIBRARIES.lower() == "true":
        remove_all_debug_libraries(install_dir)

    if archive.rpath_target:
        if not archive.rpath_target.startswith(os.sep):
            archive.rpath_target = os.sep + archive.rpath_target
        if bldinstallercommon.is_linux_platform() or bldinstallercommon.is_solaris_platform():
            bldinstallercommon.handle_component_rpath(install_dir, archive.rpath_target)

    # lastly compress the component back to .7z archive
    content_list = os.listdir(compress_content_dir)
    #adding compress_content_dir in front of every item
    content_list = [(compress_content_dir + os.sep + x) for x in content_list]

    saveas = os.path.normpath(data_dir_dest + os.sep + archive.archive_name)
    cmd_args = [ ARCHIVEGEN_TOOL, saveas] + content_list
    bldinstallercommon.do_execute_sub_process(cmd_args, data_dir_dest)


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
            print 'Removing debug information files from: ' + debug_information_dir
            if debug_information_file_ending == 'dSYM':
                # On macOS, debug symbols are often in stand alone bundles. os.walk used by bldinstallercommon.py
                # helper functions doesn't support wildchars on path names so using glob instead
                list_of_debug_information_files = glob.glob(debug_information_dir + '/*.' + debug_information_file_ending)
                for debug_information in list_of_debug_information_files:
                    bldinstallercommon.remove_tree(debug_information)
            else:
               # This will only take the text connected to the debug information file by grabbing all non-space characters (\S)
               bldinstallercommon.delete_files_by_type_recursive(debug_information_dir, '\S*\.' + debug_information_file_ending)


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
            print 'Removing Windows debug libraries from: ' + windows_debug_library_dir
            # go through all library types and related qmake files
            debug_library_file_endings = ['dll', 'lib', 'prl']
            for debug_library_file_type in debug_library_file_endings:
                if os.path.exists(windows_debug_library_dir):
                    # make list of all debug library names
                    all_debug_files_list = bldinstallercommon.make_files_list(windows_debug_library_dir, '\S*d\.' + debug_library_file_type)
                    # in case library name ends with 'd' we need to keep that and remove only library with double d at the end of file name
                    double_d_debug_files_list = bldinstallercommon.make_files_list(windows_debug_library_dir, '\S*dd\.' + debug_library_file_type)
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
                            bldinstallercommon.delete_files_by_type_recursive(windows_debug_library_dir, '\S*d\.' + debug_library_file_type)
    # remove macOS debug libraries
    elif bldinstallercommon.is_mac_platform():
        for directory in ('bin', 'lib', 'qml', 'plugins'):
            macOS_debug_library_dir = bldinstallercommon.locate_directory(install_dir, directory)
            print 'Removing macOS debug libraries from: ' + macOS_debug_library_dir
            debug_library_file_ending = '_debug\.*'
            if os.path.exists(macOS_debug_library_dir):
                bldinstallercommon.delete_files_by_type_recursive(macOS_debug_library_dir, '\S*' + debug_library_file_ending)
    else:
        print 'Host was not Windows or macOS. For Linux and others we don\'t do anything at the moment'


##############################################################
# Create target components
##############################################################
def create_target_components(target_config):
    """Create target components."""
    global ROOT_COMPONENT_NAME
    if not os.path.lexists(PACKAGES_FULL_PATH_DST):
        bldinstallercommon.create_dirs(PACKAGES_FULL_PATH_DST)

    print '================================================================='
    print '= Creating SDK components'
    print '================================================================='
    print ''
    getComponentDataWork = ThreadedWork("get components data")
    for sdk_component in SDK_COMPONENT_LIST:
        # check first for top level component
        if sdk_component.root_component == 'yes':
            ROOT_COMPONENT_NAME = sdk_component.package_name
        # check if static component or not
        if sdk_component.static_component:
            create_offline_static_component(sdk_component)
            continue

        # not a static component so "build" it
        sdk_component.print_component_data()
        dest_base = PACKAGES_FULL_PATH_DST + os.sep + sdk_component.package_name + os.sep
        meta_dir_dest = os.path.normpath(dest_base + 'meta')
        data_dir_dest = os.path.normpath(dest_base + 'data')
        temp_data_dir = os.path.normpath(dest_base + 'tmp')
        # save path for later substitute_component_tags call
        sdk_component.meta_dir_dest = meta_dir_dest
        # create meta destination folder
        if not os.path.lexists(meta_dir_dest):
            bldinstallercommon.create_dirs(meta_dir_dest)
        # Copy Meta data
        metadata_content_source_root = os.path.normpath(sdk_component.pkg_template_dir + os.sep + 'meta')
        bldinstallercommon.copy_tree(metadata_content_source_root, meta_dir_dest)
        # add files into tag substitution
        GENERAL_TAG_SUBST_LIST.append(meta_dir_dest)
        # handle archives
        if sdk_component.downloadable_archive_list:
            # save path for later substitute_component_tags call
            sdk_component.temp_data_dir = temp_data_dir
            # Copy archives into temporary build directory if exists
            for archive in sdk_component.downloadable_archive_list:
                # fetch packages only if offline installer or repo creation, for online installer just handle the metadata
                if CREATE_OFFLINE_INSTALLER or CREATE_REPOSITORY:
                    # Create needed data dirs
                    compress_content_dir = os.path.normpath(temp_data_dir + os.sep + archive.archive_name)
                    install_dir = os.path.normpath(compress_content_dir + sdk_component.target_install_base + os.sep + archive.target_install_dir)

                    if INCREMENTAL_MODE and os.path.exists(os.path.join(data_dir_dest, archive.archive_name)):
                        continue
                    # adding get_component_data task to our work queue
                    # Create needed data dirs before the threads start to work
                    if not os.path.lexists(install_dir):
                        bldinstallercommon.create_dirs(install_dir)
                    if not os.path.lexists(data_dir_dest):
                        bldinstallercommon.create_dirs(data_dir_dest)
                    if platform.system().lower().startswith('win'):
                        install_dir = win32api.GetShortPathName(install_dir)
                        data_dir_dest = win32api.GetShortPathName(data_dir_dest)
                    getComponentDataWork.addTask("adding {0} to {1}".format(archive.archive_name, sdk_component.package_name),
                                                 get_component_data, sdk_component, archive, install_dir, data_dir_dest, compress_content_dir)

    if not ARCHIVE_DOWNLOAD_SKIP:
        # start the work threaded, more then 8 parallel downloads are not so useful
        getComponentDataWork.run(min([8, multiprocessing.cpu_count()]))

    for sdk_component in SDK_COMPONENT_LIST:
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
        print '*** Given examples directory is not valid path: ' + examples_dir
        print '*** Archive not cleaned'
        return
    subdir_list = []
    regex = re.compile('^qml\S.*')
    for root, dirs, dummy in os.walk(examples_dir):
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
            print "QML example package: " + submodule
        else:
            delete_dir = os.path.join(root_dir, submodule)
            print "Delete non qml examples directory" + delete_dir
            shutil.rmtree(delete_dir)


##############################################################
# Cleanup unnecessary documentation files
##############################################################
def cleanup_docs(install_dir):
    if not os.path.isdir(install_dir):
        print '*** Given docs directory is not valid path: ' + install_dir
        print '*** Archive not cleaned'
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
                print 'Cleaning up -> deleting directory: ' + item
                shutil.rmtree(item, ignore_errors=True)
        # then remove unnecessary files
        for filename in os.listdir(submodule):
            if filename.endswith(('.qdocconf', '.sha1', '.html')):
                full_filename = os.path.join(submodule, filename)
                if os.path.isfile(full_filename):
                    print 'Cleaning up -> deleting file: ' + full_filename
                    os.remove(full_filename)


##############################################################
# Install Installer-Framework tools
##############################################################
def install_ifw_tools():
    """Setup Installer-Framework tools."""
    print '=================================================='
    print '= Install Installer Framework tools'
    print '=================================================='
    global ARCHIVEGEN_TOOL
    global BINARYCREATOR_TOOL
    global INSTALLERBASE_TOOL
    global REPOGEN_TOOL

    package_save_as_temp = None

    if os.path.exists(IFW_TOOLS_DIR):
        shutil.rmtree(IFW_TOOLS_DIR)

    if INSTALLER_FRAMEWORK_TOOLS:
        package_url = INSTALLER_FRAMEWORK_TOOLS
    else:
        package_url = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'InstallerFrameworkTools')['package_url']
    # create needed dirs
    bldinstallercommon.create_dirs(IFW_TOOLS_DIR)
    package_save_as_temp = IFW_TOOLS_DIR + os.sep + os.path.basename(package_url)
    package_save_as_temp = os.path.normpath(package_save_as_temp)
    if not(INCREMENTAL_MODE and os.path.exists(package_save_as_temp)):
        print ' Source url:   ' + package_url
        print ' Install dest: ' + package_save_as_temp
        # download IFW archive
        if not package_url == '':
            print ' Downloading:  ' + package_url
            res = bldinstallercommon.is_content_url_valid(package_url)
            if not(res):
                sys.stderr.write('*** Package URL is invalid: [' + package_url + ']')
                sys.stderr.write('*** Abort!')
                raise ValueError()
            bldinstallercommon.retrieve_url(package_url, package_save_as_temp)
        if not (os.path.isfile(package_save_as_temp)):
            sys.stderr.write('*** Downloading failed! Aborting!')
            raise RuntimeError()
        # extract IFW archive
        bldinstallercommon.extract_file(package_save_as_temp, IFW_TOOLS_DIR)
        os.remove(package_save_as_temp)
        dir_items = os.listdir(IFW_TOOLS_DIR)
        items = len(dir_items)
        if items == 1:
            dir_name = dir_items[0]
            os.chdir(IFW_TOOLS_DIR)
            bldinstallercommon.move_tree(dir_name, '.')
            bldinstallercommon.remove_tree(IFW_TOOLS_DIR + os.sep + dir_name)
            os.chdir(SCRIPT_ROOT_DIR)
        else:
            sys.stderr.write('*** Unsupported dir structure for installer-framework-tools package?!')
            sys.stderr.write('*** Abort!')
            raise RuntimeError()

    executable_suffix = bldinstallercommon.get_executable_suffix()
    ARCHIVEGEN_TOOL = bldinstallercommon.locate_executable(IFW_TOOLS_DIR, 'archivegen' + executable_suffix)
    BINARYCREATOR_TOOL = bldinstallercommon.locate_executable(IFW_TOOLS_DIR, 'binarycreator' + executable_suffix)
    INSTALLERBASE_TOOL = bldinstallercommon.locate_executable(IFW_TOOLS_DIR, 'installerbase' + executable_suffix)
    REPOGEN_TOOL = bldinstallercommon.locate_executable(IFW_TOOLS_DIR, 'repogen' + executable_suffix)
    # check
    if not (os.path.isfile(ARCHIVEGEN_TOOL)):
        raise IOError('*** Archivegen tool not found: ' + ARCHIVEGEN_TOOL)
    if not (os.path.isfile(BINARYCREATOR_TOOL)):
        raise IOError('*** Binarycreator tool not found: ' + BINARYCREATOR_TOOL)
    if not (os.path.isfile(INSTALLERBASE_TOOL)):
        raise IOError('*** Installerbase tool not found: ' + INSTALLERBASE_TOOL)
    if not (os.path.isfile(REPOGEN_TOOL)):
        raise IOError('*** Repogen tool not found: ' + REPOGEN_TOOL)

    print ' ARCHIVEGEN_TOOL: ' + ARCHIVEGEN_TOOL
    print ' BINARYCREATOR_TOOL: ' + BINARYCREATOR_TOOL
    print ' INSTALLERBASE_TOOL: ' + INSTALLERBASE_TOOL
    print ' REPOGEN_TOOL: ' + REPOGEN_TOOL


##############################################################
# Create the final installer binary
##############################################################
def create_installer_binary():
    """Create installer binary files using binarycreator tool."""
    print '=================================================='
    print '= Create installer binary'
    print '=================================================='
    global SDK_NAME

    # naming scheme: qt-<platform>-<license>-<version>-<tag>-<compiler>-<target_arch>-<offline/online>.<extension>
    #    license is opensource or commercial
    #    extension is exe, dmg, or run
    #    tag is alpha1, beta2, rc1, etc (no tag for final).
    #    platform is win, linux, mac, etc.
    platform        = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'PlatformIdentifier')['identifier']
    installer_type  = 'offline' if CREATE_OFFLINE_INSTALLER else 'online'
    extension       = '.run' if bldinstallercommon.is_linux_platform() else ''

    if not PREFERRED_INSTALLER_NAME:
        SDK_NAME = SDK_NAME + '-' + platform + '-' + LICENSE_TYPE
        SDK_NAME = SDK_NAME + '-' + installer_type
    else:
        SDK_NAME = PREFERRED_INSTALLER_NAME
    SDK_NAME += extension

    # if online installer only
    if CREATE_ONLINE_INSTALLER:
        # binarycreator arguments
        cmd_args = [BINARYCREATOR_TOOL, '-t', INSTALLERBASE_TOOL, '-v', '-p', PACKAGES_FULL_PATH_DST]
        cmd_args = cmd_args + ['--online-only', '-c', CONFIG_DIR_DST + os.sep + 'config.xml', SDK_NAME]

    # if offline-only installer
    if CREATE_OFFLINE_INSTALLER:
        cmd_args = [BINARYCREATOR_TOOL, '--offline-only']
        cmd_args = cmd_args + ['-t', INSTALLERBASE_TOOL, '-v', '-p', PACKAGES_FULL_PATH_DST]
        # check if package exclude list should be used for offline installer
        package_exclude_list = bldinstallercommon.safe_config_key_fetch(CONFIG_PARSER_TARGET, 'OfflinePackageExcludeList', 'package_list')
        package_exclude_list = package_exclude_list.replace('\n', '')
        if package_exclude_list:
            cmd_args = cmd_args + ['-e', package_exclude_list]
        cmd_args = cmd_args + ['-c', CONFIG_DIR_DST + os.sep + 'config.xml', SDK_NAME]

    # use license resource file if given
    license_resource_file = os.path.join(CONFIG_DIR_DST, 'license.qrc')
    if os.path.isfile(license_resource_file):
        cmd_args = cmd_args + ['-r', license_resource_file]

    # create installer binary
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)

    # move results to dedicated directory
    output_dir = os.path.join(SCRIPT_ROOT_DIR, pkg_constants.INSTALLER_OUTPUT_DIR_NAME)
    bldinstallercommon.create_dirs(output_dir)
    file_name = os.path.join(SCRIPT_ROOT_DIR, SDK_NAME)
    old_existing_file_name = os.path.join(output_dir, SDK_NAME)
    if bldinstallercommon.is_mac_platform():
        file_name = file_name + '.app'
        old_existing_file_name = old_existing_file_name + '.app'
    if bldinstallercommon.is_win_platform():
        file_name = file_name + '.exe'
        old_existing_file_name = old_existing_file_name + '.exe'
    # remove old if exists
    if os.path.isfile(old_existing_file_name):
        print 'Deleting old existing file: ' + old_existing_file_name
        os.remove(old_existing_file_name)
    print 'Moving: [' + file_name + '] into: [' + output_dir + ']'
    shutil.move(file_name, output_dir)


##############################################################
# Create the repository
##############################################################
def create_online_repository():
    """Create online repository using repogen tool."""
    print '=================================================='
    print '= Create online repository'
    print '=================================================='

    # handle special case if MaintenanceTool repository build and
    # update.rcc update requeste
    if CREATE_MAINTENANCE_TOOL_RESOURCE_FILE:
        create_maintenance_tool_resource_file()

    # repogen arguments
    if CREATE_REPOSITORY:
        print 'Creating repository for the SDK ...'
        print '    Outputdir: ' + REPO_OUTPUT_DIR
        print '      pkg src: ' + PACKAGES_FULL_PATH_DST
        repogen_args = [REPOGEN_TOOL, '-p', PACKAGES_FULL_PATH_DST, REPO_OUTPUT_DIR]
        # create repository
        bldinstallercommon.do_execute_sub_process(repogen_args, SCRIPT_ROOT_DIR)
        if not os.path.exists(REPO_OUTPUT_DIR):
            raise IOError('*** Fatal error! Unable to create repository directory: ' + REPO_OUTPUT_DIR)


##############################################################
# Create MaintenanceTool resource file
##############################################################
def create_maintenance_tool_resource_file():
    """Create MaintenanceTool resource file."""
    print '=================================================='
    print '= Create MaintenanceTool resource file'
    print '=================================================='
    set_config_directory()
    config_xml = set_config_xml()
    cmd_args = [BINARYCREATOR_TOOL, '--online-only', '-p', PACKAGES_FULL_PATH_DST, '-c', config_xml, '-rcc']
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)
    # archive
    resource_file = os.path.join(SCRIPT_ROOT_DIR, 'update.rcc')
    installer_base_archive = bldinstallercommon.locate_file(PACKAGES_FULL_PATH_DST, '*installerbase*')
    if not os.path.isfile(installer_base_archive):
        print('*** Unable to locate installerbase archive from: {0}'.format(PACKAGES_FULL_PATH_DST))
        print('*** update.rcc will not be included in the MaintenanceTool repository!')
        return
    # inject the resource file to the same archive where installerbase is
    inject_update_rcc_to_archive(installer_base_archive, resource_file)


###############################
# function
###############################
def inject_update_rcc_to_archive(archive_file_path, file_to_be_injected):
    print('Injecting file [{0}] into [{1}]'.format(file_to_be_injected, archive_file_path))
    if not os.path.isfile(file_to_be_injected):
        print('*** Unable to locate file: {0}'.format(file_to_be_injected))
    if not os.path.isfile(archive_file_path):
        print('*** Unable to locate file: {0}'.format(archive_file_path))
    archive_file_name = os.path.basename(archive_file_path)
    print(archive_file_name)
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
def create_mac_disk_image():
    """Create Apple disk image."""
    print '=================================================='
    print '= Create Apple disk image'
    print '=================================================='

    # create disk image
    cmd_args = ['hdiutil', 'create', '-srcfolder', \
                os.path.join(SCRIPT_ROOT_DIR, pkg_constants.INSTALLER_OUTPUT_DIR_NAME, SDK_NAME + '.app'), \
                '-volname', SDK_NAME, \
                '-format', 'UDBZ', \
                os.path.join(SCRIPT_ROOT_DIR, pkg_constants.INSTALLER_OUTPUT_DIR_NAME, SDK_NAME + '.dmg'), \
                '-ov', '-scrub', '-size', '4g']
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)


##############################################################
# Print warnings
##############################################################
def print_warnings():
    """Print warnings."""
    # check if any components were skipped
    if SDK_COMPONENT_LIST_SKIPPED:
        print ''
        print 'Warning! The following components were not included in offline'
        print '         installer or in online repository. The reason may be that'
        print '         the script was run in non-strict mode and the packages'
        print '         had incomplete metadata or the archive (.7z) was missing?'
        print ''
        for item in SDK_COMPONENT_LIST_SKIPPED:
            print '*** ' + item.package_name


##############################################################
# All main build steps
##############################################################
def create_installer():
    """Installer creation main steps."""
    print ''
    print ''
    print '=================================================='
    print '= Creating SDK'
    print '=================================================='
    # init
    bldinstallercommon.init_common_module(SCRIPT_ROOT_DIR)
    # check required tools
    check_required_tools()
    # init data
    init_data()
    # clean env before starting
    if not INCREMENTAL_MODE:
        clean_work_dirs()
    # set config templates
    if CREATE_ONLINE_INSTALLER or CREATE_OFFLINE_INSTALLER:
        set_config_directory()
        set_config_xml()
    # install Installer Framework tools
    install_ifw_tools()
    # parse SDK components
    parse_components(CONFIG_PARSER_TARGET)
    # create components
    create_target_components(CONFIG_PARSER_TARGET)
    # substitute global tags
    substitute_global_tags()
    # create the installer binary
    if CREATE_ONLINE_INSTALLER or CREATE_OFFLINE_INSTALLER:
        create_installer_binary()
        # for mac we need some extra work
        if bldinstallercommon.is_mac_platform():
            create_mac_disk_image()
    if CREATE_REPOSITORY:
        create_online_repository()
    # print warning messages if encountered any problems
    print_warnings()


##############################################################
# Start build process
##############################################################
main()
