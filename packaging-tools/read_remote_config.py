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
import sys
from configparser import ConfigParser
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, Optional, Union

import pysftp  # type: ignore
from cryptography.fernet import Fernet, InvalidToken
from paramiko import (
    AgentKey,
    AuthenticationException,
    PasswordRequiredException,
    RSAKey,
    SSHException,
)

from installer_utils import PackagingError
from logging_util import init_logger

log = init_logger(__name__, debug_mode=False)


class RemoteConfigError(Exception):
    pass


def _get_private_key() -> bytes:
    """
    Read encrypted private key file from default path

    Returns:
        Key file content in a bytes array

    Raises:
        PackagingError: When path is invalid or file cannot be found
    """
    try:
        k_path = Path.home() / "sshkeys" / os.environ["ID_RSA_FILE"]
        k_path.resolve(strict=True)
    except KeyError as err:
        raise PackagingError("Could not determine private key path from env") from err
    except FileNotFoundError as err:
        raise PackagingError(f"Failed to locate private key from path: {k_path}") from err
    log.info("Reading the private key: %s", k_path)
    with k_path.open("rb") as private_key:
        return private_key.read()


def _get_decrypt_key() -> bytes:
    """
    Read Fernet decryption key from default path

    Returns:
        Key file content in a bytes array

    Raises:
        PackagingError: When path is invalid or file cannot be found
    """
    try:
        k_path = Path(os.environ["PKG_NODE_ROOT"], os.environ["FILES_SHARE_PATH"])
        k_path.resolve(strict=True)
    except KeyError as err:
        raise PackagingError("Could not determine decryption key path from env") from err
    except FileNotFoundError as err:
        raise PackagingError(f"Failed to locate decryption key from path: {k_path}") from err
    log.info("Reading the pre-generated Fernet key: %s", k_path)
    with open(k_path, "rb") as decrypt_key:
        return decrypt_key.read()


def _decrypt_private_key(key: bytes, decrypt_key: bytes) -> RSAKey:
    """
    Decrypt a Fernet encrypted key and return a RSA key object containing the decrypted key

    Args:
        key: Encrypted content to be decrypted (Fernet token)
        decrypt_key: Key for decryption (Fernet base64-encoded 32-byte key)

    Raises:
        PackagingError: Raised on the decryption failures or if the resulting data is not valid
    """
    log.info("Decrypting private key using pre-generated Fernet key")
    try:
        fernet = Fernet(decrypt_key)
        decrypted_key = fernet.decrypt(key)
    except InvalidToken:
        raise PackagingError("Failed to decrypt private key, got invalid Fernet token") from None
    try:
        return RSAKey(file_obj=StringIO(decrypted_key.decode(encoding="utf-8")))
    except SSHException:
        raise PackagingError("Failed to create RSA key object, invalid key format?") from None


def download_remote_file_sftp(
    remote_host: Optional[str] = os.getenv("SFTP_ADDRESS"),
    remote_path: Optional[Path] = None,
    local_path: Optional[Path] = None,
    username: Optional[str] = os.getenv("SFTP_USER"),
    private_key: Optional[Union[str, RSAKey, AgentKey]] = None
) -> None:
    """
    Transfer the given remote file to a given folder via SFTP

    Args:
        remote_host: An address or a hostname for the remote server
        remote_path: A file system path on the remote server to transfer from
        local_path: A file system path where to save the file, by default set to current work dir
        username: Name used for authenticating with the remote server
        private_key: A private key object or string path to a key file when not using the default

    Raises:
        PackagingError: Raised on missing arguments
        RemoteConfigError: Re-raised on SFTP errors from pysftp.Connection
    """
    if private_key is None:  # get default RSA private key
        private_key = _decrypt_private_key(_get_private_key(), _get_decrypt_key())
    if not remote_host or remote_path is None:
        raise PackagingError("Remote host address and/or source path not specified")
    if not all((username, private_key)):
        raise PackagingError("SSH public key authentication options not specified")
    log.debug("Transfer '%s:%s' -> '%s'", remote_host, remote_path, local_path)
    cnopts = pysftp.CnOpts()
    cnopts.hostkeys = None  # disable host key checking
    try:
        with pysftp.Connection(
            host=remote_host,
            username=username,
            private_key=private_key,
            cnopts=cnopts,
        ) as sftp:
            sftp.get(remotepath=remote_path.as_posix(), localpath=local_path)
    except pysftp.ConnectionException:
        raise RemoteConfigError("Connection to the remote server failed") from None
    except pysftp.CredentialException:
        raise RemoteConfigError("Problem with credentials") from None
    except (IOError, OSError):
        raise RemoteConfigError("File doesn't exist on the remote or unable to save it") from None
    except PasswordRequiredException:
        raise RemoteConfigError("Private key was not decrypted before use") from None
    except AuthenticationException:
        raise RemoteConfigError("Authenticating with credentials failed") from None
    except SSHException:
        raise RemoteConfigError("SSH2 protocol failure") from None


