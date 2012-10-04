#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2012 Digia Plc and/or its subsidiary(-ies).
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
from time import gmtime, strftime
import urllib
from optparse import OptionParser

import bldinstallercommon
import bld_ifw_tools_impl
from archiveresolver import ArchiveLocationResolver
from sdkcomponent import SdkComponent

# ----------------------------------------------------------------------
BUILD_TIMESTAMP             = strftime('%d-%b-%Y', gmtime())
CONFIG_PARSER_COMMON        = 0
CONFIG_PARSER_TARGET        = 0
OPTION_PARSER               = 0
PLATFORM_IDENTIFIER         = ''
MAIN_CONFIG_NAME            = ''
SCRIPT_ROOT_DIR             = os.getcwd()
GENERAL_TAG_SUBST_LIST      = []
CONFIGURATIONS_DIR          = 'configurations'
CONFIG_DIR_DST              = 'config'
COMMON_CONFIG_NAME          = 'common'
COMMON_CONFIG_DIR_NAME      = 'all-os'
REPO_OUTPUT_DIR             = os.path.normpath(SCRIPT_ROOT_DIR + os.sep + 'repository')
SDK_VERSION_NUMBER          = ''
SDK_VERSION_TAG             = ''
PACKAGES_DIR_NAME_LIST      = []
PACKAGES_FULL_PATH_DST      = 'pkg'
ROOT_COMPONENT_NAME         = ''
PACKAGE_NAMESPACE           = ''
IFW_TOOLS_DIR               = ''
ARCHIVEGEN_TOOL             = ''
BINARYCREATOR_TOOL          = ''
INSTALLERBASE_TOOL          = ''
REPOGEN_TOOL                = ''
SDK_NAME_ROOT               = ''
SDK_NAME                    = ''
DEBUG_RPATH                 = False
DUMP_CONFIG                 = False
DEVELOPMENT_MODE            = False
INCREMENTAL_MODE            = False
CREATE_ONLINE_INSTALLER     = False
CREATE_OFFLINE_INSTALLER    = False
CREATE_REPOSITORY           = False
NO_REMOTE_BACKEND           = False
ARCHIVE_LOCATION_RESOLVER   = None
SDK_COMPONENT_LIST          = []
SDK_COMPONENT_LIST_SKIPPED  = []
SDK_COMPONENT_IGNORE_LIST   = []
USE_LEGACY_IFW              = False
STRICT_MODE                 = True
ARCHIVE_SERVER_BASE_URL     = ''

INSTALLER_NAMING_SCHEME_COMPILER    = ''
INSTALLER_NAMING_SCHEME_TARGET_ARCH = ''
LICENSE_TYPE                = ''

TARGET_INSTALL_DIR_NAME_TAG         = '%TARGET_INSTALL_DIR%'
PACKAGE_DEFAULT_TAG                 = '%PACKAGE_DEFAULT_TAG%'
SDK_VERSION_NUM_TAG                 = '%SDK_VERSION_NUM%'
UPDATE_REPOSITORY_URL_TAG           = '%UPDATE_REPOSITORY_URL%'
PACKAGE_CREATION_DATE_TAG           = '%PACKAGE_CREATION_DATE%'
INSTALL_PRIORITY_TAG                = '%INSTALL_PRIORITY%'
SORTING_PRIORITY_TAG                = '%SORTING_PRIORITY%'
# ----------------------------------------------------------------------


##############################################################
# Start
##############################################################
def main():
    """ Start """
    if parse_cmd_line():
        create_installer()
        sys.exit(0)
    else:
        sys.exit(-1)


##############################################################
# Check that valid tools are present in the build environment
##############################################################
def check_required_tools():
    """Check that valid tools are present in the build environment."""
    found = False
    tool_name = '7z'
    if bldinstallercommon.is_win_platform():
        tool_name = tool_name + '.exe'
    for p in os.environ["PATH"].split(os.pathsep):
        found = os.path.exists(os.path.join(p, tool_name))
        if found:
            break

    if not found:
        print '*** Error! Required tools are not present in the system (7z)'
        print '*** Abort!'
        sys.exit(-1)


##############################################################
# Check if valid platform identifier
##############################################################
def check_platform_identifier(platform_identifier):
    """Check if given platform identifier is valid."""
    path_to_be_checked = SCRIPT_ROOT_DIR + os.sep + CONFIGURATIONS_DIR + os.sep + platform_identifier
    if os.path.exists(path_to_be_checked):
        return
    print '*** Unsupported platform identifier given: ' + platform_identifier
    print '*** Following directory can not be found:   ' + path_to_be_checked
    sys.exit(-1)


