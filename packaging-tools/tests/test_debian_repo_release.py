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

import json
import random
import shutil
import socket
import subprocess
import unittest
from configparser import ConfigParser
from pathlib import Path
from time import sleep
from typing import Any, ClassVar

from ddt import ddt  # type: ignore

from debian_repo_release import AptlyApiClient
from installer_utils import PackagingError
from release_repo_updater_deb import create_and_publish_repos
from release_task_reader import TaskType, parse_data


@ddt
@unittest.skipIf(shutil.which("aptly") is None, "The aptly is not installed!")
class TestDebianRepoRelease(unittest.TestCase):
    # make mypy happy
    assets_root = None  # type: ClassVar[Path]
    aptly_root = None  # type: ClassVar[Path]
    aptly_config = None  # type: ClassVar[Path]
    aptly_exec = None  # type: ClassVar[Any]
    aptly_api = None  # type: ClassVar[str]
    aptly_publish_filesystem_endpoint_name = None  # type: ClassVar[str]
    aptly_publish_filesystem_root = None  # type: ClassVar[Path]
    proc: subprocess.Popen  # type: ignore

    @classmethod
    def get_free_port(cls) -> int:
        while True:
            port = random.randint(32768, 61000)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                if not sock.connect_ex(("127.0.0.1", port)) == 0:
                    return port

    @classmethod
    def setUpClass(cls) -> None:
        free_port = str(cls.get_free_port())
        cls.assets_root = Path(__file__).parent / "assets" / "aptly"
        cls.aptly_root = Path(__file__).parent / "aptly_testing" / free_port
        cls.aptly_root.mkdir(parents=True, exist_ok=True)
        cls.aptly_config = cls.aptly_root / ".aptly.conf"
        cls.aptly_exec = shutil.which("aptly")
        assert cls.aptly_exec is not None, "Aptly not installed on the system!"
        cls.aptly_api = f"127.0.0.1:{free_port}"
        cls.aptly_publish_filesystem_endpoint_name = "myendpoint"
        cls.aptly_publish_filesystem_root = cls.aptly_root / "publish_root"
        shutil.rmtree(cls.aptly_publish_filesystem_root, ignore_errors=True)
        cls.aptly_publish_filesystem_root.mkdir(parents=True, exist_ok=True)

        if cls.aptly_config.exists():
            cls.aptly_config.unlink()  # delete if previous should exist
        cls.drop_stub_aptly_root()
        cls.write_aptly_config()
        cls.create_stub_aptly_repo()
        cls.start_repo_service()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.aptly_config.unlink()
        cls.drop_stub_aptly_root()
        cls.stop_repo_service()
        shutil.rmtree(cls.aptly_publish_filesystem_root, ignore_errors=True)
        shutil.rmtree(cls.aptly_root / ".aptly", ignore_errors=True)

    @classmethod
    def write_aptly_config(cls) -> None:
        data = {
            "rootDir": f"{cls.aptly_root}/.aptly",
            "downloadConcurrency": 4,
            "downloadSpeedLimit": 0,
            "architectures": [],
            "dependencyFollowSuggests": False,
            "dependencyFollowRecommends": False,
            "dependencyFollowAllVariants": False,
            "dependencyFollowSource": False,
            "dependencyVerboseResolve": False,
            "gpgDisableSign": True,
            "gpgDisableVerify": True,
            "gpgProvider": "gpg",
            "downloadSourcePackages": False,
            "skipLegacyPool": True,
            "ppaDistributorID": "ubuntu",
            "ppaCodename": "",
            "skipContentsPublishing": False,
            "FileSystemPublishEndpoints": {
                f"{cls.aptly_publish_filesystem_endpoint_name}": {
                    "rootDir": f"{str(cls.aptly_publish_filesystem_root)}",
                    "linkMethod": "copy",
                    "verifyMethod": "md5",
                }
            },
            "S3PublishEndpoints": {},
            "SwiftPublishEndpoints": {},
        }

        cls.aptly_config.parent.mkdir(parents=True)
        with cls.aptly_config.open("w", encoding="utf-8") as apt_conf:
            json.dump(data, apt_conf)

    @classmethod
    def create_stub_aptly_repo(cls) -> None:
        # Aptly refuses to serve the API if there are no repositories at all so create one stub
        ret = subprocess.run(
            [cls.aptly_exec, f"-config={str(cls.aptly_config)}", "repo", "create", "stub_repo"],
            check=True,
        )
        if not ret.returncode == 0:
            cls.fail(cls, f"Could not create stub aptly repo: {ret.stderr}")  # type: ignore
        ret = subprocess.run(
            [
                cls.aptly_exec,
                f"-config={str(cls.aptly_config)}",
                "snapshot",
                "create",
                "stub_snapshot",
                "from",
                "repo",
                "stub_repo",
            ],
            check=True,
        )
        if not ret.returncode == 0:
            cls.fail(cls, f"Couldn't create stub aptly snapshot: {ret.stderr}")  # type: ignore
        ret = subprocess.run(
            [
                cls.aptly_exec,
                f"-config={str(cls.aptly_config)}",
                "publish",
                "snapshot",
                "-distribution=bullseye",
                "-architectures='default'",
                "stub_snapshot",
            ],
            check=True,
        )
        if not ret.returncode == 0:
            cls.fail(cls, f"Couldn't publish stub aptly snapshot: {ret.stderr}")  # type: ignore

    @classmethod
    def start_repo_service(cls) -> None:
        args = [
            cls.aptly_exec,
            f"-config={str(cls.aptly_config)}",
            "api",
            "serve",
            f"-listen={cls.aptly_api}",
        ]
        cls.proc = subprocess.Popen(args, stdout=subprocess.PIPE)  # pylint: disable=R1732
        # give it time to actually start up
        sleep(1)

    @classmethod
    def stop_repo_service(cls) -> None:
        cls.proc.kill()
        cls.proc.communicate()

    @classmethod
    def drop_stub_aptly_root(cls) -> None:
        print(f"Erasing Aptly root: {cls.aptly_root}")
        shutil.rmtree(cls.aptly_root, ignore_errors=True)

    def test_aptly_api_client_publish_repo(self) -> None:
        assets1 = self.assets_root / "deb1"
        client = AptlyApiClient(api_endpoint=f"http://{self.aptly_api}/", http_auth=None)
        client.create_repo(repo_name="foobar_repo", dist="bullseye", component="main")
        self.assertTrue("foobar_repo" in client.list_repos())
        client.add_to_repo_from_path(repo_name="foobar_repo", content_path=assets1)
        client.create_snapshot(snapshot_name="foobar_snapshot", repo_name="foobar_repo")
        self.assertTrue("foobar_snapshot" in client.list_snapshots())
        client.publish_snapshot(
            snapshot_name="foobar_snapshot",
            endpoint_type="filesystem",
            endpoint_name=self.aptly_publish_filesystem_endpoint_name,
            prefix="test_prefix",
            dist="bullseye",
            architectures=["amd64"],
            sign_gpgkey=None,
            sign_passphrase=None,
        )
        self.assertTrue("foobar_snapshot" in client.list_published_snapshots())

    def test_aptly_api_client_add_package_from_path(self) -> None:
        asset = self.assets_root / "deb1" / "libqt6.2.2openglwidgets6_6.2.2-1_amd64.deb"
        client = AptlyApiClient(api_endpoint=f"http://{self.aptly_api}/", http_auth=None)
        client.create_repo(repo_name="pkg_tmp", dist="bullseye", component="main")
        client.add_to_repo_from_path(repo_name="pkg_tmp", content_path=asset)
        with self.assertRaises(PackagingError):
            client.add_to_repo_from_path(repo_name="pkg_tmp", content_path=Path() / "__tmp")

    def test_repocontroller(self) -> None:
        assets_path_1 = self.assets_root / "deb1"
        assets_path_2 = self.assets_root / "deb2"
        sample_config = f"""
            [task.deb.repository.linux.amd64]
            repo_path: foobar_deb_repo_name
            distribution:  bullseye
            component: main
            architectures: amd64
            content_sources: {str(assets_path_1)}, {str(assets_path_2)}
            substitutions:
            endpoint_type: filesystem
            endpoint_name: {self.aptly_publish_filesystem_endpoint_name}
            rta_key_list: key1, key2
        """
        config = ConfigParser()
        config.read_string(sample_config)
        tasks = parse_data(config, task_type=TaskType.DEB_TASK_TYPE, task_filters=[])

        client = AptlyApiClient(api_endpoint=f"http://{self.aptly_api}/", http_auth=None)
        create_and_publish_repos(
            client,
            tasks,  # type: ignore
            gpg_key="",
            gpg_passphrase="",
            rta=None,
        )


if __name__ == "__main__":
    unittest.main()
