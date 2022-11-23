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
import json
import shutil
import sys
from pathlib import Path
from platform import mac_ver
from shutil import which
from subprocess import CalledProcessError
from typing import Optional

from bld_utils import is_macos
from installer_utils import PackagingError
from logging_util import init_logger
from read_remote_config import get_pkg_value
from runner import run_cmd, run_cmd_silent

log = init_logger(__name__, debug_mode=False)


class NotarizationError(Exception):
    """NotarizationError exception class derived from the Exception class"""


def store_credentials_api_key(profile_name: str, key: str, key_id: str, issuer: str) -> None:
    """
    Store App Store Connect API Keys to keychain and validate them with notarytool.

    Args:
        profile_name: The profile name in keychain to which to save the credentials
        key: App Store Connect API key file system path
        key_id: App Store Connect API Key ID specific to a team (~10 chars)
        issuer: App Store Connect API Issuer ID in UUID format

    Raises:
        NotarizationError: When the command saving and validating the credentials fails

    """
    log.info("Store App Store Connect API Keys to keychain profile '%s'", profile_name)
    cmd = ["xcrun", "notarytool", "store-credentials", profile_name]
    cmd += ["--key", key, "--key-id", key_id, "--issuer", issuer]
    if not run_cmd_silent(cmd=cmd):
        raise NotarizationError("Failed to save or validate API key credentials")


def store_credentials_apple_id(
    profile_name: str, apple_id: str, password: str, team_id: str
) -> None:
    """
    Store Developer Apple ID credentials to keychain and validate them with notarytool.

    Args:
        profile_name: The profile name in keychain to which to save the credentials
        apple_id: The Apple ID login username for accessing Developer ID services
        password: App-specific password generated for the aforementioned Apple ID
        team_id: The Developer Team identifier to use with the credentials (~10 chars)

    Raises:
        NotarizationError: When the command saving and validating the credentials fails

    """
    log.info("Store Developer Apple ID credentials to keychain profile '%s'", profile_name)
    cmd = ["xcrun", "notarytool", "store-credentials", profile_name]
    cmd += ["--apple-id", apple_id, "--password", password, "--team-id", team_id]
    if not run_cmd_silent(cmd=cmd):
        raise NotarizationError("Failed to save or validate Apple ID credentials")


def process_notarize_result(
    json_data: str, profile_name: str, timeout: Optional[int] = None
) -> None:
    """
    Parse and log notarization results from json_data and raise the encountered errors.

    Args:
        json_data: Output data from notarizetool with the --output-format json specified
        profile_name: The keychain profile containing the auth credentials for notarytool
        timeout: Specify a timeout for notarytool command executed via run_cmd

    Raises:
        JSONDecodeError: If json_data formatting is malformed and cannot be decoded to json
        NotarizationError: When the notarization is determined to have failed
        CalledProcessError: When the command requesting additional logs for the UUID fails

    """
    try:
        data = json.loads(json_data)
    except json.JSONDecodeError as err:
        log.exception("Error processing json response")
        raise NotarizationError(f"Notarization failed: {str(err)}") from err
    uuid = data.get("id", "")
    status = data.get("status", "")
    if status != "Accepted":
        log.error("Notarization error: %s, UUID: %s", status, uuid)
        log.error("Gathering more details about the errors...")
        cmd = ["xcrun", "notarytool", "log", uuid, "-p", profile_name]
        try:
            run_cmd(cmd=cmd, timeout=timeout)
        except CalledProcessError as err:
            log.exception("Failed to log additional details", exc_info=err)
        raise NotarizationError(f"Notarization failed, UUID: {uuid}")
    log.info("Notarization complete, UUID: %s", uuid)


def submit_for_notarization(
    path: Path, profile_name: str, timeout: Optional[int] = None, acceleration: bool = True
) -> None:
    """
    Submit a file to Apple's Notary service for notarization.
    Wait for the server to return the result and pass the output to process_notarize_result.

    Args:
        path: The file system path for the file to notarize
        profile_name: The keychain profile containing the auth credentials for notarytool
        timeout: Specify a timeout for the notarytool command and run_cmd
        acceleration: Whether to enable S3 transfer acceleration in the notarytool upload

    """
    cmd = ["xcrun", "notarytool", "submit", str(path), "-p", profile_name]
    cmd += ["--wait", "--timeout", str(timeout), "--output-format", "json"]
    if not acceleration:
        cmd += ["--no-s3-acceleration"]
    try:
        result = run_cmd(cmd=cmd, timeout=timeout)
    except CalledProcessError as err:
        raise NotarizationError("Notarytool command failed, invalid arguments?") from err
    process_notarize_result(result, profile_name, timeout=timeout)


