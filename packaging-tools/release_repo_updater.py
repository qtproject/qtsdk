#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#############################################################################
#
# Copyright (C) 2023 The Qt Company Ltd.
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

import argparse
import asyncio
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from configparser import ConfigParser, ExtendedInterpolation
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from subprocess import PIPE
from time import gmtime, sleep, strftime, time
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import urlopen, urlretrieve

from temppathlib import TemporaryDirectory

from bld_utils import is_linux
from bldinstallercommon import is_long_path_supported, locate_path
from create_installer import DryRunMode, QtInstallerTask, create_installer
from installer_utils import PackagingError, download_archive, extract_archive, is_valid_url_path
from logging_util import init_logger
from notarize import notarize
from read_remote_config import get_pkg_value
from release_task_reader import IFWReleaseTask, TaskType, parse_config
from runner import run_cmd, run_cmd_async
from sign_installer import create_mac_dmg, sign_mac_app
from sign_windows_installer import sign_executable

if sys.version_info < (3, 7):
    from asyncio_backport import run as asyncio_run
else:
    from asyncio import run as asyncio_run

if is_linux():
    import sh  # type: ignore

log = init_logger(__name__, debug_mode=False)
timestamp = datetime.fromtimestamp(time()).strftime('%Y-%m-%d--%H:%M:%S')


class EventRegister():
    event_injector: Optional[Path] = None
    python_path: str = ""

    def __init__(self, event_name: str, event_injector_path: str, summary_data: Dict[str, str]) -> None:
        self.event_name = event_name
        self.summary_data = summary_data
        self.initialize(event_injector_path)

    @classmethod
    def initialize(cls, event_injector_path: str) -> None:
        if not cls.python_path:
            if platform.system() == "Linux":
                cls.python_path = sh.which("python3")
            if platform.system() == "Windows":
                cls.python_path = os.path.join(os.getenv("PYTHON3_PATH", ""), "python.exe")
            if platform.system() == "Darwin":
                cls.python_path = os.path.join(os.getenv("PYTHON3_PATH", ""), "python3")
        if event_injector_path:
            cls.event_injector = Path(event_injector_path).resolve(strict=True)

    async def __aenter__(self) -> 'EventRegister':
        if EventRegister.event_injector:
            self.register_event(self.event_name, "START", self.summary_data, message="")
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, traceback: Any) -> bool:
        ret = True
        event_type = "FINISH"
        if traceback:
            ret = False  # will cause the exception to be propagated
            event_type = "ABORT"
        if EventRegister.event_injector:
            self.register_event(self.event_name, event_type, self.summary_data, message=exc_val)
        return ret

    def register_event(self, event_name: str, event_type: str, export_summary: Dict[str, str], message: str) -> None:
        if not EventRegister.event_injector:
            log.warning("Unable to register event as injector not found!")
            return
        cmd = [str(EventRegister.python_path), str(EventRegister.event_injector), f"--event={event_type}", f"--task={event_name}",
               f"--project-name={export_summary.get('project', '')}",
               f"--project-version={export_summary.get('version', '')}",
               f"--destination-branch={export_summary.get('destination_branch', '')}",
               f"--integration-id={export_summary.get('id', '')}",
               f"--sha1={export_summary.get('sha1', '')}",
               f"--message={message or ''}"]
        log.info("Calling: %s", " ".join(cmd))
        ret = subprocess.run(cmd, shell=False, check=False, stdout=PIPE, stderr=PIPE, encoding="utf-8", timeout=60 * 2)
        if ret.returncode:
            log.warning("Failed to register event - stdout: %s", ret.stderr)
            log.warning("Failed to register event - stderr: %s", ret.stdout)


class RepoSource(Enum):
    PENDING = "pending"
    STAGING = "staging"
    PRODUCTION = "production"


class QtRepositoryLayout:

    def __init__(self, root_path: str, license_: str, repo_domain: str) -> None:
        self.root_path = root_path
        self.license_ = license_
        self.repo_domain = repo_domain
        self.pending = RepoSource.PENDING.value
        self.staging = RepoSource.STAGING.value
        self.production = RepoSource.PRODUCTION.value
        # <root_path>/<license>/<pending|staging|production>/<repo_domain>/
        # /data/online_repositories/opensource/pending|staging|production/qtsdkrepository/
        log.info("self.root_path %s", self.root_path)
        log.info("self.license_ %s", self.license_)
        self.base_repo_path = os.path.join(self.root_path, self.license_)

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


