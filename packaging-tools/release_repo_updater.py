#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
##
## Copyright (C) 2022 The Qt Company Ltd.
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

import os
import re
import sys
import json
import time
import shutil
import asyncio
import tempfile
import platform
import datetime
import argparse
from configparser import ConfigParser, ExtendedInterpolation
from typing import List, Dict, Tuple
from time import gmtime, strftime
from pathlib import Path
import subprocess
import release_task_reader
from urllib.request import urlretrieve, urlopen
from urllib.error import HTTPError, URLError
from release_task_reader import ReleaseTask
from installer_utils import PackagingError
from runner import exec_cmd, async_exec_cmd
from logging_util import init_logger
from read_remote_config import get_pkg_value
import sign_installer

log = init_logger(__name__, debug_mode=False)
timestamp = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d--%H:%M:%S')


class event_register(object):
    event_injector: Path = None
    python_path: str = None

    def __init__(self, event_name: str, event_injector_path: str, summary_data: Dict[str, str]) -> None:
        self.event_name = event_name
        self.summary_data = summary_data
        self.initialize(event_injector_path)

    @classmethod
    def initialize(cls, event_injector_path: str):
        if not cls.python_path:
            if platform.system() == "Linux":
                import sh
                cls.python_path = sh.which("python3")
            if platform.system() == "Windows":
                cls.python_path = os.path.join(os.getenv("PYTHON3_PATH"), "python.exe")
            if platform.system() == "Darwin":
                cls.python_path = os.path.join(os.getenv("PYTHON3_PATH"), "python3")
        if event_injector_path:
            cls.event_injector = Path(event_injector_path).resolve(strict=True)

    async def __aenter__(self) -> 'event_register':
        if event_register.event_injector:
            self.register_event(self.event_name, "START", self.summary_data, message="")
        return self

    async def __aexit__(self, exc_type, exc_val, traceback) -> bool:
        ret = True
        event_type = "FINISH"
        if traceback:
            ret = False  # will cause the exception to be propagated
            event_type = "ABORT"
        if event_register.event_injector:
            self.register_event(self.event_name, event_type, self.summary_data, message=exc_val)
        return ret

    def register_event(self, event_name: str, event_type: str, export_summary: Dict[str, str], message: str) -> None:
        if not event_register.event_injector:
            log.warning("Unable to register event as injector not found!")
            return
        cmd = [str(event_register.python_path), str(event_register.event_injector), f"--event={event_type}", f"--task={event_name}",
               f"--project-name={export_summary.get('project', '')}",
               f"--project-version={export_summary.get('version', '')}",
               f"--destination-branch={export_summary.get('destination_branch', '')}",
               f"--integration-id={export_summary.get('id', '')}",
               f"--sha1={export_summary.get('sha1', '')}",
               f"--message={message or ''}"]
        log.info(f"Calling: {' '.join(cmd)}")
        ret = subprocess.run(cmd, shell=False, check=False, capture_output=True, encoding="utf-8", timeout=60 * 2)
        if ret.returncode:
            log.warning(f"Failed to register event - stdout: {ret.stderr}")
            log.warning(f"Failed to register event - stderr: {ret.stdout}")


class QtRepositoryLayout:

    def __init__(self, root_path: str, license: str, repo_domain: str) -> None:
        self.root_path = root_path
        self.license = license
        self.repo_domain = repo_domain
        self.pending = "pending"
        self.staging = "staging"
        self.production = "production"
        # <root_path>/<license>/<pending|staging|production>/<repo_domain>/
        # /data/online_repositories/opensource/pending|staging|production/qtsdkrepository/
        log.info("self.root_path %s", self.root_path)
        log.info("self.license %s", self.license)
        self.base_repo_path = os.path.join(self.root_path, self.license)

    def get_base_repo_path(self) -> str:
        return self.base_repo_path

    def get_repo_domain(self) -> str:
        return self.repo_domain

    def get_repo_layout(self) -> List[str]:
        return [os.path.join(self.base_repo_path, self.pending, self.repo_domain),
                os.path.join(self.base_repo_path, self.staging, self.repo_domain),
                os.path.join(self.base_repo_path, self.production, self.repo_domain)]

    def get_pending_path(self) -> str:
        return os.path.join(self.base_repo_path, self.pending, self.repo_domain)

    def get_staging_path(self) -> str:
        return os.path.join(self.base_repo_path, self.staging, self.repo_domain)

    def get_production_path(self) -> str:
        return os.path.join(self.base_repo_path, self.production, self.repo_domain)


def has_connection_error(output: str) -> bool:
    known_errors = ["Could not connect to the endpoint URL"]
    for line in output.splitlines():
        for known_error in known_errors:
            if line.find(known_error) >= 0:
                return True
    return False


def execute_remote_cmd(remoteServer: str, remoteServerHome: str, cmd: List[str], scriptFileName: str, timeout=60*60) -> None:
    remoteTmpDir = os.path.join(remoteServerHome, "remote_scripts", timestamp)
    create_remote_paths(remoteServer, [remoteTmpDir])
    remoteScript = create_remote_script(remoteServer, cmd, remoteTmpDir, scriptFileName)
    log.info("Created remote script: [%s] with contents: %s", remoteScript, ' '.join(cmd))
    execute_remote_script(remoteServer, remoteScript, timeout)


