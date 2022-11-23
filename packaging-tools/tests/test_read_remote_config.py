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

import unittest
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

from cryptography.fernet import Fernet
from ddt import data, ddt, unpack  # type: ignore
from paramiko import RSAKey

from installer_utils import PackagingError
from read_remote_config import _decrypt_private_key, get_pkg_value


def get_packaging_ini(_: Any) -> str:
    return """
    [foo_section]
    foo=foo
    [packaging]
    foo=foobar
    [bar_section]
    bar=bar
    """


@ddt
class TestRemoteConfig(unittest.TestCase):

    def test_decrypt_private_key(self) -> None:
        decrypt_key = Fernet.generate_key()
        rsa_key = RSAKey.generate(bits=1024)
        rsa_secret = StringIO()
        rsa_key.write_private_key(rsa_secret)
        rsa_secret.seek(0)
        encrypted_secret = Fernet(decrypt_key).encrypt(bytes(rsa_secret.read(), encoding="utf-8"))
        result = _decrypt_private_key(key=encrypted_secret, decrypt_key=decrypt_key)
        self.assertEqual(result, rsa_key)

    def test_decrypt_private_key_invalid_secret(self) -> None:
        decrypt_key = Fernet.generate_key()
        encrypted_secret = Fernet(decrypt_key).encrypt(b"")
        with self.assertRaises(PackagingError):
            _decrypt_private_key(key=encrypted_secret, decrypt_key=decrypt_key)

    def test_decrypt_private_key_invalid_token(self) -> None:
        decrypt_key = Fernet.generate_key()
        with self.assertRaises(PackagingError):
            _decrypt_private_key(key=b"", decrypt_key=decrypt_key)

    def test_decrypt_private_key_invalid_fernet_key(self) -> None:
        with self.assertRaises(ValueError):
            _decrypt_private_key(key=b"", decrypt_key=b"")

    @data(  # type: ignore
        ("missing", "missing", ""),
        ("packaging", "missing", ""),
        ("", "foo", "foo"),
        ("packaging", "foo", "foobar"),
        ("foo_section", "foo", "foo"),
        ("bar_section", "bar", "bar"),
    )
    @unpack  # type: ignore
    @patch(
        "read_remote_config._read_remote_config_sftp", side_effect=get_packaging_ini
    )
    def test_get_pkg_value(self, section: str, key: str, expected_result: str, _: Any) -> None:
        result = get_pkg_value(key=key, section=section, remote_cfg_path=Path())
        self.assertEqual(result, expected_result)


if __name__ == '__main__':
    unittest.main()
