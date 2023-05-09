#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
#
# Copyright (C) 2023 The Qt Company Ltd.
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

import argparse
import json
import os
import re
import shutil
import sys
from collections import namedtuple
from configparser import ConfigParser
from contextlib import suppress
from functools import partial
from getpass import getuser
from glob import glob
from io import TextIOWrapper
from pathlib import Path
from time import gmtime, strftime
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.request import urlopen

from bld_sdktool import build_sdktool, zip_sdktool
from bld_utils import (
    download,
    file_url,
    get_commit_sha,
    is_linux,
    is_macos,
    is_windows,
    run_command,
)
from bldinstallercommon import (
    clone_repository,
    copy_tree,
    create_download_and_extract_tasks,
    create_download_extract_task,
    create_extract_function,
    git_archive_repo,
    safe_config_key_fetch,
)
from install_qt import install_qt
from installer_utils import ch_dir
from logging_util import init_logger
from notarize import notarize
from optionparser import get_pkg_options
from read_remote_config import get_pkg_value
from runner import run_cmd
from threadedwork import Task, ThreadedWork

log = init_logger(__name__, debug_mode=False)

SCRIPT_ROOT_DIR = os.path.dirname(os.path.realpath(__file__))
WORK_DIR = os.getenv('PKG_NODE_ROOT', os.path.abspath(os.path.join(__file__, '../../../')))
LOCAL_MODE = os.getenv('LOCAL_MODE')  # if set, installers will be copied to a local directory
LOCAL_INSTALLER_DIR = os.getenv('LOCAL_INSTALLER_DIR', os.path.join(WORK_DIR, 'installers'))

if LOCAL_MODE:
    assert os.path.exists(LOCAL_INSTALLER_DIR), f"Local installer dest dir does not exist: {LOCAL_INSTALLER_DIR}"
    log.info("Installer files will be copied to local directory: %s", LOCAL_INSTALLER_DIR)


###############################
# Unlock keychain script
###############################
def unlock_keychain_script() -> str:
    return '/Users/qt/unlock-keychain.sh'


###############################
# Unlock keychain
###############################
def unlock_keychain() -> None:
    run_cmd(cmd=unlock_keychain_script(), cwd=SCRIPT_ROOT_DIR)


###############################
# Lock keychain
###############################
def lock_keychain() -> None:
    with suppress(Exception):
        run_cmd(cmd="/Users/qt/lock-keychain.sh", cwd=SCRIPT_ROOT_DIR)


###########################################
# init snapshot build dir and upload files
###########################################
def init_snapshot_dir_and_upload_files(
    option_dict: Dict[str, str],
    project_name: str,
    project_version_or_branch: str,
    build_number: str,
    file_upload_list: List[str],
    subdir: str = "",
) -> None:
    if subdir != "" and subdir[0] != "/":
        subdir = "/" + subdir
    remote_path_base = option_dict['PACKAGE_STORAGE_SERVER_BASE_DIR'] + '/' + project_name + '/' + project_version_or_branch
    remote_path_snapshot_dir = remote_path_base + '/' + build_number
    remote_path_latest_link = remote_path_base + '/' + 'latest'
    # ensure remote directory exists
    create_remote_dirs(option_dict, option_dict['PACKAGE_STORAGE_SERVER_ADDR'], remote_path_snapshot_dir + subdir)
    # upload files
    target = option_dict['PACKAGE_STORAGE_SERVER_ADDR'] + ':' + remote_path_snapshot_dir + subdir
    for item in file_upload_list:
        run_cmd(cmd=[option_dict['SCP_COMMAND'], item, target], cwd=option_dict["WORK_DIR"])
    # update 'latest' symlink
    update_latest_link(option_dict, remote_path_snapshot_dir, remote_path_latest_link)


###############################
# handle_qt_licheck_build
###############################
def handle_qt_licheck_build(option_dict: Dict[str, str]) -> None:
    if option_dict['LICENSE'] == 'enterprise':
        # Build license checker
        exe_dir = option_dict['WORK_DIR'] + '/license-managing/licheck'
        upload_path = option_dict['PACKAGE_STORAGE_SERVER_ADDR'] + ':' + option_dict['PACKAGE_STORAGE_SERVER_BASE_DIR'] + '/' + option_dict['LICENSE'] + '/licheck/'
        if option_dict['TARGET_ENV'].lower().startswith("win"):
            cmd_args = [r'c:\Utils\jom\jom.exe', '-f', 'Makefile_win']
            run_cmd(cmd=cmd_args, cwd=exe_dir)
            cmd_args = [option_dict['SCP_COMMAND'], 'licheck.exe', upload_path]
            run_cmd(cmd=cmd_args, cwd=exe_dir)
        elif option_dict['TARGET_ENV'].lower().startswith("linux"):
            cmd_args = ['make', '-j6', '-f', 'Makefile_unix']
            run_cmd(cmd=cmd_args, cwd=exe_dir)
            licheck = 'licheck64' if option_dict['TARGET_ENV'].find("x64") >= 1 else 'licheck32'
            cmd_args = ['rsync', '-r', licheck, upload_path + licheck]
            run_cmd(cmd=cmd_args, cwd=exe_dir)
        else:
            cmd_args = ['make', '-j6', '-f', 'Makefile_macos']
            run_cmd(cmd=cmd_args, cwd=exe_dir)
            cmd_args = ['rsync', '-r', 'licheck_mac', upload_path + 'licheck_mac']
            run_cmd(cmd=cmd_args, cwd=exe_dir)
    else:
        # opensource, do nothing
        log.info("Opensource build, nothing to build...")


###############################
# Download Qt documentation, extract and repackage with toplevel dir renamed
###############################
def move_files_to_parent_dir(source: str) -> None:
    destination = os.path.abspath(os.path.join(source, os.pardir))
    log.info("Moving files from: [%s] to: [%s]", source, destination)
    assert os.path.isdir(source), f"The given source is not a directory: {source}"
    assert os.path.isdir(destination), f"The destination is not a directory: {destination}"
    files_list = os.listdir(source)
    for file in files_list:
        shutil.move(os.path.join(source, file), destination)
    os.rmdir(source)


def create_download_documentation_task(
    base_url: str, download_path: str
) -> Tuple[Task, Task, str]:
    doc_base_url = base_url + "/doc"

    use_local = urlparse(doc_base_url).scheme == "file"
    log.info("doc_base_url: %s use_local: %s", doc_base_url, use_local)
    if use_local:
        file_list = os.listdir(doc_base_url[len("file:///"):])
    else:
        with urlopen(doc_base_url) as urlpath:
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

    def create_remove_one_dir_level_function(path: str) -> Any:
        return lambda: move_files_to_parent_dir(path)

    def repackage() -> None:
        source_path = extract_path
        dest_doc_path = os.path.join(download_path, 'doc')
        os.rename(source_path, dest_doc_path)
        # limit compression to 2 cores to limit memory footprint for 32bit Windows
        run_command(['7z', 'a', '-mx1', '-mmt2', '-md32m', '-ms=1g', target_filepath, dest_doc_path],
                    dest_doc_path)

    download_task = Task(f"downloading documentation from {base_url}", function=None)
    for item in file_list:
        url = base_url + '/doc/' + item
        download_filepath = os.path.join(download_path, item)
        download_task.add_function(download, url, download_filepath)
        download_task.add_function(create_extract_function(download_filepath, extract_path))
        download_task.add_function(create_remove_one_dir_level_function(os.path.join(extract_path, item.rstrip(".zip"))))

    repackage_task = Task(f"repackaging documentation as {target_filepath}", function=None)
    repackage_task.add_function(repackage)
    return (download_task, repackage_task, file_url(target_filepath))