@dataclass
class RepoUpdateStrategy:
    """Encapsulates instructions how the repository update should be performed on the remote."""

    local_repo_build: bool
    remote_repo_layout: QtRepositoryLayout
    remote_repo_update_source: RepoSource
    remote_repo_update_destinations: List[str]

    @staticmethod
    def get_strategy(staging_server_root: str, license_: str, repo_domain: str,
                     build_repositories: bool, remote_repo_update_source: RepoSource,
                     update_staging: bool, update_production: bool) -> 'RepoUpdateStrategy':
        if build_repositories and remote_repo_update_source != RepoSource.PENDING:
            raise PackagingError("You are building repositories and want to update repositories "
                                 "not using this build as the update source? Check cmd args.")
        if not build_repositories and update_staging:
            raise PackagingError("Can not update staging if you are not building the repo "
                                 "locally. The pending area would be empty. Check cmd args.")
        # get repository layout
        repo_layout = QtRepositoryLayout(staging_server_root, license_, repo_domain)
        repo_update_destinations = []
        if update_staging:
            repo_update_destinations.append(repo_layout.get_staging_path())
        if update_production:
            repo_update_destinations.append(repo_layout.get_production_path())
        return RepoUpdateStrategy(build_repositories, repo_layout, remote_repo_update_source,
                                  repo_update_destinations)

    def get_remote_source_repo_path(self, task: IFWReleaseTask) -> str:
        if self.remote_repo_update_source == RepoSource.PENDING:
            return os.path.join(str(self.remote_repo_layout.get_pending_path()),
                                task.repo_path, "repository")
        if self.remote_repo_update_source == RepoSource.STAGING:
            return os.path.join(str(self.remote_repo_layout.get_staging_path()),
                                task.repo_path)
        raise PackagingError("Invalid remote source repo defined: "
                             f"{self.remote_repo_update_source}")

    def requires_remote_update(self) -> bool:
        return bool(self.remote_repo_update_destinations)

    def requires_local_source_repo_upload(self) -> bool:
        return self.local_repo_build

    def purge_remote_source_repo(self) -> bool:
        return self.remote_repo_update_source == RepoSource.PENDING


def has_connection_error(output: str) -> bool:
    known_errors = ["Could not connect to the endpoint URL"]
    for line in output.splitlines():
        for known_error in known_errors:
            if line.find(known_error) >= 0:
                return True
    return False


def execute_remote_cmd(
    remote_server: str,
    remote_server_home: str,
    cmd: List[str],
    script_file_name: str,
    timeout: int = 60 * 60,
) -> None:
    remote_tmp_dir = os.path.join(remote_server_home, "remote_scripts", timestamp)
    create_remote_paths(remote_server, [remote_tmp_dir])
    remote_script = create_remote_script(remote_server, cmd, remote_tmp_dir, script_file_name)
    log.info("Created remote script: [%s] with contents: %s", remote_script, ' '.join(cmd))
    execute_remote_script(remote_server, remote_script, timeout)


def create_remote_script(
    server: str, cmd: List[str], remote_script_path: str, script_file_name: str
) -> str:
    with TemporaryDirectory() as tmp_base_dir:
        temp_file_path = tmp_base_dir.path / script_file_name
        with temp_file_path.open('w+', encoding="utf-8") as handle:
            handle.write("#!/usr/bin/env bash\n")
            handle.write(' '.join(cmd))
        temp_file_path.chmod(0o755)
        create_remote_paths(server, [remote_script_path])
        cmd = ['rsync', '-avzh', str(temp_file_path), server + ":" + remote_script_path]
        run_cmd(cmd=cmd, timeout=60 * 60)
        return os.path.join(remote_script_path, script_file_name)


def execute_remote_script(server: str, remote_script_path: str, timeout: int = 60 * 60) -> None:
    cmd = get_remote_login_cmd(server) + [remote_script_path]
    retry_count = 5
    delay = float(60)
    while retry_count:
        retry_count -= 1
        output = run_cmd(cmd=cmd, timeout=timeout)
        if not has_connection_error(output):
            break
        if retry_count:
            log.warning("Trying again after %ss", delay)
            sleep(delay)
            delay = delay + delay / 2  # 60, 90, 135, 202, 303
        else:
            log.critical("Execution of the remote script probably failed: %s", cmd)


async def upload_ifw_to_remote(ifw_tools: str, remote_server: str) -> str:
    assert is_valid_url_path(ifw_tools)
    log.info("Preparing ifw tools: %s", ifw_tools)
    # fetch the tool first
    ifw_tools_dir = Path.cwd() / "ifw_tools"
    if not ifw_tools_dir.is_dir():
        ifw_tools_dir.mkdir(parents=True)
        dest_file = download_archive(ifw_tools, str(ifw_tools_dir))
        await extract_archive(dest_file, str(ifw_tools_dir))
    repogen = locate_path(ifw_tools_dir, ["repogen"], filters=[os.path.isfile])
    repogen_dir = os.path.dirname(repogen)
    # upload to server
    remote_tmp_dir = os.path.join("ifw_tools", timestamp)
    # create tmp dir at remote
    create_remote_paths(remote_server, [remote_tmp_dir])
    # upload content
    cmd = ['rsync', '-avzh', repogen_dir + "/", remote_server + ":" + remote_tmp_dir]
    run_cmd(cmd=cmd, timeout=60 * 60)
    # return path on remote poiting to repogen
    return os.path.join(remote_tmp_dir, "repogen")


def check_repogen_output(output: str) -> None:
    if any(fail_string in output.strip().lower() for fail_string in ["error", "invalid", "already exists"]):
        raise PackagingError(f"Repogen failed: {output.strip()}")


def get_remote_login_cmd(server: str) -> List[str]:
    return ['ssh', '-t', '-t', server]


def trigger_rta(rta_server_url: str, task: IFWReleaseTask) -> None:
    for key in task.rta_key_list:
        url = rta_server_url + key + '/build?token=RTA_JENKINS'
        log.info("Triggering RTA case: %s", url)
        try:
            urlretrieve(url)
        except HTTPError:
            log.error("Failed to trigger RTA for: %s", url)
            # let it proceed


def _remote_path_exists(server: str, remote_path: str, test_arg: str) -> bool:
    cmd = get_remote_login_cmd(server) + ['test', test_arg, remote_path, '&& echo OK || echo NOK']
    output = subprocess.check_output(' '.join(cmd), shell=True, timeout=60 * 2).decode("utf-8")
    return output.strip() == "OK"


