#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
#
# Copyright (C) 2022 The Qt Company Ltd.
# Copyright (C) 2014 BlackBerry Limited. All rights reserved.
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

from configparser import ConfigParser
import optionparser
import argparse
import collections
from glob import glob
import json
import os
import sys
import re
import shutil
from urllib.parse import urlparse
from urllib.request import urlopen
from time import gmtime, strftime
import bld_utils
from bld_utils import is_windows, is_macos, is_linux
import bldinstallercommon
from bldinstallercommon import locate_paths
from threadedwork import ThreadedWork, Task
import bld_sdktool
from read_remote_config import get_pkg_value
from runner import do_execute_sub_process

# ----------------------------------------------------------------------
SCRIPT_ROOT_DIR             = os.path.dirname(os.path.realpath(__file__))
WORK_DIR                    = os.getenv('PKG_NODE_ROOT') if os.getenv("PKG_NODE_ROOT") else os.path.abspath(os.path.join(__file__, '../../../'))
LOCAL_MODE                  = os.getenv('LOCAL_MODE') # if set, installers will be copied to a local directory
LOCAL_INSTALLER_DIR         = os.getenv('LOCAL_INSTALLER_DIR', os.path.join(WORK_DIR, 'installers'))

if LOCAL_MODE:
    assert os.path.exists(LOCAL_INSTALLER_DIR), "Local installer destination directory does not exist: %s" % LOCAL_INSTALLER_DIR
    print("Installer files will be copied to local directory: %s" % LOCAL_INSTALLER_DIR)


###############################
# Unlock keychain script
###############################
def unlock_keychain_script():
    return '/Users/qt/unlock-keychain.sh'

###############################
# Unlock keychain
###############################
def unlock_keychain():
    cmd_args = [unlock_keychain_script()]
    do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)


###############################
# Lock keychain
###############################
def lock_keychain():
    cmd_args = ['/Users/qt/lock-keychain.sh']
    do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR, abort_on_fail=False)


###########################################
# init snapshot build dir and upload files
###########################################
def init_snapshot_dir_and_upload_files(optionDict, project_name, project_version_or_branch, build_number, file_upload_list, subdir = ''):
    if subdir is not "" and subdir[0] is not "/":
        subdir = "/" + subdir
    remote_path_base                        = optionDict['PACKAGE_STORAGE_SERVER_BASE_DIR'] + '/' + project_name + '/' + project_version_or_branch
    remote_path_snapshot_dir                = remote_path_base + '/' + build_number
    remote_path_latest_link                 = remote_path_base + '/' + 'latest'
    # ensure remote directory exists
    create_remote_dirs(optionDict, optionDict['PACKAGE_STORAGE_SERVER_ADDR'], remote_path_snapshot_dir + subdir)
    # upload files
    for item in file_upload_list:
        cmd_args = [optionDict['SCP_COMMAND'], item, optionDict['PACKAGE_STORAGE_SERVER_ADDR'] + ':' + remote_path_snapshot_dir + subdir]
        do_execute_sub_process(cmd_args, optionDict['WORK_DIR'])
    # update 'latest' symlink
    update_latest_link(optionDict, remote_path_snapshot_dir, remote_path_latest_link)


###############################
# handle_qt_licheck_build
###############################
def handle_qt_licheck_build(optionDict):
    if optionDict['LICENSE'] == 'enterprise':
        # Build license checker
        exe_dir = optionDict['WORK_DIR'] + '/license-managing/licheck'
        upload_path = optionDict['PACKAGE_STORAGE_SERVER_ADDR'] + ':' + optionDict['PACKAGE_STORAGE_SERVER_BASE_DIR'] + '/' + optionDict['LICENSE'] + '/licheck/'
        if optionDict['TARGET_ENV'].lower().startswith("win"):
            cmd_args = [r'c:\Utils\jom\jom.exe', '-f', 'Makefile_win']
            do_execute_sub_process(cmd_args, exe_dir, True)
            cmd_args = [optionDict['SCP_COMMAND'], 'licheck.exe', upload_path]
            do_execute_sub_process(cmd_args, exe_dir, True)
        elif optionDict['TARGET_ENV'].lower().startswith("linux"):
            cmd_args = ['make', '-j6', '-f', 'Makefile_unix']
            do_execute_sub_process(cmd_args, exe_dir, True)
            licheck = 'licheck64' if optionDict['TARGET_ENV'].find("x64") >= 1 else 'licheck32'
            cmd_args = ['rsync', '-r', licheck, upload_path + licheck]
            do_execute_sub_process(cmd_args, exe_dir, True)
        else:
            cmd_args = ['make', '-j6', '-f', 'Makefile_macos']
            do_execute_sub_process(cmd_args, exe_dir, True)
            cmd_args = ['rsync', '-r', 'licheck_mac', upload_path +'licheck_mac']
            do_execute_sub_process(cmd_args, exe_dir, True)
    else:
        #opensource, do nothing
        print('*** opensource build, nothing to build ...')


###############################
# Download Qt documentation, extract and repackage with toplevel dir renamed
###############################
def move_files_to_parent_dir(source):
    destination = os.path.abspath(os.path.join(source, os.pardir))
    print("Moving files from: [{0}] to: [{1}]".format(source, destination))
    assert os.path.isdir(source), "The given source is not a directory: %s" % source
    assert os.path.isdir(destination), "The destination is not a directory: %s" % destination
    files_list = os.listdir(source)
    for file in files_list:
        shutil.move(os.path.join(source, file), destination)
    os.rmdir(source)


def create_download_documentation_task(base_url, download_path):
    doc_base_url = base_url + "/doc"

    useLocal = urlparse(doc_base_url).scheme == "file"
    print("doc_base_url: {} useLocal: {}".format(doc_base_url, useLocal))
    if useLocal:
        file_list = os.listdir(doc_base_url[len("file:///"):])
    else:
        urlpath = urlopen(doc_base_url)
        string = urlpath.read().decode('utf-8')
        pattern = re.compile('[0-9a-zA-Z-]*.zip')

        file_list = pattern.findall(string)
        file_list = list(dict.fromkeys(file_list))

    # In Qt 6 a zip file with all html files and index files exists.
    # Use it if available.
    if 'qt5-documentation.zip' in file_list:
        file_list = ['qt5-documentation.zip']

    extract_path = os.path.join(download_path, 'tqtc-qt5-documentation')
    target_filepath = os.path.join(download_path, 'qt-everywhere-documentation.7z')

    def create_remove_one_dir_level_function(path):
        return lambda: move_files_to_parent_dir(path)

    def repackage():
        source_path = extract_path
        dest_doc_path = os.path.join(download_path, 'doc')
        os.rename(source_path, dest_doc_path)
        # limit compression to 2 cores to limit memory footprint for 32bit Windows
        bld_utils.runCommand(['7z', 'a', '-mx1', '-mmt2', '-md32m', '-ms=1g', target_filepath, dest_doc_path],
                             dest_doc_path, None)

    download_task = Task("downloading documentation from {0}".format(base_url))
    for item in file_list:
        url = base_url + '/doc/' + item
        download_filepath = os.path.join(download_path, item)
        download_task.addFunction(bld_utils.download, url, download_filepath)
        download_task.addFunction(bldinstallercommon.create_extract_function(download_filepath, extract_path, None))
        download_task.addFunction(create_remove_one_dir_level_function(os.path.join(extract_path, item.rstrip(".zip"))))

    repackage_task = Task("repackaging documentation as {0}".format(target_filepath))
    repackage_task.addFunction(repackage)
    return (download_task, repackage_task, bld_utils.file_url(target_filepath))

