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

import sys
import unittest
from configparser import ConfigParser, ExtendedInterpolation
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ddt import data, ddt, unpack  # type: ignore
from htmllistparse import FileEntry  # type: ignore
from temppathlib import TemporaryDirectory
from urlpath import URL  # type: ignore

from sdkcomponent import (
    ArchiveResolver,
    IfwPayloadItem,
    IfwSdkComponent,
    IfwSdkError,
    locate_pkg_templ_dir,
    parse_ifw_sdk_comp,
)

if sys.version_info < (3, 7):
    import asyncio_backport as asyncio
else:
    import asyncio


def ifw_sdk_config_valid(section_name: str) -> ConfigParser:
    conf = ConfigParser(interpolation=ExtendedInterpolation())
    conf.add_section(section_name)
    conf.set(section_name, "archives", "sub.arch1, sub.arch2, sub.sub3.arch3")
    conf.set(section_name, "target_install_base", "/%QT_VERSION%/gcc_64")
    conf.add_section("sub.arch1")
    conf.set(
        "sub.arch1", "archive_uri", "/qt/dev/release_content/qtbase/qtbase-%LINUX_GCC64_TARGET%.7z"
    )
    conf.add_section("sub.arch2")
    conf.set(
        "sub.arch2", "archive_uri", "/qt/dev/release_content/qtsvg/qtsvg-%LINUX_GCC64_TARGET%.7z"
    )
    conf.add_section("sub.sub3.arch3")
    conf.set(
        "sub.sub3.arch3",
        "archive_uri",
        "/%LICENSE%/%QT_VERSION%/foo/qtdeclarative-%LINUX_GCC64_TARGET%.7z",
    )
    return conf


def key_value_subst_dict() -> Dict[str, str]:
    return {
        "%LICENSE%": "opensource",
        "%QT_VERSION%": "5.10.0",
        "%LINUX_GCC64_TARGET%": "RHEL_7_4",
    }


def ifw_pkg_templ_dirs(ifw_pkg_names: List[str]) -> List[str]:
    ret: List[str] = []
    for ifw_pkg_name in ifw_pkg_names:
        ret.extend(
            [
                f"pkg_templates/product1/{ifw_pkg_name}/meta/package.xml",
                f"pkg_templates/product1/{ifw_pkg_name}/meta/installscript.qs",
                f"pkg_templates/product1/{ifw_pkg_name}/data/readme.txt",
            ]
        )
    return ret


def create_paths(root_folder: str, paths: List[str]) -> List[str]:
    ret: List[str] = []
    for item in paths:
        full_path = Path(root_folder, item)
        ret.append(str(full_path))
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if full_path.name:
            full_path.touch(exist_ok=True)
    return ret


def create_listing(url: URL, timeout: int) -> Tuple[Optional[Any], List[FileEntry]]:
    _ = timeout
    uri = url.as_uri().rstrip("/")
    if not uri:
        return (None, [])
    tree_dict: Dict[str, List[FileEntry]] = {
        "http://fileshare.intra/base": [FileEntry("path/", "", "", "")],
        "http://fileshare.intra/base/path": [
            FileEntry("a.7z", "", "", ""),
            FileEntry("b.7z", "", "", ""),
            FileEntry("c.tar.gz", "", "", ""),
            FileEntry("d.tar.xz", "", "", ""),
            FileEntry("child/", "", "", ""),
        ],
        "http://fileshare.intra/base/path/child": [
            FileEntry("a.7z", "", "", ""),
            FileEntry("b.7z", "", "", ""),
            FileEntry("c.tar.gz", "", "", ""),
            FileEntry("d.txt", "", "", ""),
            FileEntry("child/", "", "", ""),
        ],
        "http://fileshare.intra/base/path/child/child": [FileEntry("a.txt", "", "", "")]
    }
    return url.path if uri in tree_dict else None, tree_dict.get(uri, [])


