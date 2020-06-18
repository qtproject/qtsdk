#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
##
## Copyright (C) 2020 The Qt Company Ltd.
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
import sys
import time
import shutil
import asyncio
import tempfile
import platform
import datetime
import argparse
from configparser import ConfigParser, ExtendedInterpolation
from typing import List, Dict, Tuple
import subprocess
import release_task_reader
from urllib.request import urlretrieve
from urllib.error import HTTPError
from release_task_reader import ReleaseTask
from installer_utils import PackagingError
from runner import exec_cmd, async_exec_cmd
from logging_util import init_logger

log = init_logger(__name__, debug_mode=False)
timestamp = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d--%H:%M:%S')


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


async def execute_remote_cmd(remoteServer: str, remoteServerHome: str, cmd: List[str], scriptFileName: str, timeout=60*60) -> None:
    remoteTmpDir = os.path.join(remoteServerHome, "remote_scripts", timestamp)
    create_remote_paths(remoteServer, [remoteTmpDir])
    remoteScript = create_remote_script(remoteServer, cmd, remoteTmpDir, scriptFileName)
    log.info("Created remote script: [%s] with contents: %s", remoteScript, ' '.join(cmd))
    await execute_remote_script(remoteServer, remoteScript, timeout)


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


async def execute_remote_script(server: str, remoteScriptPath: str, timeout=60*60) -> None:
    cmd = get_remote_login_cmd(server) + [remoteScriptPath]
    await async_exec_cmd(cmd, timeout)


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
        except HTTPError as e:
            log.error("Failed to trigger RTA for: %s", url)
            # let it proceed


def _remote_path_exists(server: str, remotePath: str, type: str) -> bool:
    cmd = get_remote_login_cmd(server) + ['test', type, remotePath, '&& echo OK || echo NOK']
    output = subprocess.check_output(' '.join(cmd), shell=True, timeout=60 * 2).decode("utf-8")
    return output.strip() == "OK"


def remote_repository_exists(server: str, remotePath: str) -> bool:
    return _remote_path_exists(server, remotePath, type="-d")


def remote_file_exists(server: str, remotePath: str) -> bool:
    return _remote_path_exists(server, remotePath, type="-f")


async def ensure_ext_repo_paths(server: str, ext: str, repo: str) -> None:
    log.info("Ensure repository paths on ext: %s:%s", ext, repo)
    login = get_remote_login_cmd(server) + get_remote_login_cmd(ext)
    cmd = login + ["mkdir", "-p", repo]
    await async_exec_cmd(cmd, timeout=60*60*10)


def is_safe_repo_directory(paths: List[str]) -> None:
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
    is_safe_repo_directory(paths)
    cmd = get_remote_login_cmd(server) + ['mkdir -p', ' '.join(paths)]
    exec_cmd(cmd, timeout=60 * 2)


def delete_remote_paths(server: str, paths: List[str]) -> None:
    is_safe_repo_directory(paths)
    cmd = get_remote_login_cmd(server) + ['rm -rf', ' '.join(paths)]
    exec_cmd(cmd, timeout=60 * 2)


def upload_pending_repository_content(server: str, sourcePath: str, remoteDestinationPath: str) -> None:
    log.info("Uploading pending repository content from: [%s] -> [%s:%s]", sourcePath, server, remoteDestinationPath)
    # When uploading new content to staging the old content is always deleted
    delete_remote_paths(server, [remoteDestinationPath])
    # repository and pkg tmp paths
    create_remote_paths(server, [remoteDestinationPath])
    # upload content
    cmd = ['rsync', '-avzh', sourcePath + "/", server + ":" + remoteDestinationPath]
    exec_cmd(cmd, timeout=60*60)  # give it 60 mins