def create_download_openssl_task(url, download_path):
    # create openssl 7zips which just contain the DLLs / SOs, so they can just be extracted
    # into the Qt lib directory and later on deployed with Qt
    (_, filename) = os.path.split(url)
    download_filepath = os.path.join(download_path, filename)
    extract_path = os.path.join(download_path, 'openssl_download')
    target_filepath = os.path.join(download_path, 'openssl.7z')

    def repackage():
        listing = os.listdir(extract_path)
        subdircount = len(listing)
        base_path = os.path.join(extract_path, listing[0]) if subdircount >= 1 else extract_path
        win64dir = os.path.join(base_path, 'Win_x64', 'bin')
        win32dir = os.path.join(base_path, 'Win_x86', 'bin')
        linuxdir = os.path.join(base_path, 'openssl', 'lib')
        if os.path.exists(win64dir):
            source_path = win64dir
            pattern = '*.dll'
        elif os.path.exists(win32dir):
            source_path = win32dir
            pattern = '*.dll'
        else:
            source_path = linuxdir
            pattern = '*.so*'
        bld_utils.runCommand(['7z', 'a', '-mmt2', target_filepath, pattern],
                             source_path, None)

    download_task = Task('downloading openssl from {0}'.format(url))
    download_task.addFunction(bld_utils.download, url, download_filepath)
    repackage_task = Task("repackaging openssl as {0}".format(target_filepath))
    repackage_task.addFunction(bldinstallercommon.create_extract_function(download_filepath, extract_path, None))
    repackage_task.addFunction(repackage)
    return (download_task, repackage_task, bld_utils.file_url(target_filepath))


PluginConf = collections.namedtuple('PluginConf', ['git_url', 'branch_or_tag', 'checkout_dir'])


def parseQtCreatorPlugins(pkgConfFile):
    """Parse available Qt Creator plugins from configuration file"""
    pluginList = []
    if not pkgConfFile:
        return pluginList
    pluginOptions = optionparser.getPkgOptions(pkgConfFile)
    sectionName = "QtCreator.Build.Plugin"
    keyName = "plugins"
    if not pluginOptions.optionExists(sectionName, keyName):
        return pluginList
    pluginConfList = pluginOptions.configSectionMap(sectionName)[keyName]
    for pluginName in pluginConfList.replace(" ", "").replace("\n", "").split(","):
        section = "QtCreator.Build.Plugin." + pluginName
        pluginUrl = pluginOptions.configSectionMap(section)["QTC_PLUGIN_GIT_URL"]
        branchOrTag = pluginOptions.configSectionMap(section)["QTC_PLUGIN_GIT_BRANCH_OR_TAG"]
        checkoutDirName = pluginOptions.configSectionMap(section)["QTC_PLUGIN_CHECKOUT_DIR_NAME"]
        plugin = PluginConf(git_url=pluginUrl, branch_or_tag=branchOrTag, checkout_dir=checkoutDirName)
        pluginList.extend([plugin])
    return pluginList


QtcPlugin = collections.namedtuple('QtcPlugin', ['name',
                                                 'path',
                                                 'version',
                                                 'dependencies',
                                                 'modules',
                                                 'additional_arguments',
                                                 'build',
                                                 'package_commercial'])


def make_QtcPlugin(name, path, version, dependencies=None, modules=None,
                   additional_arguments=None, build=True,
                   package_commercial=False):
    return QtcPlugin(name=name, path=path, version=version,
                     dependencies=dependencies or [],
                     modules=modules or [],
                     additional_arguments=additional_arguments or [],
                     build=build,
                     package_commercial=package_commercial)

class BuildLog:
    def __init__(self, log_filepath, log_overwrite=False):
        self.file = None
        self.log_filepath = log_filepath
        self.log_overwrite = log_overwrite

    def __enter__(self):
        try:
            self.file = open(self.log_filepath, 'w' if self.log_overwrite else 'a')
        except Exception:
            print('Failed to write log file "' + self.log_filepath + '"')
            sys.stdout.flush()
            raise
        return self.file

    def __exit__(self, type, value, traceback):
        self.file.close()
        if type:  # exception raised -> print the log and re-raise
            with open(self.log_filepath, 'r') as f:
                print(f.read())
            return True  # re-raise

# writes output of process to log_filepath
# on error it dumps the log file to stdout as well
def check_call_log(args, execution_path, extra_env=dict(os.environ),
                   log_filepath=None, log_overwrite=False):
    if not log_filepath:
        do_execute_sub_process(args, execution_path,
                                                  extra_env=extra_env)
    else:
        with BuildLog(log_filepath, log_overwrite) as f:
            do_execute_sub_process(args, execution_path,
                                                      extra_env=extra_env,
                                                      redirect_output=f)

def create_qtcreator_source_package(source_path, plugin_name, version, edition, target_path, log_filepath):
    namepart = '-' + plugin_name if plugin_name else ''
    file_base = 'qt-creator-' + edition + namepart + '-src-' + version
    target_base = os.path.join(target_path, file_base)
    create_tar = is_linux()
    create_zip = is_windows() and '32' not in optionDict['TARGET_ENV']
    if create_tar or create_zip:
        if not os.path.exists(target_base):
            os.makedirs(target_base)
        bldinstallercommon.copy_tree(source_path, target_base)
        if create_tar:
            check_call_log(['tar', 'czf', file_base + '.tar.gz', '--exclude', '.git', file_base],
                           target_path, log_filepath=log_filepath)
            check_call_log(['tar', 'cJf', file_base + '.tar.xz', '--exclude', '.git', file_base],
                           target_path, log_filepath=log_filepath)
        if create_zip:
            check_call_log(['7z', 'a', '-tzip', file_base + '.zip', file_base, '-xr!.git'],
                           target_path, log_filepath=log_filepath)

def qtcreator_build_plugin_script(qtcreator_dev_path):
    if is_macos():
        # scripts can be within the app bundle
        apps = glob(os.path.join(qtcreator_dev_path, '*.app'))
        app = apps[0] if apps else os.path.join(qtcreator_dev_path, 'Qt Creator.app')
        path = os.path.join(app, 'Contents', 'Resources', 'scripts', 'build_plugin.py')
    else:
        # scripts can be in share directory
        path = os.path.join(qtcreator_dev_path, 'share', 'qtcreator', 'scripts', 'build_plugin.py')
    return path if os.path.exists(path) else os.path.join(qtcreator_dev_path, 'scripts', 'build_plugin.py')