##############################################################
# Check if valid configuration file
##############################################################
def check_configuration_file(configuration_name):
    """ Check if valid configuration file """
    path_to_be_checked = SCRIPT_ROOT_DIR + os.sep + CONFIGURATIONS_DIR + os.sep + configuration_name
    if os.path.isfile(path_to_be_checked):
        return
    print '*** Unable to find given configuration file: ' + path_to_be_checked
    sys.exit(-1)


##############################################################
# Setup Option Parser
##############################################################
def setup_option_parser():
    """ Set up Option Parser """
    global OPTION_PARSER
    OPTION_PARSER = OptionParser()
    OPTION_PARSER.add_option("-c", "--configurations-dir",
                      action="store", type="string", dest="configurations_dir", default="configurations",
                      help="define configurations directory where to read installer configuration files")
    OPTION_PARSER.add_option("-f", "--configuration-file",
                      action="store", type="string", dest="configuration_file", default="",
                      help="define configurations directory where to read installer configuration files")

    OPTION_PARSER.add_option("-d", "--devmode",
                      action="store_true", dest="devmode", default=False,
                      help="enable development mode, build static Qt and IFW from sources")
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
    OPTION_PARSER.add_option("-g", "--legacy-repogen",
                      action="store_true", dest="legacy_repogen", default=False,
                      help="use legacy repogen, uses different cmd line syntax")
    OPTION_PARSER.add_option("-s", "--strict",
                      action="store_true", dest="strict_mode", default=True,
                      help="use strict mode, abort on any error")
    OPTION_PARSER.add_option("-S", "--non-strict",
                      action="store_false", dest="strict_mode", default=True,
                      help="non strict mode, try to keep on going despite of errors")
    # optional override
    OPTION_PARSER.add_option("-u", "--archive-base-url",
                      action="store", dest="archive_base_url", default="",
                      help="define alternative server base url where to look for archives (.7z)")
    # installer naming scheme options, affects only the filename of the installer executable
    OPTION_PARSER.add_option("-l", "--license-type",
                      action="store", type="string", dest="license_type", default="opensource",
                      help="installer file name scheme: define license type")
    OPTION_PARSER.add_option("-a", "--target-architecture",
                      action="store", type="string", dest="target_architecture", default="",
                      help="installer file name scheme: define target architecture name")
    OPTION_PARSER.add_option("-e", "--compiler-name",
                      action="store", type="string", dest="compiler_name", default="",
                      help="installer file name scheme: define compile name")


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
    print "Configurations directory:    " + CONFIGURATIONS_DIR
    print "Configuration file:          " + MAIN_CONFIG_NAME
    print "Create online installer:     %r" % (CREATE_ONLINE_INSTALLER)
    print "Create offline installer:    %r" % (CREATE_OFFLINE_INSTALLER)
    print "Create repository:           %r" % (CREATE_REPOSITORY)
    print "Development mode:            %r" % (DEVELOPMENT_MODE)
    print "Incremental mode:            %r" % (INCREMENTAL_MODE)
    print "Legacy IFW:                  %r" % (USE_LEGACY_IFW)
    print "Strict mode:                 %r" % (STRICT_MODE)
    print
    print "Installer naming scheme options:\n"
    print "License type:                " + LICENSE_TYPE
    print "Compiler type:               " + INSTALLER_NAMING_SCHEME_COMPILER
    print "Target arch:                 " + INSTALLER_NAMING_SCHEME_TARGET_ARCH