def create_remote_script(server: str, cmd: List[str], remoteScriptPath: str, scriptFileName: str) -> str:
    with tempfile.TemporaryDirectory(dir=os.getcwd()) as tmpBaseDir:
        tempFilePath = os.path.join(tmpBaseDir, scriptFileName)
        with open(tempFilePath, 'w+') as f:
            f.write("#!/usr/bin/env bash\n")
            f.write(' '.join(cmd))
        os.chmod(tempFilePath, 0o755)
        create_remote_paths(server, [remoteScriptPath])
        cmd = ['rsync', '-avzh', tempFilePath, server + ":" + remoteScriptPath]
        exec_cmd(cmd, timeout=60 * 60)
        return os.path.join(remoteScriptPath, scriptFileName)


def execute_remote_script(server: str, remoteScriptPath: str, timeout=60*60) -> None:
    cmd = get_remote_login_cmd(server) + [remoteScriptPath]
    retry_count = 5
    delay = 60
    while retry_count:
        retry_count -= 1
        if not has_connection_error(exec_cmd(cmd, timeout)):
            break
        if retry_count:
            log.warning(f"Trying again after {delay}s")
            time.sleep(delay)
            delay = delay + delay/2  # 60, 90, 135, 202, 303
        else:
            log.critical(f"Execution of the remote script probably failed: {cmd}")


async def upload_ifw_to_remote(ifwTools: str, remoteServer: str, remoteServerHome: str) -> str:
    from installer_utils import is_valid_url_path, download_archive, extract_archive, locate_file
    assert is_valid_url_path(ifwTools)
    log.info("Preparing ifw tools: %s", ifwTools)
    # fetch the tool first
    currentDir = os.getcwd()
    ifwToolsDir = os.path.join(currentDir, "ifw_tools")
    if not os.path.isdir(ifwToolsDir):
        os.makedirs(ifwToolsDir)
        destFile = download_archive(ifwTools, ifwToolsDir)
        await extract_archive(destFile, ifwToolsDir)
    repogen = locate_file("repogen", ifwToolsDir)
    repogenDir = os.path.dirname(repogen)
    # upload to server
    remoteTmpDir = os.path.join(remoteServerHome, "ifw_tools", timestamp)
    # create tmp dir at remote
    create_remote_paths(remoteServer, [remoteTmpDir])
    # upload content
    cmd = ['rsync', '-avzh', repogenDir + "/", remoteServer + ":" + remoteTmpDir]
    exec_cmd(cmd, timeout=60*60)
    # return path on remote poiting to repogen
    return os.path.join(remoteTmpDir, "bin", "repogen")


def check_repogen_output(output: str) -> None:
    if any(fail_string in output.strip().lower() for fail_string in ["error", "invalid", "already exists"]):
        raise PackagingError("Repogen failed: {0}".format(output.strip()))


def get_remote_login_cmd(server: str) -> List[str]:
    return ['ssh', '-t', '-t', server]


def trigger_rta(rtaServerUrl: str, task: ReleaseTask) -> None:
    for key in task.get_rta_key_list():
        url = rtaServerUrl + key + '/build?token=RTA_JENKINS'
        log.info("Triggering RTA case: %s", url)
        try:
            urlretrieve(url)
        except HTTPError:
            log.error("Failed to trigger RTA for: %s", url)
            # let it proceed


def _remote_path_exists(server: str, remotePath: str, type: str) -> bool:
    cmd = get_remote_login_cmd(server) + ['test', type, remotePath, '&& echo OK || echo NOK']
    output = subprocess.check_output(' '.join(cmd), shell=True, timeout=60 * 2).decode("utf-8")
    return output.strip() == "OK"


def remote_path_exists(server: str, remotePath: str) -> bool:
    return _remote_path_exists(server, remotePath, type="-d")


def remote_file_exists(server: str, remotePath: str) -> bool:
    return _remote_path_exists(server, remotePath, type="-f")


async def ensure_ext_repo_paths(server: str, ext: str, repo: str) -> None:
    log.info("Ensure repository paths on ext: %s:%s", ext, repo)
    login = get_remote_login_cmd(server) + get_remote_login_cmd(ext)
    cmd = login + ["mkdir", "-p", repo]
    await async_exec_cmd(cmd, timeout=60*60*10)


def is_safe_directory(paths: List[str]) -> None:
    for _path in paths:
        path = os.path.abspath(_path)
        if path == "/":
            raise PackagingError("You should not make modifications directly to root: {0}".format(path))
        illegalDirectories = ("/bin", "/boot", "/sys", "/sbin", "/root", "/lib", "/dev")
        if path.startswith(illegalDirectories):
            raise PackagingError("You should not make modifications ('{0}') under these directories: {1}".format(path, illegalDirectories))
        if path in ["~", os.path.expanduser("~"), "/home"]:
            raise PackagingError("You should not make modifications directly to home directory: {0}".format(path))


def create_remote_paths(server: str, paths: List[str]) -> None:
    is_safe_directory(paths)
    cmd = get_remote_login_cmd(server) + ['mkdir -p', ' '.join(paths)]
    exec_cmd(cmd, timeout=60 * 2)


def delete_remote_paths(server: str, paths: List[str]) -> None:
    is_safe_directory(paths)
    cmd = get_remote_login_cmd(server) + ['rm -rf', ' '.join(paths)]
    exec_cmd(cmd, timeout=60 * 2)