def build_qtcreator_plugins(plugins, qtcreator_path, qtcreator_dev_path, icu_url=None,
                            openssl_url=None, additional_config=None, log_filepath=None):
    work_dir = optionDict['WORK_DIR']
    for plugin in plugins:
        plugin_path = os.path.join(work_dir, plugin.path)
        if not plugin.build or not os.path.isdir(plugin_path):
            continue
        modules = plugin.modules
        cmd_arguments = [sys.executable, '-u']
        build_path = os.path.join(work_dir, plugin.name + '-build')
        qt_path = os.path.join(build_path, 'qt')
        cmd_arguments += [qtcreator_build_plugin_script(qtcreator_dev_path),
                          '--name', plugin.name,
                          '--src', plugin_path,
                          '--build', build_path,
                          '--qt-path', qt_path,
                          '--qtc-path', qtcreator_path,
                          '--output-path', work_dir]
        for dependency_name in plugin.dependencies:
            matches = [dep for dep in plugins if dep.name == dependency_name]
            if not matches:
                raise RuntimeError('did not find dependency "{0}" for plugin "{1}"'.format(dependency_name, plugin.name))
            dependency = matches[0]
            cmd_arguments.extend(['--add-path', os.path.join(work_dir, dependency.name + '-build', 'build')])
            for module in dependency.modules:
                if module not in modules:
                    modules.append(module)
        cmd_arguments.extend(plugin.additional_arguments)
        ide_branding_path = optionDict.get('IDE_BRANDING_PATH')  # optional
        if ide_branding_path:
            cmd_arguments.extend(['--add-module-path', os.path.abspath(ide_branding_path)])
        if additional_config:
            cmd_arguments += ['--add-config=' + value for value in additional_config]

        # install qt
        qt_install_args = [sys.executable, '-u', os.path.join(SCRIPT_ROOT_DIR, 'install_qt.py'),
                           '--qt-path', qt_path, '--temp-path', os.path.join(build_path, 'temp')]
        for module in modules:
            qt_install_args.extend(['--qt-module', module])
        if is_linux() and icu_url:
            qt_install_args.extend(['--icu7z', icu_url])
        if openssl_url:
            qt_install_args.extend(['--openssl7z', openssl_url])
        check_call_log(qt_install_args, work_dir)

        check_call_log(cmd_arguments, work_dir, log_filepath=log_filepath)
        create_qtcreator_source_package(os.path.join(work_dir, plugin.path), plugin.name, plugin.version,
                                        'enterprise', work_dir, log_filepath)

def get_qtcreator_version(path_to_qtcreator_src, optionDict):
    expr = re.compile(r'\s*set[(]\s*IDE_VERSION_DISPLAY\s*"([^\s]+)"')

    ide_branding_path = optionDict.get('IDE_BRANDING_PATH')  # optional
    ide_branding_path = ide_branding_path if ide_branding_path else os.path.join(path_to_qtcreator_src, 'cmake')
    ide_branding_file = os.path.join(ide_branding_path, 'QtCreatorIDEBranding.cmake')

    with open(ide_branding_file, 'r') as f:
        for line in f:
            match = expr.match(line)
            if match:
                return match.group(1)
    return None

def make_QtcPlugin_from_json(plugin_json):
    return QtcPlugin(name=plugin_json['Name'],
                     path=plugin_json['Path'],
                     version=plugin_json.get('Version'),
                     dependencies=plugin_json.get('Dependencies') or [],
                     modules=plugin_json.get('Modules') or [],
                     additional_arguments=plugin_json.get('AdditionalArguments') or [],
                     build=plugin_json.get('Build') or True,
                     package_commercial=plugin_json.get('PackageCommercial') or False)

def parse_qt_creator_plugin_conf(plugin_conf_file_path, optionDict):
    data = {}
    with open(plugin_conf_file_path, 'r') as f:
        data = json.load(f)
    plugins_json = data['Plugins']
    if is_linux():
        platform_name = 'linux'
    elif is_windows():
        platform_name = 'windows'
    else:
        platform_name = 'mac'

    def valid_for_platform(plugin_json):
        platforms = plugin_json.get('Platforms')
        return not platforms or platform_name in platforms

    def fixup_plugin(plugin):
        plugin = plugin._replace(modules = [module % optionDict for module in plugin.modules])
        plugin = plugin._replace(additional_arguments = [arg % optionDict for arg in plugin.additional_arguments])
        return plugin
    return [fixup_plugin(make_QtcPlugin_from_json(plugin)) for plugin in plugins_json if valid_for_platform(plugin)]

def collect_qt_creator_plugin_sha1s(plugins):
    work_dir = optionDict['WORK_DIR']
    sha1s = []
    for name in [p.name for p in plugins if p.build and os.path.isdir(os.path.join(work_dir, p.path))]:
        with open(os.path.join(work_dir, name + '.7z.git_sha'), 'r') as f:
            sha = f.read().strip()
            sha1s.append(name + ': ' + sha)
    return sorted(sha1s)


# file_upload_list: list of 2-tuples,
# (source_file_relative_to_WORK_DIR, target_file_or_path_relative_to_remote_path)
def upload_files(remote_path, file_upload_list, optionDict):
    # prepare remote paths
    pkg_storage_server = optionDict['PACKAGE_STORAGE_SERVER_ADDR']
    target_env_dir = optionDict['QTC_PLATFORM']
    latest_path = remote_path + '/latest'
    dir_path = remote_path + '/' + optionDict['BUILD_NUMBER']
    create_remote_dirs(optionDict, pkg_storage_server, dir_path + '/' + target_env_dir)
    update_latest_link(optionDict, dir_path, latest_path)
    # upload files
    for source, destination in file_upload_list:
        cmd_args = [optionDict['SCP_COMMAND'], source, pkg_storage_server + ':' + dir_path + '/' + destination]
        do_execute_sub_process(cmd_args, optionDict['WORK_DIR'])

def update_job_link(remote_path_base, remote_target_path, optionDict):
    remote_link = remote_path_base + '/' + optionDict['PULSE_PROJECT']
    update_latest_link(optionDict, remote_target_path, remote_link)


def repackage_and_sign_qtcreator(qtcreator_path, work_dir, result_package,
                                 qtcreator_package, sdktool_package,
                                 additional_plugins=None,
                                 extra_env=None, log_filepath=None):
    extract_path = os.path.join(work_dir, 'temp_repackaged_qtc')
    if not os.path.exists(extract_path):
        os.makedirs(extract_path)
    # extract Qt Creator
    check_call_log(['7z', 'x', '-y',
                    os.path.join(work_dir, qtcreator_package),
                    '-o' + extract_path],
                   work_dir, log_filepath=log_filepath)
    # find app name
    apps = [d for d in os.listdir(extract_path) if d.endswith('.app')]
    app = apps[0]
    # extract sdktool
    if os.path.isfile(os.path.join(work_dir, sdktool_package)):
        check_call_log(['7z', 'x', '-y',
                        os.path.join(work_dir, sdktool_package),
                        '-o' + os.path.join(extract_path, app,
                                            'Contents', 'Resources', 'libexec')],
                       work_dir, log_filepath=log_filepath)
    # extract plugins (if applicable)
    if additional_plugins:
        for plugin in additional_plugins:
            if not plugin.package_commercial:
                continue
            plugin_package = plugin.name + '.7z'
            if os.path.isfile(os.path.join(work_dir, plugin_package)):
                check_call_log(['7z', 'x', '-y',
                                os.path.join(work_dir, plugin_package),
                                '-o' + extract_path],
                               work_dir, log_filepath=log_filepath)
    # sign
    unlock_keychain()
    import_path = os.path.join(qtcreator_path, 'scripts')
    check_call_log([sys.executable, '-u', '-c', "import common; common.codesign('" +
                    os.path.join(extract_path, app) +
                    "')"],
                   import_path, extra_env=extra_env, log_filepath=log_filepath)
    # repackage
    result_filepath = os.path.join(work_dir, result_package)
    if os.path.exists(result_filepath):
        os.remove(result_filepath)
    check_call_log(['7z', 'a', '-mmt2', result_filepath, app],
                   extract_path, log_filepath=log_filepath)
    shutil.rmtree(extract_path)