@ddt
class TestRunner(unittest.TestCase):
    def test_parse_ifw_sdk_archives(self) -> None:
        section = "qt.qt5.5100.gcc_64"
        pkg_template_paths = ifw_pkg_templ_dirs([section])
        ifw_sdk_config = ifw_sdk_config_valid(section)

        with TemporaryDirectory() as tmp_dir:
            temp_path = tmp_dir.path
            pkg_template_search_dirs: List[str] = []
            create_paths(str(temp_path), pkg_template_paths)
            pkg_template_search_dirs.append(str(temp_path / "pkg_templates"))

            file_share_base_url = "http://fileshare.intra/base/path/"
            comp = parse_ifw_sdk_comp(
                ifw_sdk_config,
                section,
                pkg_template_search_dirs,
                key_value_subst_dict(),
                file_share_base_url,
                base_work_dir=Path("."),
                notarize_payload=False,
            )

            self.assertEqual(len(comp.downloadable_archives), 3)
            self.assertListEqual(
                comp.generate_downloadable_archive_list(),
                [
                    [
                        "<!--ONLINE_ARCHIVE_LIST-->",
                        "qtbase-RHEL_7_4.7z, qtsvg-RHEL_7_4.7z, qtdeclarative-RHEL_7_4.7z",
                    ]
                ],
            )
            self.assertCountEqual(
                [a.payload_uris[0] for a in comp.downloadable_archives],
                [
                    file_share_base_url + "qt/dev/release_content/qtbase/qtbase-RHEL_7_4.7z",
                    file_share_base_url + "qt/dev/release_content/qtsvg/qtsvg-RHEL_7_4.7z",
                    file_share_base_url + "opensource/5.10.0/foo/qtdeclarative-RHEL_7_4.7z",
                ],
            )
            self.assertCountEqual(
                [a.archive_name for a in comp.downloadable_archives],
                ["qtbase-RHEL_7_4.7z", "qtsvg-RHEL_7_4.7z", "qtdeclarative-RHEL_7_4.7z"],
            )
            for downloadable_archive in comp.downloadable_archives:
                self.assertFalse(downloadable_archive.errors)
                self.assertEqual(
                    downloadable_archive.get_archive_install_dir(), Path("5.10.0", "gcc_64")
                )

    def test_ifw_payload_item_invalid(self) -> None:
        with self.assertRaises(AssertionError):
            IfwPayloadItem(
                package_name="",
                payload_uris=["http://foo.com/readme.7z"],
                archive_action=None,
                disable_extract_archive=False,
                package_strip_dirs=0,
                package_finalize_items="",
                parent_target_install_base="/base/install/dir",
                arch_target_install_base="/foo/bar",
                arch_target_install_dir="/bar/foo",
                rpath_target="",
                component_sha1="",
                archive_name="readme.7z",
            )

    def test_ifw_payload_item_valid(self) -> None:
        item = IfwPayloadItem(
            package_name="foobar",
            payload_uris=["http://foo.com/readme.7z"],
            archive_action=None,
            disable_extract_archive=False,
            package_strip_dirs=0,
            package_finalize_items="",
            parent_target_install_base="",
            arch_target_install_base="/foo/bar",
            arch_target_install_dir="",
            rpath_target="",
            component_sha1="",
            archive_name="readme.7z",
        )
        self.assertFalse(item.errors)

    @data(  # type: ignore
        ("foo.7z", None, False, 0, "", "/", "", "", "", "", False, False),
        ("foo.7z", None, True, 0, "", "/", "", "", "", "", False, False),
        ("foo.7z", (Path("foo.sh"), ""), False, 0, "", "/", "", "", "", "", True, True),
        ("foo.7z", None, False, 1, "", "/", "", "", "", "", True, True),
        ("foo.7z", None, False, 0, "foo", "/", "", "", "", "", True, True),
        ("foo.7z", None, False, 0, "", "/foo", "", "", "", "", True, True),
        ("foo.7z", None, False, 0, "", "/", "/foo", "", "", "", True, True),
        ("foo.7z", None, False, 0, "", "/", "", "foo/bar", "", "", True, True),
        ("foo.7z", None, False, 0, "", "/", "", "", "foo", "", True, True),
        ("foo.7z", None, False, 0, "", "/", "", "", "", "foo", True, False),
        ("foo.txt", None, False, 0, "", "/", "", "", "", "foo", False, False),
        ("foo.txt", None, False, 0, "", "/", "", "", "", "", False, False),
        ("foo.txt", None, False, 0, "", "/", "/foo/bar", "", "", "", False, True),
    )
    @unpack  # type: ignore
    def test_ifw_payload_item_requires_packaging_operations(
        self,
        archive_uri: str,
        archive_action: Tuple[Path, str],
        disable_extract_archive: bool,
        package_strip_dirs: int,
        package_finalize_items: str,
        parent_target_install_base: str,
        arch_target_install_base: str,
        arch_target_install_dir: str,
        rpath_target: str,
        component_sha1: str,
        expected_requires_extraction: bool,
        expected_requires_patching: bool,
    ) -> None:
        item = IfwPayloadItem(
            package_name="foobar",
            payload_uris=[archive_uri],
            archive_action=archive_action,
            disable_extract_archive=disable_extract_archive,
            package_strip_dirs=package_strip_dirs,
            package_finalize_items=package_finalize_items,
            parent_target_install_base=parent_target_install_base,
            arch_target_install_base=arch_target_install_base,
            arch_target_install_dir=arch_target_install_dir,
            rpath_target=rpath_target,
            component_sha1=component_sha1,
            archive_name="readme.7z",
        )
        self.assertEqual(item.requires_extraction, expected_requires_extraction)
        self.assertEqual(item.requires_patching, expected_requires_patching)

    def test_ifw_component_duplicate_archive_name(self) -> None:
        item = IfwPayloadItem(
            package_name="foobar",
            payload_uris=["foo.7z"],
            archive_action=None,
            disable_extract_archive=False,
            package_strip_dirs=0,
            package_finalize_items="",
            parent_target_install_base="",
            arch_target_install_base="",
            arch_target_install_dir="",
            rpath_target="",
            component_sha1="",
            archive_name="duplicate.7z",
        )
        item_duplicate = IfwPayloadItem(
            package_name="foobar_duplicate",
            payload_uris=["duplicate.7z"],
            archive_action=None,
            disable_extract_archive=False,
            package_strip_dirs=0,
            package_finalize_items="",
            parent_target_install_base="",
            arch_target_install_base="",
            arch_target_install_dir="",
            rpath_target="",
            component_sha1="",
            archive_name="",
        )
        component = IfwSdkComponent(
            ifw_sdk_comp_name="section",
            pkg_template_folder="pkg_template_folder",
            archive_resolver=ArchiveResolver("file_share_base_url", "pkg_template_folder"),
            downloadable_archives=[item, item_duplicate],
            archives_extract_dir="archives_extract_dir",
            target_install_base="target_install_base",
            version="version",
            version_tag="version_tag",
            package_default="package_default",
            comp_sha1_uri="comp_sha1_uri",
            include_filter="include_filter",
            base_work_dir=Path(".")
        )
        with self.assertRaises(IfwSdkError):
            component.validate(uri_check=False, ignore_errors=False)

    def test_archive_resolver(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            template_folder = tmp_base_dir.path / "qt.tools.foo"
            data_folder = template_folder / "data"
            payload_file = data_folder / "readme.txt"
            data_folder.mkdir(parents=True, exist_ok=True)
            with payload_file.open("a", encoding="utf-8"):
                pass

            resolver = ArchiveResolver("http://intranet.local.it/artifacts", str(template_folder))
            _, resolved = resolver.resolve_payload_uri("readme.txt")
            self.assertEqual(resolved.pop(), str(payload_file))
            _, resolved = resolver.resolve_payload_uri("qt/qtsvg/qtsvg-RHEL_7_4.7z")
            self.assertEqual(
                resolved.pop(), "http://intranet.local.it/artifacts/qt/qtsvg/qtsvg-RHEL_7_4.7z"
            )
            _, resolved = resolver.resolve_payload_uri(__file__)
            self.assertEqual(resolved.pop(), __file__)

    @data(  # type: ignore
        (
            "http://fileshare.intra/base/path/*",
            [
                URL("http://fileshare.intra/base/path/a.7z"),
                URL("http://fileshare.intra/base/path/b.7z"),
                URL('http://fileshare.intra/base/path/c.tar.gz'),
                URL('http://fileshare.intra/base/path/d.tar.xz'),
                URL('http://fileshare.intra/base/path/child/a.7z'),
                URL('http://fileshare.intra/base/path/child/b.7z'),
                URL('http://fileshare.intra/base/path/child/c.tar.gz'),
                URL('http://fileshare.intra/base/path/child/d.txt'),
                URL('http://fileshare.intra/base/path/child/child/a.txt'),
            ],
        ),
        (
            "http://fileshare.intra/base/path/*.7z",
            [
                URL("http://fileshare.intra/base/path/a.7z"),
                URL("http://fileshare.intra/base/path/b.7z"),
                URL('http://fileshare.intra/base/path/child/a.7z'),
                URL('http://fileshare.intra/base/path/child/b.7z'),
            ],
        ),
        (
            "http://fileshare.intra/base/path/*.tar.*",
            [
                URL('http://fileshare.intra/base/path/c.tar.gz'),
                URL('http://fileshare.intra/base/path/d.tar.xz'),
                URL('http://fileshare.intra/base/path/child/c.tar.gz'),
            ],
        ),
        (
            "http://fileshare.intra/base/path/*.t*",
            [
                URL('http://fileshare.intra/base/path/c.tar.gz'),
                URL('http://fileshare.intra/base/path/d.tar.xz'),
                URL('http://fileshare.intra/base/path/child/c.tar.gz'),
                URL('http://fileshare.intra/base/path/child/d.txt'),
                URL('http://fileshare.intra/base/path/child/child/a.txt'),
            ],
        ),
        (
            "http://fileshare.intra/base/path/chi?d/child/[a-f].txt",
            [
                URL('http://fileshare.intra/base/path/child/child/a.txt'),
            ],
        ),
        (
            "http://fileshare.intra/base/path/*[b-f].7z",
            [
                URL('http://fileshare.intra/base/path/b.7z'),
                URL('http://fileshare.intra/base/path/child/b.7z'),
            ],
        ),
    )
    @unpack  # type: ignore
    @unittest.mock.patch("htmllistparse.fetch_listing", side_effect=create_listing)  # type: ignore
    def test_pattern_archive_resolver(
        self, pattern: str, expected_uris: List[str], _: Any
    ) -> None:
        resolver = ArchiveResolver("", "")
        expected = (URL("http://fileshare.intra/base/path"), expected_uris)
        self.assertCountEqual(asyncio.run(resolver.resolve_uri_pattern(pattern, None)), expected)

    def test_locate_pkg_templ_dir_invalid(self) -> None:
        with TemporaryDirectory() as tmp_base_dir:
            with self.assertRaises(IfwSdkError):
                locate_pkg_templ_dir([str(tmp_base_dir.path)], "qt.foo")


if __name__ == "__main__":
    unittest.main()
