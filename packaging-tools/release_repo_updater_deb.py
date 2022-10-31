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
import os
import sys
from asyncio import Semaphore
from configparser import ConfigParser, ExtendedInterpolation
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import List, Optional
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import urlretrieve

import aiofiles
import htmllistparse  # type: ignore
from aiohttp import ClientResponseError, ClientSession, ClientTimeout
from requests.auth import HTTPBasicAuth
from temppathlib import TemporaryDirectory
from typing_extensions import Protocol

from debian_repo_release import (
    AptlyApiClient,
    create_api_arg_parser,
    create_aptly_endpoint_arg_parser,
    create_gpg_arg_parser,
    key_from_env,
)
from logging_util import init_logger
from release_task_reader import DebReleaseTask, TaskType, append_to_task_filters, parse_config

if sys.version_info < (3, 7):
    from asyncio_backport import run as asyncio_run
else:
    from asyncio import run as asyncio_run


log = init_logger(__name__, debug_mode=False)


async def batch_download(urls: List[str], dst: Path, workers: int, timeout: int) -> List[Path]:
    """Download the given URLs concurrently to given destination directory.

    Args:
        urls: List of URLs to download
        dst: The download destination folder
        workers: How many concurrent downloads
        timeout: Total timeout value for the whole batch operation

    Returns:
        A list of local absolute paths of the downloaded files
    """
    # The aiohttp.ClientTimeout 'total' is for the whole session! It needs to be greater
    # than the cumulative asyncio.wait_for calls below. Otherwise the ClientSession context manager
    # finishes before the individual tasks referencing the closed session object now, causes
    # an unhandled exception.
    ses_timeout = ClientTimeout(
        total=60 * 60 * 24, connect=None, sock_connect=None, sock_read=None
    )
    log.info("Batch download items=%s timeout=%s workers=%s", len(urls), timeout, workers)
    results: List[Path] = []
    dst.mkdir(parents=True, exist_ok=True)
    sem = Semaphore(workers)
    try:
        async with ClientSession(timeout=ses_timeout) as session:
            log.info("Starting download tasks..")
            tasks = [
                asyncio.wait_for(download_file(session, url, dst, sem), timeout) for url in urls
            ]
            # collect result as soon they start completing
            for future in asyncio.as_completed(tasks):
                result = await future
                log.debug("Completed: %s", result)
                results.append(result)
    except asyncio.TimeoutError:
        log.error("Maximum time %ss exceeded. Timeout during batch download.", timeout)
        raise
    except Exception as ex:
        log.error("Batch download failed: %s", str(ex))
        raise
    log.info("Completed batch download of %s items into: %s", len(urls), dst)
    return results


async def download_file(
    session: ClientSession, url: str, download_dst: Path, sem: Semaphore
) -> Path:
    """Download a single file asynchronously and write the stream in a file asynchronously.

    It uses aiohttp to enable asynchronous download of the file, i.e. not to block the current
    event loop. Once response data starts arriving it uses aiofiles to write the stream in
    chunks to the destination file. This is also performed asynchronously to not block the
    current event loop. This also makes it possible to not store the whole downloaded file in
    memory first which might cause issues with large files, especially if multiple concurrent
    downloads are performed.

    Args:
        session: The aiohttp session object used to execute the download request
        url: The URL to be downloaded and written into the given file
        download_dst: The filename where to download the file pointed by the URL
        sem: Shared semaphore to achieve limit for concurrent downloads. The download is
             blocked until the semaphore is acquired. Released upon the download has completed.

    Returns:
        An absolute path to the downloaded file.
    """
    dest_file = download_dst / url.split("/")[-1]  # TODO, we should keep the path structure!
    log.info("Download: '%s' into: %s", url, dest_file)
    async with sem:
        try:
            async with session.get(url, raise_for_status=True) as response:
                # write in chunks to avoid allocating big files in memory
                # use async to write files for better I/O for better concurrent operations
                chunk_size = 1024 * 1024 * 1
                async with aiofiles.open(dest_file, "+wb") as _file:
                    async for chunk in response.content.iter_chunked(chunk_size):
                        await _file.write(chunk)
        except ClientResponseError as aio_err:
            log.error("Downloading: '%s' failed: %s", url, str(aio_err))
            raise
        except Exception as ex:
            log.error("Writing: '%s' failed: %s", dest_file, str(ex))
            raise
        log.info("Download completed: %s", url)
        return dest_file


async def search_in_executor(url: str) -> List[str]:
    """A wrapper function to run the htmllistparse.fetch_listing in a separate thread

    Args:
        url: The URL to be listed.

    Returns:
        File listing of the given URL. May contain files and folders.
    """
    log.debug("Crawling: %s", url.rstrip("/").split("/")[-1])
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, htmllistparse.fetch_listing, url, 60 * 10)