###############################
# handle_qt_creator_build
###############################
def handle_qt_creator_build(optionDict, qtCreatorPlugins):
    target_env_dir = optionDict['QTC_PLATFORM']
    work_dir = optionDict['WORK_DIR']
    build_environment = dict(os.environ)
    # remove LLVM_INSTALL_DIR set by COIN templates
    build_environment.pop('LLVM_INSTALL_DIR', None)

    # Get Qt Creator sources if not present yet
    if 'QT_CREATOR_GIT_URL' in optionDict:
        qtCreatorSourceDirectory = os.path.join(work_dir, 'qt-creator')
        if os.path.exists(qtCreatorSourceDirectory):
            shutil.rmtree(qtCreatorSourceDirectory)
        os.makedirs(qtCreatorSourceDirectory)
        bldinstallercommon.clone_repository(optionDict['QT_CREATOR_GIT_URL'], optionDict['QT_CREATOR_GIT_BRANCH'],
                                            qtCreatorSourceDirectory, full_clone=True, init_subrepos=True)
    # Get Qt Creator plugin sources if not present yet
    for pluginConf in qtCreatorPlugins:
        checkoutDir = os.path.join(work_dir, pluginConf.checkout_dir)
        if pluginConf.git_url:
            if os.path.exists(checkoutDir):
                shutil.rmtree(checkoutDir)
            os.makedirs(checkoutDir)
            bldinstallercommon.clone_repository(pluginConf.git_url, pluginConf.branch_or_tag, checkoutDir, full_clone=True)

    # Build time variables
    qtcreator_source = os.path.join(work_dir, 'qt-creator')
    qtcreator_version = get_qtcreator_version(qtcreator_source, optionDict)
    pkg_base_path = optionDict['PACKAGE_STORAGE_SERVER_PATH_HTTP']
    # Check if the archives reside on network disk (http) or on local file system
    scheme = "" if urlparse(pkg_base_path).scheme != "" else "file://"
    pkg_base_path = scheme + pkg_base_path
    pkg_storage_server = optionDict['PACKAGE_STORAGE_SERVER_ADDR']
    qtcreator_edition_name = optionDict.get('QT_CREATOR_EDITION_NAME') # optional
    unversioned_base_path = optionDict['PACKAGE_STORAGE_SERVER_BASE_DIR'] + '/' + optionDict['QTC_BASE_DIR']
    base_path = unversioned_base_path + '/' + qtcreator_version
    if qtcreator_edition_name:
        base_path += '_' + qtcreator_edition_name
    snapshot_server = optionDict.get('SNAPSHOT_SERVER') # optional
    snapshot_path = optionDict['SNAPSHOT_SERVER_PATH'] # optional
    qt_base_path = optionDict['QTC_QT_BASE_DIR']
    ide_branding_path = optionDict.get('IDE_BRANDING_PATH') # optional
    installer_patch = optionDict.get('INSTALLER_PATCH') # optional
    skip_cdb = optionDict.get('SKIP_CDB') # optional
    skip_dmg = optionDict.get('SKIP_DMG') # optional
    build_id = optionDict['BUILD_NUMBER']
    icu_libs = optionDict.get('ICU_LIBS') # optional
    openssl_libs = optionDict.get('OPENSSL_LIBS') # optional
    openssl_local_url = None # optionally defined later
    qt_extra_module_url = optionDict.get('QT_EXTRA_MODULE_URL') # optional
    qt_postfix = os.environ['QT_POSTFIX']
    sdktool_base = optionDict.get('SDKTOOL_QTBASESRC_BASE') # optional
    sdktool_ext = optionDict.get('SDKTOOL_QTBASESRC_EXT') # optional
    sdktool_qtbase_src = sdktool_base + sdktool_ext if sdktool_base and sdktool_ext else None # optional
    download_temp = os.path.join(work_dir, 'downloads')
    has_unlock_keychain_script = os.path.exists(unlock_keychain_script())
    # from 4.4 on we use external elfutil builds and also build on Windows
    elfutils_url = optionDict.get('ELFUTILS_URL')
    log_filepath = os.path.join(work_dir, 'build_log.txt')
    notarize = optionDict.get('NOTARIZE')
    usp_server_url = optionDict.get('USP_SERVER_URL')
    usp_auth_key = optionDict.get('USP_AUTH_KEY')
    qtc_additional_config = optionDict.get('QTC_ADDITIONAL_CONFIG') # optional
    disable_docs = optionDict.get('DISABLE_DOCS') # optional
    if qtc_additional_config:
        qtc_additional_config = qtc_additional_config.split()
    qt_temp = os.path.join(work_dir, 'qt_temp')

    def module_filename(module):
        return module + '-' + qt_postfix + '.7z'

    def module_urls(modules):
        return [pkg_base_path + '/' + qt_base_path + '/' + module + '/' + module_filename(module)
                for module in modules]

    # Define paths for pre-built kdsme and gammaray packages
    kdsme_url = optionDict.get("GAMMARAY_BASE_DIR")
    if kdsme_url:
        kdsme_url = (pkg_base_path + '/' + kdsme_url + '/' + target_env_dir + '/qt5_kdsme.7z')
    gammaray_url = optionDict.get("GAMMARAY_BASE_DIR")
    if gammaray_url:
        gammaray_url = (pkg_base_path + '/' + gammaray_url + '/' + target_env_dir + '/qt5_gammaray.7z')

    download_work = ThreadedWork('Download packages')
    extract_work = Task('Extract packages')

    def add_download_extract(url, target_path):
        (download, extract) = bldinstallercommon.create_download_and_extract_tasks(
            url, target_path, download_temp, None)
        download_work.addTaskObject(download)
        extract_work.addFunction(extract.do)

    # clang package
    use_optimized_libclang = False
    llvm_install_dir = None
    clang_filebase = optionDict.get('CLANG_FILEBASE')
    clang_platform = optionDict.get('CLANG_PLATFORM')
    if clang_filebase and clang_platform:
        clang_extract_path = os.path.join(download_temp, 'libclang')
        llvm_install_dir = os.path.join(clang_extract_path, 'libclang') # package contains libclang subdir
        clang_suffix = optionDict.get('CLANG_FILESUFFIX')
        clang_suffix = clang_suffix if clang_suffix is not None else ''
        clang_url = (pkg_base_path + '/' + optionDict['CLANG_FILEBASE'] + '-' + clang_platform + clang_suffix + '.7z')
        add_download_extract(clang_url, clang_extract_path)
        use_optimized_libclang = is_windows()
        if use_optimized_libclang:
            opt_clang_url = (pkg_base_path + '/' + optionDict['CLANG_FILEBASE'] + '-windows-mingw_64' + clang_suffix + '.7z')
            opt_clang_path = os.path.join(download_temp, 'opt_libclang')
            opt_clang_to_copy = [os.path.join('bin', file) for file
                                 in ['libclang.dll', 'clangd.exe', 'clang-tidy.exe']]
            add_download_extract(opt_clang_url, opt_clang_path)

    elfutils_path = None
    if elfutils_url:
        elfutils_path = os.path.join(download_temp, 'elfutils')
        add_download_extract(elfutils_url, elfutils_path)

    python_path = None
    python_url = optionDict.get('PYTHON_URL')
    if is_windows() and python_url:
        python_path = os.path.join(download_temp, 'python')
        add_download_extract(python_url, python_path)

    # Documentation package for cross-references to Qt.
    # Unfortunately this doesn't follow the normal module naming convention.
    # We have to download, unpack, and repack renaming the toplevel directory.
    (download, repackage, documentation_local_url) = create_download_documentation_task(
        pkg_base_path + '/' + qt_base_path, os.path.join(download_temp, 'qtdocumentation'))
    download_work.addTaskObject(download)
    extract_work.addFunction(repackage.do)

    if openssl_libs:
        (download, repackage, openssl_local_url) = create_download_openssl_task(openssl_libs, os.path.join(download_temp, 'openssl'))
        download_work.addTaskObject(download)
        extract_work.addFunction(repackage.do)

    download_packages_work = Task('Get and extract all needed packages')
    download_packages_work.addFunction(download_work.run)
    download_packages_work.addFunction(extract_work.do)
    download_packages_work.do()

    # copy optimized clang package
    if use_optimized_libclang:
        for file in opt_clang_to_copy:
            source = os.path.join(opt_clang_path, 'libclang', file)
            target = os.path.join(llvm_install_dir, file)
            shutil.copyfile(source, target)

    # Qt Creator build depends on pre-built Qt binary packages.
    # Define the exact archive locations for each required module.
    qt_modules = ['qt5compat', 'qtbase', 'qtdeclarative', 'qtgraphicaleffects',
                  'qtimageformats', 'qtlocation', 'qtmacextras',
                  'qtquick3d', 'qtquickcontrols', 'qtquickcontrols2', 'qtquicktimeline',
                  'qtscript', 'qtserialport', 'qtshadertools', 'qtsvg', 'qttools',
                  'qttranslations', 'qtwayland', 'qtx11extras', 'qtxmlpatterns']
    qt_module_urls = module_urls(qt_modules)
    qt_module_urls.append(documentation_local_url)
    if qt_extra_module_url:
        qt_module_urls.append(qt_extra_module_url)
    qt_module_local_urls = [bld_utils.file_url(os.path.join(qt_temp, os.path.basename(url)))
                            for url in qt_module_urls]

    # download and install qt
    qt_path = os.path.join(work_dir, 'qt_install_dir')
    src_path = os.path.join(work_dir, 'qt-creator')
    build_path = os.path.join(work_dir, 'qt-creator_build')
    qt_install_args = [sys.executable, '-u', os.path.join(SCRIPT_ROOT_DIR, 'install_qt.py'),
                       '--qt-path', qt_path, '--temp-path', qt_temp]
    for module_url in qt_module_urls:
        qt_install_args.extend(['--qt-module', module_url])
    if is_linux() and icu_libs:
        qt_install_args.extend(['--icu7z', icu_libs])
    if is_windows():
        d3d_url = optionDict['D3D_URL']
        opengl_url = optionDict['OPENGLSW_URL']
        qt_install_args.extend(['--d3dcompiler7z', d3d_url,
                                '--opengl32sw7z', opengl_url])
    if openssl_local_url:
        qt_install_args.extend(['--openssl7z', openssl_local_url])
    check_call_log(qt_install_args,
                   work_dir)
    # Define Qt Creator build script arguments
    cmd_args = [sys.executable, '-u']
    cmd_args += [os.path.join(src_path, 'scripts', 'build.py'),
                 '--src', src_path,
                 '--build', build_path,
                 '--qt-path', qt_path]
    if llvm_install_dir:
        cmd_args += ['--llvm-path', llvm_install_dir]
    if ide_branding_path:
        cmd_args += ['--add-module-path', os.path.abspath(ide_branding_path)]
    if qtc_additional_config:
        cmd_args += ['--add-config=' + value for value in qtc_additional_config]
    if disable_docs:
        cmd_args += ['--no-docs']
    if skip_dmg:
        cmd_args += ['--no-dmg']
    for key in ['SIGNING_IDENTITY', 'SIGNING_FLAGS']:
        try:
            value = get_pkg_value(key)
            # for python2 this is unicode which is not accepted as environment
            if value and type(value) is not str:
                value = value.encode('UTF-8')
            if value:
                build_environment[key] = value
        except Exception:
            pass

    if is_macos():
        if has_unlock_keychain_script:
            cmd_args.extend(['--keychain-unlock-script', unlock_keychain_script()])
    if python_path:
        cmd_args.extend(['--python-path', python_path])
    if elfutils_path:
        cmd_args.extend(['--elfutils-path', elfutils_path])
    if skip_cdb:
        cmd_args.append('--no-cdb')
    check_call_log(cmd_args, work_dir, extra_env=build_environment, log_filepath=log_filepath, log_overwrite=True)

    if is_macos() and has_unlock_keychain_script:
        lock_keychain()

    # Qt Creator plugins
    plugin_dependencies = []
    additional_plugins = []

    if os.path.isdir(os.path.join(work_dir, "licensechecker")):
        add_args = ['--add-path', os.path.join(work_dir, 'license-managing')]
        additional_plugins.extend([make_QtcPlugin('licensechecker', 'licensechecker', qtcreator_version,
                                                  modules=qt_module_local_urls,
                                                  additional_arguments=add_args,
                                                  package_commercial=True)])
        plugin_dependencies = ['licensechecker']
    additional_plugins.extend([make_QtcPlugin('vxworks-qtcreator-plugin', 'vxworks-qtcreator-plugin', qtcreator_version,
                                              modules=qt_module_local_urls, dependencies=plugin_dependencies,
                                              package_commercial=True)])
    additional_plugins.extend([make_QtcPlugin('isoiconbrowser', 'qtquickdesigner', qtcreator_version,
                                              modules=qt_module_local_urls, dependencies=plugin_dependencies,
                                              package_commercial=True)])
    additional_plugins.extend([make_QtcPlugin('gammarayintegration', 'gammarayintegration', qtcreator_version,
                                              modules=qt_module_local_urls + [kdsme_url, gammaray_url] + module_urls(['qt3d', 'qtgamepad']),
                                              dependencies=plugin_dependencies,
                                              additional_arguments=['--deploy'])])
    additional_plugins.extend([make_QtcPlugin('appmanagerintegration', 'pcore-plugin-appman', qtcreator_version,
                                              modules=qt_module_local_urls,
                                              dependencies=plugin_dependencies,
                                              additional_arguments=['--with-docs'])]),
    plugin_telemetry_args = []
    if usp_server_url and usp_auth_key:
        plugin_telemetry_args = ['--add-config=-DUSP_SERVER_URL=' + optionDict['USP_SERVER_URL'],
                                 '--add-config=-DUSP_AUTH_KEY=' + optionDict['USP_AUTH_KEY']]
    additional_plugins.extend([make_QtcPlugin('plugin-telemetry', 'plugin-telemetry', qtcreator_version,
                                              modules=qt_module_local_urls,
                                              additional_arguments=plugin_telemetry_args)]),

    # Build Qt Creator plugins
    icu_local_url = bld_utils.file_url(os.path.join(qt_temp, os.path.basename(icu_libs))) if is_linux() else None
    ## extract qtcreator bin and dev packages
    qtcreator_path = os.path.join(work_dir, 'qtc_build')
    check_call_log(['7z', 'x', '-y', os.path.join(work_dir, 'qt-creator_build', 'qtcreator.7z'), '-o' + qtcreator_path],
                   work_dir, log_filepath=log_filepath)
    check_call_log(['7z', 'x', '-y', os.path.join(work_dir, 'qt-creator_build', 'qtcreator_dev.7z'), '-o' + qtcreator_path],
                   work_dir, log_filepath=log_filepath)
    build_qtcreator_plugins(additional_plugins, qtcreator_path, qtcreator_path, icu_url=icu_local_url,
                            openssl_url=openssl_local_url, additional_config=qtc_additional_config,
                            log_filepath=log_filepath)

    qtcreator_sha = bld_utils.get_commit_SHA(qtcreator_source)
    with open(os.path.join(work_dir, 'QTC_SHA1'), 'w') as f:
        f.write(qtcreator_sha + '\n')

    if is_linux():
        # summary of git SHA1s
        sha1s = collect_qt_creator_plugin_sha1s(additional_plugins)
        licensemanaging_source = os.path.join(work_dir, 'license-managing')
        if os.path.exists(licensemanaging_source):
            sha1s.append('license-managing: ' + bld_utils.get_commit_SHA(licensemanaging_source))
        sha1s.append('qt-creator: ' + qtcreator_sha)
        with open(os.path.join(work_dir, 'SHA1'), 'w') as f:
            f.writelines([sha + '\n' for sha in sha1s])

    # Create opensource source package
    create_qtcreator_source_package(os.path.join(work_dir, 'qt-creator'), None, qtcreator_version,
                                    'opensource', work_dir, log_filepath)
    # Create enterprise source package
    if installer_patch:
        check_call_log(['git', 'apply', installer_patch],
                       os.path.join(work_dir, 'qt-creator'), log_filepath=log_filepath)
        create_qtcreator_source_package(os.path.join(work_dir, 'qt-creator'), None, qtcreator_version,
                                        'enterprise', work_dir, log_filepath)

    # Build sdktool
    if sdktool_qtbase_src:
        sdktool_build_path = os.path.join(work_dir, 'sdktool_build')
        sdktool_target_path = os.path.join(sdktool_build_path, 'target')
        with BuildLog(log_filepath) as f:
            bld_sdktool.build_sdktool(sdktool_qtbase_src, os.path.join(sdktool_build_path, 'qt'),
                                      os.path.join(work_dir, 'qt-creator', 'src', 'tools', 'sdktool'),
                                      os.path.join(sdktool_build_path, 'src', 'tools', 'sdktool'),
                                      sdktool_target_path,
                                      'nmake' if is_windows() else 'make',
                                      redirect_output=f)
            bld_sdktool.zip_sdktool(sdktool_target_path, os.path.join(work_dir, 'sdktool.7z'),
                                    redirect_output=f)

    # repackage and sign opensource and enterprise packages on macOS
    # these are then for direct packaging in the offline installers
    if is_macos() and get_pkg_value('SIGNING_IDENTITY') and not os.getenv('DISABLE_MAC_SIGNING'):
        # use build_environment for SIGNING_IDENTITY
        repackage_and_sign_qtcreator(src_path, work_dir,
                                     'qtcreator-signed.7z',
                                     os.path.join(build_path, 'qtcreator.7z'), 'sdktool.7z',
                                     extra_env=build_environment)
        # packages plugins with package_commercial=True
        repackage_and_sign_qtcreator(src_path, work_dir,
                                     'qtcreator-commercial-signed.7z',
                                     os.path.join(build_path, 'qtcreator.7z'), 'sdktool.7z',
                                     extra_env=build_environment,
                                     additional_plugins=additional_plugins)

    # notarize
    if is_macos() and notarize:
        notarizeDmg(os.path.join(work_dir, 'qt-creator_build', 'qt-creator.dmg'), 'Qt Creator')

    # Upload
    file_upload_list = [] # pairs (source, dest), source relative to WORK_DIR, dest relative to server + dir_path
    snapshot_upload_list = [] # pairs (source, dest), source relative to server + dir_path, dest relative to snapshot server + snapshot_path

    # build log
    file_upload_list.append((log_filepath, target_env_dir + '/build_log.txt'))

    # macOS opensource dmg
    if is_macos() and not skip_dmg:
        dmg_filename = 'qt-creator-opensource-mac-x86_64-' + qtcreator_version + '.dmg'
        file_upload_list.append(('qt-creator_build/qt-creator.dmg', dmg_filename))
        snapshot_upload_list.append((dmg_filename, dmg_filename))

    # macOS signed zip
    if is_macos() and get_pkg_value('SIGNING_IDENTITY') and not os.getenv('DISABLE_MAC_SIGNING'):
        file_upload_list.append(('qtcreator-signed.7z', target_env_dir + '/qtcreator-signed.7z'))
        snapshot_upload_list.append((target_env_dir + '/qtcreator-signed.7z', target_env_dir + '/qtcreator-signed.7z'))
        file_upload_list.append(('qtcreator-commercial-signed.7z', target_env_dir + '/qtcreator-commercial-signed.7z'))

    # source packages
    source_package_list = glob(os.path.join(work_dir, 'qt-creator-*-src-' + qtcreator_version + '.*'))
    file_upload_list.extend([(os.path.basename(fn), '') for fn in source_package_list])
    qtc_source_packages = [os.path.basename(fn) for fn in
                           glob(os.path.join(work_dir, 'qt-creator-opensource-src-' + qtcreator_version + '.*'))]
    snapshot_upload_list.extend([(fn, fn) for fn in qtc_source_packages])

    if is_linux():
        # summary of git SHA1s
        file_upload_list.append(('SHA1', ''))
    file_upload_list.append(('QTC_SHA1', target_env_dir + '/QTC_SHA1'))
    snapshot_upload_list.append((target_env_dir + '/QTC_SHA1', target_env_dir + '/SHA1'))

    # installer 7z sources
    file_upload_list.append(('qt-creator_build/qtcreator.7z', target_env_dir + '/qtcreator.7z'))
    file_upload_list.append(('qt-creator_build/qtcreator_dev.7z', target_env_dir + '/qtcreator_dev.7z'))
    snapshot_upload_list.append((target_env_dir + '/qtcreator.7z', target_env_dir + '/qtcreator.7z'))
    snapshot_upload_list.append((target_env_dir + '/qtcreator_dev.7z', target_env_dir + '/qtcreator_dev.7z'))
    file_upload_list.append(('qt-creator_build/qtcreator-debug.7z', target_env_dir + '/qtcreator-debug.7z'))
    snapshot_upload_list.append((target_env_dir + '/qtcreator-debug.7z', target_env_dir + '/qtcreator-debug.7z'))
    for plugin in additional_plugins:
        plugin_name = plugin.name + '.7z'
        plugin_dev_name = plugin.name + '_dev.7z'
        plugin_debug_name = plugin.name + '-debug.7z'
        if os.path.isfile(os.path.join(work_dir, plugin_name)):
            file_upload_list.append((plugin_name, target_env_dir + '/' + plugin_name))
        if os.path.isfile(os.path.join(work_dir, plugin_dev_name)):
            file_upload_list.append((plugin_dev_name, target_env_dir + '/' + plugin_dev_name))
        if os.path.isfile(os.path.join(work_dir, plugin_debug_name)):
            file_upload_list.append((plugin_debug_name, target_env_dir + '/' + plugin_debug_name))
    if is_windows():
        if not skip_cdb:
            file_upload_list.append(('qt-creator_build/qtcreatorcdbext.7z', target_env_dir + '/qtcreatorcdbext.7z'))
            snapshot_upload_list.append((target_env_dir + '/qtcreatorcdbext.7z', target_env_dir + '/qtcreatorcdbext.7z'))
            file_upload_list.append(('qt-creator_build/wininterrupt.7z', target_env_dir + '/wininterrupt.7z'))
            snapshot_upload_list.append((target_env_dir + '/wininterrupt.7z', target_env_dir + '/wininterrupt.7z'))
    if sdktool_qtbase_src:
        file_upload_list.append(('sdktool.7z', target_env_dir + '/sdktool.7z'))
        snapshot_upload_list.append((target_env_dir + '/sdktool.7z', target_env_dir + '/sdktool.7z'))
    # upload files
    upload_files(base_path, file_upload_list, optionDict)
    remote_path = base_path + '/latest'
    # public snapshot
    if snapshot_server and snapshot_path:
        qtcreator_shortversion = re.match(r'\d+[.]\d+', qtcreator_version).group()
        snapshot_base = snapshot_path + '/' + qtcreator_shortversion + '/' + qtcreator_version + '/installer_source/'
        snapshot_target = snapshot_base + build_id + '/'
        do_execute_sub_process(
            [optionDict['SSH_COMMAND'], pkg_storage_server,
             "ssh", snapshot_server,
             'mkdir', '-p', snapshot_target + target_env_dir],
            work_dir, True)
        do_execute_sub_process(
            [optionDict['SSH_COMMAND'], pkg_storage_server,
             "ssh", snapshot_server,
             'ln', '-sfn', snapshot_target, snapshot_base + 'latest'],
            work_dir, True)

        for source, destination in snapshot_upload_list:
            cmd_args = [optionDict['SSH_COMMAND'], pkg_storage_server, "scp",
                        remote_path + '/' + source,
                        snapshot_server + ':' + snapshot_target + '/' + destination]
            do_execute_sub_process(cmd_args, work_dir)
    # create link from job name to display name
    update_job_link(unversioned_base_path, base_path, optionDict)