def create_download_openssl_task(url: str, download_path: str) -> Tuple[Task, Task, str]:
    # create openssl 7zips which just contain the DLLs / SOs, so they can just be extracted
    # into the Qt lib directory and later on deployed with Qt
    filename = Path(url).name
    download_filepath = os.path.join(download_path, filename)
    extract_path = os.path.join(download_path, 'openssl_download')
    target_filepath = os.path.join(download_path, 'openssl.7z')

    def repackage() -> None:
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
        run_command(['7z', 'a', '-mmt2', target_filepath, pattern],
                    source_path)

    download_task = Task(f"downloading openssl from {url}", function=None)
    download_task.add_function(download, url, download_filepath)
    repackage_task = Task(f"repackaging openssl as {target_filepath}", function=None)
    repackage_task.add_function(create_extract_function(download_filepath, extract_path))
    repackage_task.add_function(repackage)
    return (download_task, repackage_task, file_url(target_filepath))


PluginConf = namedtuple('PluginConf', ['git_url', 'branch_or_tag', 'checkout_dir'])


def parse_qtcreator_plugins(pkg_conf_file: str) -> List[PluginConf]:
    """Parse available Qt Creator plugins from configuration file"""
    plugin_list: List[PluginConf] = []
    if not pkg_conf_file:
        return plugin_list
    plugin_options = get_pkg_options(pkg_conf_file)
    section_name = "QtCreator.Build.Plugin"
    key_name = "plugins"
    if not plugin_options.option_exists(section_name, key_name):
        return plugin_list
    plugin_conf_list = plugin_options.config_section_map(section_name)[key_name]
    for plugin_name in plugin_conf_list.replace(" ", "").replace("\n", "").split(","):
        section = "QtCreator.Build.Plugin." + plugin_name
        plugin_url = plugin_options.config_section_map(section)["QTC_PLUGIN_GIT_URL"]
        branch_or_tag = plugin_options.config_section_map(section)["QTC_PLUGIN_GIT_BRANCH_OR_TAG"]
        checkout_dir_name = plugin_options.config_section_map(section)["QTC_PLUGIN_CHECKOUT_DIR_NAME"]
        plugin = PluginConf(git_url=plugin_url, branch_or_tag=branch_or_tag, checkout_dir=checkout_dir_name)
        plugin_list.extend([plugin])
    return plugin_list


QtcPlugin = namedtuple('QtcPlugin', ['name',
                                     'path',
                                     'version',
                                     'dependencies',
                                     'modules',
                                     'additional_arguments',
                                     'build',
                                     'package_commercial'])


def make_qtcplugin(
    name: str,
    path: str,
    version: str,
    dependencies: Optional[List[str]] = None,
    modules: Optional[List[str]] = None,
    additional_arguments: Optional[List[str]] = None,
    build: bool = True,
    package_commercial: bool = False,
) -> QtcPlugin:
    return QtcPlugin(
        name=name,
        path=path,
        version=version,
        dependencies=dependencies or [],
        modules=modules or [],
        additional_arguments=additional_arguments or [],
        build=build,
        package_commercial=package_commercial,
    )


class BuildLog:
    def __init__(self, log_filepath: str, log_overwrite: bool = False) -> None:
        self.file: Optional[TextIOWrapper] = None
        self.log_filepath = log_filepath
        self.log_overwrite = log_overwrite

    def __enter__(self) -> TextIOWrapper:
        try:
            self.file = open(self.log_filepath, 'w' if self.log_overwrite else 'a', encoding="utf-8")
        except Exception:
            log.error("Failed to write log file '%s'", self.log_filepath)
            sys.stdout.flush()
            raise
        return self.file

    def __exit__(self, exc_type: Any, exc_value: Any, exc_traceback: Any) -> Optional[bool]:
        if self.file is not None:
            self.file.close()
        if exc_type:  # exception raised -> print the log and re-raise
            with open(self.log_filepath, "r", encoding="utf-8") as handle:
                log.info(handle.read())
            return True  # re-raise
        return None


# writes output of process to log_filepath
# on error it dumps the log file to stdout as well
def check_call_log(
    args: List[str],
    execution_path: str,
    extra_env: Optional[Dict[str, str]] = None,
    log_filepath: Optional[str] = None,
    log_overwrite: bool = False,
) -> None:
    extra_env = extra_env or os.environ.copy()
    if not log_filepath:
        run_cmd(cmd=args, cwd=execution_path, env=extra_env)
    else:
        with BuildLog(log_filepath, log_overwrite) as handle:
            run_cmd(cmd=args, cwd=execution_path, env=extra_env, redirect=handle)


def create_qtcreator_source_package(option_dict: Dict[str, str], source_path: str, plugin_name: Optional[str], version: str, edition: str, target_path: str, log_filepath: str) -> None:
    namepart = '-' + plugin_name if plugin_name else ''
    file_base = 'qt-creator-' + edition + namepart + '-src-' + version
    target_base = os.path.join(target_path, file_base)
    create_tar = is_linux()
    create_zip = is_windows() and '32' not in option_dict['TARGET_ENV']
    if create_tar or create_zip:
        Path(target_base).mkdir(parents=True, exist_ok=True)
        copy_tree(source_path, target_base)
        if create_tar:
            check_call_log(['tar', 'czf', file_base + '.tar.gz', '--exclude', '.git', file_base],
                           target_path, log_filepath=log_filepath)
            check_call_log(['tar', 'cJf', file_base + '.tar.xz', '--exclude', '.git', file_base],
                           target_path, log_filepath=log_filepath)
        if create_zip:
            check_call_log(['7z', 'a', '-tzip', file_base + '.zip', file_base, '-xr!.git'],
                           target_path, log_filepath=log_filepath)


def qtcreator_build_plugin_script(qtcreator_dev_path: str) -> str:
    if is_macos():
        # scripts can be within the app bundle
        apps = glob(os.path.join(qtcreator_dev_path, '*.app'))
        app = apps[0] if apps else os.path.join(qtcreator_dev_path, 'Qt Creator.app')
        path = os.path.join(app, 'Contents', 'Resources', 'scripts', 'build_plugin.py')
    else:
        # scripts can be in share directory
        path = os.path.join(qtcreator_dev_path, 'share', 'qtcreator', 'scripts', 'build_plugin.py')
    return path if os.path.exists(path) else os.path.join(qtcreator_dev_path, 'scripts', 'build_plugin.py')