def reset_new_remote_repository(server: str, remoteSourceRepoPath: str, remoteTargetRepoPath: str) -> None:
    if not remote_repository_exists(server, remoteSourceRepoPath):
        raise PackagingError("The remote source repository path did not exist on the server: {0}:{1}".format(server, remoteSourceRepoPath))
    if remote_file_exists(server, os.path.join(remoteTargetRepoPath, 'Updates.xml')):
        raise PackagingError("The remote target repository already exists: {0}:{1}".format(server, remoteTargetRepoPath))

    log.info("Reset new remote repository: source: [%s] target: [%s]", remoteSourceRepoPath, remoteTargetRepoPath)
    create_remote_paths(server, [remoteTargetRepoPath])
    cmd = get_remote_login_cmd(server) + ['cp', '-Rv', remoteSourceRepoPath + '/*', remoteTargetRepoPath]
    exec_cmd(cmd, timeout=60 * 60)  # give it 60 mins


def create_remote_repository_backup(server: str, remoteTargetRepoPath: str) -> str:
    remoteRepositoryBackupPath = os.path.join(remoteTargetRepoPath + "-backup-" + timestamp)
    if remote_repository_exists(server, remoteRepositoryBackupPath):
        raise PackagingError("The remote target repository back path already exists on the server: {0}:{1}".format(server, remoteRepositoryBackupPath))
    cmd = get_remote_login_cmd(server) + ['cp', '-Rv', remoteTargetRepoPath, remoteRepositoryBackupPath]
    exec_cmd(cmd, timeout=60 * 60)  # give it 60 mins
    log.info("Created remote repository backup: %s:%s", server, remoteRepositoryBackupPath)
    return remoteRepositoryBackupPath


def update_remote_repository(server: str, remoteRepogen: str, remoteSourcePkgPath: str, remoteTargetRepoPath: str, updateNewOnly=False) -> None:
    if not remote_file_exists(server, os.path.join(remoteTargetRepoPath, 'Updates.xml')):
        raise PackagingError("The remote target repository does not exist - can not update: {0}:{1}".format(server, os.path.join(remoteTargetRepoPath, 'Updates.xml')))
    if not remote_file_exists(server, remoteRepogen):
        raise PackagingError("The 'repogen' tool did not exist on the remote server: {0}:{1}".format(server, remoteRepogen))

    log.info("Update remote repository: source: [%s] target: [%s]", remoteSourcePkgPath, remoteTargetRepoPath)
    cmd = get_remote_login_cmd(server) + [remoteRepogen]
    if updateNewOnly:
        cmd += ['--update-new-components']  # usually for production to update only those with version number increase
    else:
        cmd += ['--update']  # usually staging
    cmd += ['-p', remoteSourcePkgPath, remoteTargetRepoPath]
    output = exec_cmd(cmd, timeout=60 * 60)  # give it 60 mins
    check_repogen_output(output)


async def sync_production_repositories_to_s3(server: str, s3: str, updatedProductionRepositories: Dict[str, str], remoteRootPath: str) -> None:
    remoteLogsBasePath = os.path.join(remoteRootPath, "s3_sync_logs")
    create_remote_paths(server, [remoteLogsBasePath])

    for repo, remoteProductionRepoFullPath in updatedProductionRepositories.items():
        remoteLogFileBase = os.path.join(remoteLogsBasePath, repo, "log-s3-" + timestamp)
        create_remote_paths(server, [os.path.dirname(remoteLogFileBase)])

        s3RepoPath = os.path.join(s3, repo)
        tipPrefix = repo.replace("/", "-") + "-"

        remoteLogFile = remoteLogFileBase + "-7z.txt"
        await sync_production_7z_to_s3(server, remoteRootPath, remoteProductionRepoFullPath, s3RepoPath, remoteLogFile, tipPrefix)
        remoteLogFile = remoteLogFileBase + "-xml.txt"
        await sync_production_xml_to_s3(server, remoteRootPath, remoteProductionRepoFullPath, s3RepoPath, remoteLogFile, tipPrefix)


async def sync_production_7z_to_s3(server: str, serverHome: str, productionRepoPath: str, s3RepoPath: str, remoteLogFile: str, tip: str) -> None:
    log.info("Syncing .7z to s3: [%s:%s] -> [%s]", server, productionRepoPath, s3RepoPath)

    cmd = ["aws", "s3", "sync", productionRepoPath, s3RepoPath]
    cmd = cmd + ["--exclude", '"*"', "--include", '"*.7z"', "--include", '"*.sha1"']
    await spawn_remote_background_task(server, serverHome, cmd, remoteLogFile, tip=tip + "7z")