###############################
# handle_sdktool_build
###############################
def handle_sdktool_build(optionDict):
    # environment
    target_env_dir = optionDict['QTC_PLATFORM']
    work_dir = optionDict['WORK_DIR']
    qtcreator_version = get_qtcreator_version(os.path.join(work_dir, 'qt-creator'), optionDict)
    qtcreator_edition_name = optionDict.get('QT_CREATOR_EDITION_NAME') # optional
    unversioned_base_path = (optionDict['PACKAGE_STORAGE_SERVER_BASE_DIR']
                             + '/' + optionDict['QTC_BASE_DIR'])
    base_path = unversioned_base_path + '/' + qtcreator_version
    if qtcreator_edition_name:
        base_path += '_' + qtcreator_edition_name
    sdktool_qtbase_src = optionDict['SDKTOOL_QTBASESRC_BASE'] + optionDict['SDKTOOL_QTBASESRC_EXT']
    # build
    qtcreator_src = os.path.join(work_dir, 'qt-creator')
    download_temp = os.path.join(work_dir, 'downloads')
    sdktool_build_path = os.path.join(work_dir, 'sdktool_build')
    sdktool_target_path = os.path.join(sdktool_build_path, 'target')
    bld_sdktool.build_sdktool(sdktool_qtbase_src, os.path.join(sdktool_build_path, 'qt'),
                              os.path.join(work_dir, 'qt-creator', 'src', 'tools', 'sdktool'),
                              os.path.join(sdktool_build_path, 'src', 'tools', 'sdktool'),
                              sdktool_target_path,
                              'nmake' if is_windows() else 'make')
    bld_sdktool.zip_sdktool(sdktool_target_path, os.path.join(work_dir, 'sdktool.7z'))
    file_upload_list = [('sdktool.7z', target_env_dir + '/sdktool.7z')]
    if is_windows(): # wininterrupt & qtcreatorcdbext
        cmd_args = [sys.executable, '-u', os.path.join(qtcreator_src, 'scripts', 'build.py'),
                    '--src', qtcreator_src,
                    '--build', os.path.join(work_dir, 'build'),
                    '--no-qtcreator']

        download_packages_work = ThreadedWork('Get and extract all needed packages')
        python_path = None
        python_url = optionDict.get('PYTHON_URL')
        if python_url:
            python_path = os.path.join(download_temp, 'python')
            download_packages_work.addTaskObject(bldinstallercommon.create_download_extract_task(
                python_url, python_path, download_temp, None))
            cmd_args.extend(['--python-path', python_path])

        download_packages_work.run()

        check_call_log(cmd_args, work_dir)
        file_upload_list += [('build/wininterrupt.7z', target_env_dir + '/wininterrupt.7z'),
                             ('build/qtcreatorcdbext.7z', target_env_dir + '/qtcreatorcdbext.7z')]
    # upload
    upload_files(base_path, file_upload_list, optionDict)
    update_job_link(unversioned_base_path, base_path, optionDict)