async def search_files_from_url(base_url: str, fn_mask: str) -> List[str]:
    """Search the given base URL recursively for files matching the given mask.

    Args:
        base_url: Start searching content starting from this base URL recursively
        fn_mask: A file name mask for the content to be searched

    Returns:
        An URL listing of all files found matching the criteria.
    """
    url_parts = urlparse(base_url)
    scheme_and_domain = url_parts.scheme + "://" + url_parts.netloc
    results: List[str] = []
    search_urls = [base_url]
    while search_urls:
        log.info("Search %s URL(s)", len(search_urls))
        # run concurrently
        coros = [search_in_executor(url) for url in search_urls]
        resp = await asyncio.gather(*coros)
        # parse results
        for cwd, items in resp:
            base = scheme_and_domain + cwd
            search_urls = [base + "/" + f.name for f in items if f.name.endswith("/")]
            files = [
                base + "/" + f.name
                for f in items
                if not f.name.endswith("/") and fnmatch(f.name, fn_mask)
            ]
            # extend is thread safe
            results.extend(files)
    return results


class Transaction(Protocol):
    """Implement a protocol for execute and undo operations. Classes implementing the
    functions defined by this class are considered implementing the Transaction interface."""

    def execute(self) -> None:
        ...

    def undo(self) -> None:
        ...


@dataclass
class CreateRepoCmd:
    """Repository creation command implementing the Transaction protocol.

    This command is used to create a repository.

    Args:
        client: The Aptly API client instance
        repo_name: The name of the repository to be created
        dist: The Debian distribution name for this repository
        component: The component specifier for this repository
    """

    client: AptlyApiClient
    repo_name: str
    dist: str
    component: str

    def execute(self) -> None:
        self.client.create_repo(repo_name=self.repo_name, dist=self.dist, component=self.component)

    def undo(self) -> None:
        self.client.delete_repo(repo_name=self.repo_name, force=False)