async def sync_production_xml_to_s3(server: str, serverHome: str, productionRepoPath: str, s3RepoPath: str, remoteLogFile: str, tip: str) -> None:
    log.info("Syncing .xml to s3: [%s:%s] -> [%s]", server, productionRepoPath, s3RepoPath)

    cmd = ["aws", "s3", "sync", productionRepoPath, s3RepoPath]
    cmd = cmd + ["--cache-control", '"max-age=0"', "--exclude", '"*"', "--include", '"*.xml"']
    await spawn_remote_background_task(server, serverHome, cmd, remoteLogFile, tip=tip + "xml")


async def sync_production_repositories_to_ext(server: str, ext: str, updatedProductionRepositories: Dict[str, str], remoteRootPath: str) -> None:
    remoteLogsBasePath = os.path.join(remoteRootPath, "ext_sync_logs")
    create_remote_paths(server, [remoteLogsBasePath])

    extServer, extBasePath = parse_ext(ext)

    for repo, remoteProductionRepoFullPath in updatedProductionRepositories.items():
        remoteLogFile = os.path.join(remoteLogsBasePath, repo, "log-ext-" + timestamp + ".txt")
        create_remote_paths(server, [os.path.dirname(remoteLogFile)])

        extRepoPath = os.path.join(extBasePath, repo)
        tipPrefix = repo.replace("/", "-") + "-"

        await ensure_ext_repo_paths(server, extServer, extRepoPath)  # rsync can not create missing nested directories
        cmd = ["rsync", "-r", "--omit-dir-times", "--delete", "--progress", remoteProductionRepoFullPath + "/", extServer + ":" + extRepoPath]
        await spawn_remote_background_task(server, remoteRootPath, cmd, remoteLogFile, tip=tipPrefix + "ext")


async def spawn_remote_background_task(server: str, serverHome: str, remoteCmd: List[str], remoteLogFile: str, tip: str) -> None:
    if not tip:
        tip = ""
    cmd = ["nohup"] + remoteCmd + ["</dev/null >", remoteLogFile, "2>&1"]
    remoteScriptFileName = "sync-production-" + tip + "-" + timestamp + ".sh"
    await execute_remote_cmd(server, serverHome, cmd, remoteScriptFileName, timeout=60*60)