def remote_path_exists(server: str, remote_path: str) -> bool:
    return _remote_path_exists(server, remote_path, test_arg="-d")


def remote_file_exists(server: str, remote_path: str) -> bool:
    return _remote_path_exists(server, remote_path, test_arg="-f")


async def ensure_ext_repo_paths(server: str, ext: str, repo: str) -> None:
    log.info("Ensure repository paths on ext: %s:%s", ext, repo)
    login = get_remote_login_cmd(server) + get_remote_login_cmd(ext)
    cmd = login + ["mkdir", "-p", repo]
    await run_cmd_async(cmd=cmd, timeout=60 * 60 * 10)


def is_safe_directory(paths: List[str]) -> None:
    for _path in paths:
        path = os.path.abspath(_path)
        if path == "/":
            raise PackagingError(f"You should not make modifications directly to root: {path}")
        illegal_directories = ("/bin", "/boot", "/sys", "/sbin", "/root", "/lib", "/dev")
        if path.startswith(illegal_directories):
            raise PackagingError(f"You should not make modifications ('{path}') under these directories: {illegal_directories}")
        if path in ["~", str(Path.home()), "/home"]:
            raise PackagingError(f"You should not make modifications directly to home directory: {path}")


def create_remote_paths(server: str, paths: List[str]) -> None:
    is_safe_directory(paths)
    cmd = get_remote_login_cmd(server) + ['mkdir -p', ' '.join(paths)]
    run_cmd(cmd=cmd, timeout=60 * 2)


def delete_remote_paths(server: str, paths: List[str]) -> None:
    is_safe_directory(paths)
    cmd = get_remote_login_cmd(server) + ['rm -rf', ' '.join(paths)]
    run_cmd(cmd=cmd, timeout=60 * 2)


def upload_pending_repository_content(server: str, source_path: str, remote_destination_path: str) -> None:
    log.info("Uploading pending repository content from: [%s] -> [%s:%s]", source_path, server, remote_destination_path)
    # When uploading new content to staging the old content is always deleted
    delete_remote_paths(server, [remote_destination_path])
    # repository paths
    create_remote_paths(server, [remote_destination_path])
    # upload content
    cmd = ['rsync', '-avzh', source_path + "/", server + ":" + remote_destination_path]
    run_cmd(cmd=cmd, timeout=60 * 60)  # give it 60 mins


def reset_new_remote_repository(server: str, remote_source_repo_path: str, remote_target_repo_path: str) -> None:
    if not remote_path_exists(server, remote_source_repo_path):
        raise PackagingError(f"The remote source repository path did not exist on the server: {server}:{remote_source_repo_path}")
    if remote_path_exists(server, remote_target_repo_path):
        # this will _move_ the currect repo as backup
        create_remote_repository_backup(server, remote_target_repo_path)

    log.info("Reset new remote repository: source: [%s] target: [%s]", remote_source_repo_path, remote_target_repo_path)
    create_remote_paths(server, [remote_target_repo_path])
    args = ['cp', '-Rv', remote_source_repo_path + '/*', remote_target_repo_path]
    run_cmd(cmd=get_remote_login_cmd(server) + args, timeout=60 * 60)  # give it 60 mins


def create_remote_repository_backup(server: str, remote_repo_path: str) -> str:
    backup_path = os.path.join(remote_repo_path + "____snapshot_backup")
    # if there exists a backup already then delete it, we keep only one backup
    if remote_path_exists(server, backup_path):
        log.info("Deleting old backup repo: %s", backup_path)
        delete_remote_paths(server, [backup_path])
    # move the repo as backup
    args = ["mv", "-v", remote_repo_path, backup_path]
    run_cmd(cmd=get_remote_login_cmd(server) + args, timeout=60 * 60)  # give it 60 mins
    log.info("Moved remote repo as backup: %s:%s -> %s", server, remote_repo_path, backup_path)
    return backup_path


def sync_production_repositories_to_s3(server: str, s3_path: str, updated_production_repositories: Dict[str, str],
                                       remote_root_path: str, license_: str) -> None:
    remote_logs_base_path = os.path.join(remote_root_path, license_, "s3_sync_logs")
    create_remote_paths(server, [remote_logs_base_path])

    for repo, remote_production_repo_full_path in updated_production_repositories.items():
        remote_log_file_base = os.path.join(remote_logs_base_path, repo, "log-s3-" + timestamp)
        create_remote_paths(server, [os.path.dirname(remote_log_file_base)])

        s3_repo_path = os.path.join(s3_path, repo)
        tip_prefix = repo.replace("/", "-") + "-"

        remote_log_file = remote_log_file_base + "-7z.txt"
        sync_production_payload_to_s3(server, remote_root_path, remote_production_repo_full_path, s3_repo_path, remote_log_file, tip_prefix)
        remote_log_file = remote_log_file_base + "-xml.txt"
        sync_production_xml_to_s3(server, remote_root_path, remote_production_repo_full_path, s3_repo_path, remote_log_file, tip_prefix)