def build_qtcreator_plugins(
    option_dict: Dict[str, str],
    build_environment: Dict[str, str],
    plugins: List[QtcPlugin],
    qtcreator_path: str,
    qtcreator_dev_path: str,
    icu_url: Optional[str] = None,
    openssl_url: Optional[str] = None,
    additional_config: Optional[List[str]] = None,
    log_filepath: str = "",
) -> None:
    work_dir = option_dict['WORK_DIR']
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
                raise RuntimeError(f'did not find dependency "{dependency_name}" for plugin "{plugin.name}"')
            dependency = matches[0]
            cmd_arguments.extend(['--add-path', os.path.join(work_dir, dependency.name + '-build', 'build')])
            for module in dependency.modules:
                if module not in modules:
                    modules.append(module)
        cmd_arguments.extend(plugin.additional_arguments)
        ide_branding_path = option_dict.get('IDE_BRANDING_PATH')  # optional
        if ide_branding_path:
            cmd_arguments.extend(['--add-module-path', os.path.abspath(ide_branding_path)])
        if additional_config:
            cmd_arguments += ['--add-config=' + value for value in additional_config]

        # install qt
        with ch_dir(work_dir):
            install_qt(
                qt_path=qt_path,
                qt_modules=modules,
                icu_url=icu_url if is_linux() else None,
                openssl_url=openssl_url,
            )

        check_call_log(cmd_arguments, work_dir, extra_env=build_environment,
                       log_filepath=log_filepath)
        create_qtcreator_source_package(option_dict, os.path.join(work_dir, plugin.path), plugin.name, plugin.version,
                                        'enterprise', work_dir, log_filepath)


def get_qtcreator_version(path_to_qtcreator_src: str, option_dict: Dict[str, str]) -> str:
    expr = re.compile(r'\s*set[(]\s*IDE_VERSION_DISPLAY\s*"([^\s]+)"')

    ide_branding_path = option_dict.get('IDE_BRANDING_PATH')  # optional
    ide_branding_path = ide_branding_path if ide_branding_path else os.path.join(path_to_qtcreator_src, 'cmake')
    ide_branding_file = os.path.join(ide_branding_path, 'QtCreatorIDEBranding.cmake')

    with open(ide_branding_file, 'r', encoding="utf-8") as handle:
        for line in handle:
            match = expr.match(line)
            if match:
                return match.group(1)
    return ""


def make_qtcplugin_from_json(plugin_json: Dict[str, str]) -> QtcPlugin:
    return QtcPlugin(name=plugin_json['Name'],
                     path=plugin_json['Path'],
                     version=plugin_json.get('Version'),
                     dependencies=plugin_json.get('Dependencies') or [],
                     modules=plugin_json.get('Modules') or [],
                     additional_arguments=plugin_json.get('AdditionalArguments') or [],
                     build=plugin_json.get('Build') or True,
                     package_commercial=plugin_json.get('PackageCommercial') or False)


def parse_qt_creator_plugin_conf(
    plugin_conf_file_path: str, option_dict: Dict[str, str]
) -> List[QtcPlugin]:
    data = {}
    with open(plugin_conf_file_path, 'r', encoding="utf-8") as handle:
        data = json.load(handle)
    plugins_json = data['Plugins']
    if is_linux():
        platform_name = 'linux'
    elif is_windows():
        platform_name = 'windows'
    else:
        platform_name = 'mac'

    def valid_for_platform(plugin_json: Dict[str, str]) -> bool:
        platforms = plugin_json.get('Platforms')
        return not platforms or platform_name in platforms

    def fixup_plugin(plugin: QtcPlugin) -> QtcPlugin:
        plugin = plugin._replace(modules=[module % option_dict for module in plugin.modules])
        plugin = plugin._replace(additional_arguments=[arg % option_dict for arg in plugin.additional_arguments])
        return plugin
    return [fixup_plugin(make_qtcplugin_from_json(plugin)) for plugin in plugins_json if valid_for_platform(plugin)]


def collect_qt_creator_plugin_sha1s(option_dict: Dict[str, str], plugins: List[QtcPlugin]) -> List[str]:
    work_dir = option_dict['WORK_DIR']
    sha1s = []
    for name in [p.name for p in plugins if p.build and os.path.isdir(os.path.join(work_dir, p.path))]:
        with open(os.path.join(work_dir, name + '.7z.git_sha'), 'r', encoding="utf-8") as handle:
            sha = handle.read().strip()
            sha1s.append(name + ': ' + sha)
    return sorted(sha1s)


# file_upload_list: list of 2-tuples,
# (source_file_relative_to_WORK_DIR, target_file_or_path_relative_to_remote_path)
def upload_files(remote_path: str, file_upload_list: List[Tuple[str, str]], option_dict: Dict[str, str]) -> None:
    # prepare remote paths
    pkg_storage_server = option_dict['PACKAGE_STORAGE_SERVER_ADDR']
    latest_path = remote_path + '/latest'
    dir_path = remote_path + '/' + option_dict['BUILD_NUMBER']
    # create destination paths
    directories = [os.path.dirname(dest) for (_, dest) in file_upload_list]
    for destdir in set(directories):
        create_remote_dirs(option_dict, pkg_storage_server, dir_path + '/' + destdir)
    # "latest" link
    update_latest_link(option_dict, dir_path, latest_path)
    # upload files
    for source, destination in file_upload_list:
        target = pkg_storage_server + ':' + dir_path + '/' + destination
        cmd_args = [option_dict['SCP_COMMAND'], source, target]
        run_cmd(cmd=cmd_args, cwd=option_dict["WORK_DIR"])


def update_job_link(
    remote_path_base: str, remote_target_path: str, option_dict: Dict[str, str]
) -> None:
    remote_link = remote_path_base + '/' + option_dict['PULSE_PROJECT']
    update_latest_link(option_dict, remote_target_path, remote_link)


def extract_qtc_sdktool(
    sdktool_package: str,
    extract_path: str,
    app: str,
    log_filepath: Optional[str]
) -> None:
    check_call_log(['7z', 'x', '-y',
                    sdktool_package,
                    '-o' + os.path.join(extract_path, app,
                                        'Contents', 'Resources', 'libexec')],
                   extract_path, log_filepath=log_filepath)


def write_qtc_settings(
    settings: List[str],
    extract_path: str,
    app: str,
    log_filepath: Optional[str]  # pylint: disable=W0613
) -> None:
    settingspath = (
        os.path.join(extract_path, app, 'Contents', 'Resources', 'QtProject')
        if is_macos()
        else os.path.join(extract_path, 'share', 'qtcreator', 'QtProject'))
    Path(settingspath).mkdir(parents=True, exist_ok=True)
    with open(os.path.join(settingspath, 'QtCreator.ini'), 'w', encoding='utf-8') as file:
        text = '\n'.join(settings)
        file.write(text)


def sign_qtc(
    qtcreator_path: str,
    extra_env: Dict[str, str],
    extract_path: str,
    app: str,
    log_filepath: Optional[str]
) -> None:
    if not is_macos() or not get_pkg_value('SIGNING_IDENTITY'):
        return
    unlock_keychain()
    import_path = os.path.join(qtcreator_path, 'scripts')
    check_call_log([sys.executable, '-u', '-c', "import common; common.codesign('"
                    + os.path.join(extract_path, app)
                    + "')"],
                   import_path, extra_env=extra_env, log_filepath=log_filepath)