def upload_pending_repository_content(server: str, sourcePath: str, remoteDestinationPath: str) -> None:
    log.info("Uploading pending repository content from: [%s] -> [%s:%s]", sourcePath, server, remoteDestinationPath)
    # When uploading new content to staging the old content is always deleted
    delete_remote_paths(server, [remoteDestinationPath])
    # repository paths
    create_remote_paths(server, [remoteDestinationPath])
    # upload content
    cmd = ['rsync', '-avzh', sourcePath + "/", server + ":" + remoteDestinationPath]
    exec_cmd(cmd, timeout=60*60)  # give it 60 mins


def reset_new_remote_repository(server: str, remoteSourceRepoPath: str, remoteTargetRepoPath: str) -> None:
    if not remote_path_exists(server, remoteSourceRepoPath):
        raise PackagingError("The remote source repository path did not exist on the server: {0}:{1}".format(server, remoteSourceRepoPath))
    if remote_path_exists(server, remoteTargetRepoPath):
        # this will _move_ the currect repo as backup
        create_remote_repository_backup(server, remoteTargetRepoPath)

    log.info("Reset new remote repository: source: [%s] target: [%s]", remoteSourceRepoPath, remoteTargetRepoPath)
    create_remote_paths(server, [remoteTargetRepoPath])
    cmd = get_remote_login_cmd(server) + ['cp', '-Rv', remoteSourceRepoPath + '/*', remoteTargetRepoPath]
    exec_cmd(cmd, timeout=60 * 60)  # give it 60 mins


def create_remote_repository_backup(server: str, remote_repo_path: str) -> None:
    backup_path = os.path.join(remote_repo_path + "____snapshot_backup")
    # if there exists a backup already then delete it, we keep only one backup
    if remote_path_exists(server, backup_path):
        log.info("Deleting old backup repo: %s", backup_path)
        delete_remote_paths(server, [backup_path])
    # move the repo as backup
    cmd = get_remote_login_cmd(server) + ['mv', '-v', remote_repo_path, backup_path]
    exec_cmd(cmd, timeout=60 * 60)  # give it 60 mins
    log.info("Moved remote repository as backup: %s:%s -> %s", server, remote_repo_path, backup_path)
    return backup_path


def sync_production_repositories_to_s3(server: str, s3: str, updatedProductionRepositories: Dict[str, str],
                                       remoteRootPath: str, license: str) -> None:
    remoteLogsBasePath = os.path.join(remoteRootPath, license, "s3_sync_logs")
    create_remote_paths(server, [remoteLogsBasePath])

    for repo, remoteProductionRepoFullPath in updatedProductionRepositories.items():
        remoteLogFileBase = os.path.join(remoteLogsBasePath, repo, "log-s3-" + timestamp)
        create_remote_paths(server, [os.path.dirname(remoteLogFileBase)])

        s3RepoPath = os.path.join(s3, repo)
        tipPrefix = repo.replace("/", "-") + "-"

        remoteLogFile = remoteLogFileBase + "-7z.txt"
        sync_production_7z_to_s3(server, remoteRootPath, remoteProductionRepoFullPath, s3RepoPath, remoteLogFile, tipPrefix)
        remoteLogFile = remoteLogFileBase + "-xml.txt"
        sync_production_xml_to_s3(server, remoteRootPath, remoteProductionRepoFullPath, s3RepoPath, remoteLogFile, tipPrefix)


def sync_production_7z_to_s3(server: str, serverHome: str, productionRepoPath: str, s3RepoPath: str, remoteLogFile: str, tip: str) -> None:
    log.info("Syncing .7z to s3: [%s:%s] -> [%s]", server, productionRepoPath, s3RepoPath)

    cmd = ["aws", "s3", "sync", productionRepoPath, s3RepoPath]
    cmd = cmd + ["--exclude", '"*"', "--include", '"*.7z"', "--include", '"*.sha1"']
    spawn_remote_background_task(server, serverHome, cmd, remoteLogFile, tip=tip + "7z")


def sync_production_xml_to_s3(server: str, serverHome: str, productionRepoPath: str, s3RepoPath: str, remoteLogFile: str, tip: str) -> None:
    log.info("Syncing .xml to s3: [%s:%s] -> [%s]", server, productionRepoPath, s3RepoPath)

    cmd = ["aws", "s3", "sync", productionRepoPath, s3RepoPath]
    cmd = cmd + ["--cache-control", '"max-age=0"', "--exclude", '"*"', "--include", '"*.xml"']
    spawn_remote_background_task(server, serverHome, cmd, remoteLogFile, tip=tip + "xml")


async def sync_production_repositories_to_ext(server: str, ext: str, updatedProductionRepositories: Dict[str, str],
                                              remoteRootPath: str, license: str) -> None:
    remoteLogsBasePath = os.path.join(remoteRootPath, license, "ext_sync_logs")
    create_remote_paths(server, [remoteLogsBasePath])

    extServer, extBasePath = parse_ext(ext)

    for repo, remoteProductionRepoFullPath in updatedProductionRepositories.items():
        remoteLogFile = os.path.join(remoteLogsBasePath, repo, "log-ext-" + timestamp + ".txt")
        create_remote_paths(server, [os.path.dirname(remoteLogFile)])

        extRepoPath = os.path.join(extBasePath, repo)
        tipPrefix = repo.replace("/", "-") + "-"

        await ensure_ext_repo_paths(server, extServer, extRepoPath)  # rsync can not create missing nested directories
        cmd = ["rsync", "-r", "--omit-dir-times", "--delete-delay", "--progress", remoteProductionRepoFullPath + "/", extServer + ":" + extRepoPath]
        spawn_remote_background_task(server, remoteRootPath, cmd, remoteLogFile, tip=tipPrefix + "ext")