async def update_repository(stagingServer: str, repoLayout: QtRepositoryLayout, task: ReleaseTask,
                            updateStaging: bool, updateProduction: bool, rta: str, remoteRepogen: str) -> None:
    assert task.get_source_online_repository_path(), "Can not update repository: [{0}] because source repo is missing".format(task.get_repo_path())
    assert task.get_source_pkg_path(), "Can not update repository: [{0}] because source pkg is missing".format(task.get_repo_path())
    # ensure the repository paths exists at server
    log.info("Starting repository update: %s", task.get_repo_path())
    create_remote_paths(stagingServer, repoLayout.get_repo_layout())

    isNewStagingRepository = True
    isNewProductionRepository = True

    remotePendingPath = os.path.join(repoLayout.get_pending_path(), task.get_repo_path())
    remotePendingPathRepository = os.path.join(remotePendingPath, "repository")
    remotePendingPathPkg = os.path.join(remotePendingPath, "pkg")

    remoteStagingDestinationRepositoryPath = os.path.join(repoLayout.get_staging_path(), task.get_repo_path())
    remoteProductionDestinationRepositoryPath = os.path.join(repoLayout.get_production_path(), task.get_repo_path())

    if remote_file_exists(stagingServer, os.path.join(remoteStagingDestinationRepositoryPath, 'Updates.xml')):
        isNewStagingRepository = False
    if remote_file_exists(stagingServer, os.path.join(remoteProductionDestinationRepositoryPath, 'Updates.xml')):
        isNewProductionRepository = False

    # Upload only the needed content to remote for the update:
    # When creating a new repository from scratch we upload the complete 'repository'.
    # When updating existing repository we upload the intermediate 'pkg' for the update process.
    if isNewStagingRepository or isNewProductionRepository:
        upload_pending_repository_content(stagingServer, task.get_source_online_repository_path(), remotePendingPathRepository)
    if not isNewStagingRepository or not isNewProductionRepository:
        upload_pending_repository_content(stagingServer, task.get_source_pkg_path(), remotePendingPathPkg)

    # Now we can run the updates on the remote
    if updateStaging:
        if isNewStagingRepository:
            reset_new_remote_repository(stagingServer, remotePendingPathRepository, remoteStagingDestinationRepositoryPath)
        else:
            update_remote_repository(stagingServer, remoteRepogen, remotePendingPathPkg, remoteStagingDestinationRepositoryPath, updateNewOnly=False)
    if updateProduction:
        if isNewProductionRepository:
            reset_new_remote_repository(stagingServer, remotePendingPathRepository, remoteProductionDestinationRepositoryPath)
        else:
            create_remote_repository_backup(stagingServer, remoteProductionDestinationRepositoryPath)
            update_remote_repository(stagingServer, remoteRepogen, remotePendingPathPkg, remoteProductionDestinationRepositoryPath, updateNewOnly=True)

    log.info("Starting update done: %s", task.get_repo_path())
    # Now we can delete pending content
    delete_remote_paths(stagingServer, [remotePendingPathRepository, remotePendingPathPkg])
    # trigger RTA cases for the task if specified
    if rta:
        trigger_rta(rta, task)


async def build_online_repositories(tasks: List[ReleaseTask], license: str, installerConfigBaseDir: str, artifactShareBaseUrl: str,
                                    ifwTools: str, buildRepositories: bool) -> None:
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
    scriptPath = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "create_installer.py"))
    assert os.path.isfile(scriptPath), "Not a valid script path: {0}".format(scriptPath)

    # build online repositories first
    for task in tasks:
        tmpDir = os.path.join(tmpBaseDir, task.get_repo_path())
        task.source_online_repository_path = os.path.join(tmpDir, "online_repository")
        task.source_pkg_path = os.path.join(tmpDir, "pkg")
        if not buildRepositories:
            # this is usually for testing purposes in env where repositories are already built, we just update task objects
            continue

        log.info("Building repository: %s", task.get_repo_path())
        installerConfigFile = os.path.join(installerConfigBaseDir, task.get_config_file())
        if not os.path.isfile(installerConfigFile):
            raise PackagingError("Invalid 'config_file' path: {0}".format(installerConfigFile))

        # TODO: license
        cmd = ["python", scriptPath, "-c", installerConfigBaseDir, "-f", installerConfigFile]
        cmd += ["--create-repo", "-l", license, "--license-type", license, "-u", artifactShareBaseUrl, "--ifw-tools", ifwTools]
        cmd += ["--force-version-number-increase"]
        for substitution in task.get_installer_string_replacement_list():
            cmd += ["--add-substitution=" + substitution]

        try:
            await async_exec_cmd(cmd, timeout=60*60*2)  # 2h for one repo build should suffice
        except Exception as e:
            log.error(str(e))
            raise

        onlineRepositoryPath = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "online_repository"))
        assert os.path.isdir(onlineRepositoryPath), "Not a valid path: {0}".format(onlineRepositoryPath)
        onlineRepositoryPkgPath = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, "pkg"))
        assert os.path.isdir(onlineRepositoryPkgPath), "Not a valid path: {0}".format(onlineRepositoryPkgPath)
        shutil.move(onlineRepositoryPath, task.source_online_repository_path)
        shutil.move(onlineRepositoryPkgPath, task.source_pkg_path)
        log.info("Repository created at: %s", tmpDir)


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
                          stagingServer: str, stagingServerRoot: str) -> None:
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
        await sync_production_repositories_to_s3(stagingServer, syncS3, updatedProductionRepositories, stagingServerRoot)
    if syncExt:
        await sync_production_repositories_to_ext(stagingServer, syncExt, updatedProductionRepositories, stagingServerRoot)
    log.info("Production sync trigger done!")


