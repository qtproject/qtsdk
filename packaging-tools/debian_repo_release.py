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

import getpass
import os
import shlex
import sys
from argparse import ArgumentParser, Namespace
from datetime import datetime
from pathlib import Path
from time import time
from typing import Dict, List, NewType, Optional, Tuple

import validators  # type: ignore
from aptly_api import Client as AptlyClient  # type: ignore
from aptly_api.base import AptlyAPIException  # type: ignore
from aptly_api.parts.publish import PublishEndpoint  # type: ignore
from aptly_api.parts.repos import Repo  # type: ignore
from aptly_api.parts.snapshots import Snapshot  # type: ignore
from requests.auth import AuthBase

from installer_utils import PackagingError
from logging_util import init_logger
from read_remote_config import get_pkg_value

log = init_logger(__name__, debug_mode=False)

DebRepo = NewType("DebRepo", Repo)  # type: ignore
DebSnapshot = NewType("DebSnapshot", Snapshot)  # type: ignore
DebPublishedSnapshot = NewType("DebPublishedSnapshot", PublishEndpoint)  # type: ignore


class AptlyApiClient:
    def __init__(self, api_endpoint: str, http_auth: Optional[AuthBase]) -> None:
        if not validators.url(api_endpoint):
            raise PackagingError(f"Not a valid URL: {api_endpoint}")
        self.api_endpoint = api_endpoint
        self.client = AptlyClient(self.api_endpoint, http_auth=http_auth, timeout=60 * 60)

    @staticmethod
    def packages_from_path(path: Path) -> List[Optional[Path]]:
        """Return all Debian package(s) from the given path.

        If the path points to a file with '.deb' extension then return it.

        If the path points to a valid directory then scan it recursively
        and return all found files with '.deb' extension.

        Args:
            path: The path to search for.

        Returns:
            A list of found '.deb' files.

        Raises:
            PackagingError: if invalid path is given.

        """
        if not path.exists():
            raise PackagingError(f"Can't search for .deb packages from non-existent path: {path}")
        if path.is_file() and path.suffix == ".deb":
            return [path]
        return list(path.rglob("*.deb"))

    @staticmethod
    def endpoint_types() -> Tuple[str, ...]:
        """Get supported endpoint types for Aptly

        Returns:
            A tuple listing the supported endpoint types.
        """
        return ("filesystem", "s3")

    @staticmethod
    def publish_prefix(*, endpoint_type: str, endpoint_name: str, prefix: str) -> str:
        """Format a suitable publish prefix for an Aptly endpoint.

        Aptly publishes the snapshots/repositories using a prefix with the following format:
            <endpoint_type>:<endpoint_name>:<prefix>
            For example: s3:s3_endpoint:my_repository_name

        Format a suitable publish prefix from the given arguments.

        Args:
            endpoint_type: The endpoint type. See 'endpoint_types()'
            endpoint_name: The name of the endpoint.
            prefix: Usually the name of the repository containing the snapshot.

        Returns:
            The formatted publish prefix

        Raises:
            PackagingError: If using unsupported endpoint type of empty endpoint name.
        """
        if endpoint_type not in AptlyApiClient.endpoint_types():
            raise PackagingError(f"Unsupported endpoint type: {endpoint_type}")
        if not endpoint_name:
            raise PackagingError("Endpoint name is undefined!")
        if not prefix:
            raise PackagingError("Prefix is undefined!")
        return f"{endpoint_type}:{endpoint_name}:{prefix}"

    def list_repos(self) -> Dict[str, DebRepo]:
        """List all available repositories.

        Returns:
            Dictionary containing all the available repositories.

        Raises:
            PackagingError: If the connection to Aptly repo manager failed.
        """
        try:
            log.debug("List repositories")
            return {r.name: r for r in self.client.repos.list()}
        except AptlyAPIException as api_err:
            log.exception("Failed to list repositories. %s", str(api_err))
            raise PackagingError from api_err

    def create_repo(self, *, repo_name: str, dist: str, component: str) -> None:
        """Create a new repository for Debian packages.

        Args:
            repo_name: Unique name for the repository
            dist: Debian repository distribution name
            component: Debian repository component name

        Raises:
            PackagingError: PackagingError if the repository could not be created.
        """
        try:
            log.info("Creating repo: '%s', dist=%s, component=%s", repo_name, dist, component)
            self.client.repos.create(
                reponame=repo_name, default_distribution=dist, default_component=component
            )
            log.info("Repo: '%s' created successfully.", repo_name)
        except AptlyAPIException as api_err:
            log.exception("Failed to create repo: '%s'. %s", repo_name, str(api_err))
            raise PackagingError from api_err

    def delete_repo(self, *, repo_name: str, force: bool = False) -> None:
        """Delete the given repository.

        Args:
            repo_name: The name of the repository to be deleted.
            force: Force remove the repository. Defaults to False.

        Raises:
            PackagingError: If the repository could not be deleted.
        """
        try:
            log.warning("Deleting repo: %s", repo_name)
            self.client.repos.delete(repo_name, force=force)
            log.warning("Repository deleted: %s", repo_name)
        except AptlyAPIException as api_err:
            log.exception("Failed to delete repo: '%s'. %s", repo_name, str(api_err))
            raise PackagingError from api_err

    def add_to_repo_from_path(self, *, repo_name: str, content_path: Path) -> None:
        """Add Debian packages to given repository from the given path.

        Args:
            repo_name: Add .deb packages into this existing repository.
            content_path: Add .deb package(s) from this path. Can be a path
                                 pointing to a single file or a directory that is
                                 scanned recursively.

        Raises:
            PackagingError: If adding .deb files failed to given repository.
            PackagingError: If cleaning of temporary items failed.
        """
        log.info("Adding packages to repo '%s' from: %s", repo_name, str(content_path))
        packages = self.packages_from_path(content_path)

        timestamp = datetime.fromtimestamp(time()).strftime("%Y-%m-%d--%H_%M_%S")
        upload_folder = repo_name + "__" + getpass.getuser() + "__" + timestamp
        log.info("Uploading %s packages into: %s", len(packages), upload_folder)

        try:
            # upload package(s) first into temp folder
            for idx, pkg in enumerate(packages):
                log.info("Uploading: %s/%s: %s", idx, len(packages), str(pkg))
                self.client.files.upload(upload_folder, str(pkg))

            # then add the package(s) to the repo from the temp folder
            log.info("Add files from '%s' into repo: %s", upload_folder, repo_name)
            self.client.repos.add_uploaded_file(repo_name, upload_folder)
        except AptlyAPIException as api_err:
            log.exception("Failed to upload file(s) to: '%s'. %s", upload_folder, str(api_err))
            raise PackagingError from api_err
        except Exception as ex:
            log.error("Repo population failed: %s", str(ex))
            log.exception(ex)
            raise PackagingError from ex
        finally:
            try:
                # finally remove the temp folder
                log.info("Remove tmp upload folder: %s", upload_folder)
                self.client.files.delete(upload_folder)
            except AptlyAPIException as delete_err:
                log.exception("Failed cleaning tmp folder: '%s'. %s", upload_folder, str(delete_err))
                raise PackagingError from delete_err
        log.info("File(s) uploaded successfully into: %s", upload_folder)

    def create_snapshot(self, *, snapshot_name: str, repo_name: str) -> None:
        """Create an Aptly snapshot of the contents inside the given repository.

        The snapshot is an immutable collection of packages that can be signed.
        The snapshot can then be published in later step to become visible to users.

        Args:
            snapshot_name: The name for the snapshot to be created.
            repo_name: The name of the repository from which to create the snapshot.

        Raises:
            PackagingError: If the snapshot creation failed.
        """
        try:
            log.info("Creating snapshot '%s' from: '%s'", snapshot_name, repo_name)
            self.client.snapshots.create_from_repo(
                reponame=repo_name, snapshotname=snapshot_name, description=""
            )
            log.info("Snapshot '%s' from: '%s' created successfully.", snapshot_name, repo_name)
        except AptlyAPIException as api_err:
            log.exception("Failed to create snapshot '%s' from: '%s'. %s", snapshot_name, repo_name, str(api_err))
            raise PackagingError from api_err

    def list_snapshots(self) -> Dict[str, DebSnapshot]:
        """List all available snapshots.

        Returns:
            Dictionary containing all the available snapshots.

        Raises:
            PackagingError: If the connection to Aptly repo manager failed.
        """
        try:
            log.debug("List snapshots")
            return {r.name: r for r in self.client.snapshots.list()}
        except AptlyAPIException as api_err:
            log.exception("Failed to list snapshots. %s", str(api_err))
            raise PackagingError from api_err

    def delete_snapshot(self, *, snapshot_name: str, force: bool = False) -> None:
        """Delete the given snapshot.

        Args:
            snapshot_name: The snapshot to be deleted.
            force: Force the removal.

        Raises:
            PackagingError: If the snapshot deletion fails for any reason.
        """
        try:
            log.warning("Deleting snapshot: %s", snapshot_name)
            self.client.snapshots.delete(snapshotname=snapshot_name, force=force)
            log.warning("Snapshot '%s' deleted successfully.", snapshot_name)
        except AptlyAPIException as api_err:
            log.exception("Failed to delete snapshot: '%s'. %s", snapshot_name, str(api_err))
            raise PackagingError from api_err

    def publish_snapshot(
        self,
        *,
        snapshot_name: str,
        endpoint_type: str,
        endpoint_name: str,
        prefix: Optional[str],
        dist: str,
        architectures: List[str],
        sign_gpgkey: Optional[str],
        sign_passphrase: Optional[str],
    ) -> None:
        """Publish the given snapshot to specified endpoint.

        The snapshots are not visible to users until those are published.
        The snapshots are published to given endpoint which specifies the distribution
        system and repository name the end user can access.

        The snapshots to be published are usually also signed with gpg.

        Args:
            snapshot_name: The name of the snapshot to be published.
            endpoint_type: The endpoint type. See 'endpoint_types()'.
            endpoint_name: The endpoint name, refers to endpoint configuration in '.aptly.conf'
            prefix: The endpoint prefix, usually the repository name. Visible to users.
                    The value '.' can be used to publish into root though not recommended!
            dist: The Debian distribution intended for this snapshot.
            architectures: The Debian architecture(s) intended for this snapshot.
            sign_gpgkey: The GPG key
            sign_passphrase: The GPG passphrase

        Raises:
            PackagingError: If the snapshot publishing failed for any reason.
        """
        if not prefix:
            log.warning("No prefix given for publish. Using endpoint root. Not recommended!")
            prefix = "."
        publish_prefix = AptlyApiClient.publish_prefix(
            endpoint_type=endpoint_type, endpoint_name=endpoint_name, prefix=prefix
        )
        sign_skip = False
        sign_batch = True
        if not sign_gpgkey or sign_passphrase:
            log.warning("Publishing snapshot '%s' without signing it!", snapshot_name)
            sign_skip = True
            sign_batch = False
        try:
            log.info("Publish snapshot '%s' into: %s", snapshot_name, publish_prefix)
            self.client.publish.publish(
                source_kind="snapshot",
                sources=[{"Name": snapshot_name}],
                architectures=architectures,
                prefix=publish_prefix,
                distribution=dist,
                sign_skip=sign_skip,
                sign_batch=sign_batch,
                sign_gpgkey=sign_gpgkey,
                sign_passphrase=sign_passphrase,
            )
            public_url = self.api_endpoint.rstrip("/") + "/" + publish_prefix
            log.info("Snapshot '%s' published successfully: %s", snapshot_name, public_url)
        except AptlyAPIException as api_err:
            log.exception("Failed to publish '%s' into: '%s'. %s", snapshot_name, publish_prefix, str(api_err))
            raise PackagingError from api_err

    def list_published_snapshots(self) -> Dict[str, DebPublishedSnapshot]:
        """List all published snapshots.

        Returns:
            Dictionary containing all the published snapshots.

        Raises:
            PackagingError: If the connection to Aptly repo manager failed.
        """
        try:
            log.debug("List snapshots")
            return {r.sources[0]["Name"]: r for r in self.client.publish.list()}
        except AptlyAPIException as api_err:
            log.exception("Failed to list snapshots. %s", str(api_err))
            raise PackagingError from api_err

    def delete_published_snapshot(
        self,
        *,
        prefix: str,
        endpoint_type: str,
        endpoint_name: str,
        dist: str,
        force: bool = False,
    ) -> None:
        """Delete the given published snapshot.

        Args:
            prefix: The snapshot prefix.
            endpoint_type: The endpoint type. See 'endpoint_types()'.
            endpoint_name: The endpoint name, refers to endpoint configuration in '.aptly.conf'
            dist: The snapshot distribution.
            force: Force the removal.

        Raises:
            PackagingError: If the snapshot deletion fails for any reason.
        """
        publish_prefix = AptlyApiClient.publish_prefix(
            endpoint_type=endpoint_type, endpoint_name=endpoint_name, prefix=prefix
        )
        try:
            log.warning("Deleting published snapshot: prefix='%s' dist='%s'", publish_prefix, dist)
            self.client.publish.drop(prefix=publish_prefix, distribution=dist, force_delete=force)
            log.warning("Published snapshot deleted successfully: prefix='%s' dist='%s'", publish_prefix, dist)
        except AptlyAPIException as api_err:
            log.exception("Failed to delete: prefix='%s' dist='%s'. %s", publish_prefix, dist, str(api_err))
            raise PackagingError from api_err