def sync_production_payload_to_s3(server: str, server_home: str, production_repo_path: str, s3_repo_path: str, remote_log_file: str, tip: str) -> None:
    log.info("Syncing payload to s3: [%s:%s] -> [%s]", server, production_repo_path, s3_repo_path)

    cmd = ["aws", "s3", "sync", production_repo_path, s3_repo_path]
    cmd.extend(["--exclude", '"*"', "--include", '"*.7z"', "--include", '"*.tar.xz"'])
    cmd.extend(["--include", '"*.tar.bz2"', "--include", '"*.tar"', "--include", '"*.tar.gz"'])
    cmd.extend(["--include", '"*.zip"', "--include", '"*.sha1"'])
    spawn_remote_background_task(server, server_home, cmd, remote_log_file, tip=tip + "7z")


def sync_production_xml_to_s3(server: str, server_home: str, production_repo_path: str, s3_repo_path: str, remote_log_file: str, tip: str) -> None:
    log.info("Syncing .xml to s3: [%s:%s] -> [%s]", server, production_repo_path, s3_repo_path)

    cmd = ["aws", "s3", "sync", production_repo_path, s3_repo_path]
    cmd = cmd + ["--cache-control", '"max-age=0"', "--exclude", '"*"', "--include", '"*.xml"']
    spawn_remote_background_task(server, server_home, cmd, remote_log_file, tip=tip + "xml")


async def sync_production_repositories_to_ext(server: str, ext: str, updated_production_repositories: Dict[str, str],
                                              remote_root_path: str, license_: str) -> None:
    remote_logs_base_path = os.path.join(remote_root_path, license_, "ext_sync_logs")
    create_remote_paths(server, [remote_logs_base_path])

    ext_server, ext_base_path = parse_ext(ext)

    for repo, remote_production_repo_full_path in updated_production_repositories.items():
        remote_log_file = os.path.join(remote_logs_base_path, repo, "log-ext-" + timestamp + ".txt")
        create_remote_paths(server, [os.path.dirname(remote_log_file)])

        ext_repo_path = os.path.join(ext_base_path, repo)
        tip_prefix = repo.replace("/", "-") + "-"

        await ensure_ext_repo_paths(server, ext_server, ext_repo_path)  # rsync can not create missing nested directories
        cmd = ["rsync", "-r", "--omit-dir-times", "--delete-delay", "--progress", remote_production_repo_full_path + "/", ext_server + ":" + ext_repo_path]
        spawn_remote_background_task(server, remote_root_path, cmd, remote_log_file, tip=tip_prefix + "ext")


def spawn_remote_background_task(server: str, server_home: str, remote_cmd: List[str], remote_log_file: str, tip: str) -> None:
    if not tip:
        tip = ""
    cmd = remote_cmd + ["2>&1", "|", "tee", remote_log_file]
    remote_script_file_name = "sync-production-" + tip + "-" + timestamp + ".sh"
    execute_remote_cmd(server, server_home, cmd, remote_script_file_name, timeout=60 * 60 * 2)  # 2h timeout for uploading data to CDN


async def update_repository(staging_server: str, update_strategy: RepoUpdateStrategy,
                            task: IFWReleaseTask, rta: str) -> None:
    # ensure the repository paths exists at server
    log.info("Starting repository update: %s", task.repo_path)
    create_remote_paths(staging_server, update_strategy.remote_repo_layout.get_repo_layout())

    # this is the repo path on remote which will act as the 'source' for remote updates
    # on the remote machine
    remote_repo_source_path = update_strategy.get_remote_source_repo_path(task)

    if update_strategy.requires_local_source_repo_upload():
        # this is the repo path from local repo build which will act as the 'source' which to
        # upload to the remote
        local_repo_source_path = task.source_online_repository_path
        # We always replace existing repository if previous version should exist.
        # Previous version is moved as backup
        upload_pending_repository_content(staging_server, local_repo_source_path,
                                          remote_repo_source_path)

    # Now we can run the updates on the remote
    for update_destination in update_strategy.remote_repo_update_destinations:
        remote_repo_destination_path = os.path.join(update_destination, task.repo_path)
        reset_new_remote_repository(staging_server, remote_repo_source_path,
                                    remote_repo_destination_path)
    log.info("Update done: %s", task.repo_path)

    # Delete pending content
    if update_strategy.purge_remote_source_repo():
        delete_remote_paths(staging_server, [remote_repo_source_path])
    # trigger RTA cases for the task if specified
    if rta:
        trigger_rta(rta, task)