async def handle_update(stagingServer: str, stagingServerRoot: str, license: str, tasks: List[ReleaseTask],
                        repoDomain: str, installerConfigBaseDir: str, artifactShareBaseUrl: str,
                        updateStaging: bool, updateProduction: bool, syncS3: str, syncExt: str, rta: str, ifwTools: str,
                        buildRepositories: bool, updateRepositories: bool, syncRepositories: bool) -> None:
    """Build all online repositories, update those to staging area and sync to production."""
    log.info("Starting repository update for %i tasks..", len(tasks))

    # get repository layout
    repoLayout = QtRepositoryLayout(stagingServerRoot, license, repoDomain)
    # this may take a while depending on how big the repositories are
    await build_online_repositories(tasks, license, installerConfigBaseDir, artifactShareBaseUrl, ifwTools, buildRepositories)

    if updateRepositories:
        await update_repositories(tasks, stagingServer, stagingServerRoot, repoLayout, updateStaging, updateProduction, rta, ifwTools)
    if syncRepositories:
        await sync_production(tasks, repoLayout, syncS3, syncExt, stagingServer, stagingServerRoot)

    log.info("Repository updates done!")


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
    return ["repository," + x if x else "repository" for x in task_filters] if task_filters else ["repository"]


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

    parser.add_argument("--staging-server", dest="staging_server", type=str, default=os.getenv("STAGING_SERVER"),
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

    parser.add_argument("--build-repositories", dest="build_repositories", type=string_to_bool, nargs='?', default=True,
                        help="Build online repositories defined by '--config' file on current machine")

    parser.add_argument("--update-staging", dest="update_staging", action='store_true', default=os.getenv("DO_UPDATE_STAGING_REPOSITORY", False),
                        help="Should the staging repository be updated?")
    parser.add_argument("--update-production", dest="update_production", action='store_true', default=os.getenv("DO_UPDATE_PRODUCTION_REPOSITORY", False),
                        help="Should the production repository be updated?")

    parser.add_argument("--rta", dest="rta", type=str, default=os.getenv("RTA_SERVER_BASE_URL"),
                        help="If specified then trigger RTA for tasks found from --config")

    parser.add_argument("--sync-s3", dest="sync_s3", type=str,
                        help="Sync online repositories defined by '--config' file to S3 production. Supports 'enterprise' license only at the moment.")
    parser.add_argument("--sync-ext", dest="sync_ext", type=str,
                        help="Sync online repositories defined by '--config' file to Ext production.")
    parser.set_defaults(**defaults)  # these are from provided --config file
    args = parser.parse_args(sys.argv[1:])

    do_update_repositories = args.update_staging or args.update_production
    do_sync_repositories = args.sync_s3 or args.sync_ext

    assert args.config, "'--config' was not given!"
    assert args.staging_server_root, "'--staging-server-root' was not given!"
    assert "windows" not in platform.system().lower(), "This script is meant to be run on Unix only!"
    if args.license == "opensource":
        assert not args.sync_s3, "The '--sync-s3' is not supported for 'opensource' license!"

    # get repository tasks
    tasks = release_task_reader.parse_config(args.config, task_filters=append_to_task_filters(args.task_filters, "repository"))
    # installer configuration files are relative to the given top level release description file
    installerConfigBaseDir = os.path.abspath(os.path.join(os.path.dirname(args.config), os.pardir))
    assert os.path.isdir(installerConfigBaseDir), "Not able to figure out 'configurations/' directory correctly: {0}".format(installerConfigBaseDir)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(handle_update(args.staging_server, args.staging_server_root, args.license, tasks,
                                          args.repo_domain, installerConfigBaseDir, args.artifact_share_url,
                                          args.update_staging, args.update_production, args.sync_s3, args.sync_ext,
                                          args.rta, args.ifw_tools,
                                          args.build_repositories, do_update_repositories, do_sync_repositories))