##############################################################
# Parse command line arguments
##############################################################
def parse_cmd_line():
    """Parse command line arguments."""
    arg_count = len(sys.argv)
    if arg_count < 2:
        return False
    setup_option_parser()
    (options, args) = OPTION_PARSER.parse_args()

    global MAIN_CONFIG_NAME
    global DEVELOPMENT_MODE
    global INCREMENTAL_MODE
    global CREATE_ONLINE_INSTALLER
    global CREATE_OFFLINE_INSTALLER
    global CREATE_REPOSITORY
    global NO_REMOTE_BACKEND
    global USE_LEGACY_IFW
    global INSTALLER_NAMING_SCHEME_COMPILER
    global INSTALLER_NAMING_SCHEME_TARGET_ARCH
    global LICENSE_TYPE
    global CONFIGURATIONS_DIR
    global STRICT_MODE
    global ARCHIVE_SERVER_BASE_URL

    CONFIGURATIONS_DIR                  = options.configurations_dir
    MAIN_CONFIG_NAME                    = options.configuration_file
    LICENSE_TYPE                        = options.license_type
    DEVELOPMENT_MODE                    = options.devmode
    INCREMENTAL_MODE                    = options.incremental
    CREATE_ONLINE_INSTALLER             = options.online_installer
    CREATE_OFFLINE_INSTALLER            = options.offline_installer
    CREATE_REPOSITORY                   = options.create_repository
    USE_LEGACY_IFW                      = options.legacy_repogen
    STRICT_MODE                         = options.strict_mode
    INSTALLER_NAMING_SCHEME_TARGET_ARCH = options.target_architecture
    INSTALLER_NAMING_SCHEME_COMPILER    = options.compiler_name
    ARCHIVE_SERVER_BASE_URL             = options.archive_base_url

    if INCREMENTAL_MODE:
        DEVELOPMENT_MODE = True
    if CREATE_ONLINE_INSTALLER and CREATE_OFFLINE_INSTALLER:
        print '*** Error! This script does not support (yet) creating offline and online installers at the same time!'
        print '*** Choose either offline or online!'
        sys.exit(-1)
    if CREATE_ONLINE_INSTALLER and CREATE_REPOSITORY:
        print '*** Error! This script does not support (yet) creating online installer and repository at the same time!'
        print '*** Choose either online installer or repository creation!'
        sys.exit(-1)

    # check that given configuration exits
    check_configuration_file(MAIN_CONFIG_NAME)
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
    global SDK_VERSION_NUMBER
    global SDK_VERSION_TAG
    global SDK_NAME
    global LICENSE_TYPE
    global SDK_NAME_ROOT
    global PACKAGE_NAMESPACE
    global PACKAGES_FULL_PATH_DST
    global IFW_TOOLS_DIR
    global ARCHIVE_LOCATION_RESOLVER
    global CONFIG_DIR
    global PLATFORM_IDENTIFIER

    if DEVELOPMENT_MODE:
        print ' --------------------------'
        print ' [Development mode enabled]'
        print ' --------------------------'

    common_conf_path = SCRIPT_ROOT_DIR + os.sep + CONFIGURATIONS_DIR + os.sep + COMMON_CONFIG_DIR_NAME + os.sep + COMMON_CONFIG_NAME
    target_conf_path = SCRIPT_ROOT_DIR + os.sep + CONFIGURATIONS_DIR + os.sep + MAIN_CONFIG_NAME
    CONFIG_PARSER_COMMON = ConfigParser.ConfigParser()
    print ' Parsing: ' + common_conf_path
    CONFIG_PARSER_COMMON.readfp(open(common_conf_path))
    CONFIG_PARSER_TARGET = ConfigParser.ConfigParser()
    print ' Parsing: ' + target_conf_path
    CONFIG_PARSER_TARGET.readfp(open(target_conf_path))

    PLATFORM_IDENTIFIER = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'PlatformIdentifier')['identifier']
    check_platform_identifier(PLATFORM_IDENTIFIER)
    CONFIG_DIR_DST      = os.path.normpath(SCRIPT_ROOT_DIR + os.sep + 'config')
    PACKAGES_DIR_NAME   = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'WorkingDirectories')['packages_dir']
    PACKAGES_DIR_NAME   = os.path.normpath(PACKAGES_DIR_NAME)
    SDK_VERSION_NUMBER  = bldinstallercommon.config_section_map(CONFIG_PARSER_COMMON,'SdkCommon')['version']
    SDK_VERSION_TAG     = bldinstallercommon.config_section_map(CONFIG_PARSER_COMMON,'SdkCommon')['tag']
    SDK_NAME            = bldinstallercommon.config_section_map(CONFIG_PARSER_COMMON,'SdkCommon')['name']
    if not LICENSE_TYPE:
        LICENSE_TYPE        = bldinstallercommon.config_section_map(CONFIG_PARSER_COMMON,'SdkCommon')['license']
    SDK_NAME_ROOT       = SDK_NAME
    PACKAGE_NAMESPACE   = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'PackageNamespace')['name']

    PACKAGES_FULL_PATH_DST = os.path.normpath(SCRIPT_ROOT_DIR + os.sep + PACKAGES_FULL_PATH_DST)
    packages_list_raw      = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'WorkingDirectories')['packages_dir']
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
            PACKAGES_DIR_NAME_LIST.append(os.path.normpath(SCRIPT_ROOT_DIR + os.sep + CONFIGURATIONS_DIR + os.sep + package_template_dir))

    if not DEVELOPMENT_MODE:
        tools_dir_name = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'InstallerFrameworkTools')['name']
        IFW_TOOLS_DIR = SCRIPT_ROOT_DIR + os.sep + tools_dir_name
        IFW_TOOLS_DIR = os.path.normpath(IFW_TOOLS_DIR)

    # init data for archive locator
    ARCHIVE_LOCATION_RESOLVER = ArchiveLocationResolver(CONFIG_PARSER_TARGET, ARCHIVE_SERVER_BASE_URL, SCRIPT_ROOT_DIR + os.sep + CONFIGURATIONS_DIR)
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
    # delete "/ifw-tools"
    if os.path.exists(IFW_TOOLS_DIR):
        bldinstallercommon.remove_tree(IFW_TOOLS_DIR)
        print ' -> deleted old existing directory: ' + IFW_TOOLS_DIR
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
    config_dir_template = os.path.normpath(SCRIPT_ROOT_DIR + os.sep + CONFIGURATIONS_DIR + os.sep + config_dir_template)

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
    config_template_source = SCRIPT_ROOT_DIR + os.sep + CONFIGURATIONS_DIR + os.sep + PLATFORM_IDENTIFIER + os.sep + configxml_filename
    # if no config.xml template, we assume the "config" template dir already contains it
    if not os.path.exists(config_template_source):
        print '*** Error!'
        print '*** Given config.xml template does not exist: ' + config_template_source
        print '*** Abort!'
        sys.exit(-1)

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

    update_repository_url = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'SdkUpdateRepository')['repository_url_release']

    fileslist = [config_template_dest]
    bldinstallercommon.replace_in_files(fileslist, SDK_VERSION_NUM_TAG, SDK_VERSION_NUMBER)
    bldinstallercommon.replace_in_files(fileslist, UPDATE_REPOSITORY_URL_TAG, update_repository_url)