async def build_online_repositories(
    tasks: List[IFWReleaseTask],
    license_: str,
    installer_config_base_dir: str,
    artifact_share_base_url: str,
    ifw_tools: str,
    build_repositories: bool,
    dry_run: Optional[DryRunMode] = None,
) -> List[str]:
    log.info("Building online repositories: %i", len(tasks))
    # create base tmp dir
    tmp_base_dir = Path.cwd() / "_repo_update_jobs"
    if build_repositories:
        shutil.rmtree(tmp_base_dir, ignore_errors=True)
    tmp_base_dir.mkdir(parents=True, exist_ok=True)

    assert license_, "The 'license_' must be defined!"
    assert artifact_share_base_url, "The 'artifact_share_base_url' must be defined!"
    assert ifw_tools, "The 'ifw_tools' must be defined!"

    # build online repositories first
    done_repositories = []  # type: List[str]
    if sys.version_info < (3, 7):
        loop = asyncio.get_event_loop()
    else:
        loop = asyncio.get_running_loop()  # pylint: disable=no-member
    # use same timestamp for all built repos
    job_timestamp = strftime("%Y-%m-%d", gmtime())
    for task in tasks:
        tmp_dir = os.path.join(tmp_base_dir, task.repo_path)
        task.source_online_repository_path = os.path.join(tmp_dir, "online_repository")
        if not build_repositories:
            # this is usually for testing purposes in env where repositories are already built, we just update task objects
            continue

        log.info("Building repository: %s", task.repo_path)
        installer_config_file = os.path.join(installer_config_base_dir, task.config_file)
        if not os.path.isfile(installer_config_file):
            raise PackagingError(f"Invalid 'config_file' path: {installer_config_file}")

        installer_task: QtInstallerTask[Any] = QtInstallerTask(
            configurations_dir=installer_config_base_dir,
            configuration_file=installer_config_file,
            create_repository=True,
            license_type=license_,
            archive_base_url=artifact_share_base_url,
            ifw_tools_uri=ifw_tools,
            force_version_number_increase=True,
            substitution_list=task.substitutions,
            build_timestamp=job_timestamp,
            dry_run=dry_run,
        )
        log.info(str(installer_task))
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, create_installer, installer_task),
                timeout=60 * 60 * 3  # 3h for one repo build
            )
        except Exception as exc:
            log.exception("Repository build failed!")
            raise PackagingError from exc
        if not dry_run:
            script_dir = os.path.dirname(__file__)
            online_repo_path = os.path.abspath(os.path.join(script_dir, "online_repository"))
            assert os.path.isdir(online_repo_path), f"Not a valid path: {online_repo_path}"
            shutil.move(online_repo_path, task.source_online_repository_path)
            log.info("Repository created at: %s", task.source_online_repository_path)
            done_repositories.append(task.source_online_repository_path)
    return done_repositories


async def update_repositories(
    tasks: List[IFWReleaseTask],
    staging_server: str,
    update_strategy: RepoUpdateStrategy,
    rta: str,
) -> None:
    try:
        for task in tasks:
            await update_repository(staging_server, update_strategy, task, rta)
    except PackagingError as error:
        log.error("Aborting online repository update: %s", str(error))
        raise


async def sync_production(tasks: List[IFWReleaseTask], repo_layout: QtRepositoryLayout, sync_s3: str, sync_ext: str,
                          staging_server: str, staging_server_root: str, license_: str, event_injector: str,
                          export_data: Dict[str, str]) -> None:
    log.info("triggering production sync..")
    # collect production sync jobs
    updated_production_repositories = {}  # type: Dict[str, str]
    for task in tasks:
        key = os.path.join(repo_layout.get_repo_domain(), task.repo_path)
        if key in updated_production_repositories:
            raise PackagingError(f"Duplicate repository path found: {key}")
        updated_production_repositories[key] = os.path.join(repo_layout.get_production_path(), task.repo_path)

    # if _all_ repository updates to production were successful then we can sync to production
    if sync_s3:
        async with EventRegister(f"{license_}: repo sync s3", event_injector, export_data):
            sync_production_repositories_to_s3(staging_server, sync_s3, updated_production_repositories,
                                               staging_server_root, license_)
    if sync_ext:
        async with EventRegister(f"{license_}: repo sync ext", event_injector, export_data):
            await sync_production_repositories_to_ext(staging_server, sync_ext, updated_production_repositories,
                                                      staging_server_root, license_)
    log.info("Production sync trigger done!")


async def handle_update(
    staging_server: str,
    staging_server_root: str,
    license_: str,
    tasks: List[IFWReleaseTask],
    installer_config_base_dir: str,
    artifact_share_base_url: str,
    update_strategy: RepoUpdateStrategy,
    sync_s3: str,
    sync_ext: str,
    rta: str,
    ifw_tools: str,
    build_repositories: bool,
    sync_repositories: bool,
    event_injector: str,
    export_data: Dict[str, str],
    dry_run: Optional[DryRunMode] = None,
) -> None:
    """Build all online repositories, update those to staging area and sync to production."""
    log.info("Starting repository update for %i tasks..", len(tasks))
    if build_repositories:
        # this may take a while depending on how big the repositories are
        async with EventRegister(f"{license_}: repo build", event_injector, export_data):
            await build_online_repositories(
                tasks,
                license_,
                installer_config_base_dir,
                artifact_share_base_url,
                ifw_tools,
                build_repositories,
                dry_run,
            )
    if update_strategy.requires_remote_update():
        async with EventRegister(f"{license_}: repo update", event_injector, export_data):
            await update_repositories(tasks, staging_server, update_strategy, rta)
    if sync_repositories:
        await sync_production(tasks, update_strategy.remote_repo_layout, sync_s3, sync_ext, staging_server,
                              staging_server_root, license_, event_injector, export_data)
    log.info("Repository updates done!")


def string_to_bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    if value.lower() in ('yes', 'true', 'y', '1'):
        return True
    if value.lower() in ('no', 'false', 'n', '0'):
        return False
    raise argparse.ArgumentTypeError(f"Unable to convert to boolean: {value}")


def parse_ext(ext: str) -> Tuple[str, str]:
    parts = ext.split(":")
    if len(parts) != 2:
        raise PackagingError(f"Ext format should be '<login>@<server>:/base/path'. Format was invalid: {ext}")
    if not parts[1].startswith("/"):
        raise PackagingError(f"Ext server path should start with '/'. Format was invalid: {parts[1]}")
    return parts[0], parts[1]


def append_to_task_filters(task_filters: List[str], task_filter: str) -> List[str]:
    return [task_filter + "," + x if x else task_filter for x in task_filters] if task_filters else [task_filter]