def parse_architectures(value: str) -> List[str]:
    return shlex.split(value.strip('",').replace(",", " "))


def key_from_env(key: str) -> Optional[str]:
    """Attempt to locate the value for the given key from local and remote env.

    If the key is not found from local env then attempt to read it from the remove
    env config.

    Args:
        key: The key to look for from local and remote env.

    Returns:
        The matching value. If key exists in local env then it's preferred over the remote one.
    """
    value = os.getenv(key)
    log.debug("Environment variable '%s' value from local env: %s", key, value)
    if value is None:
        try:
            value = get_pkg_value(key)
        except Exception:
            pass
        log.debug("Environment variable '%s' value from remote env: %s", key, value)
    return value


def create_api_arg_parser() -> ArgumentParser:
    # common options for interfacing Aptly Rest API
    aptly_api = ArgumentParser(add_help=False)
    aptly_api_url = key_from_env("APTLY_API_URL")
    aptly_api.add_argument(
        "--aptly-api-url",
        dest="aptly_api_url",
        required=not bool(aptly_api_url),
        default=aptly_api_url,
        help="Aptly API URL",
    )
    aptly_api_user = key_from_env("APTLY_API_USER")
    aptly_api.add_argument(
        "--aptly-api-user",
        dest="aptly_api_user",
        required=not bool(aptly_api_user),
        default=aptly_api_user,
        help="Aptly API username. Can be set also via 'APTLY_API_USER' env.",
    )
    aptly_api_pass = key_from_env("APTLY_API_PASS")
    aptly_api.add_argument(
        "--aptly-api-pass",
        dest="api_pass",
        required=not bool(aptly_api_pass),
        default=aptly_api_pass,
        help="Aptly API passphrase. Can be set also via 'APTLY_API_PASS' env.",
    )
    return aptly_api