def _read_remote_config_sftp(remote_ini_path: Path) -> str:
    """
    Transfer the given remote config file to a temporary dir via SFTP and return the file content

    Args:
        remote_ini_path: A file system path on the remote host to read from

    Returns:
        Remote config .ini contents

    Raises:
        RemoteConfigError: Re-raised on config download error from download_remote_file_sftp
    """
    with TemporaryDirectory() as temp_dir:
        local_path = Path(temp_dir) / "config.ini"
        try:
            download_remote_file_sftp(remote_path=remote_ini_path, local_path=local_path)
        except RemoteConfigError as err:
            raise RemoteConfigError("Failed to receive remote config!") from err
        with open(local_path, "rb") as config:
            return config.read().decode('utf-8').strip()


def _parse_remote_config(config: str) -> ConfigParser:
    """
    Parse config using ConfigParser

    Args:
        config: A string containing the .ini file content

    Returns:
        An instance of ConfigParser with the parsed config
    """
    buf = StringIO(config)
    settings = ConfigParser()
    settings.read_file(buf)
    return settings


def get_pkg_value(
    key: str,
    section: str = "packaging",
    remote_cfg_path: Optional[Path] = None
) -> str:
    """
    Get value for section and key in remote packaging config ini (sftp)
    Configs dict will be cached as a function attribute 'cfg_cache' for future calls

    Args:
        key: A key in the config section
        section: A section in the config (if empty, first section is used)
        remote_cfg_path: A file system location for the config file on the remote

    Returns:
        Value for key (and section) or empty string if it doesn't exist

    Raises:
        PackagingError: When the config path is not specified or found
    """
    # Use the default packaging config ini from env if not specified
    if remote_cfg_path is None:
        try:
            default_config_path_env = os.environ["PACKAGING_KEYS_CONFIG_PATH"]
        except KeyError as err:
            raise PackagingError("Remote config path not found from env or not specified") from err
        remote_cfg_path = Path(default_config_path_env)
    # Cache config to a function attribute
    if getattr(get_pkg_value, 'cfg_cache', None) is None:
        get_pkg_value.cfg_cache: Dict[Path, ConfigParser] = {}  # type: ignore
    if get_pkg_value.cfg_cache.get(remote_cfg_path, None) is None:  # type: ignore
        try:
            config = _read_remote_config_sftp(remote_cfg_path)
        except RemoteConfigError as err:
            raise RemoteConfigError("Error while receiving config from the server") from err
        get_pkg_value.cfg_cache[remote_cfg_path] = _parse_remote_config(config)  # type: ignore
    # Use the first section if an empty section was specified
    section = section or get_pkg_value.cfg_cache[remote_cfg_path].sections()[0]  # type: ignore
    # Return the value for the key, or an empty string
    return get_pkg_value.cfg_cache[remote_cfg_path].get(section, key, fallback="")  # type: ignore


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(prog="Read values from remote config .ini file")
    subparsers = parser.add_subparsers(dest="command")
    # Subparser for read-remote-env
    p_read_remote = subparsers.add_parser(
        "read-remote-env", help="Read environment value from SFTP remote config"
    )
    p_read_remote.add_argument(
        "--config", dest="config", type=str, default=os.getenv("PACKAGING_KEYS_CONFIG_PATH"),
        help="A file system path on the remote pointing to file to be read"
    )
    p_read_remote.add_argument(
        "--section", type=str, default="packaging", help="The config section within the .ini"
    )
    p_read_remote.add_argument(
        "--key", type=str, required=True, help="The config key within the section"
    )
    # Subparser for fetch-remote-file
    p_fetch_file = subparsers.add_parser(
        "fetch-remote-file", help="Fetch a file from a remote SFTP server"
    )
    p_fetch_file.add_argument(
        "--remote-path", type=str, required=True, help="Remote sftp path e.g. [user@][server:]path"
    )
    p_fetch_file.add_argument(
        "--output-path", type=Path, default=None, help="Local save path for file (default=cwd)"
    )
    # Parse args
    args = parser.parse_args(sys.argv[1:])
    if args.command == "read-remote-env":
        if not all((args.config, args.section, args.key)):
            p_read_remote.print_help(sys.stderr)
            raise SystemExit("Invalid/missing arguments for read-remote-env")
        log.info("%s: '%s'", args.key, get_pkg_value(args.key, args.section, args.config))
    elif args.command == "fetch-remote-file":
        if not args.remote_path:
            p_fetch_file.print_help(sys.stderr)
            raise SystemExit("Missing --remote-path for fetch-remote-file")
        username = None
        hostname = None
        try:
            if "@" in args.remote_path:  # user@server:path
                username, args.remote_path = args.remote_path.split("@")
                hostname, args.remote_path = args.remote_path.split(":")
            elif ":" in args.remote_path:  # server:path
                hostname, args.remote_path = args.remote_path.split(":")
            remote_path = Path(args.remote_path)
        except ValueError:
            p_fetch_file.print_help(sys.stderr)
            raise SystemExit("Invalid --remote-path: Expected [user@][server:]path") from None
        download_remote_file_sftp(
            remote_host=hostname or os.getenv("SFTP_ADDRESS"),
            remote_path=remote_path,
            local_path=args.output_path,
            username=username or os.getenv("SFTP_USER"),
        )
    else:
        parser.print_help(sys.stderr)


if __name__ == "__main__":
    main()