@dataclass
class PopulateRepoCmd:
    """Repository population command implementing Transaction protocol.

    This class is used to populate a given repository with content.

    Args:
        client: The Aptly API client instance
        repo_name: The name of the repository to be created
        content_paths: Local paths or URLs to be searched for .(d)deb packages. All found .(d)deb
                       packages are put into the given repository.
        workers: How many concurrent workers to download content. Default: 10
        timeout: How logs the whole operation may last. Default: 1h
    """

    client: AptlyApiClient
    repo_name: str
    content_paths: List[str] = field(default_factory=list)
    workers: int = 10
    timeout: int = 60 * 60

    def execute(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            self._execute(work_dir=tmp_dir.path)

    def _execute(self, work_dir: Path) -> None:
        for content_path in self.content_paths:
            # support local filesystem paths
            source_path = Path(content_path).resolve()
            # if not local filesystem path then we assume an URL
            if not source_path.exists():
                results = asyncio_run(search_files_from_url(str(content_path), fn_mask="*.*deb"))
                asyncio_run(
                    batch_download(
                        urls=results, dst=work_dir, workers=self.workers, timeout=self.timeout
                    )
                )
                source_path = work_dir
            self.client.add_to_repo_from_path(repo_name=self.repo_name, content_path=source_path)

    def undo(self) -> None:
        # aptly db cleanup
        pass


@dataclass
class CreateSnapshotCmd:
    """Snapshot creation command implementing Transaction protocol.

    This command is used to create a snapshot of the repository contents.

    Args:
        client: The Aptly API client instance
        snapshot_name: The name of the snapshot to be created
        repo_name: The name of the repository from which the snapshot is to be created
    """

    client: AptlyApiClient
    snapshot_name: str
    repo_name: str

    def execute(self) -> None:
        self.client.create_snapshot(snapshot_name=self.snapshot_name, repo_name=self.repo_name)

    def undo(self) -> None:
        self.client.delete_snapshot(snapshot_name=self.snapshot_name, force=False)


@dataclass
class PublishSnapshotCmd:
    """Snapshot publish command implementing Transaction protocol.

    This command is used to publish the snapshot i.e. make it visible to users.
    The published repository is also signed.

    Args:
        client: The Aptly API client instance
        snapshot_name: The name of the snapshot to be published
        endpoint_type: 'S3' or 'filesystem'
        endpoint_name: Name of the endpoint configuration in .aptly.conf
        public_repo_name: This will be the public name of the repository
        distribution: The Debian distribution for this repo/snapshot
        sign_gpgkey: The private GPG key to sign the repository
        sign_passphrase: The GPG passphrase for the GPG key
        architectures: List of package architectures contained in this repo/snapshot.
    """

    client: AptlyApiClient
    snapshot_name: str
    endpoint_type: str
    endpoint_name: str
    public_repo_name: str
    distribution: str
    sign_gpgkey: str
    sign_passphrase: str
    architectures: List[str] = field(default_factory=list)

    def execute(self) -> None:
        self.client.publish_snapshot(
            snapshot_name=self.snapshot_name,
            endpoint_type=self.endpoint_type,
            endpoint_name=self.endpoint_name,
            prefix=self.public_repo_name,
            dist=self.distribution,
            architectures=self.architectures,
            sign_gpgkey=self.sign_gpgkey,
            sign_passphrase=self.sign_passphrase,
        )

    def undo(self) -> None:
        self.client.delete_published_snapshot(
            prefix=self.public_repo_name,
            endpoint_type=self.endpoint_type,
            endpoint_name=self.endpoint_name,
            dist=self.distribution,
        )


@dataclass
class TriggerRTACmd:
    """Trigger RTA command implementing Transaction protocol.

    This command is used to trigger RTA for the published repositories.

    Args:
        client: The Aptly API client instance
        rta_server_url: The name of the Release Test Automation server
        rta_keys: Identifiers for RTA what to test
    """

    client: AptlyApiClient
    rta_server_url: Optional[str]
    rta_keys: List[str]

    def execute(self) -> None:
        if not self.rta_server_url:
            return
        for key in self.rta_keys:
            url = self.rta_server_url.rstrip("/") + "/" + key + "/build?token=RTA_JENKINS"
            log.info("Triggering RTA case: %s", url)
            try:
                urlretrieve(url)
            except HTTPError as h_err:
                log.error("Failed to trigger RTA for: '%s'. Reason: %s", url, str(h_err))
                # let it proceed

    def undo(self) -> None:
        # nothing to undo at the moment
        pass


@dataclass
class BatchOperation:
    """Batch operation implementing Transaction protocol.

    This operation can be used to execute multiple commands sequentially.
    If any of the commands should fail then the undo operation will revert the executed
    commands in reverse order.

    Args:
        commands: ordered list of commands to execute
    """

    commands: List[Transaction] = field(default_factory=list)

    def execute(self) -> None:
        completed: List[Transaction] = []
        try:
            for command in self.commands:
                command.execute()
                completed.append(command)
        except Exception as ex:
            log.error("Batch operation failed: %s", str(ex))
            log.error("Undo operations..")
            for command in reversed(completed):
                command.undo()
            raise

    def undo(self) -> None:
        for command in reversed(self.commands):
            command.undo()


@dataclass
class RepoController:
    """RepoController implementing Transaction protocol.

    The RepoController can be used to manage multiple Transactions where each Transaction
    knows the individual commands.

    Every Transaction which is executed via the RepoController is appended into undo stack
    which can be rewound if any of the Transactions should have failed.
    """

    undo_stack: list[Transaction] = field(default_factory=list)

    def execute(self, transaction: Transaction) -> None:
        transaction.execute()
        self.undo_stack.append(transaction)

    def undo(self) -> None:
        if not self.undo_stack:
            return
        transaction = self.undo_stack.pop()
        transaction.undo()


def create_and_publish_repos(
    api: AptlyApiClient,
    tasks: List[DebReleaseTask],
    gpg_key: str,
    gpg_passphrase: str,
    rta: Optional[str],
) -> None:
    """A top level operation to create and publish a one or multiple repositories.

    For each given task a new repository is created. The repository is populated with content
    defined by the task. Finally a signed snapshot is created from the repository and it is
    published to the given endpoint visible to users.

    Args:
        api: The Aptly API client instance
        tasks: Each task contains information for full repo creation and publishing
        gpg_key: The private GPG key to sign the published repository
        gpg_passphrase: The passphrase for the private GPG key
        rta: If given, points to Jenkins API end point to trigger RTA testing
    """
    controller = RepoController()
    for task in tasks:
        controller.execute(
            BatchOperation(
                commands=[
                    # first we create an unique repo
                    CreateRepoCmd(
                        client=api,
                        repo_name=task.repo_path,
                        dist=task.distribution,
                        component=task.component,
                    ),
                    # then populate the repo with content
                    PopulateRepoCmd(
                        client=api, repo_name=task.repo_path, content_paths=task.content_sources
                    ),
                    # create a snapshot of the repo
                    CreateSnapshotCmd(
                        client=api, snapshot_name=task.snapshot_name, repo_name=task.repo_path
                    ),
                    # sign and publish it to the given endpoint
                    PublishSnapshotCmd(
                        client=api,
                        snapshot_name=task.snapshot_name,
                        endpoint_type=task.endpoint_type,
                        endpoint_name=task.endpoint_name,
                        public_repo_name=task.repo_path,
                        distribution=task.distribution,
                        sign_gpgkey=gpg_key,
                        sign_passphrase=gpg_passphrase,
                        architectures=task.architectures,
                    ),
                    TriggerRTACmd(
                        client=api,
                        rta_server_url=rta,
                        rta_keys=task.rta_key_list,
                    ),
                ]
            )
        )


def parse_args() -> argparse.Namespace:
    """Main"""
    args_from_file_parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # Turn off help, so we print all options in response to -h
        add_help=False,
    )
    args_from_file_parser.add_argument(
        "--config",
        dest="config",
        type=str,
        default=os.getenv("RELEASE_DESCRIPTION_FILE"),
        help="Path to top level release config file",
        metavar="FILE",
    )
    args, _ = args_from_file_parser.parse_known_args()
    defaults = {"option": "default"}

    if args.config:
        config = ConfigParser(interpolation=ExtendedInterpolation())
        config.read([args.config])
        # if the --config contains [script.default_args] then those will be used
        if config.has_section("script.default_args"):
            defaults.update(dict(config.items("script.default_args")))

    remote_api = create_api_arg_parser()
    gpg_p = create_gpg_arg_parser()
    endpoint_p = create_aptly_endpoint_arg_parser()

    parser = argparse.ArgumentParser(
        description="Script to create and publish Debian repositories from release content.",
        usage="To create and publish a Debian repository to S3 endpoint: \n\n"
        "release_repo_updater_deb.py "
        "--config=<path to top level config .ini file> "
        "--aptly-api-url=http://foo.bar:8080  # or via 'APTLY_API_URL' env"
        "--aptly-api-user=<user>  # or via 'APTLY_API_USER' env"
        "--aptly-api-pass=<pass>  # or via 'APTLY_API_PASS' env"
        "--gpg-key=<user>  # or via 'DEBIAN_GPG_KEY' env"
        "--gpg-passphrase=<pass>  # or via 'DEBIAN_GPG_PASSPHRASE' env"
        "--endpoint-type=s3  # or 'filesystem'"
        "--endpoint-name=foo  # refer to .aptly.conf on machine hosting the repos"
        "--task-filter=deb,amd64 --task-filter=deb,arm64 "
        "--artifacts-share-url=<http(s)://some.server.com/base/path/for/artifacts> "
        "--license=opensource "
        "--rta=<RTA trigger base URL> ",
        parents=[remote_api, gpg_p, endpoint_p],
    )
    parser.add_argument(
        "--config",
        dest="config",
        type=str,
        default=os.getenv("RELEASE_DESCRIPTION_FILE"),
        help="Path to top level release config file",
    )
    parser.add_argument(
        "--task-filter",
        dest="task_filters",
        action="append",
        default=[],
        help="Task include filters per section name in the --config file to match with "
        "the section name, e.g. 'offline', 'repository', ...",
    )
    parser.add_argument(
        "--artifacts-share-url",
        dest="artifact_share_url",
        type=str,
        default=os.getenv("ARTIFACTS_SHARE_URL"),
        help="Root URL for artifacts",
    )
    parser.add_argument(
        "--license",
        dest="license_",
        type=str,
        choices=["enterprise", "opensource"],
        default=os.getenv("LICENSE"),
        help="enterprise/opensource",
    )
    rta_url = key_from_env("RTA_SERVER_BASE_URL")
    parser.add_argument(
        "--rta",
        dest="rta",
        type=str,
        default=rta_url,
        help="If specified then trigger RTA for tasks found from --config",
    )

    parser.set_defaults(**defaults)  # these are from provided --config file
    args = parser.parse_args(sys.argv[1:])

    assert args.config, "'--config' was not given!"

    # user explicitly disabled rta triggers
    if args.rta in ["0", "disable", "false", "no"]:
        args.rta = None

    return args


def run(args: argparse.Namespace) -> None:
    tasks = parse_config(
        args.config,
        task_type=TaskType.DEB_TASK_TYPE,
        task_filters=append_to_task_filters(args.task_filters, "deb"),
    )
    auth = HTTPBasicAuth(username=args.aptly_api_user, password=args.api_pass)
    client = AptlyApiClient(api_endpoint=args.aptly_api_url, http_auth=auth)
    create_and_publish_repos(
        api=client,
        tasks=tasks,  # type: ignore
        gpg_key=args.gpg_key,
        gpg_passphrase=args.gpg_passphrase,
        rta=args.rta,
    )


def main() -> None:
    args = parse_args()
    run(args)


if __name__ == "__main__":
    main()
