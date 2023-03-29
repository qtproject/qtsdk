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
import os
import sys
from contextlib import suppress
from pathlib import Path
from shutil import rmtree
from subprocess import CalledProcessError
from typing import List, Optional, Tuple

from macholib import MachO  # type: ignore
from temppathlib import TemporaryDirectory

from bldinstallercommon import locate_paths
from logging_util import init_logger
from notarize import embed_notarization, notarize
from read_remote_config import get_pkg_value
from runner import run_cmd, run_cmd_silent

log = init_logger(__name__, debug_mode=False)


def _is_app_bundle(path: Path) -> bool:
    """
    Determine whether a folder contains .app bundle structure based on contents

    Args:
        path: A file system path to .app directory

    Returns:
        True if 'Info.plist' file found, otherwise False
    """
    if path.suffix != ".app":
        return False
    return path.joinpath("Contents", "Info.plist").exists()


def _is_mach_o_file(path: Path) -> bool:
    """
    Determine whether a file is a Mach-O image containing native code

    Args:
        path: A file system path to a file

    Returns:
        True if Mach-O header found successfully, otherwise False
    """
    try:
        headers = MachO.MachO(path.resolve(strict=True)).headers
        return bool(headers)
    except Exception:
        return False


def _is_framework_version(path: Path) -> bool:
    """
    Determine whether a folder is part of a macOS multi-versioned framework

    Args:
        path: A file system path to a folder

    Returns:
        True if directory is a framework version bundle, otherwise False
    """
    path = path.resolve(strict=True)
    with suppress(IndexError):
        if path.parent.name == "Versions" and path.parents[1].suffix == ".framework":
            return True
    return False


def _find_signable_content(pkg_dir: Path) -> Tuple[List[Path], List[Path]]:
    """
    Find all content to be signed, and that supports stapling:
    .app bundles, frameworks, packages, disk images, binaries (e.g. executables, dylib)

    Args:
        pkg_dir: A file system path to a directory to search recursively from

    Returns:
        Lists of paths sorted for codesign and staple operations
    """

    def not_link(path: Path) -> bool:
        """
        Check if path is not a symlink

        Args:
            path: Path to check
        Returns:
            True for resolved paths, False for symlinks
        """
        return not path.is_symlink()

    sign_list: List[Path] = []
    staple_list: List[Path] = []
    for path in sorted(
        set(Path(p).resolve() for p in locate_paths(pkg_dir, patterns=["*"], filters=[not_link])),
        key=lambda path: len(path.parts),  # Sort by path part length
        reverse=True,  # Nested items first to ensure signing order (important)
    ):
        if path.is_symlink():
            continue  # ignore symlinks
        # App bundles and frameworks
        if path.is_dir():
            if _is_app_bundle(path):
                sign_list.append(path)
                staple_list.append(path)
            elif _is_framework_version(path):
                sign_list.append(path)
        # Containers, Mach-O shared libraries and dynamically loaded modules, Mach-O executables
        elif path.is_file():
            # Known suffixes for containers
            if path.suffix in (".pkg", ".dmg"):
                sign_list.append(path)
                staple_list.append(path)
            # Mach-O images (executables, libraries, modules)
            if _is_mach_o_file(path):
                sign_list.append(path)
    return sign_list, staple_list


def recursive_sign_notarize(pkg_dir: Path) -> None:
    """
    Sign, notarize, and staple content from a directory recursively

    Args:
        pkg_dir: A file system path to the directory with content
    """
    sign_items, staple_items = _find_signable_content(pkg_dir=pkg_dir)
    if not sign_items:
        log.info("No signable content found from '%s', continuing", str(pkg_dir))
        return
    # Run codesign for items
    sign_mac_content(sign_items)
    # Copy only the notarizable (codesigned) content to a temporary dir
    # (ditto does not support multiple source items for archive generation)
    # Exclude other content from the notarization request to reduce file size
    with TemporaryDirectory() as notarize_dir:
        for path in reversed(sign_items):
            # Skip if parent directory already in list
            if not any(p for p in path.parents if p in sign_items):
                create_dir = notarize_dir.path / path.relative_to(pkg_dir).parent
                create_dir.mkdir(parents=True, exist_ok=True)
                # use ditto here to copy, preserves the directory hierarchy and the extended
                # attributes containing the signature for files
                run_cmd(["ditto", str(path), str(create_dir / path.name)])
        # Notarize
        notarize(notarize_dir.path)
    # Staple original files
    count = len(staple_items)
    log.info("Stapling ticket to %s payload items", count)
    for idx, path in enumerate(staple_items):
        log.info("[%s/%s] Staple: %s", idx, count, str(path))
        embed_notarization(path)