def create_gpg_arg_parser() -> ArgumentParser:
    # common options for interfacing Aptly Rest API
    gpg_parser = ArgumentParser(add_help=False)
    gpg_key = key_from_env("DEBIAN_GPG_KEY")
    gpg_parser.add_argument(
        "--gpg-key",
        dest="gpg_key",
        required=not bool(gpg_key),
        default=gpg_key,
        help="The GPG key to sign the snapshot.",
    )
    gpg_passphrase = key_from_env("DEBIAN_GPG_PASSPHRASE")
    gpg_parser.add_argument(
        "--gpg-passphrase",
        dest="gpg_passphrase",
        required=not bool(gpg_passphrase),
        default=gpg_passphrase,
        help="The GPG passphrase to sign the snapshot.",
    )
    return gpg_parser


def parse_args() -> Namespace:
    parser = ArgumentParser(prog="Create and publish Debian repositories using Aptly.")
    subparsers = parser.add_subparsers(dest="command")

    # common options for interfacing Aptly Rest API
    aptly_api = create_api_arg_parser()

    # commands to list resources from the Aptly service
    list_p = subparsers.add_parser("list", parents=[aptly_api])
    list_p.add_argument("--repositories", dest="list_repositories", action="store_true")
    list_p.add_argument("--snapshots", dest="list_snapshots", action="store_true")
    list_p.add_argument("--published-snapshots", dest="list_pub_snapshots", action="store_true")

    # creation commands
    cr_p = subparsers.add_parser("create_repo", parents=[aptly_api])
    cr_p.add_argument("--repo-name", dest="repo_name", required=True)
    cr_p.add_argument("--dist", dest="dist", required=True)
    cr_p.add_argument("--component", dest="component", required=True)
    cr_p.add_argument("--content-source", dest="content_source")

    cs_p = subparsers.add_parser("create_snapshot", parents=[aptly_api])
    cs_p.add_argument("--snapshot-name", dest="snapshot_name")
    cs_p.add_argument("--repo-name", dest="repo_name")

    # common options for dealing with publishing snapshots
    p_common_args = ArgumentParser(add_help=False)
    p_common_args.add_argument("--prefix", dest="prefix", default="", required=False)
    p_common_args.add_argument("--dist", dest="dist", required=True)
    p_common_args.add_argument(
        "--endpoint-type",
        dest="endpoint_type",
        required=True,
        choices=AptlyApiClient.endpoint_types(),
    )
    p_common_args.add_argument("--endpoint-name", dest="endpoint_name", required=True)

    # publish commands
    gpg_p = create_gpg_arg_parser()
    ps_p = subparsers.add_parser("publish_snapshot", parents=[aptly_api, p_common_args, gpg_p])
    ps_p.add_argument("--snapshot-name", dest="snapshot_name")
    ps_p.add_argument("--architectures", dest="archs", required=True, type=parse_architectures)

    # delete commands
    dr_p = subparsers.add_parser("delete_repo", parents=[aptly_api])
    dr_p.add_argument("--repo-name", dest="repo_name", required=True)
    ds_p = subparsers.add_parser("delete_snapshot", parents=[aptly_api])
    ds_p.add_argument("--snapshot-name", dest="snapshot_name", required=True)
    subparsers.add_parser("delete_published_snapshot", parents=[aptly_api, p_common_args])

    args = parser.parse_args(sys.argv[1:])
    if not args.command:
        log.warning("You need to specify a 'command' to proceed")
        parser.print_help()
        sys.exit(-1)
    return args