def spawn_remote_background_task(server: str, serverHome: str, remoteCmd: List[str], remoteLogFile: str, tip: str) -> None:
    if not tip:
        tip = ""
    cmd = remoteCmd + ["2>&1", "|", "tee", remoteLogFile]
    remoteScriptFileName = "sync-production-" + tip + "-" + timestamp + ".sh"
    execute_remote_cmd(server, serverHome, cmd, remoteScriptFileName, timeout=60*60*2)  # 2h timeout for uploading data to CDN


async def update_repository(stagingServer: str, repoLayout: QtRepositoryLayout, task: ReleaseTask,
                            updateStaging: bool, updateProduction: bool, rta: str, remoteRepogen: str) -> None:
    assert task.get_source_online_repository_path(), "Can not update repository: [{0}] because source repo is missing".format(task.get_repo_path())
    # ensure the repository paths exists at server
    log.info("Starting repository update: %s", task.get_repo_path())
    create_remote_paths(stagingServer, repoLayout.get_repo_layout())

    remotePendingPath = os.path.join(repoLayout.get_pending_path(), task.get_repo_path())
    remotePendingPathRepository = os.path.join(remotePendingPath, "repository")

    remoteStagingDestinationRepositoryPath = os.path.join(repoLayout.get_staging_path(), task.get_repo_path())
    remoteProductionDestinationRepositoryPath = os.path.join(repoLayout.get_production_path(), task.get_repo_path())

    # We always replace existing repository if previous version should exist.
    # Previous version is moved as backup
    upload_pending_repository_content(stagingServer, task.get_source_online_repository_path(), remotePendingPathRepository)

    # Now we can run the updates on the remote
    if updateStaging:
        reset_new_remote_repository(stagingServer, remotePendingPathRepository, remoteStagingDestinationRepositoryPath)
    if updateProduction:
        reset_new_remote_repository(stagingServer, remotePendingPathRepository, remoteProductionDestinationRepositoryPath)

    log.info("Update done: %s", task.get_repo_path())
    # Now we can delete pending content
    delete_remote_paths(stagingServer, [remotePendingPathRepository])
    # trigger RTA cases for the task if specified
    if rta:
        trigger_rta(rta, task)


async def build_online_repositories(tasks: List[ReleaseTask], license: str, installerConfigBaseDir: str, artifactShareBaseUrl: str,
                                    ifwTools: str, buildRepositories: bool) -> List[str]:
    log.info("Building online repositories: %i", len(tasks))
    # create base tmp dir
    tmpBaseDir = os.path.join(os.getcwd(), "_repo_update_jobs")
    if buildRepositories:
        shutil.rmtree(tmpBaseDir, ignore_errors=True)
    os.makedirs(tmpBaseDir, exist_ok=True)

    assert license, "The 'license' must be defined!"
    assert artifactShareBaseUrl, "The 'artifactShareBaseUrl' must be defined!"
    assert ifwTools, "The 'ifwTools' must be defined!"
    # locate the repo build script
    scriptPath = os.path.abspath(os.path.join(os.path.dirname(__file__), "create_installer.py"))
    assert os.path.isfile(scriptPath), "Not a valid script path: {0}".format(scriptPath)

    # build online repositories first
    done_repositories = []  # type: List[str]
    for task in tasks:
        tmpDir = os.path.join(tmpBaseDir, task.get_repo_path())
        task.source_online_repository_path = os.path.join(tmpDir, "online_repository")
        if not buildRepositories:
            # this is usually for testing purposes in env where repositories are already built, we just update task objects
            continue

        log.info("Building repository: %s", task.get_repo_path())
        installerConfigFile = os.path.join(installerConfigBaseDir, task.get_config_file())
        if not os.path.isfile(installerConfigFile):
            raise PackagingError("Invalid 'config_file' path: {0}".format(installerConfigFile))

        # TODO: license
        cmd = [sys.executable, scriptPath, "-c", installerConfigBaseDir, "-f", installerConfigFile]
        cmd += ["--create-repo", "-l", license, "--license-type", license, "-u", artifactShareBaseUrl, "--ifw-tools", ifwTools]
        cmd += ["--force-version-number-increase"]
        for substitution in task.get_installer_string_replacement_list():
            cmd += ["--add-substitution=" + substitution]

        try:
            await async_exec_cmd(cmd, timeout=60*60*3)  # 3h for one repo build
        except Exception as e:
            log.error(str(e))
            raise

        onlineRepositoryPath = os.path.abspath(os.path.join(os.path.dirname(__file__), "online_repository"))
        assert os.path.isdir(onlineRepositoryPath), "Not a valid path: {0}".format(onlineRepositoryPath)
        shutil.move(onlineRepositoryPath, task.source_online_repository_path)
        log.info("Repository created at: %s", task.source_online_repository_path)
        done_repositories.append(task.source_online_repository_path)
    return done_repositories


