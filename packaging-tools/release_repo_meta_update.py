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

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from time import time
from typing import Dict, List, Tuple

from bldinstallercommon import locate_path
from installer_utils import download_archive, extract_archive, is_valid_url_path
from logging_util import init_logger
from runner import run_cmd

if sys.version_info < (3, 7):
    import asyncio_backport as asyncio
else:
    import asyncio

log = init_logger(__name__, debug_mode=False)
session_timestamp = datetime.fromtimestamp(time()).strftime('%Y-%m-%d--%H:%M:%S')
CONVERT_SUFFIX = "____unified_metadata_update"
BACKUP_SUFFIX = "____split_metadata_backup-"


class IfwRepoUpdateError(Exception):
    pass


async def fetch_repogen(ifw_tools_url: str) -> str:
    assert is_valid_url_path(ifw_tools_url)
    log.info("Preparing ifw tools: %s", ifw_tools_url)
    # fetch the tool first
    current_dir = os.getcwd()
    ifw_tools_dir = os.path.join(current_dir, "ifw_tools")
    if not os.path.isdir(ifw_tools_dir):
        os.makedirs(ifw_tools_dir)
        dest_file = download_archive(ifw_tools_url, ifw_tools_dir)
        await extract_archive(dest_file, ifw_tools_dir)
    tool_name = "repogen"
    return locate_path(ifw_tools_dir, [tool_name])


