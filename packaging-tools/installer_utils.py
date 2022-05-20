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
from contextlib import contextmanager
from fnmatch import fnmatch
from typing import Any, Generator, List
from urllib.parse import urlparse

import wget  # type: ignore

from logging_util import init_logger
from runner import run_cmd

log = init_logger(__name__, debug_mode=False)


class PackagingError(Exception):
    pass


@contextmanager
def ch_dir(path: str) -> Generator[Any, Any, Any]:
    oldwd = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(oldwd)


def is_valid_url_path(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc, result.path])
    except Exception:
        return False


def download_archive(url: str, dest_dir: str) -> str:
    parts = urlparse(url)
    file_name = os.path.basename(parts.path)
    dest_file = os.path.join(dest_dir, file_name)
    if os.path.isfile(dest_file):
        log.info("Using existing downloaded file: %s", dest_file)
    else:
        wget.download(url, dest_file)
    return dest_file


def get_extract_cmd(artifact: str) -> List[str]:
    if artifact.endswith(".7z") or artifact.endswith(".zip"):
        return ['7z', 'x', artifact]
    if any(fnmatch(artifact, p) for p in ["*.tar*", "*.tgz"]):
        return ['tar', '-xf', artifact]
    raise PackagingError(f"Could not find suitable extractor for: {artifact}")


async def extract_archive(artifact: str, destination_dir: str) -> None:
    log.info("Extracting file: %s into: %s", artifact, destination_dir)
    extract_cmd = get_extract_cmd(artifact)
    try:
        os.makedirs(destination_dir, exist_ok=True)
        with ch_dir(destination_dir):
            run_cmd(cmd=extract_cmd)
    except Exception:
        log.exception("Could not extact a file %s to %s", artifact, destination_dir)
        raise