async def update_repositories(tasks: List[ReleaseTask], stagingServer: str, stagingServerRoot: str, repoLayout: QtRepositoryLayout,
                              updateStaging: bool, updateProduction: bool, rta: str, ifwTools: str) -> None:
    # upload ifw tools to remote
    remoteRepogen = await upload_ifw_to_remote(ifwTools, stagingServer, stagingServerRoot)
    try:
        for task in tasks:
            await update_repository(stagingServer, repoLayout, task, updateStaging, updateProduction, rta, remoteRepogen)
    except PackagingError as e:
        log.error("Aborting online repository update: %s", str(e))
        raise
    finally:
        # Now we can delete the ifw tools at remote
        delete_remote_paths(stagingServer, [os.path.dirname(os.path.dirname(remoteRepogen))])


async def sync_production(tasks: List[ReleaseTask], repoLayout: QtRepositoryLayout, syncS3: str, syncExt: str,
                          stagingServer: str, stagingServerRoot: str, license: str, event_injector: str,
                          export_data: Dict[str, str]) -> None:
    log.info("triggering production sync..")
    # collect production sync jobs
    updatedProductionRepositories = {}  # type: Dict[str, str]
    for task in tasks:
        key = os.path.join(repoLayout.get_repo_domain(), task.get_repo_path())
        if key in updatedProductionRepositories:
            raise PackagingError("Duplicate repository path found: {0}".format(key))
        updatedProductionRepositories[key] = os.path.join(repoLayout.get_production_path(), task.get_repo_path())

    # if _all_ repository updates to production were successful then we can sync to production
    if syncS3:
        async with event_register(f"{license}: repo sync s3", event_injector, export_data):
            sync_production_repositories_to_s3(stagingServer, syncS3, updatedProductionRepositories,
                                               stagingServerRoot, license)
    if syncExt:
        async with event_register(f"{license}: repo sync ext", event_injector, export_data):
            await sync_production_repositories_to_ext(stagingServer, syncExt, updatedProductionRepositories,
                                                      stagingServerRoot, license)
    log.info("Production sync trigger done!")


async def handle_update(stagingServer: str, stagingServerRoot: str, license: str, tasks: List[ReleaseTask],
                        repoDomain: str, installerConfigBaseDir: str, artifactShareBaseUrl: str,
                        updateStaging: bool, updateProduction: bool, syncS3: str, syncExt: str, rta: str, ifwTools: str,
                        buildRepositories: bool, updateRepositories: bool, syncRepositories: bool,
                        event_injector: str, export_data: Dict[str, str]) -> List[str]:
    """Build all online repositories, update those to staging area and sync to production."""
    log.info("Starting repository update for %i tasks..", len(tasks))
    # get repository layout
    repoLayout = QtRepositoryLayout(stagingServerRoot, license, repoDomain)
    # this may take a while depending on how big the repositories are
    async with event_register(f"{license}: repo build", event_injector, export_data):
        ret = await build_online_repositories(tasks, license, installerConfigBaseDir, artifactShareBaseUrl, ifwTools,
                                              buildRepositories)

    if updateRepositories:
        async with event_register(f"{license}: repo update", event_injector, export_data):
            await update_repositories(tasks, stagingServer, stagingServerRoot, repoLayout, updateStaging, updateProduction,
                                      rta, ifwTools)
    if syncRepositories:
        await sync_production(tasks, repoLayout, syncS3, syncExt, stagingServer, stagingServerRoot, license,
                              event_injector, export_data)

    log.info("Repository updates done!")
    return ret