def format_task_filters(task_filters: List[str]) -> List[str]:
    return [char.replace('.', ',') for char in task_filters]


def create_offline_remote_dirs(task: IFWReleaseTask, staging_server: str, staging_server_root: str, installer_build_id: str) -> str:
    remote_base_dir = staging_server_root + '/' + task.project_name + '/' + task.version + '/' + 'installers'
    remote_dir = remote_base_dir + '/' + installer_build_id + '/'
    remote_latest_available_dir = remote_base_dir + '/' + 'latest_available' + '/'
    if not remote_path_exists(staging_server, remote_dir):
        create_remote_paths(staging_server, [remote_dir])
    if not remote_path_exists(staging_server, remote_latest_available_dir):
        create_remote_paths(staging_server, [remote_latest_available_dir])
    return remote_dir


def update_remote_latest_available_dir(new_installer: str, remote_upload_path: str, task: IFWReleaseTask, staging_server_root: str, installer_build_id: str) -> None:
    log.info("Update latest available installer directory: %s", remote_upload_path)
    regex = re.compile('.*' + task.version)
    new_installer_base_path = "".join(regex.findall(new_installer))
    name = Path(new_installer_base_path).name

    # update latest_available
    latest_available_path = re.sub(r"\/" + str(installer_build_id) + r"\/", "/latest_available/", remote_upload_path)
    previous_installer_path = latest_available_path + name + '*'
    try:
        cmd_rm = get_remote_login_cmd(staging_server_root) + ['rm', previous_installer_path.split(':')[1]]
        log.info("Running remove cmd: %s", cmd_rm)
        run_cmd(cmd=cmd_rm, timeout=60 * 60)  # 1h
    except Exception:
        log.info("Running cmd failed - this happens only if latest_available is empty")
    cmd_cp = get_remote_login_cmd(staging_server_root) + ['cp', remote_upload_path.split(':')[1] + name + '*', latest_available_path.split(':')[1]]
    log.info("Running copy cmd: %s", cmd_cp)
    run_cmd(cmd=cmd_cp, timeout=60 * 60)  # 1h


def upload_offline_to_remote(installer_path: str, remote_upload_path: str, staging_server: str, task: IFWReleaseTask,
                             installer_build_id: str, enable_oss_snapshots: bool, license_: str) -> None:
    for file in os.listdir(installer_path):
        file_path = Path(file)
        file_ext = file_path.suffix
        if file_ext == ".app":
            continue
        name = str(file_path.with_suffix(""))
        file_name_final = name + "_" + installer_build_id + file_ext
        installer = os.path.join(installer_path, file_name_final)
        os.rename(os.path.join(installer_path, file), installer)
        remote_destination = staging_server + ":" + remote_upload_path
        cmd = ['scp', installer, remote_destination]
        log.info("Uploading offline installer: %s to: %s", installer, remote_destination)
        run_cmd(cmd=cmd, timeout=60 * 60)  # 1h
        update_remote_latest_available_dir(installer, remote_destination, task, staging_server, installer_build_id)
        if enable_oss_snapshots and license_ == "opensource":
            upload_snapshots_to_remote(staging_server, remote_upload_path, task, installer_build_id, file_name_final)


async def sign_offline_installer(installer_path: str, installer_name: str) -> None:
    if platform.system() == "Windows":
        log.info("Sign Windows installer")
        sign_executable(os.path.join(installer_path, installer_name) + '.exe')
    elif platform.system() == "Darwin":
        log.info("Sign macOS .app bundle")
        sign_mac_app(os.path.join(installer_path, installer_name + '.app'), get_pkg_value("SIGNING_IDENTITY"))
        log.info("Create macOS dmg file")
        create_mac_dmg(os.path.join(installer_path, installer_name) + '.app')
        log.info("Notarize macOS installer")
        notarize(path=Path(installer_path, installer_name + '.dmg'))
    else:
        log.info("No signing available for this host platform: %s", platform.system())


async def build_offline_tasks(
    staging_server: str,
    staging_server_root: str,
    tasks: List[IFWReleaseTask],
    license_: str,
    installer_config_base_dir: str,
    artifact_share_base_url: str,
    ifw_tools: str,
    installer_build_id: str,
    update_staging: bool,
    enable_oss_snapshots: bool,
    event_injector: str,
    export_data: Dict[str, str],
    dry_run: Optional[DryRunMode] = None,
) -> None:
    async with EventRegister(f"{license_}: offline", event_injector, export_data):
        await _build_offline_tasks(
            staging_server,
            staging_server_root,
            tasks,
            license_,
            installer_config_base_dir,
            artifact_share_base_url,
            ifw_tools,
            installer_build_id,
            update_staging,
            enable_oss_snapshots,
            dry_run,
        )