##############################################################
# Substitute common version numbers etc., match against tags
##############################################################
def substitute_global_tags():
    """ Substitute common version numbers etc., match against tags """
    print ' ----------------------------------------'
    print ' Substituting global tags:'
    print '    %PACKAGE_CREATION_DATE% = ' + BUILD_TIMESTAMP
    print '    %SDK_VERSION_NUM%       = ' + SDK_VERSION_NUMBER

    # initialize the file list
    fileslist = []
    for directory in GENERAL_TAG_SUBST_LIST:
        for root, dirs, files in os.walk(directory):
            for name in files:
                path = os.path.join(root, name)
                fileslist.append(path)

    bldinstallercommon.replace_in_files(fileslist, SDK_VERSION_NUM_TAG, SDK_VERSION_NUMBER)
    bldinstallercommon.replace_in_files(fileslist, PACKAGE_CREATION_DATE_TAG, BUILD_TIMESTAMP)


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

    for root, dirs, files in os.walk(meta_dir_dest):
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
# Repackage content of the installable compoment
##############################################################
def repackage_content_for_installation(install_dir, package_raw_name, target_install_base, rpath_target, package_strip_dirs, package_name, archive_name):
    """Repackage content into 7z archive."""
    # if no data to be installed, then just return
    if not package_raw_name:
        return
    if not package_strip_dirs:
        package_strip_dirs = '0'

    print '     +++++++++++++++++++++++++++++++++++++++++'
    print '     Repackage:             ' + package_raw_name
    print '     Location:              ' + install_dir
    print '     Dirs to be stripped:   ' + package_strip_dirs
    if not rpath_target:
        print '     Relocate RPath:        No'
    else:
        print '     Relocate RPath into:   ' + '(' + install_dir + ') '+ rpath_target
    print ''

    if package_raw_name.endswith('.7z') and package_strip_dirs == '0' and not rpath_target and target_install_base == '/':
        print '     No repackaging actions requred for the package'
        return

    # extract contents
    extracted = bldinstallercommon.extract_file(install_dir + os.sep + package_raw_name, install_dir)
    # remove old package
    if extracted:
        os.remove(install_dir + os.sep + package_raw_name)
    # strip out unnecessary folder structure based on the configuration
    count = 0
    iterations = int(package_strip_dirs)
    while(count < iterations):
        #print 'Strip iteration: ' + str(count)
        count = count + 1
        l = os.listdir(install_dir)
        items = len(l)
        if items == 1:
            dir_name = l[0]
            os.chdir(install_dir)
            # TODO, windows hack, on windows path+filename > 255 causes error, so truncate temp path as much as possible
            temp_path_name = 'a'
            os.rename(dir_name, temp_path_name)
            bldinstallercommon.move_tree(temp_path_name, '.')
            bldinstallercommon.remove_tree(install_dir + os.sep + temp_path_name)
            os.chdir(SCRIPT_ROOT_DIR)
        else:
            print '*** Error: unsupported folder structure encountered, abort!'
            print '*** Found items: ' + str(items) + ' in directory: ' + install_dir
            sys.exit(-1)

    if rpath_target:
        if not rpath_target.startswith( os.sep ):
            rpath_target = os.sep + rpath_target
        if bldinstallercommon.is_linux_platform() or bldinstallercommon.is_solaris_platform():
            bldinstallercommon.handle_component_rpath(install_dir, rpath_target)

    # lastly compress the component back to .7z archive
    archive_component(package_name, archive_name)
    # move archive in temporary path
    tmp_path = os.path.normpath(PACKAGES_FULL_PATH_DST + os.sep + package_name + os.sep + 'tmp')
    bldinstallercommon.create_dirs(tmp_path)
    src_file = os.path.normpath(PACKAGES_FULL_PATH_DST + os.sep + package_name + os.sep + 'data' + os.sep + archive_name)
    dst_file = os.path.normpath(PACKAGES_FULL_PATH_DST + os.sep + package_name + os.sep + 'tmp' + os.sep + archive_name)
    print '     Moving: ' + src_file
    print '       Into: ' + dst_file
    shutil.move(src_file, dst_file)