def string_to_bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    if value.lower() in ('yes', 'true', 'y', '1'):
        return True
    elif value.lower() in ('no', 'false', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Unable to convert to boolean: {0}'.format(value))


def parse_ext(ext: str) -> Tuple[str, str]:
    parts = ext.split(":")
    if len(parts) != 2:
        raise PackagingError("Ext format should be '<login>@<server>:/base/path'. Format was invalid: {0}".format(ext))
    if not parts[1].startswith("/"):
        raise PackagingError("Ext server path should start with '/'. Format was invalid: {0}".format(parts[1]))
    return parts[0], parts[1]


def append_to_task_filters(task_filters: List[str], task_filter: str) -> List[str]:
    return [task_filter + "," + x if x else task_filter for x in task_filters] if task_filters else [task_filter]


def format_task_filters(task_filters: List[str]) -> List[str]:
    if task_filters:
        return [char.replace('.', ',') for char in task_filters]


def create_offline_remote_dirs(task: ReleaseTask, stagingServer: str, stagingServerRoot: str, installerBuildId: str) -> str:
    remote_base_dir = stagingServerRoot + '/' + task.get_project_name() + '/' + task.get_version() + '/' + 'installers'
    remote_dir = remote_base_dir + '/' + installerBuildId + '/'
    remote_latest_available_dir = remote_base_dir + '/' + 'latest_available' + '/'
    if not remote_path_exists(stagingServer, remote_dir):
        create_remote_paths(stagingServer, [remote_dir])
    if not remote_path_exists(stagingServer, remote_latest_available_dir):
        create_remote_paths(stagingServer, [remote_latest_available_dir])
    return remote_dir


def update_remote_latest_available_dir(newInstaller: str, remoteUploadPath: str, task: ReleaseTask, stagingServerRoot: str, installerBuildId: str) -> None:
    log.info(f"Update latest available installer directory: {remoteUploadPath}")
    regex = re.compile('.*' + task.get_version())
    new_installer_base_path = "".join(regex.findall(newInstaller))
    path, name = os.path.split(new_installer_base_path)

    # update latest_available
    latest_available_path = re.sub(r"\/" + str(installerBuildId) + r"\/", "/latest_available/", remoteUploadPath)
    previous_installer_path = latest_available_path + name + '*'
    try:
        cmd_rm = get_remote_login_cmd(stagingServerRoot) + ['rm', previous_installer_path.split(':')[1]]
        log.info(f"Running remove cmd: {cmd_rm}")
        exec_cmd(cmd_rm, timeout=60*60)  # 1h
    except Exception:
        log.info("Running cmd failed - this happens only if latest_available is empty")
        pass
    cmd_cp = get_remote_login_cmd(stagingServerRoot) + ['cp', remoteUploadPath.split(':')[1] + name + '*', latest_available_path.split(':')[1]]
    log.info(f"Running copy cmd: {cmd_cp}")
    exec_cmd(cmd_cp, timeout=60*60)  # 1h


def upload_offline_to_remote(installerPath: str, remoteUploadPath: str, stagingServer: str, task: ReleaseTask,
                             installerBuildId: str, enable_oss_snapshots: bool, license: str) -> None:
    for file in [f for f in os.listdir(installerPath)]:
        if file.endswith(".app"):
            continue
        name, file_ext = os.path.splitext(file)
        file_name_final = name + "_" + installerBuildId + file_ext
        installer = os.path.join(installerPath, file_name_final)
        os.rename(os.path.join(installerPath, file), installer)
        remote_destination = stagingServer + ":" + remoteUploadPath
        cmd = ['scp', installer, remote_destination]
        log.info(f"Uploading offline installer: {installer} to: {remote_destination}")
        exec_cmd(cmd, timeout=60*60)  # 1h
        update_remote_latest_available_dir(installer, remote_destination, task, stagingServer, installerBuildId)
        if enable_oss_snapshots and license == "opensource":
            upload_snapshots_to_remote(stagingServer, remoteUploadPath, task, installerBuildId, file_name_final)


def sign_offline_installer(installer_path: str, installer_name: str) -> None:
    if platform.system() == "Windows":
        log.info("Sign Windows installer")
        from sign_windows_installer import sign_executable
        sign_executable(os.path.join(installer_path, installer_name) + '.exe')
    elif platform.system() == "Darwin":
        log.info("Sign macOS .app bundle")
        sign_installer.sign_mac_app(os.path.join(installer_path, installer_name + '.app'), get_pkg_value("SIGNING_IDENTITY"))
        log.info("Create macOS dmg file")
        sign_installer.create_mac_dmg(os.path.join(installer_path, installer_name) + '.app')
        log.info("Notarize macOS installer")
        notarize_dmg(os.path.join(installer_path, installer_name + '.dmg'), installer_name)
    else:
        log.info(f"No signing available for this host platform: {platform.system()}")


def notarize_dmg(dmgPath, installerBasename) -> None:
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "notarize.py"))
    # bundle-id is just a unique identifier without any special meaning, used to track the notarization progress
    bundleId = installerBasename + "-" + strftime('%Y-%m-%d-%H-%M', gmtime())
    bundleId = bundleId.replace('_', '-').replace(' ', '')  # replace illegal characters for bundleId
    cmd = [sys.executable, script_path, '--dmg=' + dmgPath, '--bundle-id=' + bundleId]
    exec_cmd(cmd, timeout=60*60*3)


async def build_offline_tasks(stagingServer: str, stagingServerRoot: str, tasks: List[ReleaseTask], license: str,
                              installerConfigBaseDir: str, artifactShareBaseUrl: str,
                              ifwTools: str, installerBuildId: str, updateStaging: bool,
                              enable_oss_snapshots: bool, event_injector: str, export_data: Dict[str, str]) -> None:
    async with event_register(f"{license}: offline", event_injector, export_data):
        await _build_offline_tasks(stagingServer, stagingServerRoot, tasks, license, installerConfigBaseDir,
                                   artifactShareBaseUrl, ifwTools, installerBuildId, updateStaging, enable_oss_snapshots)


