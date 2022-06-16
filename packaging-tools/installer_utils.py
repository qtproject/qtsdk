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
import wget
import fnmatch
from contextlib import contextmanager
from urllib.parse import urlparse
from typing import Generator, List
from logging_util import init_logger
from runner import async_exec_cmd

log = init_logger(__name__, debug_mode=False)


class PackagingError(Exception):
    pass


@contextmanager
def cd(path: str) -> Generator:
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


def download_archive(url: str, destDir: str) -> str:
    parts = urlparse(url)
    fileName = os.path.basename(parts.path)
    destFile = os.path.join(destDir, fileName)
    if os.path.isfile(destFile):
        log.info("Using existing downloaded file: %s", destFile)
    else:
        wget.download(url, destFile)
    return destFile


def get_extract_cmd(artifact: str) -> List[str]:
    if artifact.endswith(".7z") or artifact.endswith(".zip"):
        return ['7z', 'x', artifact]
    elif any(fnmatch.fnmatch(artifact, p) for p in ["*.tar*", "*.tgz"]):
        return ['tar', '-xf', artifact]
    else:
        raise PackagingError("Could not find suitable extractor for: {0}".format(artifact))


async def extract_archive(artifact: str, destinationDir: str) -> None:
    log.info("Extracting file: %s into: %s", artifact, destinationDir)
    extractCmd = get_extract_cmd(artifact)
    try:
        os.makedirs(destinationDir, exist_ok=True)
        with cd(destinationDir):
            await async_exec_cmd(extractCmd)
    except Exception:
        log.exception("Could not extact a file %s to %s", artifact, destinationDir)
        raise