def repackage_qtcreator(
    work_dir: str,
    qtcreator_package: str,
    result_package: str,
    operations: List[Callable[[str, str, Optional[str]], None]],
    log_filepath: Optional[str] = None,
) -> None:
    extract_path = os.path.join(work_dir, 'temp_repackaged_qtc')
    Path(extract_path).mkdir(parents=True, exist_ok=True)
    # extract Qt Creator
    check_call_log(['7z', 'x', '-y',
                    os.path.join(work_dir, qtcreator_package),
                    '-o' + extract_path],
                   work_dir, log_filepath=log_filepath)
    # find app name
    apps = [d for d in os.listdir(extract_path) if d.endswith('.app')]
    app = apps[0] if is_macos() else '*'
    # ^ '*' is for Lin/Win for the 7z re-packaging at the end, see zipPatternForApp in qtc/build.py
    for operation in operations:
        operation(extract_path, app, log_filepath)
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
def handle_qt_creator_build(option_dict: Dict[str, str], qtcreator_plugins: List[PluginConf]) -> None:
    target_env_dir = option_dict['QTC_PLATFORM']
    work_dir = option_dict['WORK_DIR']
    build_environment = dict(os.environ)
    # remove LLVM_INSTALL_DIR set by COIN templates
    build_environment.pop('LLVM_INSTALL_DIR', None)

    # Get Qt Creator sources if not present yet
    if 'QT_CREATOR_GIT_URL' in option_dict:
        qtcreator_source_directory = os.path.join(work_dir, 'qt-creator')
        if os.path.exists(qtcreator_source_directory):
            shutil.rmtree(qtcreator_source_directory)
        Path(qtcreator_source_directory).mkdir(parents=True)
        clone_repository(option_dict['QT_CREATOR_GIT_URL'], option_dict['QT_CREATOR_GIT_BRANCH'],
                         qtcreator_source_directory, full_clone=True, init_subrepos=True)
    # Get Qt Creator plugin sources if not present yet
    for plugin_conf in qtcreator_plugins:
        checkout_dir = os.path.join(work_dir, plugin_conf.checkout_dir)
        if plugin_conf.git_url:
            if os.path.exists(checkout_dir):
                shutil.rmtree(checkout_dir)
            Path(checkout_dir).mkdir(parents=True)
            clone_repository(plugin_conf.git_url, plugin_conf.branch_or_tag, checkout_dir, full_clone=True)

    # Build time variables
    qtcreator_source = os.path.join(work_dir, 'qt-creator')
    qtcreator_version = get_qtcreator_version(qtcreator_source, option_dict)
    pkg_base_path = option_dict['PACKAGE_STORAGE_SERVER_PATH_HTTP']
    # Check if the archives reside on network disk (http) or on local file system
    scheme = "" if urlparse(pkg_base_path).scheme != "" else "file://"
    pkg_base_path = scheme + pkg_base_path
    pkg_storage_server = option_dict['PACKAGE_STORAGE_SERVER_ADDR']
    qtcreator_edition_name = option_dict.get('QT_CREATOR_EDITION_NAME')  # optional
    unversioned_base_path = option_dict['PACKAGE_STORAGE_SERVER_BASE_DIR'] + '/' + option_dict['QTC_BASE_DIR']
    base_path = unversioned_base_path + '/' + qtcreator_version
    if qtcreator_edition_name:
        base_path += '_' + qtcreator_edition_name
    snapshot_server = option_dict.get('SNAPSHOT_SERVER')  # optional
    snapshot_path = option_dict['SNAPSHOT_SERVER_PATH']  # optional
    qt_base_path = option_dict['QTC_QT_BASE_DIR']
    ide_branding_path = option_dict.get('IDE_BRANDING_PATH')  # optional
    installer_patch = option_dict.get('INSTALLER_PATCH')  # optional
    skip_cdb = option_dict.get('SKIP_CDB')  # optional
    skip_dmg = option_dict.get('SKIP_DMG')  # optional
    with_cpack = option_dict.get('WITH_CPACK')  # optional
    build_id = option_dict['BUILD_NUMBER']
    icu_libs = option_dict.get('ICU_LIBS')  # optional
    openssl_libs = option_dict.get('OPENSSL_LIBS')  # optional
    openssl_local_url = None  # optionally defined later
    qt_extra_module_url = option_dict.get('QT_EXTRA_MODULE_URL')  # optional
    qt_postfix = os.environ['QT_POSTFIX']
    sdktool_base = option_dict.get('SDKTOOL_QTBASESRC_BASE')  # optional
    sdktool_ext = option_dict.get('SDKTOOL_QTBASESRC_EXT')  # optional
    sdktool_qtbase_src = sdktool_base + sdktool_ext if sdktool_base and sdktool_ext else None  # optional
    download_temp = os.path.join(work_dir, 'downloads')
    has_unlock_keychain_script = os.path.exists(unlock_keychain_script())
    # from 4.4 on we use external elfutil builds and also build on Windows
    elfutils_url = option_dict.get('ELFUTILS_URL')
    log_filepath = os.path.join(work_dir, 'build_log.txt')
    do_notarize = option_dict.get('NOTARIZE')
    usp_server_url = option_dict.get('USP_SERVER_URL')
    usp_auth_key = option_dict.get('USP_AUTH_KEY')
    qtc_additional_cfg: str = option_dict.get('QTC_ADDITIONAL_CONFIG', '')  # optional
    disable_docs = option_dict.get('DISABLE_DOCS')  # optional
    do_repackaging = not option_dict.get('DISABLE_MAC_SIGNING')
    qtc_additional_config: List[str] = qtc_additional_cfg.split()
    qt_temp = os.path.join(work_dir, 'qt_temp')

    def module_filename(module: str) -> str:
        return module + '-' + qt_postfix + '.7z'

    def module_urls(modules: List[str]) -> List[str]:
        return [pkg_base_path + '/' + qt_base_path + '/' + module + '/' + module_filename(module)
                for module in modules]

    # Define paths for pre-built kdsme and gammaray packages
    kdsme_url = option_dict.get("GAMMARAY_BASE_DIR", "")
    if kdsme_url:
        kdsme_url = pkg_base_path + '/' + kdsme_url + '/' + target_env_dir + '/qt5_kdsme.7z'
    gammaray_url = option_dict.get("GAMMARAY_BASE_DIR", "")
    if gammaray_url:
        gammaray_url = (
            pkg_base_path + '/' + gammaray_url + '/' + target_env_dir + '/qt5_gammaray.7z'
        )

    download_work = ThreadedWork('Download packages')
    extract_work = Task('Extract packages', function=None)

    def add_download_extract(url: str, target_path: str) -> None:
        (dl_task, extract) = create_download_and_extract_tasks(
            url, target_path, download_temp)
        download_work.add_task_object(dl_task)
        extract_work.add_function(extract.do_task)

    # clang package
    use_optimized_libclang = False
    llvm_install_dir = None
    clang_filebase = option_dict.get('CLANG_FILEBASE')
    clang_platform = option_dict.get('CLANG_PLATFORM')
    opt_clang_to_copy: List[str] = []
    if clang_filebase and clang_platform:
        clang_extract_path = os.path.join(download_temp, 'libclang')
        llvm_install_dir = os.path.join(clang_extract_path, 'libclang')  # package contains libclang subdir
        clang_suffix = option_dict.get('CLANG_FILESUFFIX')
        clang_suffix = clang_suffix if clang_suffix is not None else ''
        clang_url = (
            pkg_base_path + '/' + option_dict['CLANG_FILEBASE'] + '-' + clang_platform
            + clang_suffix + '.7z'
        )
        add_download_extract(clang_url, clang_extract_path)
        use_optimized_libclang = is_windows()
        if use_optimized_libclang:
            opt_clang_url = (
                pkg_base_path + '/' + option_dict['CLANG_FILEBASE'] + '-windows-mingw_64'
                + clang_suffix + '.7z'
            )
            opt_clang_path = os.path.join(download_temp, 'opt_libclang')
            opt_clang_to_copy = [os.path.join('bin', file) for file
                                 in ['libclang.dll', 'clangd.exe', 'clang-tidy.exe']]
            add_download_extract(opt_clang_url, opt_clang_path)

    elfutils_path = None
    if elfutils_url:
        elfutils_path = os.path.join(download_temp, 'elfutils')
        add_download_extract(elfutils_url, elfutils_path)

    python_path = None
    python_url = option_dict.get('PYTHON_URL')
    if is_windows() and python_url:
        python_path = os.path.join(download_temp, 'python')
        add_download_extract(python_url, python_path)

    # Documentation package for cross-references to Qt.
    # Unfortunately this doesn't follow the normal module naming convention.
    # We have to download, unpack, and repack renaming the toplevel directory.
    (dl_task, repackage, documentation_local_url) = create_download_documentation_task(
        pkg_base_path + '/' + qt_base_path, os.path.join(download_temp, 'qtdocumentation'))
    download_work.add_task_object(dl_task)
    extract_work.add_function(repackage.do_task)

    if openssl_libs:
        (dl_task, repackage, openssl_local_url) = create_download_openssl_task(openssl_libs, os.path.join(download_temp, 'openssl'))
        download_work.add_task_object(dl_task)
        extract_work.add_function(repackage.do_task)

    download_packages_work = Task('Get and extract all needed packages', function=None)
    download_packages_work.add_function(download_work.run)
    download_packages_work.add_function(extract_work.do_task)
    download_packages_work.do_task()

    # copy optimized clang package
    if use_optimized_libclang:
        for file in opt_clang_to_copy:
            source = os.path.join(opt_clang_path, 'libclang', file)
            target = os.path.join(llvm_install_dir or "", file)
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
    qt_module_local_urls = [file_url(os.path.join(qt_temp, os.path.basename(url)))
                            for url in qt_module_urls]

    # download and install qt
    qt_path = os.path.join(work_dir, 'qt_install_dir')
    src_path = os.path.join(work_dir, 'qt-creator')
    build_path = os.path.join(work_dir, 'qt-creator_build')
    with ch_dir(work_dir):
        install_qt(
            qt_path=qt_path,
            qt_modules=qt_module_urls,
            temp_path=qt_temp,
            icu_url=icu_libs if is_linux() else None,
            d3d_url=option_dict["D3D_URL"] if is_windows() else None,
            opengl_url=option_dict["OPENGLSW_URL"] if is_windows() else None,
            openssl_url=openssl_local_url if openssl_local_url else None,
        )
    # Define Qt Creator build script arguments
    cmd_args = [sys.executable, '-u']
    cmd_args += [os.path.join(src_path, 'scripts', 'build.py'),
                 '--src', src_path,
                 '--build', build_path,
                 '--qt-path', qt_path]
    if with_cpack:
        cmd_args += ['--with-cpack']
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
            if value and not isinstance(value, str):
                value = value.encode('UTF-8')
            if value:
                build_environment[key] = value
        except Exception:
            pass

    if is_macos():
        if has_unlock_keychain_script:
            cmd_args.extend(['--keychain-unlock-script', unlock_keychain_script()])
    if is_windows():
        python3_path = option_dict.get('PYTHON3_PATH') or ''
        cmd_args.extend(['--sign-command', '"' + os.path.join(python3_path, 'python.exe')
                         + '" -m pipenv run python -u qtsdk/packaging-tools/sign_windows_installer.py --file'])
        # we cannot change the CWD, and pipenv doesn't support specifying a pipfile on the command line
        # (https://github.com/pypa/pipenv/issues/2237), so we need to set this globally in the environment
        # ...which would break things if the QtC build script required a pipenv itself...
        build_environment['PIPENV_PIPFILE'] = os.path.join(work_dir, 'qtsdk', 'Pipfile')
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
        additional_plugins.extend([make_qtcplugin('licensechecker', 'licensechecker', qtcreator_version,
                                                  modules=qt_module_local_urls,
                                                  additional_arguments=add_args,
                                                  package_commercial=True)])
        plugin_dependencies = ['licensechecker']
    additional_plugins.extend([make_qtcplugin('vxworks-qtcreator-plugin', 'vxworks-qtcreator-plugin', qtcreator_version,
                                              modules=qt_module_local_urls, dependencies=plugin_dependencies,
                                              package_commercial=True)])
    additional_plugins.extend([make_qtcplugin('isoiconbrowser', 'qtquickdesigner', qtcreator_version,
                                              modules=qt_module_local_urls, dependencies=plugin_dependencies,
                                              package_commercial=True)])
    additional_plugins.extend([make_qtcplugin('gammarayintegration', 'gammarayintegration', qtcreator_version,
                                              modules=qt_module_local_urls + [kdsme_url, gammaray_url] + module_urls(['qt3d', 'qtgamepad']),
                                              dependencies=plugin_dependencies,
                                              additional_arguments=['--deploy'])])
    additional_plugins.extend([make_qtcplugin('appmanagerintegration', 'pcore-plugin-appman', qtcreator_version,
                                              modules=qt_module_local_urls,
                                              dependencies=plugin_dependencies,
                                              additional_arguments=['--with-docs'])])
    plugin_telemetry_args = []
    if usp_server_url and usp_auth_key:
        plugin_telemetry_args = ['--add-config=-DUSP_SERVER_URL=' + option_dict['USP_SERVER_URL'],
                                 '--add-config=-DUSP_AUTH_KEY=' + option_dict['USP_AUTH_KEY']]
    additional_plugins.extend([make_qtcplugin('plugin-telemetry', 'plugin-telemetry', qtcreator_version,
                                              modules=qt_module_local_urls,
                                              additional_arguments=plugin_telemetry_args)])

    # Build Qt Creator plugins
    icu_local_url = file_url(os.path.join(qt_temp, os.path.basename(icu_libs or ""))) if is_linux() else None
    # extract qtcreator bin and dev packages
    qtcreator_path = os.path.join(work_dir, 'qtc_build')
    check_call_log(['7z', 'x', '-y', os.path.join(work_dir, 'qt-creator_build', 'qtcreator.7z'), '-o' + qtcreator_path],
                   work_dir, log_filepath=log_filepath)
    check_call_log(['7z', 'x', '-y', os.path.join(work_dir, 'qt-creator_build', 'qtcreator_dev.7z'), '-o' + qtcreator_path],
                   work_dir, log_filepath=log_filepath)
    build_qtcreator_plugins(option_dict,
                            build_environment,
                            additional_plugins, qtcreator_path, qtcreator_path, icu_url=icu_local_url,
                            openssl_url=openssl_local_url, additional_config=qtc_additional_config,
                            log_filepath=log_filepath)

    qtcreator_sha = get_commit_sha(qtcreator_source)
    with open(os.path.join(work_dir, 'QTC_SHA1'), 'w', encoding="utf-8") as handle:
        handle.write(qtcreator_sha + '\n')

    if is_linux():
        # summary of git SHA1s
        sha1s = collect_qt_creator_plugin_sha1s(option_dict, additional_plugins)
        licensemanaging_source = os.path.join(work_dir, 'license-managing')
        if os.path.exists(licensemanaging_source):
            sha1s.append('license-managing: ' + get_commit_sha(licensemanaging_source))
        sha1s.append('qt-creator: ' + qtcreator_sha)
        with open(os.path.join(work_dir, 'SHA1'), 'w', encoding="utf-8") as handle:
            handle.writelines([sha + '\n' for sha in sha1s])

    # Create opensource source package
    create_qtcreator_source_package(option_dict, os.path.join(work_dir, 'qt-creator'), None, qtcreator_version,
                                    'opensource', work_dir, log_filepath)
    # Create enterprise source package
    if installer_patch:
        check_call_log(['git', 'apply', installer_patch],
                       os.path.join(work_dir, 'qt-creator'), log_filepath=log_filepath)
        create_qtcreator_source_package(option_dict, os.path.join(work_dir, 'qt-creator'), None, qtcreator_version,
                                        'enterprise', work_dir, log_filepath)

    # Build sdktool
    if sdktool_qtbase_src:
        sdktool_build_path = os.path.join(work_dir, 'sdktool_build')
        sdktool_target_path = os.path.join(sdktool_build_path, 'target')
        with BuildLog(log_filepath) as handle:
            build_sdktool(sdktool_qtbase_src, os.path.join(sdktool_build_path, 'qt'),
                          os.path.join(work_dir, 'qt-creator', 'src', 'tools', 'sdktool'),
                          os.path.join(sdktool_build_path, 'src', 'tools', 'sdktool'),
                          sdktool_target_path,
                          'nmake' if is_windows() else 'make',
                          redirect_output=handle)
            zip_sdktool(sdktool_target_path, os.path.join(work_dir, 'sdktool.7z'),
                        redirect_output=handle)

    # create up to 3 packages from the original
    # macOS: we may not change app bundle after signing,
    #        so we include sdktool for offline,
    #        write additional plugin path for optional plugins for commercial & online/Qt offline,
    #        write settings that redirect to sdktool for online/Qt offline.
    # - opensource offline: QtC + sdktool (signed)
    # - commercial offline: QtC + sdktool + pluginpath (signed)
    # - online/Qt offline: QtC + pluginpath + settings that redirect to sdktool (signed)
    # other: install settings must be read from sdktool location
    # - online/Qt offline: QtC + settings that redirect to sdktool
    if do_repackaging:
        settingspath = '../../../Tools/sdktool'
        if not is_macos():
            settingspath += '/share/qtcreator'
        qtcreator_package = os.path.join(build_path, 'qtcreator.7z')
        if is_macos():
            # use build_environment for SIGNING_IDENTITY
            sign_task = partial(sign_qtc, src_path, build_environment)
            sdktool_task = partial(extract_qtc_sdktool, os.path.join(work_dir, 'sdktool.7z'))
            plugin_path_settings = ['[Settings]',
                                    'InstallPluginPaths=../../../Tools/QtCreator ' + qtcreator_version + '/PlugIns']
            online_settings = plugin_path_settings + ['InstallSettings=' + settingspath]
            commercial_settings_task = partial(write_qtc_settings, plugin_path_settings)
            online_settings_task = partial(write_qtc_settings, online_settings)
            # opensource offline: QtC + sdktool (signed)
            repackage_qtcreator(work_dir,
                                qtcreator_package,
                                'qtcreator-signed.7z',
                                [sdktool_task, sign_task],
                                log_filepath)
            # commercial offline: QtC + sdktool + pluginpath (signed)
            repackage_qtcreator(work_dir,
                                qtcreator_package,
                                'qtcreator-commercial-signed.7z',
                                [sdktool_task, commercial_settings_task, sign_task],
                                log_filepath)
            # online/Qt offline: QtC + pluginpath + settings that redirect to sdktool (signed)
            repackage_qtcreator(work_dir,
                                qtcreator_package,
                                'qtcreator-qtinstaller.7z',
                                [online_settings_task, sign_task],
                                log_filepath)
        else:
            # online/Qt offline: QtC + settings that redirect to sdktool
            online_settings_task = partial(write_qtc_settings,
                                           ['[Settings]', 'InstallSettings=' + settingspath])
            repackage_qtcreator(work_dir,
                                qtcreator_package,
                                'qtcreator-qtinstaller.7z',
                                [online_settings_task],
                                log_filepath)

    # notarize
    if is_macos() and do_notarize:
        with ch_dir(SCRIPT_ROOT_DIR):
            notarize(path=Path(work_dir, 'qt-creator_build', 'qt-creator.dmg'))

    # Upload
    file_upload_list: List[Tuple[str, str]] = []  # pairs (source, dest), source relative to WORK_DIR, dest relative to server + dir_path
    snapshot_upload_list: List[Tuple[str, str]] = []  # pairs (source, dest), source relative to server + dir_path, dest relative to snapshot server + snapshot_path

    # build log
    file_upload_list.append((log_filepath, target_env_dir + '/build_log.txt'))

    # macOS opensource dmg
    if is_macos() and not skip_dmg:
        dmg_filename = 'qt-creator-opensource-mac-x86_64-' + qtcreator_version + '.dmg'
        file_upload_list.append(('qt-creator_build/qt-creator.dmg', dmg_filename))
        snapshot_upload_list.append((dmg_filename, dmg_filename))

    # macOS signed zip
    if do_repackaging:
        if is_macos():
            file_upload_list.append(('qtcreator-signed.7z', target_env_dir + '/qtcreator-signed.7z'))
            snapshot_upload_list.append((target_env_dir + '/qtcreator-signed.7z', target_env_dir + '/qtcreator-signed.7z'))
            file_upload_list.append(('qtcreator-commercial-signed.7z', target_env_dir + '/qtcreator-commercial-signed.7z'))
        file_upload_list.append(('qtcreator-qtinstaller.7z', target_env_dir + '/qtcreator-qtinstaller.7z'))

    # cpack created packages
    if with_cpack:
        if os.path.exists(os.path.join(build_path, 'build', 'qtcreator.exe')):  # NSIS
            nsis_filename = 'cpack_experimental/qtcreator-opensource-windows-x86_64-' + qtcreator_version + '.exe'
            file_upload_list.append(('qt-creator_build/build/qtcreator.exe', nsis_filename))
            snapshot_upload_list.append((nsis_filename, nsis_filename))
        if os.path.exists(os.path.join(build_path, 'build', 'qtcreator.msi')):  # WIX
            msi_filename = 'cpack_experimental/qtcreator-opensource-windows-x86_64-' + qtcreator_version + '.msi'
            file_upload_list.append(('qt-creator_build/build/qtcreator.msi', msi_filename))
            snapshot_upload_list.append((msi_filename, msi_filename))
        if os.path.exists(os.path.join(build_path, 'build', 'qtcreator.deb')):  # DEB
            deb_filename = 'cpack_experimental/qtcreator-opensource-linux-x86_64-' + qtcreator_version + '.deb'
            file_upload_list.append(('qt-creator_build/build/qtcreator.deb', deb_filename))
            snapshot_upload_list.append((deb_filename, deb_filename))

    # source packages
    source_package_list = glob(os.path.join(work_dir, 'qt-creator-*-src-' + qtcreator_version + '.*'))
    file_upload_list.extend([(os.path.basename(fn), '') for fn in source_package_list])
    qtc_source_packages = [
        Path(fn).name for fn in glob(
            os.path.join(work_dir, 'qt-creator-opensource-src-' + qtcreator_version + '.*')
        )
    ]
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
        plugin_signed_name = plugin.name + '-signed.7z'
        plugin_dev_name = plugin.name + '_dev.7z'
        plugin_debug_name = plugin.name + '-debug.7z'
        if os.path.isfile(os.path.join(work_dir, plugin_name)):
            file_upload_list.append((plugin_name, target_env_dir + '/' + plugin_name))
        if os.path.isfile(os.path.join(work_dir, plugin_signed_name)):
            file_upload_list.append((plugin_signed_name, target_env_dir + '/' + plugin_signed_name))
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
    upload_files(base_path, file_upload_list, option_dict)
    remote_path = base_path + '/latest'
    # public snapshot
    if snapshot_server and snapshot_path:
        matches = re.match(r'\d+[.]\d+', qtcreator_version)
        qtcreator_shortversion = matches.group() if matches else ""
        snapshot_base = snapshot_path + '/' + qtcreator_shortversion + '/' + qtcreator_version + '/installer_source/'
        snapshot_target = snapshot_base + build_id + '/'
        # create destination paths
        ssh_cmd = [option_dict['SSH_COMMAND'], pkg_storage_server, "ssh", snapshot_server]
        directories = [os.path.dirname(dest) for (_, dest) in snapshot_upload_list]
        for destdir in set(directories):
            cmd = ssh_cmd + ['mkdir', '-p', snapshot_target + destdir]
            run_cmd(cmd=cmd, cwd=work_dir)
        cmd = ssh_cmd + ['ln', '-sfn', snapshot_target, snapshot_base + 'latest']
        run_cmd(cmd=cmd, cwd=work_dir)

        base_scp_cmd = [option_dict['SSH_COMMAND'], pkg_storage_server, "scp"]
        for source, destination in snapshot_upload_list:
            source = remote_path + '/' + source
            target = snapshot_server + ':' + snapshot_target + '/' + destination
            run_cmd(cmd=base_scp_cmd + [source, target], cwd=work_dir)
    # create link from job name to display name
    update_job_link(unversioned_base_path, base_path, option_dict)