##############################################################
# Archive installable component
##############################################################
def archive_component(package, package_archive_name):
    """Use archivegen tool to archive component."""
    full_path = os.path.normpath(PACKAGES_FULL_PATH_DST + os.sep + package + os.sep + 'data')
    content_path = full_path + os.sep + '*'
    package_path = full_path + os.sep + package_archive_name
    print '      --------------------------------------------------------------------'
    print '      Archive package: ' + package
    print '      Content from:    ' + content_path
    print '      Final archive:   ' + package_path

    saveas = os.path.normpath(PACKAGES_FULL_PATH_DST + os.sep + package + os.sep + package_archive_name)
    cmd_args = ARCHIVEGEN_TOOL + ' ' + saveas + ' .'
    bldinstallercommon.do_execute_sub_process_2(cmd_args, full_path, True)
    shutil.copy(saveas, full_path + os.sep + package_archive_name)
    os.remove(saveas)

    # remove stuff after archive creation
    ldir = os.listdir(full_path)
    for item in ldir:
        if not item == package_archive_name:
            item_full_path = full_path + os.sep + item
            if os.path.isdir(item_full_path):
                bldinstallercommon.remove_tree(item_full_path)
            else:
                os.remove(item_full_path)


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
# Handle archive
##############################################################
def handle_archive(sdk_component, archive):
    """Handle single archive."""
    print '   --------------------------------------------------------------'
    print '   Handle archive:        '   + archive.archive_name
    print '     archive_uri:         '   + archive.archive_uri
    print '     package_strip_dirs:  '   + archive.package_strip_dirs
    print '     target_install_base: '   + sdk_component.target_install_base
    print '     target_install_dir:  '   + archive.target_install_dir
    print '     rpath_target:        '   + archive.rpath_target
    print ''

    # Create needed data dirs
    data_dir_dest = os.path.normpath(PACKAGES_FULL_PATH_DST + os.sep + sdk_component.package_name + os.sep + 'data')
    install_dir = os.path.normpath(data_dir_dest + os.sep + sdk_component.target_install_base + os.sep + archive.target_install_dir)

    if INCREMENTAL_MODE and os.path.exists(os.path.join(data_dir_dest, archive.archive_name)):
        return

    bldinstallercommon.create_dirs(install_dir)
    print '     -> Created:         ' + install_dir
    # generate save as filename
    package_raw_name     = os.path.basename(archive.archive_uri)
    package_save_as_temp = os.path.normpath(install_dir + os.sep + os.path.basename(archive.archive_uri))
    # if URI points to http location -> download it
    if archive.archive_uri.startswith('http'):
        print '     Downloading:        ' + archive.archive_uri
        print '            into:        ' + package_save_as_temp
        # start download
        bldinstallercommon.retrieve_url(archive.archive_uri, package_save_as_temp)
        print '     Downloading completed'
    else:
        print '     Copying:        ' + archive.archive_uri
        print '        into:        ' + package_save_as_temp
        # copy file on local file system or shared network drive
        shutil.copy(archive.archive_uri, package_save_as_temp)
        print '     Copying completed'

    # repackage content so that correct dir structure will get into the package
    repackage_content_for_installation(install_dir, package_raw_name,
                                       sdk_component.target_install_base,
                                       archive.rpath_target,
                                       archive.package_strip_dirs,
                                       sdk_component.package_name,
                                       archive.archive_name)


##############################################################
# Finalize package archives
##############################################################
def finalize_package_archives(sdk_component):
    """Finalize package archives"""
    print '     Finalize package archives for: ' + sdk_component.package_name
    # move arhives from tmp under data
    src_path = os.path.normpath(PACKAGES_FULL_PATH_DST + os.sep + sdk_component.package_name + os.sep + 'tmp')
    if not os.path.exists(src_path):
        return

    dst_path = os.path.normpath(PACKAGES_FULL_PATH_DST + os.sep + sdk_component.package_name + os.sep + 'data')
    ldir = os.listdir(src_path)
    for item in ldir:
        src_file = src_path + os.sep + item
        dst_file = dst_path + os.sep + item
        print '     Moving: ' + src_file
        print '       Into: ' + dst_file
        shutil.move(src_file, dst_file)
    # lastly remove tmp dir
    bldinstallercommon.remove_tree(src_path)


