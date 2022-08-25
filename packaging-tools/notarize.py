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
import asyncio
import sys
from shutil import which
from subprocess import PIPE, STDOUT, CalledProcessError, TimeoutExpired
from time import gmtime, sleep, strftime
from typing import List

from logging_util import init_logger
from read_remote_config import get_pkg_value

if sys.version_info < (3, 7):
    from asyncio_backport import run as asyncio_run
else:
    from asyncio import run as asyncio_run

log = init_logger(__name__, debug_mode=False)


class NotarizationError(Exception):
    pass


def parse_value_from_data(key: str, data: str) -> str:
    for line in data.split("\n"):
        if line.strip().startswith(key):
            return line.split(key)[-1].strip()
    return ""


async def request_cmd(timeout: float, cmd: List[str]) -> str:
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=STDOUT)
    attempts = 3

    while attempts:
        try:
            data = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            break
        except (asyncio.TimeoutError, TimeoutExpired):
            log.warning("Timeout (%ss)", str(timeout))
            attempts -= 1
            if attempts:
                log.info("Waiting a bit before next attempt..")
                await asyncio.sleep(60)
        except CalledProcessError as command_err:
            log.critical("Failed to run command: %s", str(command_err))
            raise
        except Exception as error:
            log.critical("Something failed: %s", str(error))
            raise

    return data[0].decode('utf-8')


async def request_notarization(
    user: str, passwd: str, bundle_id: str, dmg: str, timeout: float
) -> str:
    # long lasting command, it uploads the binary to Apple server
    cmd = ["xcrun", "altool", "-u", user, "-p", passwd, "--notarize-app", "-t", "osx"]
    cmd += ["--primary-bundle-id", bundle_id, "-f", dmg]

    data = await request_cmd(timeout, cmd)
    request_uuid = parse_value_from_data("RequestUUID", data)
    if not request_uuid:
        raise NotarizationError(f"Failed to notarize app:\n\n{data}")
    return request_uuid.split("=")[-1].strip()


async def poll_notarization_completed(
    user: str, passwd: str, dmg: str, timeout: float, uuid: str
) -> bool:
    cmd = ["xcrun", "altool", "-u", user, "-p", passwd, "--notarization-info", uuid]

    attempts = 180
    poll_interval = 60  # attempts * poll_interval = 3h
    while attempts:
        data = await request_cmd(timeout, cmd)
        status_code = parse_value_from_data("Status Code:", data)

        if status_code == "0":
            log.info("Notarization succeeded for: %s", dmg)
            log.info("%s", data)
            return True
        if status_code == "2":
            log.info("Notarization failed for: %s", dmg)
            raise NotarizationError(f"Notarization failed:\n\n{data}")
        log.info("Notarization not ready yet for: %s", dmg)
        log.info("%s", data)

        attempts -= 1
        log.info("Sleeping %is before next poll attempt (attempts left: %i)", poll_interval, attempts)
        await asyncio.sleep(poll_interval)

    log.warning("Notarization poll timeout..")
    return False


async def embed_notarization(dmg: str, timeout: float) -> None:
    # Embed the notarization in the dmg package
    cmd = ["xcrun", "stapler", "staple", dmg]
    retry_count = 10
    delay: float = 60
    while retry_count:
        retry_count -= 1
        data = await request_cmd(timeout, cmd)
        status = parse_value_from_data("The staple and validate action", data)

        if status.lower().startswith("worked"):
            log.info("The [%s] was notirized successfully!", dmg)
            break

        log.error("Failed to 'staple' the %s - Reason:\n\n%s", dmg, data)

        if retry_count:
            log.warning("Trying again after %ss", delay)
            sleep(delay)
            delay = delay + delay / 2  # 60, 90, 135, 202, 303
        else:
            log.critical("Execution of the remote script probably failed!")
            raise NotarizationError(f"Failed to 'staple' the: {dmg}")


async def notarize(
    dmg: str,
    user: str = "",
    passwd: str = "",
    bundle_id: str = strftime("%Y-%m-%d-%H-%M-%S", gmtime()),
    timeout: float = 60 * 60 * 3,
) -> None:
    """Notarize"""
    user = user or get_pkg_value("AC_USERNAME")
    passwd = passwd or get_pkg_value("AC_PASSWORD")
    uuid = await request_notarization(user, passwd, bundle_id, dmg, timeout)
    if not await poll_notarization_completed(user, passwd, dmg, timeout, uuid):
        raise NotarizationError(f"Notarization failed for: {dmg}")
    await embed_notarization(dmg, timeout)


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(prog="Helper script to notarize given macOS disk image (.dmg)")
    parser.add_argument("--dmg", dest="dmg", required=True, type=str, help=".dmg file")
    parser.add_argument("--user", dest="user", type=str, default=get_pkg_value("AC_USERNAME"), help="App Store Connect Username")
    parser.add_argument("--passwd", dest="passwd", type=str, default=get_pkg_value("AC_PASSWORD"), help="App Store Connect Password")
    parser.add_argument("--bundle-id", dest="bundle_id", default=strftime('%Y-%m-%d-%H-%M-%S', gmtime()), type=str, help="Give unique id for this bundle")
    parser.add_argument("--timeout", dest="timeout", type=int, default=60 * 60 * 3, help="Timeout value for the remote requests")
    args = parser.parse_args(sys.argv[1:])

    if not which("xcrun"):
        raise SystemExit("Could not find 'xcrun' from the system for notarization. Aborting..")

    asyncio_run(
        notarize(
            dmg=args.dmg,
            user=args.user,
            passwd=args.passwd,
            bundle_id=args.bundle_id,
            timeout=args.timeout,
        )
    )


if __name__ == "__main__":
    main()