def notarizeDmg(dmgPath, installer_name_base):
    # bundle-id is just a unique identifier without any special meaning, used to track the notarization progress
    bundleId = installer_name_base + "-" + strftime('%Y-%m-%d', gmtime())
    bundleId = bundleId.replace('_', '-').replace(' ', '')  # replace illegal characters for bundleId
    args = [sys.executable, 'notarize.py', '--dmg=' + dmgPath, '--bundle-id=' + bundleId]
    do_execute_sub_process(args, SCRIPT_ROOT_DIR)


###############################
# Update latest link
###############################
def update_latest_link(optionDict, remote_dest_dir, latest_dir):
    cmd_args = [optionDict['SSH_COMMAND'], optionDict['PACKAGE_STORAGE_SERVER_ADDR'], 'ln -sfn', remote_dest_dir, latest_dir]
    do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)


###############################
# create_remote_dirs
###############################
def create_remote_dirs(optionDict, server, dir_path):
    cmd_args = [optionDict['SSH_COMMAND'], '-t', '-t', server, 'mkdir -p', dir_path]
    do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)


###############################
# git archive given repository
###############################
def git_archive_repo(optionDict, repo_and_ref):
    archive_name = bldinstallercommon.git_archive_repo(repo_and_ref)
    # Create remote dest directories
    remote_dest_dir_base = optionDict['PACKAGE_STORAGE_SERVER_BASE_DIR'] + '/' + project_name + '/' + ref
    remote_dest_dir = remote_dest_dir_base + '/' + optionDict['BUILD_NUMBER']
    remote_dest_dir_latest = remote_dest_dir_base + '/' + 'latest'
    create_remote_dirs(optionDict, optionDict['PACKAGE_STORAGE_SERVER_ADDR'], remote_dest_dir)
    update_latest_link(optionDict, remote_dest_dir, remote_dest_dir_latest)
    # upload archive to network disk
    dest_dir = optionDict['PACKAGE_STORAGE_SERVER_USER'] + '@' + optionDict['PACKAGE_STORAGE_SERVER'] + ':' + remote_dest_dir
    cmd_args = ['scp', archive_name, remote_dest_dir]
    do_execute_sub_process(cmd_args, SCRIPT_ROOT_DIR)