##############################################################
# Parse SDK components
##############################################################
def parse_component_data(configuration_file, configurations_base_path):
    """Parse SDK component data"""
    global SDK_COMPONENT_LIST
    global SDK_COMPONENT_LIST_SKIPPED
    global SDK_COMPONENT_IGNORE_LIST
    print ' -> Reading target configuration file: ' + configuration_file
    configuration = ConfigParser.ConfigParser()
    configuration.readfp(open(configuration_file))

    # parse package ignore list first
    sdk_component_exclude_list = bldinstallercommon.safe_config_key_fetch(configuration, 'PackageIgnoreList', 'packages')
    if sdk_component_exclude_list:
        sdk_component_exclude_list = sdk_component_exclude_list.replace(' ', '')
        pkg_list = sdk_component_exclude_list.split(',')
        for item in pkg_list:
            SDK_COMPONENT_IGNORE_LIST.append(item)
    # parse sdk components
    for section in configuration.sections():
        if section.startswith(PACKAGE_NAMESPACE + '.') or section == PACKAGE_NAMESPACE:
            if section not in SDK_COMPONENT_IGNORE_LIST:
                sdk_component = SdkComponent(section, configuration, PACKAGES_DIR_NAME_LIST, ARCHIVE_LOCATION_RESOLVER)
                # if online installer, we are interested only about the root component!
                if CREATE_ONLINE_INSTALLER and not sdk_component.is_root_component():
                    continue

                # validate component
                sdk_component.validate()
                if sdk_component.is_valid():
                    SDK_COMPONENT_LIST.append(sdk_component)
                else:
                    if STRICT_MODE:
                        print sdk_component.error_msg()
                        sys.exit(-1)
                    else:
                        print '!!! Ignored component in non-strict mode (missing archive data or metadata?): ' + section
                        SDK_COMPONENT_LIST_SKIPPED.append(sdk_component)
    # check for extra configuration files if defined
    extra_conf_list = bldinstallercommon.safe_config_key_fetch(configuration, 'ExtraPackageConfigurationFiles', 'file_list')
    if extra_conf_list:
        extra_conf_list = extra_conf_list.replace(' ', '')
        file_list = extra_conf_list.split(',')
        for extra_conf_file in file_list:
            extra_conf_file_path = os.path.normpath(configurations_base_path + os.sep + extra_conf_file)
            if not os.path.isfile(extra_conf_file_path):
                # then the file should exist in common (all-os) directory
                extra_conf_file_path = os.path.normpath(CONFIGURATIONS_DIR + os.sep + COMMON_CONFIG_DIR_NAME + os.sep + extra_conf_file)
                if not os.path.isfile(extra_conf_file_path):
                    print '*** Error! Unable to locate configuration file: ' + extra_conf_file_path
            # recursive call
            parse_component_data(extra_conf_file_path, configurations_base_path)


##############################################################
# Parse SDK components
##############################################################
def parse_components(target_config):
    """Parse SDK all components"""
    print '----------------------------------------'
    print ' Parse target configuration files'
    conf_base_path = SCRIPT_ROOT_DIR + os.sep + CONFIGURATIONS_DIR + os.sep + PLATFORM_IDENTIFIER + os.sep
    main_conf_file = SCRIPT_ROOT_DIR + os.sep + CONFIGURATIONS_DIR + os.sep + MAIN_CONFIG_NAME
    parse_component_data(main_conf_file, conf_base_path)
    return