def check_repos_which_can_be_updated(repositories_to_migrate: List[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    log.info("Analysing repositories..")
    existing_pending_repos = {}  # type: Dict[str, str]
    updatable_repos = {}  # type: Dict[str, str]
    for repo in repositories_to_migrate:
        if repo.endswith(CONVERT_SUFFIX):
            log.info("Skipping '%s' as it already is the pending repository", repo)
            continue
        if BACKUP_SUFFIX in repo:
            log.info("Skipping backup repo: %s", repo)
            continue
        migrated_repo = repo + CONVERT_SUFFIX
        if os.path.exists(migrated_repo):
            log.warning("There already exists pending repository '%s' for the source repo: %s", migrated_repo, repo)
            existing_pending_repos[repo] = migrated_repo
        else:
            updatable_repos[repo] = migrated_repo
    return (updatable_repos, existing_pending_repos)


async def create_converted_repositories(repogen: str, repositories_to_migrate: List[str], dry_run: bool = False) -> Tuple[Dict[str, str], Dict[str, str]]:
    # first check that pending repository does not already exist per given repository
    log.info("Starting to create new converted repositories: %s", len(repositories_to_migrate))
    updatable_repos, existing_pending_repos = check_repos_which_can_be_updated(repositories_to_migrate)
    if existing_pending_repos:
        log.warning("There are already existing pending repositories which should be completed first:")
        for repo in existing_pending_repos:
            log.warning("  %s", repo)
        raise IfwRepoUpdateError("Repositories found in pending state, complete those first!")

    # convert all repositories to combined metadata version
    successful_conversions = {}  # type: Dict[str, str]
    failed_conversions = {}  # type: Dict[str, str]
    for repo in updatable_repos:
        repo_output_path = repo + CONVERT_SUFFIX  # the "pending" repository
        cmd = [repogen, "--repository", repo, "--unite-metadata", repo_output_path]
        if dry_run:
            cmd.insert(0, "echo")
        try:
            # perform the update
            run_cmd(cmd=cmd, timeout=60 * 15)
            successful_conversions[repo] = repo_output_path
        except Exception as error:
            log.error("Failed to update metadata for repository: %s - reason: %s", repo, str(error))
            failed_conversions[repo] = repo_output_path

    return (successful_conversions, failed_conversions)


def swap_repositories(repositories_to_swap: Dict[str, str]) -> Tuple[Dict[str, Tuple[str, str, str]], Dict[str, Tuple[str, str, str]]]:
    log.info("Starting to swap converted repositories with destination directories: %s", len(repositories_to_swap))
    errors = []  # type: List[Tuple[str, str]]
    for orig_repo, converted_repo in repositories_to_swap.items():
        backup_repo_name = orig_repo + BACKUP_SUFFIX + session_timestamp
        if os.path.exists(backup_repo_name):
            # this really should not happen as backup dir name contains timestamp, but do check anyways
            errors.append((orig_repo, f"Destination backup directory already exists: {backup_repo_name}"))
        if not os.path.exists(orig_repo):
            errors.append((orig_repo, f"Source repository did not exist: {orig_repo}"))
        if not os.path.exists(converted_repo):
            errors.append((orig_repo, f"Converted repository did not exist: {converted_repo}"))

    if errors:
        log.error("Unable to proceed to swap repositories due to following found issues:")
        for orig_repo, msg in errors:
            log.error("  [%s]: %s", orig_repo, msg)
        raise IfwRepoUpdateError("Failed to swap repositories!")

    operations_ok = {}  # type: Dict[str, Tuple[str, str, str]]
    operations_nok = {}  # type: Dict[str, Tuple[str, str, str]]
    for orig_repo, converted_repo in repositories_to_swap.items():
        log.info("-> swapping: %s", orig_repo)
        backup_repo_name = orig_repo + BACKUP_SUFFIX + session_timestamp  # unique backup dir name
        try:
            # We want only unified metadata .7z and updated Updates.xml from the top level
            # and we want to ensure the data portion stays the same, so:
            # Remove all subdirs from converted repo
            for item in os.listdir(converted_repo):
                if os.path.isdir(os.path.join(converted_repo, item)):
                    shutil.rmtree(os.path.join(converted_repo, item))
            # Copy subdirs & content from orig repo to converted repo i.e. data portion
            for item in os.listdir(orig_repo):
                if os.path.isdir(os.path.join(orig_repo, item)):
                    shutil.copytree(os.path.join(orig_repo, item), os.path.join(converted_repo, item))

            # rename original repo as backup
            os.rename(orig_repo, backup_repo_name)
            # rename converted repo as the existing one
            os.rename(converted_repo, orig_repo)
            operations_ok[orig_repo] = (converted_repo, backup_repo_name, "")
        except Exception as error:
            log.error("%s", str(error))
            operations_nok[orig_repo] = (converted_repo, backup_repo_name, str(error))
    return (operations_ok, operations_nok)


def scan_repositories(search_path: str) -> Tuple[List[str], List[str], List[str], List[str]]:
    assert os.path.isdir(search_path), f"Not a valid directory: {search_path}"
    log.info("Scan repository status from: %s", search_path)

    def check_unified_meta_exists(path: Path) -> bool:
        return any(Path(path).glob("*_meta.7z"))

    repos = [path.resolve().parent for path in Path(search_path).rglob('Updates.xml')]
    done_repos = []  # type: List[str]
    pending_repos = []  # type: List[str]
    unconverted_repos = []  # type: List[str]
    broken_repos = []  # type: List[str]
    for repo in repos:
        if BACKUP_SUFFIX in repo.as_posix():
            log.info("Skipping backup repo: %s", repo.as_posix())
            continue
        if repo.as_posix().endswith(CONVERT_SUFFIX):
            if not check_unified_meta_exists(repo):
                # this is broken pending repo
                log.error("Pending repository was missing '_meta.7z'")
                broken_repos.append(repo.as_posix())
                continue
            # expected destination repo
            expected_destination_repo = Path(repo.as_posix().rstrip(CONVERT_SUFFIX))
            if not expected_destination_repo.exists():
                # this is broken pending repo
                log.error("Pending repository '%s' was missing matching destination directory: %s", repo.as_posix(), expected_destination_repo.as_posix())
                broken_repos.append(repo.as_posix())
                continue
            pending_repos.append(repo.as_posix())
        else:
            if check_unified_meta_exists(repo):
                done_repos.append(repo.as_posix())
            else:
                unconverted_repos.append(repo.as_posix())

    return (done_repos, pending_repos, unconverted_repos, broken_repos)


def convert_repos(search_path: str, ifw_tools_url: str) -> None:
    repogen = asyncio.run(fetch_repogen(ifw_tools_url))
    log.info("Using repogen from: %s", repogen)
    to_convert = scan_repositories(search_path)[2]
    converted_repos, failed_repos = asyncio.run(create_converted_repositories(repogen, to_convert))
    operations_ok, operations_nok = swap_repositories(converted_repos)
    for orig_repo, items in operations_ok.items():
        backup_repo_name = items[1]
        log.info("Converted repo: %s", orig_repo)
        log.info("  original backup: %s", backup_repo_name)
    if failed_repos:
        log.error("Some of the conversions failed -> aborting! Original repo(s) are in place. Cleanup tmp converted repo dirs!:")
        for repo, expected_output_repo in failed_repos.items():
            log.error("  '%s' -> '%s'", repo, expected_output_repo)
    for orig_repo, items in operations_nok.items():
        backup_repo_name = items[1]
        log.error("Failed swaps: %s", orig_repo)
        log.warning("  original backup: %s", backup_repo_name)


def revert_repos(search_path: str, ifw_tools_url: str, time_stamp: str, dry_run: bool) -> None:
    repogen = asyncio.run(fetch_repogen(ifw_tools_url))
    log.info("Using repogen from: %s", repogen)
    converted_repos = scan_repositories(search_path)[0]

    revert_actions: Dict[str, str] = {}
    for converted_repo in converted_repos:
        expected_backup_repo = converted_repo + "____split_metadata_backup-" + time_stamp
        if not os.path.isdir(expected_backup_repo):
            log.warning("Can not revert repository as original backup repo does not exist: %s", expected_backup_repo)
            continue
        revert_actions[converted_repo] = expected_backup_repo

    for converted, backup in revert_actions.items():
        reverted_backup_repo_name = converted + "____REVERTED"
        log.info("Reverting: '%s' -> '%s'", backup, converted)
        if dry_run:
            continue
        try:
            os.rename(converted, reverted_backup_repo_name)
            os.rename(backup, converted)
        except Exception:
            log.error("Failed to revert: '{backup}' -> '{converted}'")


def scan_repos(search_path: str) -> None:
    done_repos, pending_repos, unconverted_repos, broken_repos = scan_repositories(search_path)
    log.info("")
    log.info("--- Scan results ---")
    log.info("")
    log.info("Repositories already containing combined metadata:")
    for repo in sorted(done_repos):
        log.info("%s", repo)
    log.info("")
    log.info("Pending repositories containing combined metadata updates:")
    for repo in sorted(pending_repos):
        log.info("%s", repo)
    log.info("")
    log.info("Repositories that do not contain combined metadata (needs update):")
    for repo in sorted(unconverted_repos):
        log.info("%s", repo)
    log.info("")
    log.info("Broken repositories:")
    for repo in sorted(broken_repos):
        log.error("%s", repo)


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(prog="Script to update split metadata to unified metadata in online repositories.")
    parser.add_argument("--search-path", dest="search_path", type=str, required=True, help="Path to scan for online repositories")
    parser.add_argument("--ifw-tools", dest="ifw_tools_url", type=str, required=True, help="Archive containing repogen(.exe)")
    parser.add_argument("--command", dest="command", type=str, choices=["scan", "convert", "revert"], required=True, help="")
    parser.add_argument("--revert-timestamp", dest="revert_timestamp", type=str, default="", help="Which backup to use")
    parser.add_argument("--dry-run", dest="dry_run", action='store_true')

    args = parser.parse_args(sys.argv[1:])
    if args.command == "scan":
        scan_repos(args.search_path)
    elif args.command == "convert":
        convert_repos(args.search_path, args.ifw_tools_url)
    elif args.command == "revert":
        revert_repos(args.search_path, args.ifw_tools_url, args.revert_timestamp, args.dry_run)
    else:
        log.error("Invalid command given: %s", args.command)


if __name__ == "__main__":
    main()