def initPkgOptions(args):
    def mergeTwoDicts(x, y):
        """Given two dicts, merge them into a new dict as a shallow copy."""
        z = x.copy()
        z.update(y)
        return z

    def getDefaultTargetEnv():
        """For local builds define default build target"""
        if is_windows():
            return "win-msvc2015-Windows10-x64"
        elif is_linux():
            return "linux-g++-Rhel6.6-x64"
        elif is_macos():
            return "mac-clang-10.11-x64"
        else:
            raise RuntimeError("Unsupported host platform")

    optionDict = {}
    # Are we using local conf file for pkg options?
    if args.pkg_conf_file:
        options = optionparser.getPkgOptions(args.pkg_conf_file)
        optionDict = mergeTwoDicts(optionDict, options.configMap())
        optionDict['TARGET_ENV'] = args.target_env if args.target_env else getDefaultTargetEnv()
        optionDict['BUILD_NUMBER'] = str(strftime('%Y%m%d%H%M%S', gmtime()))
        optionDict['PACKAGE_STORAGE_SERVER_ADDR'] = optionDict['PACKAGE_STORAGE_SERVER_USER'] + '@' + optionDict['PACKAGE_STORAGE_SERVER']
    else:
        optionDict = dict(os.environ)
        # Check for command line overrides
        optionDict['LICENSE'] = args.license
        optionDict['PACKAGE_STORAGE_SERVER_BASE_DIR'] = args.path
        optionDict['OPENSSL_LIBS'] = args.openssl_libs
        optionDict['SNAPSHOT_SERVER_PATH'] = args.snapshot_path
        optionDict['TARGET_ENV'] = args.target_env if args.target_env else os.environ.get('cfg')
        optionDict['BUILD_NUMBER'] = args.build_number if args.build_number else os.environ.get('BUILD_NUMBER')

        optionDict['SIGNING_SERVER'] = get_pkg_value("SIGNING_SERVER")
        optionDict['SIGNING_PASSWORD'] = get_pkg_value("SIGNING_PASSWORD")
        optionDict['USP_SERVER_URL'] = get_pkg_value("USP_SERVER_URL")
        optionDict['USP_AUTH_KEY'] = get_pkg_value("USP_AUTH_KEY")
        optionDict['PACKAGE_STORAGE_SERVER_USER'] = get_pkg_value("PACKAGE_STORAGE_SERVER_USER")
        optionDict['PACKAGE_STORAGE_SERVER'] = get_pkg_value("PACKAGE_STORAGE_SERVER")
        optionDict['PACKAGE_STORAGE_SERVER_ADDR'] = args.server or get_pkg_value("PACKAGE_STORAGE_SERVER_ADDR")
        optionDict['PACKAGE_STORAGE_SERVER_PATH_HTTP'] = args.override_server_path_http or get_pkg_value("PACKAGE_STORAGE_SERVER_PATH_HTTP")
        optionDict['SNAPSHOT_SERVER'] = args.snapshot_server or get_pkg_value("SNAPSHOT_SERVER")
        optionDict['EXT_SERVER_BASE_URL'] = get_pkg_value("EXT_SERVER_BASE_URL")
        optionDict['RTA_SERVER_BASE_URL'] = get_pkg_value("RTA_SERVER_BASE_URL")
        optionDict['PKG_STAGING_SERVER'] = get_pkg_value("PKG_STAGING_SERVER")
        optionDict['PKG_STAGING_SERVER_UNAME'] = get_pkg_value("PKG_STAGING_SERVER_UNAME")
        optionDict['PROD_USER'] = get_pkg_value("PROD_USER")
        optionDict['PROD_ADDR'] = get_pkg_value("PROD_ADDR")

        if LOCAL_MODE:
            from getpass import getuser
            optionDict['PACKAGE_STORAGE_SERVER_USER'] = getuser() # current user
            optionDict['PACKAGE_STORAGE_SERVER'] = "127.0.0.1"
            optionDict['PACKAGE_STORAGE_SERVER_ADDR'] = optionDict['PACKAGE_STORAGE_SERVER_USER'] + "@" + optionDict['PACKAGE_STORAGE_SERVER']
            optionDict['PACKAGE_STORAGE_SERVER_BASE_DIR'] = LOCAL_INSTALLER_DIR
            optionDict['SNAPSHOT_SERVER'] = optionDict['PACKAGE_STORAGE_SERVER_ADDR']
            optionDict['SNAPSHOT_SERVER_PATH'] = LOCAL_INSTALLER_DIR

    if is_linux():
        optionDict['HOST_PLATFORM'] = 'linux'
    elif is_macos():
        optionDict['HOST_PLATFORM'] = 'mac'
    else:
        optionDict['HOST_PLATFORM'] = 'windows'

    optionDict['CURL_COMMAND'] = '%CURL%' if is_windows() else 'curl'
    optionDict['RM_COMMAND'] = '%RM%' if is_windows() else 'rm'
    optionDict['SSH_COMMAND'] = '%SSH%' if is_windows() else 'ssh'
    optionDict['SCP_COMMAND'] = '%SCP%' if is_windows() else 'scp'
    optionDict['WORK_DIR'] = WORK_DIR

    # Parse version number info if this build utilizes release description file
    if 'RELEASE_DESCRIPTION_FILE' in optionDict:
        # Path relative to script or absolute file path
        path = optionDict['RELEASE_DESCRIPTION_FILE']
        path = path if (os.path.isabs(path) and os.path.isfile(path)) else os.path.join(optionDict['WORK_DIR'], path)
        optionDict['RELEASE_DESCRIPTION_FILE'] = path
        # resolve configuration files base dir
        confBaseDir = optionDict['CONFIGURATIONS_FILE_BASE_DIR']
        confBaseDir = confBaseDir if (os.path.isabs(confBaseDir) and os.path.isdir(confBaseDir)) else os.path.join(optionDict['WORK_DIR'], confBaseDir)
        optionDict['CONFIGURATIONS_FILE_BASE_DIR'] = confBaseDir

        parser = ConfigParser()
        parser.read(path)
        for s in parser.sections():
            if s == 'release.global':
                version = bldinstallercommon.safe_config_key_fetch(parser, s, 'version')
                version_tag = bldinstallercommon.safe_config_key_fetch(parser, s, 'version_tag')
                optionDict['VERSION'] = version
                optionDict['VERSION_TAG'] = version_tag
                optionDict['VERSION_FULL'] = version if not version_tag else version + '-' + version_tag
    return optionDict