##############################################################
# Create target components
##############################################################
def create_target_components(target_config):
    """Create target components."""
    global ROOT_COMPONENT_NAME
    bldinstallercommon.create_dirs(PACKAGES_FULL_PATH_DST)

    print '================================================================='
    print '= Creating SDK components'
    print '================================================================='
    print ''
    for sdk_component in SDK_COMPONENT_LIST:
        # check first for top level component
        if sdk_component.root_component == 'yes':
            ROOT_COMPONENT_NAME = sdk_component.package_name
        # for online installer handle only the root component, nothing else
        if CREATE_ONLINE_INSTALLER and not sdk_component.root_component == 'yes':
            continue

        # check if static component or not
        if sdk_component.static_component:
            create_offline_static_component(sdk_component)
            continue

        # not a static component so "build" it
        sdk_component.print_component_data()
        # create destination meta data folder
        meta_dir_dest = os.path.normpath(PACKAGES_FULL_PATH_DST + os.sep + sdk_component.package_name + os.sep + 'meta')
        bldinstallercommon.create_dirs(meta_dir_dest)
        print '   -> Created:                 ' + meta_dir_dest
        # Copy Meta data
        metadata_content_source_root = os.path.normpath(sdk_component.pkg_template_dir + os.sep + 'meta')
        bldinstallercommon.copy_tree(metadata_content_source_root, meta_dir_dest)
        print '   -> Copied meta data from:   ' + metadata_content_source_root
        # add files into tag substitution
        GENERAL_TAG_SUBST_LIST.append(meta_dir_dest)
        # create lists for component specific tag substitutions
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
        # handle archives
        if sdk_component.downloadable_archive_list:
            downloadable_archive_list = []
            # Copy archives into temporary build directory if exists
            for archive in sdk_component.downloadable_archive_list:
                downloadable_archive_list.append(archive.archive_name)
                # fetch packages only if offline installer or repo creation, for online installer just handle the metadata
                if CREATE_OFFLINE_INSTALLER or CREATE_REPOSITORY:
                    handle_archive(sdk_component, archive)
            # finalize archives
            finalize_package_archives(sdk_component)
            # substitute downloadable archive names in installscript.qs
            downloadableArchives_list = sdk_component.generate_downloadable_archive_list(downloadable_archive_list)
            substitute_component_tags(downloadableArchives_list, meta_dir_dest)
        # substitute tags
        substitute_component_tags(component_metadata_tag_pair_list, meta_dir_dest)


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

    # if "devmode" mode used, then build IFW from sources
    if DEVELOPMENT_MODE:
        tools_dir_temp = bld_ifw_tools_impl.build_ifw(True, INCREMENTAL_MODE, CONFIGURATIONS_DIR, PLATFORM_IDENTIFIER)
        tools_bin_path = SCRIPT_ROOT_DIR + os.sep + tools_dir_temp
    else:
        tools_dir_name = bldinstallercommon.config_section_map(CONFIG_PARSER_TARGET,'InstallerFrameworkTools')['name']
        tools_dir_name = os.path.normpath(tools_dir_name)
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
                    print '*** Package URL is invalid: [' + package_url + ']'
                    print '*** Abort!'
                    sys.exit(-1)
                bldinstallercommon.retrieve_url(package_url, package_save_as_temp)
            if not (os.path.isfile(package_save_as_temp)):
                print '*** Downloading failed! Aborting!'
                sys.exit(-1)
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
                print '*** Unsupported dir structure for installer-framework-tools package?!'
                print '*** Abort!'
                sys.exit(-1)
            tools_bin_path = IFW_TOOLS_DIR

    executable_suffix = bldinstallercommon.get_executable_suffix()
    ARCHIVEGEN_TOOL = bldinstallercommon.locate_executable(tools_bin_path, 'archivegen' + executable_suffix)
    BINARYCREATOR_TOOL = bldinstallercommon.locate_executable(tools_bin_path, 'binarycreator' + executable_suffix)
    INSTALLERBASE_TOOL = bldinstallercommon.locate_executable(tools_bin_path, 'installerbase' + executable_suffix)
    REPOGEN_TOOL = bldinstallercommon.locate_executable(tools_bin_path, 'repogen' + executable_suffix)
    # check
    if not (os.path.isfile(ARCHIVEGEN_TOOL)):
        print '*** Archivegen tool not found: ' + ARCHIVEGEN_TOOL
        sys.exit(-1)
    if not (os.path.isfile(BINARYCREATOR_TOOL)):
        print '*** Binarycreator tool not found: ' + BINARYCREATOR_TOOL
        sys.exit(-1)
    if not (os.path.isfile(INSTALLERBASE_TOOL)):
        print '*** Installerbase tool not found: ' + INSTALLERBASE_TOOL
        sys.exit(-1)
    if not (os.path.isfile(REPOGEN_TOOL)):
        print '*** Repogen tool not found: ' + REPOGEN_TOOL
        sys.exit(-1)

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

    SDK_NAME = SDK_NAME + '-' + platform + '-' + LICENSE_TYPE + '-' + SDK_VERSION_NUMBER
    # optional
    if SDK_VERSION_TAG:
        SDK_NAME = SDK_NAME + '-' + SDK_VERSION_TAG
    # optional
    if INSTALLER_NAMING_SCHEME_COMPILER:
        SDK_NAME = SDK_NAME + '-' + INSTALLER_NAMING_SCHEME_COMPILER
    # optional
    if INSTALLER_NAMING_SCHEME_TARGET_ARCH:
        SDK_NAME = SDK_NAME + '-' + INSTALLER_NAMING_SCHEME_TARGET_ARCH
    SDK_NAME = SDK_NAME + '-' + installer_type + extension

    # if online installer only
    if CREATE_ONLINE_INSTALLER:
        # binarycreator arguments
        cmd_args = [BINARYCREATOR_TOOL, '-t', INSTALLERBASE_TOOL, '-v', '-p', PACKAGES_FULL_PATH_DST]
        # check if we are using older binarycreator version
        if USE_LEGACY_IFW:
            cmd_args = cmd_args + ['-c', CONFIG_DIR_DST, SDK_NAME, ROOT_COMPONENT_NAME]
        else:
            cmd_args = cmd_args + ['-c', CONFIG_DIR_DST + os.sep + 'config.xml', SDK_NAME]
        # create installer binary
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)

    # if offline-only installer
    if CREATE_OFFLINE_INSTALLER:
        cmd_args = [BINARYCREATOR_TOOL, '--offline-only']
        cmd_args = cmd_args + ['-t', INSTALLERBASE_TOOL, '-v', '-p', PACKAGES_FULL_PATH_DST]
        # check if package exclude list should be used for offline installer
        package_exclude_list = bldinstallercommon.safe_config_key_fetch(CONFIG_PARSER_TARGET, 'OfflinePackageExcludeList', 'package_list')
        package_exclude_list = package_exclude_list.replace('\n', '')
        if package_exclude_list:
            cmd_args = cmd_args + ['-e', package_exclude_list]
        # check if we are using older binarycreator version
        if USE_LEGACY_IFW:
            cmd_args = cmd_args + ['-c', CONFIG_DIR_DST, SDK_NAME, ROOT_COMPONENT_NAME]
        else:
            cmd_args = cmd_args + ['-c', CONFIG_DIR_DST + os.sep + 'config.xml', SDK_NAME]
        # create installer binary
        bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


