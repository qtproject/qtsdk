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

import os
import sys
import argparse
import asyncio
import time
import datetime
import shutil
from pathlib import Path
from runner import exec_cmd
from typing import List, Dict, Tuple
from logging_util import init_logger
from installer_utils import is_valid_url_path, download_archive, extract_archive
from bldinstallercommon import locate_path

log = init_logger(__name__, debug_mode=False)
session_timestamp = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d--%H:%M:%S')
convert_suffix = "____unified_metadata_update"
backup_suffix = "____split_metadata_backup-"


class IfwRepoUpdateError(Exception):
    pass


async def fetch_repogen(ifw_tools_url: str) -> str:
    assert is_valid_url_path(ifw_tools_url)
    log.info("Preparing ifw tools: %s", ifw_tools_url)
    # fetch the tool first
    currentDir = os.getcwd()
    ifw_tools_dir = os.path.join(currentDir, "ifw_tools")
    if not os.path.isdir(ifw_tools_dir):
        os.makedirs(ifw_tools_dir)
        destFile = download_archive(ifw_tools_url, ifw_tools_dir)
        await extract_archive(destFile, ifw_tools_dir)
    tool_name = "repogen"
    return locate_path(ifw_tools_dir, [tool_name])


def check_repos_which_can_be_updated(repositories_to_migrate: List[str]) -> Tuple[Dict[str, str], Dict[str, str]]:
    log.info("Analysing repositories..")
    existing_pending_repos = {}  # type: Dict[str, str]
    updatable_repos = {}  # type: Dict[str, str]
    for repo in repositories_to_migrate:
        if repo.endswith(convert_suffix):
            log.info(f"Skipping '{repo}' as it already is the pending repository")
            continue
        if backup_suffix in repo:
            log.info(f"Skipping backup repo: {repo}")
            continue
        migrated_repo = repo + convert_suffix
        if os.path.exists(migrated_repo):
            log.warning(f"There already exists pending repository '{migrated_repo}' for the source repo: {repo}")
            existing_pending_repos[repo] = migrated_repo
        else:
            updatable_repos[repo] = migrated_repo
    return (updatable_repos, existing_pending_repos)


async def create_converted_repositories(repogen: str, repositories_to_migrate: List[str], dry_run=False) -> Tuple[Dict[str, str], Dict[str, str]]:
    # first check that pending repository does not already exist per given repository
    log.info(f"Starting to create new converted repositories: {len(repositories_to_migrate)}")
    updatable_repos, existing_pending_repos = check_repos_which_can_be_updated(repositories_to_migrate)
    if existing_pending_repos:
        log.warning("There are already existing pending repositories which should be completed first:")
        for repo in existing_pending_repos:
            log.warning(f"  {repo}")
        raise IfwRepoUpdateError("Repositories found in pending state, complete those first!")

    # convert all repositories to combined metadata version
    successful_conversions = {}  # type: Dict[str, str]
    failed_conversions = {}  # type: Dict[str, str]
    for repo in updatable_repos:
        repo_output_path = repo + convert_suffix  # the "pending" repository
        cmd = [repogen, "--repository", repo, "--unite-metadata", repo_output_path]
        if dry_run:
            cmd.insert(0, "echo")
        try:
            # perform the update
            exec_cmd(cmd, timeout=60 * 15)
            successful_conversions[repo] = repo_output_path
        except Exception as e:
            log.error(f"Failed to update metadata for repository: {repo} - reason: {str(e)}")
            failed_conversions[repo] = repo_output_path

    return (successful_conversions, failed_conversions)


def swap_repositories(repositories_to_swap: Dict[str, str]) -> Tuple[Dict[str, Tuple[str, str, str]], Dict[str, Tuple[str, str, str]]]:
    log.info(f"Starting to swap converted repositories with destination directories: {len(repositories_to_swap)}")
    errors = []  # type: List[Tuple[str, str]]
    for orig_repo, converted_repo in repositories_to_swap.items():
        backup_repo_name = orig_repo + backup_suffix + session_timestamp
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
            log.error(f"  [{orig_repo}]: {msg}")
        raise IfwRepoUpdateError("Failed to swap repositories!")

    operations_ok = {}  # type: Dict[str, Tuple[str, str, str]]
    operations_nok = {}  # type: Dict[str, Tuple[str, str, str]]
    for orig_repo, converted_repo in repositories_to_swap.items():
        log.info("-> swapping: %s", orig_repo)
        backup_repo_name = orig_repo + backup_suffix + session_timestamp  # unique backup dir name
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
        except Exception as e:
            log.error("%s", str(e))
            operations_nok[orig_repo] = (converted_repo, backup_repo_name, str(e))
    return (operations_ok, operations_nok)