async def _build_offline_tasks(
    staging_server: str,
    staging_server_root: str,
    tasks: List[IFWReleaseTask],
    license_: str,
    installer_config_base_dir: str,
    artifact_share_base_url: str,
    ifw_tools: str,
    installer_build_id: str,
    update_staging: bool,
    enable_oss_snapshots: bool,
    dry_run: Optional[DryRunMode] = None,
) -> None:
    log.info("Offline installer task(s): %i", len(tasks))

    assert license_, "The 'license_' must be defined!"
    assert artifact_share_base_url, "The 'artifact_share_base_url' must be defined!"
    assert ifw_tools, "The 'ifw_tools' must be defined!"

    curr_dir = os.path.dirname(__file__)
    installer_output_dir = os.path.abspath(os.path.join(curr_dir, "installer_output"))

    # build installers
    if sys.version_info < (3, 7):
        loop = asyncio.get_event_loop()
    else:
        loop = asyncio.get_running_loop()  # pylint: disable=no-member
    # use same timestamp for all installer tasks
    job_timestamp = strftime("%Y-%m-%d", gmtime())
    for task in tasks:
        log.info("Building offline installer: %s", task.installer_name)
        installer_config_file = os.path.join(installer_config_base_dir, task.config_file)
        if not os.path.isfile(installer_config_file):
            raise PackagingError(f"Invalid 'config_file' path: {installer_config_file}")

        installer_task: QtInstallerTask[Any] = QtInstallerTask(
            configurations_dir=installer_config_base_dir,
            configuration_file=installer_config_file,
            offline_installer=True,
            license_type=license_,
            archive_base_url=artifact_share_base_url,
            ifw_tools_uri=ifw_tools,
            installer_name=task.installer_name,
            force_version_number_increase=True,
            substitution_list=task.substitutions,
            build_timestamp=job_timestamp,
            dry_run=dry_run,
        )
        log.info(str(installer_task))
        try:
            await asyncio.wait_for(
                loop.run_in_executor(None, create_installer, installer_task),
                timeout=60 * 60 * 3  # 3h
            )
        except Exception as exc:
            log.exception("Installer build failed!")
            raise PackagingError from exc

        await sign_offline_installer(installer_output_dir, task.installer_name)
        if update_staging:
            remote_upload_path = create_offline_remote_dirs(task, staging_server, staging_server_root, installer_build_id)
            upload_offline_to_remote(installer_output_dir, remote_upload_path, staging_server, task, installer_build_id, enable_oss_snapshots, license_)


def upload_snapshots_to_remote(staging_server: str, remote_upload_path: str, task: IFWReleaseTask, installer_build_id: str, installer_filename: str) -> None:
    project_name = task.project_name
    version_full = task.version
    version_minor_match = re.match(r"\d+\.\d+", version_full)
    if version_minor_match:
        version_minor = version_minor_match[0]
    else:
        raise PackagingError(f"Could not determine minor version from {version_full}")
    snapshot_path = Path(get_pkg_value("SNAPSHOT_PATH"))
    if snapshot_path.name != project_name:
        snapshot_path = snapshot_path.with_name(project_name)
    snapshot_upload_path = os.path.join(snapshot_path, version_minor, version_full + task.prerelease_version, installer_build_id)
    remote_installer_path = os.path.join(remote_upload_path, installer_filename)
    if platform.system() == "Windows":
        # commands are run in Linux, adjust the upload paths
        snapshot_upload_path = snapshot_upload_path.replace("\\", "/")
        remote_installer_path = remote_installer_path.replace("\\", "/")
    snapshot_srv = get_pkg_value("SNAPSHOT_SERVER")
    login = get_remote_login_cmd(staging_server) + get_remote_login_cmd(snapshot_srv)
    cmd_mkdir = login + ["mkdir", "-p", snapshot_upload_path]
    log.info("Creating offline snapshot directory: %s", cmd_mkdir)
    run_cmd(cmd=cmd_mkdir, timeout=60 * 60)
    args = ["scp", "-r", remote_installer_path] + [snapshot_srv + ":" + snapshot_upload_path + "/"]
    log.info("Uploading offline snapshot: %s", args)
    run_cmd(cmd=get_remote_login_cmd(staging_server) + args, timeout=60 * 60 * 2)


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
        log.info("Export summary file url not present in: %s", config_file)
    except URLError as error:
        log.warning("Unable to read export summary file: %s", str(error))
    except ValueError:
        # it's ok, not mandatory
        pass
    return ret