def prepare_payload(path: Path) -> Path:
    """
    Pack payload into a .zip archive if the path does not point to file supported by notarytool.
    The Apple Notary service accepts the following formats:
        - disk images (UDIF format), ending in .dmg
        - signed flat installer packages, ending in .pkg
        - ZIP compressed archives, ending in .zip

    Args:
        path: The file system path to the file or folder to process

    Returns:
        path: The file system path to the created zip file or the path originally passed in

    Raises:
        CalledProcessError: When the compress command via run_cmd returns a non-zero exit status.
        NotarizationError: Raised on CalledProcessError

    """
    if path.suffix not in (".dmg", ".pkg", ".zip"):
        zip_path: Path = path.with_suffix(".zip")
        log.info("Compress to .zip before upload: %s", zip_path)
        ditto_tool = shutil.which("ditto") or "/usr/bin/ditto"
        cmd = [ditto_tool, "-c", "-k", "--keepParent", str(path), str(zip_path)]
        try:
            run_cmd(cmd=cmd)
        except CalledProcessError as err:
            raise NotarizationError(f"Failed to compress {path} to .zip") from err
        path = zip_path
    log.info("Ready to upload: %s", path)
    return path


def embed_notarization(path: Path) -> None:
    """
    Embed the ticket in the notarized package, supported file formats by stapler are:
        - UDIF disk images (.dmg)
        - code-signed executable bundles (.app)
        - signed "flat" installer packages (.pkg)

    Args:
        path: The file system path to the previously notarized file

    Raises:
        CalledProcessError: When the stapler command via run_cmd returns a non-zero exit status.
        NotarizationError: Raised on CalledProcessError on a supported file type.

    """
    log.info("Stapling package: %s", path)
    try:
        cmd = ['xcrun', 'stapler', 'staple', str(path)]
        run_cmd(cmd=cmd)
    except CalledProcessError as err:
        if path.suffix in (".dmg", ".app", ".pkg"):
            raise NotarizationError(f"Error embedding ticket: Stapler failed for {path}") from err
        # Do not raise when file format is not known to support stapling, but log the error instead
        log.exception("Ignored error while stapling %s: %s", str(path), str(err), exc_info=err)


def key_from_remote_env(key: str) -> str:
    """
    Get value from remote environment with get_pkg_value if it exists, or return an empty string

    Args:
        key: The key for the value to look for in the environment

    Returns:
        Returned value from get_pkg_value if no exception was handled or an empty string (str)

    """
    try:
        return get_pkg_value(key)
    except PackagingError:
        return ""  # Do not raise here if remote environment is not in use


def check_notarize_reqs() -> None:
    """
    Check if the system supports notarization via notarytool and has the required tools installed.

    Raises:
        NotarizationError: If there are missing tools or the platform is not supported.

    """
    if not is_macos():
        raise NotarizationError("Only macOS is supported. For other platforms see Notary API.")
    if not [int(x) for x in mac_ver()[0].split(".")] >= [10, 15, 7]:
        raise NotarizationError("Only macOS version 10.15.7+ is supported by notarytool")
    if not shutil.which("ditto") and not Path("/usr/bin/ditto").exists():
        raise NotarizationError("Couldn't find 'ditto': '/usr/bin/ditto' missing or not in PATH")
    if not which("xcrun"):
        raise NotarizationError("Couldn't find 'xcrun'. Xcode Command Line Tools is required")
    try:
        run_cmd(["xcrun", "--find", "stapler"])
    except CalledProcessError as err:
        raise NotarizationError("Couldn't find 'stapler'. Xcode is required") from err
    try:
        run_cmd(["xcrun", "--find", "notarytool"])
    except CalledProcessError as err:
        raise NotarizationError("Couldn't find 'notarytool'. Xcode 13+ is required") from err


