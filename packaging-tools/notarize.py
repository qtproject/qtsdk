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
import logging
import sys
from shutil import which
from subprocess import STDOUT, CalledProcessError, TimeoutExpired
from time import gmtime, sleep, strftime

from read_remote_config import get_pkg_value

LOG_FMT_CI = "%(asctime)s %(levelname)s:%(filename)s:%(lineno)d(%(process)d): %(message)s"
log = logging.getLogger("Notarizer")
log.setLevel(logging.INFO)
# Unify format of all messages
try:
    from rainbow_logging_handler import RainbowLoggingHandler  # type: ignore
    handler = RainbowLoggingHandler(sys.stderr, color_asctime=(None, None, False))
except ImportError:
    handler = logging.StreamHandler()

formatter = logging.Formatter(LOG_FMT_CI)
handler.setFormatter(formatter)
log.addHandler(handler)


class NotarizationError(Exception):
    pass


def parseValueFromData(key, data):
    for line in data.split("\n"):
        if line.strip().startswith(key):
            return line.split(key)[-1].strip()
    return ""


async def requestCmd(args, cmd):
    p = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=STDOUT)
    attempts = 3

    while attempts:
        try:
            data = await asyncio.wait_for(p.communicate(), timeout=args.timeout)
            break
        except (asyncio.TimeoutError, TimeoutExpired):
            log.warning("Timeout (%ss)", str(args.timeout))
            attempts -= 1
            if attempts:
                log.info("Waiting a bit before next attempt..")
                await asyncio.sleep(60)
        except CalledProcessError as commandErr:
            log.critical("Failed to run command: %s", str(commandErr))
            raise
        except Exception as e:
            log.critical("Something failed: %s", str(e))
            raise

    return data[0].decode('utf-8')


async def requestNotarization(args):
    # long lasting command, it uploads the binary to Apple server
    cmd = ['xcrun', 'altool', '-u', args.user, '-p', args.passwd, '--notarize-app', '-t', 'osx']
    cmd += ['--primary-bundle-id', args.bundle_id, '-f', args.dmg]

    data = await requestCmd(args, cmd)
    requestUUID = parseValueFromData("RequestUUID", data)
    if not requestUUID:
        raise NotarizationError(f"Failed to notarize app:\n\n{data}")
    return requestUUID.split("=")[-1].strip()


async def pollNotarizationCompleted(args, uuid):
    cmd = ['xcrun', 'altool', '-u', args.user, '-p', args.passwd, '--notarization-info', uuid]

    attempts = 180
    pollInterval = 60  # attempts * pollInterval = 3h
    while attempts:
        data = await requestCmd(args, cmd)
        statusCode = parseValueFromData("Status Code:", data)

        if statusCode == "0":
            log.info("Notarization succeeded for: %s", args.dmg)
            log.info("%s", data)
            return True
        if statusCode == "2":
            log.info("Notarization failed for: %s", args.dmg)
            raise NotarizationError(f"Notarization failed:\n\n{data}")
        log.info("Notarization not ready yet for: %s", args.dmg)
        log.info("%s", data)

        attempts -= 1
        log.info("Sleeping %is before next poll attempt (attempts left: %i)", pollInterval, attempts)
        await asyncio.sleep(pollInterval)

    log.warning("Notarization poll timeout..")
    return False


async def embedNotarization(args):
    # Embed the notarization in the dmg package
    cmd = ['xcrun', 'stapler', 'staple', args.dmg]
    retry_count = 10
    delay = 60
    while retry_count:
        retry_count -= 1
        data = await requestCmd(args, cmd)
        status = parseValueFromData("The staple and validate action", data)

        if status.lower().startswith("worked"):
            log.info("The [%s] was notirized successfully!", args.dmg)
            break

        log.error("Failed to 'staple' the %s - Reason:\n\n%s", args.dmg, data)

        if retry_count:
            log.warning("Trying again after %ss", delay)
            sleep(delay)
            delay = delay + delay / 2  # 60, 90, 135, 202, 303
        else:
            log.critical("Execution of the remote script probably failed!")
            raise NotarizationError(f"Failed to 'staple' the: {args.dmg}")


async def main(args):
    uuid = await requestNotarization(args)
    if not await pollNotarizationCompleted(args, uuid):
        raise NotarizationError(f"Notarization failed for: {args.dmg}")
    await embedNotarization(args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Helper script to notarize given macOS disk image (.dmg)")
    parser.add_argument("--dmg", dest="dmg", required=True, type=str, help=".dmg file")
    parser.add_argument("--user", dest="user", type=str, default=get_pkg_value("AC_USERNAME"), help="App Store Connect Username")
    parser.add_argument("--passwd", dest="passwd", type=str, default=get_pkg_value("AC_PASSWORD"), help="App Store Connect Password")
    parser.add_argument("--bundle-id", dest="bundle_id", default=strftime('%Y-%m-%d-%H-%M-%S', gmtime()), type=str, help="Give unique id for this bundle")
    parser.add_argument("--timeout", dest="timeout", type=int, default=60 * 60 * 3, help="Timeout value for the remote requests")
    args = parser.parse_args(sys.argv[1:])

    if not which("xcrun"):
        log.error("Could not find 'xcrun' from the system. This tool is needed for notarization. Aborting..")
        sys.exit(1)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(args))