def main() -> None:
    args = parse_args()
    client = AptlyApiClient(api_endpoint=args.aptly_api_url, http_auth=None)

    try:
        if args.command == "list":
            if args.list_repositories:
                log.info("Available repositories in: %s", args.aptly_api_url)
                for repo in client.list_repos():
                    log.info("  %s}", repo)
            elif args.list_snapshots:
                log.info("Available snapshots in: %s", args.aptly_api_url)
                for snapshot in client.list_snapshots():
                    log.info("  %s}", snapshot)
            elif args.list_pub_snapshots:
                log.info("Available published snapshots in: %s", args.aptly_api_url)
                for name, data in client.list_published_snapshots().items():
                    log.info("{%s}: storage='%s' prefix='%s' dist='%s' architectures=%s", name,
                             data.storage, data.prefix, data.distribution, data.architectures)
            else:
                log.warning("You forgot to define what resources to list?")
        elif args.command == "create_repo":
            client.create_repo(repo_name=args.repo_name, dist=args.dist, component=args.component)
            if args.content_source:
                client.add_to_repo_from_path(
                    repo_name=args.repo_name, content_path=Path(args.content_source)
                )
            else:
                log.warning("Repository created without any content, is this what you wanted?")
        elif args.command == "create_snapshot":
            client.create_snapshot(snapshot_name=args.snapshot_name, repo_name=args.repo_name)
        elif args.command == "publish_snapshot":
            client.publish_snapshot(
                snapshot_name=args.snapshot_name,
                endpoint_type=args.endpoint_type,
                endpoint_name=args.endpoint_name,
                prefix=args.prefix,
                dist=args.dist,
                architectures=args.archs,
                sign_gpgkey=args.gpg_key,
                sign_passphrase=args.gpg_passphrase,
            )
        elif args.command == "delete_repo":
            client.delete_repo(repo_name=args.repo_name)
        elif args.command == "delete_snapshot":
            client.delete_snapshot(snapshot_name=args.snapshot_name)
        elif args.command == "delete_published_snapshot":
            client.delete_published_snapshot(
                prefix=args.prefix,
                endpoint_type=args.endpoint_type,
                endpoint_name=args.endpoint_name,
                dist=args.dist,
            )
        else:
            log.warning("Unknown command: %s", args.command)
    except PackagingError as err:
        # detailed error is logged by the client already
        log.error("Failed to perform: %s request: %s", args.command, str(err))


if __name__ == "__main__":
    main()