if __name__ == '__main__':
    # Define supported build steps
    bld_qtcreator                           = 'build_creator'
    bld_qtc_sdktool                         = 'build_sdktool'
    bld_licheck                             = 'licheck_bld'
    archive_repository                      = 'archive_repo'
    CMD_LIST =  (bld_qtcreator, bld_qtc_sdktool, bld_licheck, archive_repository)

    parser = argparse.ArgumentParser(prog="Build Wrapper", description="Manage all packaging related build steps.")
    parser.add_argument("-c", "--command", dest="command", required=True, choices=CMD_LIST, help=CMD_LIST)
    parser.add_argument("--pkg-conf-file", dest="pkg_conf_file", default="", help="instead of reading various config options from env variables read them from the given file.")
    parser.add_argument("-l", "--license", dest="license", default="", help="license type: enterprise or opensource")
    parser.add_argument("-b", "--build_number", dest="build_number", default="", help="Unique build number identifier")
    parser.add_argument("-s", "--server", dest="server", default="", help="Upload server e.g. <user>@<host>")
    parser.add_argument("--override_server_path_http", dest="override_server_path_http", help="In case we already have local downloaded modules or we want to use a different source it can be overwritten here.")
    parser.add_argument("-p", "--path", dest="path", default="", help="Path on server")
    parser.add_argument("-e", "--target_env", dest="target_env", default="", help="Target environment: Linux, Linux_64, mac, win")
    parser.add_argument("-o", "--openssl_libs", dest="openssl_libs", default="", help="Url for pre-compiled openssl libraries")
    parser.add_argument("--archive-repo", dest="archive_repo", default="", help="Create Git archive from the given repository. Use syntax: \"git-url#ref\"")
    parser.add_argument("--snapshot-server", dest="snapshot_server", default="", help="Additional snapshot upload server <user>@<host> (is uploaded from upload server)")
    parser.add_argument("-snapshot-path", dest="snapshot_path", default="", help="Path on additional snapshot upload server")
    parser.add_argument("--qtcreator-plugin-config", help="Path to Qt Creator plugin specification to be used with build_qtcreator_plugins command")
    if len(sys.argv) < 2:
        parser.print_usage()
        raise RuntimeError()
    args = parser.parse_args(sys.argv[1:])

    # Init configuration options first
    optionDict = initPkgOptions(args)

    # Execute given command
    # QtCreator specific
    if args.command == bld_qtcreator:
        handle_qt_creator_build(optionDict, parseQtCreatorPlugins(args.pkg_conf_file))
    # sdktool
    elif args.command == bld_qtc_sdktool:
        handle_sdktool_build(optionDict)
    # Qt Installer-Framework specific
    elif args.command == bld_licheck:
        handle_qt_licheck_build(optionDict)
    elif args.command == archive_repository:
        git_archive_repo(optionDict, args.archive_repo)
    else:
        print('Unsupported command')