###############################
# handle_sdktool_build
###############################
def handle_sdktool_build(option_dict: Dict[str, str]) -> None:
    # environment
    target_env_dir = option_dict['QTC_PLATFORM']
    work_dir = option_dict['WORK_DIR']
    qtcreator_version = get_qtcreator_version(os.path.join(work_dir, 'qt-creator'), option_dict)
    qtcreator_edition_name = option_dict.get('QT_CREATOR_EDITION_NAME')  # optional
    unversioned_base_path = (option_dict['PACKAGE_STORAGE_SERVER_BASE_DIR']
                             + '/' + option_dict['QTC_BASE_DIR'])
    base_path = unversioned_base_path + '/' + qtcreator_version
    if qtcreator_edition_name:
        base_path += '_' + qtcreator_edition_name
    sdktool_qtbase_src = option_dict['SDKTOOL_QTBASESRC_BASE'] + option_dict['SDKTOOL_QTBASESRC_EXT']
    # build
    qtcreator_src = os.path.join(work_dir, 'qt-creator')
    download_temp = os.path.join(work_dir, 'downloads')
    sdktool_build_path = os.path.join(work_dir, 'sdktool_build')
    sdktool_target_path = os.path.join(sdktool_build_path, 'target')
    build_sdktool(sdktool_qtbase_src, os.path.join(sdktool_build_path, 'qt'),
                  os.path.join(work_dir, 'qt-creator', 'src', 'tools', 'sdktool'),
                  os.path.join(sdktool_build_path, 'src', 'tools', 'sdktool'),
                  sdktool_target_path,
                  'nmake' if is_windows() else 'make')
    zip_sdktool(sdktool_target_path, os.path.join(work_dir, 'sdktool.7z'))
    file_upload_list = [('sdktool.7z', target_env_dir + '/sdktool.7z')]
    if is_windows():  # wininterrupt & qtcreatorcdbext
        cmd_args = [sys.executable, '-u', os.path.join(qtcreator_src, 'scripts', 'build.py'),
                    '--src', qtcreator_src,
                    '--build', os.path.join(work_dir, 'build'),
                    '--no-qtcreator']

        download_packages_work = ThreadedWork('Get and extract all needed packages')
        python_path = None
        python_url = option_dict.get('PYTHON_URL')
        if python_url:
            python_path = os.path.join(download_temp, 'python')
            download_packages_work.add_task_object(create_download_extract_task(
                python_url, python_path, download_temp))
            cmd_args.extend(['--python-path', python_path])

        download_packages_work.run()

        check_call_log(cmd_args, work_dir)
        file_upload_list += [('build/wininterrupt.7z', target_env_dir + '/wininterrupt.7z'),
                             ('build/qtcreatorcdbext.7z', target_env_dir + '/qtcreatorcdbext.7z')]
    # upload
    upload_files(base_path, file_upload_list, option_dict)
    update_job_link(unversioned_base_path, base_path, option_dict)