async def _build_offline_tasks(stagingServer: str, stagingServerRoot: str, tasks: List[ReleaseTask], license: str,
                               installerConfigBaseDir: str, artifactShareBaseUrl: str,
                               ifwTools: str, installerBuildId: str, updateStaging: bool, enable_oss_snapshots: bool) -> None:
    log.info("Offline installer task(s): %i", len(tasks))

    assert license, "The 'license' must be defined!"
    assert artifactShareBaseUrl, "The 'artifactShareBaseUrl' must be defined!"
    assert ifwTools, "The 'ifwTools' must be defined!"

    scriptPath = os.path.abspath(os.path.join(os.path.dirname(__file__), "create_installer.py"))
    assert os.path.isfile(scriptPath), "Not a valid script path: {0}".format(scriptPath)
    installer_output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "installer_output"))

    # build installers
    for task in tasks:
        log.info(f"Building offline installer: {task.get_installer_name()}")
        installerConfigFile = os.path.join(installerConfigBaseDir, task.get_config_file())
        if not os.path.isfile(installerConfigFile):
            raise PackagingError(f"Invalid 'config_file' path: {installerConfigFile}")

        cmd = [sys.executable, scriptPath, "-c", installerConfigBaseDir, "-f", installerConfigFile]
        cmd += ["--offline", "-l", license, "--license-type", license, "-u", artifactShareBaseUrl, "--ifw-tools", ifwTools]
        cmd += ["--preferred-installer-name", task.get_installer_name()]
        cmd += ["--force-version-number-increase"]
        cmd.extend(["--add-substitution=" + s for s in task.get_installer_string_replacement_list()])
        try:
            await async_exec_cmd(cmd, timeout=60*60*3)  # 3h
        except Exception as e:
            log.error(str(e))
            raise

        sign_offline_installer(installer_output_dir, task.get_installer_name())
        if updateStaging:
            remote_upload_path = create_offline_remote_dirs(task, stagingServer, stagingServerRoot, installerBuildId)
            upload_offline_to_remote(installer_output_dir, remote_upload_path, stagingServer, task, installerBuildId, enable_oss_snapshots, license)


def upload_snapshots_to_remote(staging_server: str, remote_upload_path: str, task: ReleaseTask, installer_build_id: str, installer_filename: str):
    project_name = task.get_project_name()
    version_full = task.get_version()
    version_minor = re.match(r"\d+\.\d+", version_full).group(0)
    base, last_dir = os.path.split(get_pkg_value("SNAPSHOT_PATH").rstrip("/"))
    if last_dir == project_name:
        snapshot_path = get_pkg_value("SNAPSHOT_PATH")
    else:
        snapshot_path = os.path.join(base, project_name)
    snapshot_upload_path = os.path.join(snapshot_path, version_minor, version_full + task.get_prerelease_version(), installer_build_id)
    remote_installer_path = os.path.join(remote_upload_path, installer_filename)
    if platform.system() == "Windows":
        # commands are run in Linux, adjust the upload paths
        snapshot_upload_path = snapshot_upload_path.replace("\\", "/")
        remote_installer_path = remote_installer_path.replace("\\", "/")
    login = get_remote_login_cmd(staging_server) + get_remote_login_cmd(get_pkg_value("SNAPSHOT_SERVER"))
    cmd_mkdir = login + ["mkdir", "-p", snapshot_upload_path]
    log.info(f"Creating offline snapshot directory: {cmd_mkdir}")
    exec_cmd(cmd_mkdir, timeout=60*60)
    cmd_scp_installer = get_remote_login_cmd(staging_server) + ["scp", "-r", remote_installer_path] + [get_pkg_value("SNAPSHOT_SERVER") + ":" + snapshot_upload_path + "/"]
    log.info(f"Uploading offline snapshot: {cmd_scp_installer}")
    exec_cmd(cmd_scp_installer, timeout=60*60*2)


def load_export_summary_data(config_file: Path) -> Dict[str, str]:
    settings = ConfigParser(interpolation=ExtendedInterpolation())
    settings.read(str(config_file.resolve(strict=True)))
    ret: Dict[str, str] = {}

    try:
        summary_url = settings['common.definitions']['export_summary_url']
        with urlopen(summary_url) as url:
            ret = json.loads(url.read().decode())
    except KeyError:
        # it's ok, not mandatory
        log.info(f"Export summary file url not present in: {config_file}")
        pass
    except URLError as e:
        log.warning(f"Unable to read export summary file: {str(e)}")
    except ValueError:
        # it's ok, not mandatory
        pass
    return ret