##############################################################
# Create the repository
##############################################################
def create_offline_repository():
    """Create offline repository using repogen tool."""
    print '=================================================='
    print '= Create offline repository'
    print '=================================================='

    # repogen arguments
    if CREATE_REPOSITORY:
        print 'Creating repository for the SDK ...'
        print '    Outputdir: ' + REPO_OUTPUT_DIR
        print '      pkg src: ' + PACKAGES_FULL_PATH_DST
        repogen_args = []
        if USE_LEGACY_IFW:
            print '(legacy syntax)'
            repogen_args = [REPOGEN_TOOL, '-p', PACKAGES_FULL_PATH_DST, '-c', CONFIG_DIR_DST, REPO_OUTPUT_DIR, ROOT_COMPONENT_NAME, '-v']
        else:
            repogen_args = [REPOGEN_TOOL, '-p', PACKAGES_FULL_PATH_DST, '-c', CONFIG_DIR_DST + os.sep + 'config.xml', REPO_OUTPUT_DIR]
        # create repository
        bldinstallercommon.do_execute_sub_process(repogen_args, SCRIPT_ROOT_DIR, True)
        if not os.path.exists(REPO_OUTPUT_DIR):
            print '*** Fatal error! Unable to create repository directory: ' + REPO_OUTPUT_DIR
            sys.exit(-1)


##############################################################
# Create the final installer binary
##############################################################
def create_mac_disk_image():
    """Create Mac disk image."""
    print '=================================================='
    print '= Create mac disk image'
    print '=================================================='

    nib_archive_name = bldinstallercommon.safe_config_key_fetch(CONFIG_PARSER_TARGET, 'qtmenunib', 'package_url')
    package_save_as_folder = SCRIPT_ROOT_DIR + os.sep + SDK_NAME + '.app' + os.sep + 'Contents' + os.sep + 'Resources'
    package_save_as_temp = package_save_as_folder + os.sep + os.path.basename(nib_archive_name)
    print ' package_url: ' + nib_archive_name
    print ' save as:     ' + package_save_as_temp

    if not nib_archive_name == '':
        print '    Downloading:            ' + nib_archive_name
        print '           into:            ' + package_save_as_temp
        res = bldinstallercommon.is_content_url_valid(nib_archive_name)
        if not(res):
            print '*** Package URL is invalid: [' + nib_archive_name + ']'
            print '*** Abort!'
            sys.exit(-1)
        bldinstallercommon.retrieve_url(nib_archive_name, package_save_as_temp)

    # extract contents
    bldinstallercommon.extract_file(package_save_as_temp, package_save_as_folder)

    # create disk image
    cmd_args = ['hdiutil', 'create', '-fs', 'HFS+', '-srcfolder', \
                os.path.join(SCRIPT_ROOT_DIR, SDK_NAME + '.app'), \
                '-volname', SDK_NAME, \
                os.path.join(SCRIPT_ROOT_DIR, SDK_NAME + '.dmg')]
    bldinstallercommon.do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, True)


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
    if CREATE_REPOSITORY:
        create_offline_repository()
    # for mac we need some extra work
    if bldinstallercommon.is_mac_platform():
        create_mac_disk_image()
    # print warning messages if encountered any problems
    print_warnings()


##############################################################
# Start build process
##############################################################
main()