###############################
# Update latest link
###############################
def update_latest_link(option_dict: Dict[str, str], remote_dest_dir: str, latest_dir: str) -> None:
    package_server = option_dict['PACKAGE_STORAGE_SERVER_ADDR']
    cmd_args = [option_dict['SSH_COMMAND'], package_server, 'ln -sfn', remote_dest_dir, latest_dir]
    run_cmd(cmd=cmd_args, cwd=SCRIPT_ROOT_DIR)


###############################
# create_remote_dirs
###############################
def create_remote_dirs(option_dict: Dict[str, str], server: str, dir_path: str) -> None:
    cmd_args = [option_dict['SSH_COMMAND'], '-t', '-t', server, 'mkdir -p', dir_path]
    run_cmd(cmd=cmd_args, cwd=SCRIPT_ROOT_DIR)


###############################
# git archive given repository
###############################
def do_git_archive_repo(option_dict: Dict[str, str], repo_and_ref: str) -> None:
    archive_name = git_archive_repo(repo_and_ref)
    (repository, ref) = repo_and_ref.split("#")
    project_name = repository.split("/")[-1].split(".")[0]
    # Create remote dest directories
    remote_dest_dir_base = option_dict['PACKAGE_STORAGE_SERVER_BASE_DIR'] + '/' + project_name + '/' + ref
    remote_dest_dir = remote_dest_dir_base + '/' + option_dict['BUILD_NUMBER']
    remote_dest_dir_latest = remote_dest_dir_base + '/' + 'latest'
    create_remote_dirs(option_dict, option_dict['PACKAGE_STORAGE_SERVER_ADDR'], remote_dest_dir)
    update_latest_link(option_dict, remote_dest_dir, remote_dest_dir_latest)
    # upload archive to network disk
    cmd_args = ['scp', archive_name, remote_dest_dir]
    run_cmd(cmd=cmd_args, cwd=SCRIPT_ROOT_DIR)