def scan_repositories(search_path: str) -> Tuple[List[str], List[str], List[str], List[str]]:
    assert os.path.isdir(search_path), "Not a valid directory: {0}".format(args.search_path)
    log.info(f"Scan repository status from: {search_path}")

    def check_unified_meta_exists(path: str) -> bool:
        return any(Path(path).glob("*_meta.7z"))

    repos = [path.resolve().parent for path in Path(search_path).rglob('Updates.xml')]
    done_repos = []  # type: List[str]
    pending_repos = []  # type: List[str]
    unconverted_repos = []  # type: List[str]
    broken_repos = []  # type: List[str]
    for repo in repos:
        if backup_suffix in repo.as_posix():
            log.info(f"Skipping backup repo: {repo.as_posix()}")
            continue
        elif repo.as_posix().endswith(convert_suffix):
            if not check_unified_meta_exists(repo):
                # this is broken pending repo
                log.error(f"Pending repository was missing '_meta.7z'")
                broken_repos.append(repo.as_posix())
                continue
            # expected destination repo
            expected_destination_repo = Path(repo.as_posix().rstrip(convert_suffix))
            if not expected_destination_repo.exists():
                # this is broken pending repo
                log.error(f"Pending repository '{repo.as_posix()}' was missing matching destination directory: {expected_destination_repo.as_posix()}")
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
    loop = asyncio.get_event_loop()
    repogen = loop.run_until_complete(fetch_repogen(ifw_tools_url))
    log.info(f"Using repogen from: {repogen}")
    done_repos, pending_repos, unconverted_repos, broken_repos = scan_repositories(search_path)
    successful_conversions, failed_conversions = loop.run_until_complete(create_converted_repositories(repogen, unconverted_repos))
    operations_ok, operations_nok = swap_repositories(successful_conversions)
    for orig_repo, items in operations_ok.items():
        converted_repo, backup_repo_name, _msg = items
        log.info(f"Converted repo: {orig_repo}")
        log.info(f"  original backup: {backup_repo_name}")
    if failed_conversions:
        log.error("Some of the conversions failed -> aborting! Original repo(s) are in place. Cleanup tmp converted repo dirs!:")
        for repo, expected_output_repo in failed_conversions.items():
            log.error(f"  '{repo}' -> '{expected_output_repo}'")
    for orig_repo, items in operations_nok.items():
        converted_repo, backup_repo_name, _msg = items
        log.error(f"Failed swaps: {orig_repo}")
        log.warning(f"  original backup: {backup_repo_name}")


def revert_repos(search_path: str, ifw_tools_url: str, time_stamp: str, dry_run: bool) -> None:
    loop = asyncio.get_event_loop()
    repogen = loop.run_until_complete(fetch_repogen(ifw_tools_url))
    log.info(f"Using repogen from: {repogen}")
    converted_repos, pending_repos, unconverted_repos, broken_repos = scan_repositories(search_path)

    revert_actions = {}
    for converted_repo in converted_repos():
        expected_backup_repo = converted_repo + "____split_metadata_backup-" + time_stamp
        if not os.path.isdir(expected_backup_repo):
            log.warning(f"Can not revert repository as original backup repo does not exist: {expected_backup_repo}")
            continue
        revert_actions[converted_repo] = expected_backup_repo

    for converted, backup in revert_actions:
        reverted_backup_repo_name = converted + "____REVERTED"
        log.info(f"Reverting: '{backup}' -> '{converted}'")
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
        log.info(f"{repo}")
    log.info("")
    log.info("Pending repositories containing combined metadata updates:")
    for repo in sorted(pending_repos):
        log.info(f"{repo}")
    log.info("")
    log.info("Repositories that do not contain combined metadata (needs update):")
    for repo in sorted(unconverted_repos):
        log.info(f"{repo}")
    log.info("")
    log.info("Broken repositories:")
    for repo in sorted(broken_repos):
        log.error(f"{repo}")


if __name__ == "__main__":
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
        convert_repos(args.search_path, args.ifw_tools_url, args.revert_timestamp, args.dry_run)
    else:
        log.error(f"Invalid command given: {args.command}")