def main() -> None:
    """Main"""
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

    parser = argparse.ArgumentParser(
        description="Script to update release repositories",
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
              "--sync-s3=<S3 bucket address> ",
        parents=[DryRunMode.get_parser()]  # add parser for --dry-run argument as parent
    )
    parser.add_argument("--ifw-tools", dest="ifw_tools", type=str, default=os.getenv("IFW_TOOLS"),
                        help="Archive which contains the ifw tools")

    parser.add_argument("--staging-server", dest="staging_server", type=str, default=get_pkg_value("STAGING_SERVER_LOGIN"),
                        help="Staging server")
    parser.add_argument("--staging-server-root", dest="staging_server_root", type=str, default=os.getenv("STAGING_SERVER_ROOT"),
                        help="Online repositories root directory")

    parser.add_argument("--config", dest="config", type=str, default=os.getenv("RELEASE_DESCRIPTION_FILE"),
                        help="Path to top level release config file")
    parser.add_argument("--task-filter", dest="task_filters", action='append', default=[],
                        help="Task include filters per section name in the --config file to match with "
                        "the section name, e.g. 'offline', 'repository', ...")
    parser.add_argument("--artifacts-share-url", dest="artifact_share_url", type=str, default=os.getenv("ARTIFACTS_SHARE_URL"),
                        help="Root URL for artifacts")

    parser.add_argument("--license", dest="license_", type=str, choices=["enterprise", "opensource"], default=os.getenv("LICENSE"),
                        help="enterprise/opensource")
    parser.add_argument("--repo-domain", dest="repo_domain", type=str, choices=["qtsdkrepository", "marketplace"],
                        help="qtsdkrepository/marketplace")

    parser.add_argument("--build-repositories", dest="build_repositories", type=string_to_bool, nargs='?', default=False,
                        help="Build online repositories defined by '--config' file on current machine")

    parser.add_argument("--build-offline", dest="build_offline", type=string_to_bool, nargs='?', default=False,
                        help="Build offline installers defined by '--config' file")
    parser.add_argument("--offline-installer-build-id", dest="offline_installer_id", type=str, default=os.getenv('BUILD_NUMBER', timestamp),
                        help="Add unique id for the offline installer")

    parser.add_argument("--update-staging", dest="update_staging", action='store_true', default=bool(os.getenv("DO_UPDATE_STAGING_REPOSITORY", "")),
                        help="Should the staging repository be updated?")
    parser.add_argument("--update-production", dest="update_production", action='store_true', default=bool(os.getenv("DO_UPDATE_PRODUCTION_REPOSITORY", "")),
                        help="Should the production repository be updated?")
    parser.add_argument("--update-source", dest="update_source_type", type=str,
                        choices=[RepoSource.PENDING.value, RepoSource.STAGING.value],
                        default=RepoSource.PENDING.value,
                        help="Which origin to use for the remote updates. E.g. possible to "
                             "update production with content from staging")
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
    parser.add_argument(
        "--disable-path-limit-check",
        dest="require_long_path_support",
        action="store_false",
        default=True
    )
    parser.set_defaults(**defaults)  # these are from provided --config file
    args = parser.parse_args(sys.argv[1:])
    if args.require_long_path_support is True and is_long_path_supported() is False:
        log.error("Path names longer than 260 are not supported by the current environment")
        log.error("To continue, the maximum path limitation must be disabled in Windows registry")
        log.error("Set --disable-path-limit-check to bypass this check")
        raise SystemExit("Long path support is required to build the installer/repository")
    if args.dry_run:
        assert not args.sync_s3, "'--sync-s3' specified with '--dry-run'"
        assert not args.sync_ext, "'--sync-ext' specified with '--dry-run'"
        assert not args.update_staging, "'--update-staging' specified with '--dry-run'"
        assert not args.update_production, "'--update-production' specified with '--dry-run'"
    assert args.config, "'--config' was not given!"
    assert args.staging_server_root, "'--staging-server-root' was not given!"

    if args.license_ == "opensource":
        assert not args.sync_s3, "The '--sync-s3' is not supported for 'opensource' license!"

    # user explicitly disabled rta triggers
    if args.rta in ["0", "disable", "false", "no"]:
        args.rta = None

    # format task string in case full task section string is used
    args.task_filters = format_task_filters(args.task_filters)
    # installer configuration files are relative to the given top level release description file
    installer_config_base_dir = os.path.abspath(os.path.join(os.path.dirname(args.config), os.pardir))
    assert os.path.isdir(installer_config_base_dir), f"Not able to figure out 'configurations/' directory correctly: {installer_config_base_dir}"

    export_data = load_export_summary_data(Path(args.config)) if args.event_injector else {}

    if args.build_offline:
        # get offline tasks
        tasks = parse_config(
            config_file=args.config,
            task_type=TaskType.IFW_TASK_TYPE,
            task_filters=append_to_task_filters(args.task_filters, "offline"),
        )
        asyncio_run(
            build_offline_tasks(
                staging_server=args.staging_server,
                staging_server_root=args.staging_server_root,
                tasks=tasks,  # type: ignore
                license_=args.license_,
                installer_config_base_dir=installer_config_base_dir,
                artifact_share_base_url=args.artifact_share_url,
                ifw_tools=args.ifw_tools,
                installer_build_id=args.offline_installer_id,
                update_staging=args.update_staging,
                enable_oss_snapshots=args.enable_oss_snapshots,
                event_injector=args.event_injector,
                export_data=export_data,
                dry_run=DryRunMode[args.dry_run] if args.dry_run else None,
            )
        )

    else:  # this is either repository build or repository sync build
        # get repository tasks
        tasks = parse_config(
            config_file=args.config,
            task_type=TaskType.IFW_TASK_TYPE,
            task_filters=append_to_task_filters(args.task_filters, "repository"),
        )
        update_strategy = RepoUpdateStrategy.get_strategy(
            staging_server_root=args.staging_server_root,
            license_=args.license_,
            repo_domain=args.repo_domain,
            build_repositories=args.build_repositories,
            remote_repo_update_source=RepoSource(args.update_source_type),
            update_staging=args.update_staging,
            update_production=args.update_production,
        )
        asyncio_run(
            handle_update(
                staging_server=args.staging_server,
                staging_server_root=args.staging_server_root,
                license_=args.license_,
                tasks=tasks,  # type: ignore
                installer_config_base_dir=installer_config_base_dir,
                artifact_share_base_url=args.artifact_share_url,
                update_strategy=update_strategy,
                sync_s3=args.sync_s3,
                sync_ext=args.sync_ext,
                rta=args.rta or "",
                ifw_tools=args.ifw_tools,
                build_repositories=args.build_repositories,
                sync_repositories=args.sync_s3 or args.sync_ext,
                event_injector=args.event_injector,
                export_data=export_data,
                dry_run=DryRunMode[args.dry_run] if args.dry_run else None,
            )
        )


if __name__ == "__main__":
    main()