def init_pkg_options(args: argparse.Namespace) -> Dict[str, str]:
    def merge_two_dicts(x_dict: Dict[Any, Any], y_dict: Dict[Any, Any]) -> Dict[Any, Any]:
        """Given two dicts, merge them into a new dict as a shallow copy."""
        z_dict = x_dict.copy()
        z_dict.update(y_dict)
        return z_dict

    def get_default_target_env() -> str:
        """For local builds define default build target"""
        if is_windows():
            return "win-msvc2015-Windows10-x64"
        if is_linux():
            return "linux-g++-Rhel6.6-x64"
        if is_macos():
            return "mac-clang-10.11-x64"
        raise RuntimeError("Unsupported host platform")

    option_dict: Dict[str, str] = {}
    # Are we using local conf file for pkg options?
    if args.pkg_conf_file:
        options = get_pkg_options(args.pkg_conf_file)
        option_dict = merge_two_dicts(option_dict, options.config_map())
        option_dict['TARGET_ENV'] = args.target_env if args.target_env else get_default_target_env()
        option_dict['BUILD_NUMBER'] = str(strftime('%Y%m%d%H%M%S', gmtime()))
        option_dict['PACKAGE_STORAGE_SERVER_ADDR'] = option_dict['PACKAGE_STORAGE_SERVER_USER'] + '@' + option_dict['PACKAGE_STORAGE_SERVER']
    else:
        option_dict = dict(os.environ)
        # Check for command line overrides
        option_dict['LICENSE'] = args.license_
        option_dict['PACKAGE_STORAGE_SERVER_BASE_DIR'] = args.path
        option_dict['OPENSSL_LIBS'] = args.openssl_libs
        option_dict['SNAPSHOT_SERVER_PATH'] = args.snapshot_path
        option_dict['TARGET_ENV'] = args.target_env if args.target_env else os.environ.get('cfg')
        option_dict['BUILD_NUMBER'] = args.build_number if args.build_number else os.environ.get('BUILD_NUMBER')

        option_dict['SIGNING_SERVER'] = get_pkg_value("SIGNING_SERVER")
        option_dict['SIGNING_PASSWORD'] = get_pkg_value("SIGNING_PASSWORD")
        option_dict['USP_SERVER_URL'] = get_pkg_value("USP_SERVER_URL")
        option_dict['USP_AUTH_KEY'] = get_pkg_value("USP_AUTH_KEY")
        option_dict['PACKAGE_STORAGE_SERVER_USER'] = get_pkg_value("PACKAGE_STORAGE_SERVER_USER")
        option_dict['PACKAGE_STORAGE_SERVER'] = get_pkg_value("PACKAGE_STORAGE_SERVER")
        option_dict['PACKAGE_STORAGE_SERVER_ADDR'] = args.server or get_pkg_value("PACKAGE_STORAGE_SERVER_ADDR")
        option_dict['PACKAGE_STORAGE_SERVER_PATH_HTTP'] = args.override_server_path_http or get_pkg_value("PACKAGE_STORAGE_SERVER_PATH_HTTP")
        option_dict['SNAPSHOT_SERVER'] = args.snapshot_server or get_pkg_value("SNAPSHOT_SERVER")
        option_dict['EXT_SERVER_BASE_URL'] = get_pkg_value("EXT_SERVER_BASE_URL")
        option_dict['RTA_SERVER_BASE_URL'] = get_pkg_value("RTA_SERVER_BASE_URL")
        option_dict['PKG_STAGING_SERVER'] = get_pkg_value("PKG_STAGING_SERVER")
        option_dict['PKG_STAGING_SERVER_UNAME'] = get_pkg_value("PKG_STAGING_SERVER_UNAME")
        option_dict['PROD_USER'] = get_pkg_value("PROD_USER")
        option_dict['PROD_ADDR'] = get_pkg_value("PROD_ADDR")

        if LOCAL_MODE:
            option_dict['PACKAGE_STORAGE_SERVER_USER'] = getuser()  # current user
            option_dict['PACKAGE_STORAGE_SERVER'] = "127.0.0.1"
            option_dict['PACKAGE_STORAGE_SERVER_ADDR'] = option_dict['PACKAGE_STORAGE_SERVER_USER'] + "@" + option_dict['PACKAGE_STORAGE_SERVER']
            option_dict['PACKAGE_STORAGE_SERVER_BASE_DIR'] = LOCAL_INSTALLER_DIR
            option_dict['SNAPSHOT_SERVER'] = option_dict['PACKAGE_STORAGE_SERVER_ADDR']
            option_dict['SNAPSHOT_SERVER_PATH'] = LOCAL_INSTALLER_DIR

    if is_linux():
        option_dict['HOST_PLATFORM'] = 'linux'
    elif is_macos():
        option_dict['HOST_PLATFORM'] = 'mac'
    else:
        option_dict['HOST_PLATFORM'] = 'windows'

    option_dict['CURL_COMMAND'] = '%CURL%' if is_windows() else 'curl'
    option_dict['RM_COMMAND'] = '%RM%' if is_windows() else 'rm'
    option_dict['SSH_COMMAND'] = '%SSH%' if is_windows() else 'ssh'
    option_dict['SCP_COMMAND'] = '%SCP%' if is_windows() else 'scp'
    option_dict['WORK_DIR'] = WORK_DIR

    # Parse version number info if this build utilizes release description file
    if 'RELEASE_DESCRIPTION_FILE' in option_dict:
        # Path relative to script or absolute file path
        path = option_dict['RELEASE_DESCRIPTION_FILE']
        path = path if (os.path.isabs(path) and os.path.isfile(path)) else os.path.join(option_dict['WORK_DIR'], path)
        option_dict['RELEASE_DESCRIPTION_FILE'] = path
        # resolve configuration files base dir
        conf_base_dir = option_dict['CONFIGURATIONS_FILE_BASE_DIR']
        conf_base_dir = conf_base_dir if (os.path.isabs(conf_base_dir) and os.path.isdir(conf_base_dir)) else os.path.join(option_dict['WORK_DIR'], conf_base_dir)
        option_dict['CONFIGURATIONS_FILE_BASE_DIR'] = conf_base_dir

        parser = ConfigParser()
        parser.read(path)
        for section in parser.sections():
            if section == 'release.global':
                version = safe_config_key_fetch(parser, section, 'version')
                version_tag = safe_config_key_fetch(parser, section, 'version_tag')
                option_dict['VERSION'] = version
                option_dict['VERSION_TAG'] = version_tag
                option_dict['VERSION_FULL'] = version if not version_tag else version + '-' + version_tag
    return option_dict