def notarize(
    path: Path,
    apple_id: str = key_from_remote_env("AC_USERNAME"),
    password: str = key_from_remote_env("AC_PASSWORD"),
    team_id: str = key_from_remote_env("QT_CODESIGN_IDENTITY_KEY"),
    key: str = key_from_remote_env("AC_KEY"),
    key_id: str = key_from_remote_env("AC_KEYID"),
    issuer: str = key_from_remote_env("AC_ISSUER"),
    profile: str = key_from_remote_env("AC_NOTARY") or "AC_NOTARY",
    timeout: Optional[int] = 60 * 60 * 3,
    acceleration: bool = True
) -> None:
    """
    Run notarize and staple actions for the given file with arguments specified
    Notarytool authentication options:
        - apple_id, password, team_id -> saved to profile
        - key, key_id, issuer -> saved to profile
        - profile -> use from profile directly

    Args:
        path: The file system path to the file or folder to notarize
        apple_id: The Apple ID login username to save
        password: App-specific password to save
        team_id: The Developer Team identifier to save
        key: App Store Connect API key file system path to save
        key_id: App Store Connect API Key ID to save
        issuer: App Store Connect API Issuer UUID to save
        profile: Profile name in keychain for saving and accessing credentials
        timeout: Timeout for all of the notarytool commands executed
        acceleration: Whether to enable transfer acceleration in notarytool uploads

    Raises:
        NotarizationError: When conditions required for notarization are not met or it fails

    """
    # Check system requirements
    check_notarize_reqs()
    # Store credentials for later
    if not profile:
        raise NotarizationError("Keychain profile name is empty?")
    if key and key_id and issuer:
        store_credentials_api_key(profile, key, key_id, issuer)
    elif apple_id and password and team_id:
        store_credentials_apple_id(profile, apple_id, password, team_id)
    else:
        log.warning("App Store Connect API keys or Apple ID credentials not provided.")
        log.info("Attempting to use previously saved credentials from profile '%s'", profile)
    # Pack the file if necessary, return the new path
    notarize_path = prepare_payload(path)
    # Submit payload for notarization and wait for it to complete
    log.info("Notarize %s", notarize_path)
    submit_for_notarization(notarize_path, profile, timeout, acceleration)
    # Embed the notarization ticket to the file if file type supports it (DMG, PKG)
    # If required, stapler needs to be run separately for each file inside the ZIP archive
    if notarize_path.suffix != ".zip":
        embed_notarization(notarize_path)
    # Remove the zipped archive as this is no longer needed, keeping only the original data
    if path != notarize_path:
        notarize_path.unlink()


def main() -> None:
    """Main function, parse arguments with ArgumentParser and call the notarize function."""
    parser = argparse.ArgumentParser(prog="Helper script to notarize content from given path")
    parser.add_argument(
        "--bundle-id",  # TODO: remove
        dest="bundle_id", required=False, type=str, help="Deprecated"
    )
    parser.add_argument(
        "--path",
        "--dmg",  # TODO: remove
        dest="path", required=True, type=str, help="Path to a file or a folder"
    )
    parser.add_argument(
        "--apple-id",
        "--user",  # TODO: remove
        dest="apple_id", type=str, default=key_from_remote_env("AC_USERNAME"),
        help="Developer Apple ID login username"
    )
    parser.add_argument(
        "--password",
        "--passwd",  # TODO: remove
        dest="password", type=str, default=key_from_remote_env("AC_PASSWORD"),
        help="App-specific password for Apple ID"
    )
    parser.add_argument(
        "--team-id", dest="team_id", type=str,
        default=key_from_remote_env("QT_CODESIGN_IDENTITY_KEY"), help="Developer Team identifier"
    )
    parser.add_argument(
        "--key", dest="key", type=str, default=key_from_remote_env("AC_KEY"),
        help="Path for App Store Connect API key"
    )
    parser.add_argument(
        "--key-id", dest="key_id", type=str, default=key_from_remote_env("AC_KEYID"),
        help="App Store Connect API Key ID"
    )
    parser.add_argument(
        "--issuer", dest="issuer", type=str, default=key_from_remote_env("AC_ISSUER"),
        help="App Store Connect API Issuer UUID"
    )
    parser.add_argument(
        "--timeout", dest="timeout", type=int, default=10800,
        help="Timeout value for remote requests"
    )
    parser.add_argument(
        "--profile", dest="profile", type=str,
        default=key_from_remote_env("AC_NOTARY") or "AC_NOTARY",
        help="Notarytool profile name for saved credentials"
    )
    parser.add_argument(
        "--acceleration", dest="acceleration", action="store_true", default=True,
        help="Enable S3 Acceleration"
    )
    args = parser.parse_args(sys.argv[1:])
    try:
        notarize(
            path=Path(args.path),
            apple_id=args.apple_id,
            password=args.password,
            team_id=args.team_id,
            key=args.key,
            key_id=args.key_id,
            issuer=args.issuer,
            timeout=args.timeout,
            profile=args.profile,
            acceleration=args.acceleration,
        )
    except NotarizationError as err:
        log.exception("Notarize script failed: %s", str(err), exc_info=err)
        raise SystemExit from err


if __name__ == "__main__":
    main()