if __name__ == "__main__":
    args_from_file_parser = argparse.ArgumentParser(
            description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            # Turn off help, so we print all options in response to -h
            add_help=False
            )
    args_from_file_parser.add_argument("--config", dest="config", type=str, default=os.getenv("RELEASE_DESCRIPTION_FILE"),
                                       help="Path to top level release config file", metavar="FILE")
    args, _ = args_from_file_parser.parse_known_args()
    defaults = {"option": "default"}

    if args.config:
        config = ConfigParser(interpolation=ExtendedInterpolation())
        config.read([args.config])
        # if the --config contains [script.default_args] then those will be used
        if config.has_section("script.default_args"):
            defaults.update(dict(config.items("script.default_args")))

    parser = argparse.ArgumentParser(description="Script to update release repositories",
                                     usage="To build linux android only repositories from given config file and update staging "
                                           "and production repositories and sync to S3 distribution:\n\n"
                                           "release_repo_updater.py --ifw-tools=<7z URL> "
                                           "--staging-server=username@server.com "
                                           "--staging-server-root=/base/path/for/online/repositories "
                                           "--config=<path to top level config .ini file> "
                                           "--task-filter=linux,x64,common --task-filter=linux,x64,opensource "
                                           "--artifacts-share-url=<http(s)://some.server.com/base/path/for/artifacts> "
                                           "--license=opensource "
                                           "--repo-domain=qtsdkrepository "
                                           "--build-repositories "
                                           "--update-staging "
                                           "--update-production "
                                           "--rta=<RTA trigger base URL> "
                                           "--sync-s3=<S3 bucket address> ")
    parser.add_argument("--ifw-tools", dest="ifw_tools", type=str, default=os.getenv("IFW_TOOLS"),
                        help="Archive which contains the ifw tools")

    parser.add_argument("--staging-server", dest="staging_server", type=str, default=get_pkg_value("STAGING_SERVER_LOGIN"),
                        help="Staging server")
    parser.add_argument("--staging-server-root", dest="staging_server_root", type=str, default=os.getenv("STAGING_SERVER_ROOT"),
                        help="Online repositories root directory")

    parser.add_argument("--config", dest="config", type=str, default=os.getenv("RELEASE_DESCRIPTION_FILE"),
                        help="Path to top level release config file")
    parser.add_argument("--task-filter", dest="task_filters", action='append',
                        help="Task include filters per section name in the --config file to match with "
                        "the section name, e.g. 'offline', 'repository', ...")
    parser.add_argument("--artifacts-share-url", dest="artifact_share_url", type=str, default=os.getenv("ARTIFACTS_SHARE_URL"),
                        help="Root URL for artifacts")

    parser.add_argument("--license", dest="license", type=str, choices=["enterprise", "opensource"], default=os.getenv("LICENSE"),
                        help="enterprise/opensource")
    parser.add_argument("--repo-domain", dest="repo_domain", type=str, choices=["qtsdkrepository", "marketplace"],
                        help="qtsdkrepository/marketplace")

    parser.add_argument("--build-repositories", dest="build_repositories", type=string_to_bool, nargs='?', default=False,
                        help="Build online repositories defined by '--config' file on current machine")
    parser.add_argument("--build-offline", dest="build_offline", type=string_to_bool, nargs='?', default=False,
                        help="Build offline installers defined by '--config' file")
    parser.add_argument("--offline-installer-build-id", dest="offline_installer_id", type=str, default=os.getenv('BUILD_NUMBER', timestamp),
                        help="Add unique id for the offline installer")

    parser.add_argument("--update-staging", dest="update_staging", action='store_true', default=os.getenv("DO_UPDATE_STAGING_REPOSITORY", False),
                        help="Should the staging repository be updated?")
    parser.add_argument("--update-production", dest="update_production", action='store_true', default=os.getenv("DO_UPDATE_PRODUCTION_REPOSITORY", False),
                        help="Should the production repository be updated?")
    parser.add_argument("--enable-oss-snapshots", dest="enable_oss_snapshots", action='store_true', default=False,
                        help="Upload snapshot to opensource file server")

    parser.add_argument("--rta", dest="rta", type=str, default=get_pkg_value("RTA_SERVER_BASE_URL"),
                        help="If specified then trigger RTA for tasks found from --config")

    parser.add_argument("--sync-s3", dest="sync_s3", type=str,
                        help="Sync online repositories defined by '--config' file to S3 production. Supports 'enterprise' license only at the moment.")
    parser.add_argument("--sync-ext", dest="sync_ext", type=str,
                        help="Sync online repositories defined by '--config' file to Ext production.")
    parser.add_argument("--event-injector", dest="event_injector", type=str, default=os.getenv('PKG_EVENT_INJECTOR'),
                        help="Register events to monitoring system with the given injector. "
                             "The --config file must point to export summary file.")
    parser.set_defaults(**defaults)  # these are from provided --config file
    args = parser.parse_args(sys.argv[1:])

    do_update_repositories = args.update_staging or args.update_production
    do_sync_repositories = args.sync_s3 or args.sync_ext

    assert args.config, "'--config' was not given!"
    assert args.staging_server_root, "'--staging-server-root' was not given!"

    if args.license == "opensource":
        assert not args.sync_s3, "The '--sync-s3' is not supported for 'opensource' license!"

    # user explicitly disabled rta triggers
    if args.rta in ["0", "disable", "false", "no"]:
        args.rta = None

    # format task string in case full task section string is used
    args.task_filters = format_task_filters(args.task_filters)
    # installer configuration files are relative to the given top level release description file
    installerConfigBaseDir = os.path.abspath(os.path.join(os.path.dirname(args.config), os.pardir))
    assert os.path.isdir(installerConfigBaseDir), "Not able to figure out 'configurations/' directory correctly: {0}".format(installerConfigBaseDir)

    export_data = load_export_summary_data(Path(args.config)) if args.event_injector else None

    loop = asyncio.get_event_loop()
    if args.build_offline:
        # get offline tasks
        tasks = release_task_reader.parse_config(args.config, task_filters=append_to_task_filters(args.task_filters, "offline"))
        loop.run_until_complete(build_offline_tasks(args.staging_server, args.staging_server_root, tasks, args.license,
                                                    installerConfigBaseDir, args.artifact_share_url, args.ifw_tools,
                                                    args.offline_installer_id, args.update_staging,
                                                    args.enable_oss_snapshots, args.event_injector, export_data))

    else:  # this is either repository build or repository sync build
        # get repository tasks
        tasks = release_task_reader.parse_config(args.config, task_filters=append_to_task_filters(args.task_filters, "repository"))
        ret = loop.run_until_complete(handle_update(args.staging_server, args.staging_server_root, args.license, tasks,
                                      args.repo_domain, installerConfigBaseDir, args.artifact_share_url,
                                      args.update_staging, args.update_production, args.sync_s3, args.sync_ext,
                                      args.rta, args.ifw_tools,
                                      args.build_repositories, do_update_repositories, do_sync_repositories,
                                      args.event_injector, export_data))
        for repo in ret:
            log.info(f"{repo}")
