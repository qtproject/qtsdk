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

"""Update component translations"""

import argparse
import sys
from pathlib import Path

from bldinstallercommon import locate_paths
from logging_util import init_logger
from runner import run_cmd

log = init_logger(__name__, debug_mode=False)


def usage() -> None:
    """Log usage"""
    log.info("Usage: $0 [OPTION]... [PKG_DIR]")
    log.info("Performs linguist operations for component translations.")
    log.info("This script takes only one positional argument [PKG_DIR] which")
    log.info("is a path for the package templates directory to work in.")
    log.info("  -u <path to lupdate>   Updates source strings in existing TS files")
    log.info("  -r <path to lrelease>  Produces QM files out of TS files")


def lupdate(lupdate_path: Path, pkg_root: Path) -> None:
    """
    Updates source strings in existing TS files

    Args:
        lupdate_path: Path to lupdate tool
        pkg_root: Path for the package templates directory containing TS files
    """
    ts_files = locate_paths(pkg_root, ["*.ts"])
    for ts_file in ts_files:
        ts_file_path = Path(ts_file).resolve()
        ts_file_dir = ts_file_path.parent
        log.info("lupdate: %s", str(ts_file_path))
        cmd = [str(lupdate_path), "-locations", "none", "-no-ui-lines", "-no-sort", "-no-obsolete"]
        cmd += [str(ts_file_dir), "-ts", ts_file_path.name]
        run_cmd(cmd=cmd, cwd=ts_file_dir)
    log.info("lupdate: Done")


def lrelease(lrelease_path: Path, pkg_root: Path) -> None:
    """
    Produces QM files out of TS files

    Args:
        lrelease_path: Path to lrelease tool
        pkg_root: Path for the package templates directory containing TS files
    """
    ts_files = locate_paths(pkg_root, ["*.ts"])
    for ts_file in ts_files:
        ts_file_path = Path(ts_file).resolve()
        ts_file_dir = ts_file_path.parent
        locale = ts_file_path.stem
        log.info("lrelease: %s", str(ts_file_path))
        if locale in ("ko", "zh", "untranslated"):
            log.info('Skipping locale "%s": %s', locale, ts_file_path)
            continue
        run_cmd(cmd=[str(lrelease_path), str(ts_file_path)], cwd=ts_file_dir)
        package_xml = ts_file_dir / "package.xml"
        xml_contents = package_xml.read_text(encoding="utf-8")
        if locale + ".qm" in xml_contents:
            log.info("Translation file '%s.qm' already defined in package.xml", locale)
        else:
            xml_contents = xml_contents.replace("</Package>", "")  # remove </Package> closing tag
            if "Translations" in xml_contents:
                # remove </Translations> closing tag if already contains <Translations>
                xml_contents = xml_contents.replace("</Translations>", "")
                lines = xml_contents.splitlines()
            else:
                lines = xml_contents.splitlines()
                lines.append("  <Translations>")  # append <Translations> tag
            lines.append(f"    <Translation>{locale}.qm</Translation>")
            lines.append("  </Translations>")
            lines.append("</Package>")
            package_xml.unlink()
            with package_xml.open("w", encoding="utf-8") as new_file:
                for line in lines:
                    new_file.write(line)
    log.info("lrelease: Done")


def main() -> None:
    """Main"""
    parser = argparse.ArgumentParser(
        prog="Performs linguist operations for component translations.", add_help=True
    )
    parser.add_argument(
        "-u", dest="lupdate_path", type=Path, required=False, help="Path to lupdate"
    )
    parser.add_argument(
        "-r", dest="lrelease_path", type=Path, required=False, help="Path to lrelease"
    )
    parser.add_argument(
        dest="pkg_dir", type=Path, help="Path to package templates directory"
    )
    args = parser.parse_args(sys.argv[1:])
    if args.pkg_dir is None or (args.lupdate_path is None and args.lrelease_path is None):
        usage()
        raise SystemExit(1)
    try:
        pkg_root = args.pkg_dir.resolve(strict=True)
    except OSError as err:
        log.error("The specified package templates directory doesn't exist: %s", str(args.pkg_dir))
        raise SystemExit(1) from err
    if args.lupdate_path is not None:
        lupdate_path = args.lupdate_path.resolve(strict=True)
        lupdate(lupdate_path, pkg_root)
    if args.lrelease_path is not None:
        lrelease_path = args.lrelease_path.resolve(strict=True)
        lrelease(lrelease_path, pkg_root)


if __name__ == "__main__":
    main()