def sign_mac_content(paths: List[Path], identity: Optional[str] = None) -> None:
    """
    Run codesign for the given paths

    Args:
        paths: List of signable content

    Raises:
        CalledProcessError: On code signing failure
    """
    run_cmd(cmd=["/Users/qt/unlock-keychain.sh"])  # unlock the keychain first
    count = len(paths)
    log.info("Codesigning %s items", count)
    for idx, path in enumerate(paths):
        log.info("[%s/%s] Codesign: %s", idx, count, str(path))
        cmd_args = [
            'codesign', '--verbose=3', str(path),
            '-r', get_pkg_value("SIGNING_FLAGS"),  # signing requirements
            '-s', identity or get_pkg_value("SIGNING_IDENTITY"),  # developer id identity
            '-o', 'runtime',  # enable hardened runtime, required for notarization
            "--timestamp",  # contact apple servers for time validation
            "--force"  # resign all the code with different signature
        ]
        try:
            run_cmd_silent(cmd=cmd_args)
        except CalledProcessError as err:
            raise Exception(f"Failed to codesign: {str(path)}") from err


def create_mac_dmg(src_path: Path) -> Path:
    """
    Create a macOS disk image (.dmg) from the content source specified.
    The .dmg file will be placed in the parent directory of the specified source path.

    Args:
        src_path: A folder/file to include inside the .dmg file.

    Returns:
        Path to the generated .dmg file
    """
    installer_name_base = src_path.stem
    destination_dmg_path = src_path.with_suffix(".dmg")  # replace last suffix with '.dmg'
    cmd_args = ['hdiutil', 'create', '-srcfolder', str(src_path), '-volname', installer_name_base]
    cmd_args += ['-format', 'UDBZ', str(destination_dmg_path), '-ov', '-scrub', '-size', '4g']
    run_cmd(cmd=cmd_args)
    log.info("Successfully created: %s", str(destination_dmg_path))
    return destination_dmg_path


def sign_windows_executable(file_path: str) -> None:
    sign_tools = ["signtool32.exe", "keys.pfx", "capicom.dll"]
    sign_tools_temp_dir = r'C:\Utils\sign_tools_temp'
    for item in sign_tools:
        dest = os.path.join(sign_tools_temp_dir, item)
        curl_cmd = ['curl', "--fail", "-L", "--retry", "5", "--retry-delay", "30", "-o", dest]
        curl_cmd += ['--create-dirs', get_pkg_value("SIGN_TOOLS_ADDR") + item]
        run_cmd(cmd=curl_cmd)
    sign_tool_executable = os.path.join(sign_tools_temp_dir, 'signtool32.exe')
    keys_path = os.path.join(sign_tools_temp_dir, 'keys.pfx')
    signing_server = get_pkg_value("SIGNING_SERVER")
    timestamp_server = get_pkg_value("TIMESTAMP_SERVER")
    signing_password = get_pkg_value("SIGNING_PASSWORD")
    cmd = [sign_tool_executable, 'sign', '/v', '/du', signing_server, '/p', signing_password]
    cmd += ['/tr', timestamp_server, '/f', keys_path, '/td', "sha256", '/fd', "sha256", file_path]
    # redact sensitive data from logging
    log_entry = cmd[:]
    log_entry[4] = "****"
    log_entry[6] = "****"
    log.info("Calling: %s", " ".join(log_entry))
    sign_success = run_cmd_silent(cmd=cmd)
    rmtree(sign_tools_temp_dir)
    if sign_success:
        log.info("Successfully signed: %s", file_path)
    else:
        log.info("Error signing: %s", file_path)


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(prog="Helper script to sign macOS .app bundle and create .dmg from it or sign a Windows .exe")
    subparsers = parser.add_subparsers(dest='command')

    app_parser = subparsers.add_parser("mac")
    exe_parser = subparsers.add_parser("win")

    app_parser.add_argument(
        "--file",
        dest="file_path",
        required=True,
        type=Path,
        help="Path to a signable macOS bundle/directory/file containing code.",
    )
    app_parser.add_argument(
        "--skip-dmg", dest="create_dmg", action="store_false",
        help="Skip packing the file to a .dmg disk image and signing it"
    )
    app_parser.add_argument("--signing-identity", default=get_pkg_value("SIGNING_IDENTITY"))

    exe_parser.add_argument("--file", dest="file_path", required=True, help="Full path to .exe file")
    exe_parser.add_argument("--signing-server", required=False, default=get_pkg_value("SIGNING_SERVER"))
    exe_parser.add_argument("--signing-pass", required=False, default=get_pkg_value("SIGNING_PASSWORD"))
    exe_parser.add_argument("--timestamp", required=False, default="http://timestamp.digicert.com")

    args = parser.parse_args(sys.argv[1:])
    if args.command == 'mac':
        sign_mac_content([args.file_path], args.signing_identity)
        if args.create_dmg is True:
            dmg_path = create_mac_dmg(args.file_path)
            sign_mac_content([dmg_path], args.signing_identity)
    if args.command == 'win':
        sign_windows_executable(args.file_path)


if __name__ == "__main__":
    main()