def main() -> None:
    """Main"""
    # Define supported build steps
    bld_qtcreator = 'build_creator'
    bld_qtc_sdktool = 'build_sdktool'
    bld_licheck = 'licheck_bld'
    archive_repository = 'archive_repo'
    cmd_list = (bld_qtcreator, bld_qtc_sdktool, bld_licheck, archive_repository)

    parser = argparse.ArgumentParser(prog="Build Wrapper", description="Manage all packaging related build steps.")
    parser.add_argument("-c", "--command", dest="command", required=True, choices=cmd_list, help=str(cmd_list))
    parser.add_argument("--pkg-conf-file", dest="pkg_conf_file", default="", help="instead of reading various config options from env variables read them from the given file.")
    parser.add_argument("-l", "--license", dest="license_", default="", help="license type: enterprise or opensource")
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
    option_dict = init_pkg_options(args)

    # Execute given command
    # QtCreator specific
    if args.command == bld_qtcreator:
        handle_qt_creator_build(option_dict, parse_qtcreator_plugins(args.pkg_conf_file))
    # sdktool
    elif args.command == bld_qtc_sdktool:
        handle_sdktool_build(option_dict)
    # Qt Installer-Framework specific
    elif args.command == bld_licheck:
        handle_qt_licheck_build(option_dict)
    elif args.command == archive_repository:
        do_git_archive_repo(option_dict, args.archive_repo)
    else:
        log.info("Unsupported command: %s", args.command)


if __name__ == '__main__':
    main()
