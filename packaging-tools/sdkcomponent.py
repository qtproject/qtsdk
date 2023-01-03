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

import asyncio
import os
import re
import sys
from configparser import ConfigParser
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import htmllistparse  # type: ignore
from urlpath import URL  # type: ignore

from bldinstallercommon import uri_exists
from logging_util import init_logger

if sys.version_info < (3, 7):
    from asyncio_backport import run as asyncio_run
else:
    from asyncio import run as asyncio_run


log = init_logger(__name__, debug_mode=False)


class IfwSdkError(Exception):
    """Exception class for IfwSdkComponent errors"""


@dataclass
class IfwPayloadItem:
    """Payload item class for IfwSdkComponent's archives"""

    package_name: str
    archive_uri: str
    archive_action: Optional[Tuple[Path, str]]
    disable_extract_archive: bool
    package_strip_dirs: int
    package_finalize_items: str
    parent_target_install_base: str
    arch_target_install_base: str
    arch_target_install_dir: str
    rpath_target: str
    component_sha1: str
    archive_name: str
    errors: List[str] = field(default_factory=list)
    # List of archive formats supported by Installer Framework:
    ifw_arch_formats: Tuple[str, ...] = (".7z", ".tar", ".gz", ".zip", ".xz", ".bz2")
    # List of payload archive formats supported by scripts for extraction:
    supported_arch_formats: Tuple[str, ...] = (".7z", ".tar", ".gz", ".zip", ".xz", ".bz2")
    _requires_extraction: Optional[bool] = None
    _requires_patching: Optional[bool] = None

    def __post_init__(self) -> None:
        """Post init: run sanity checks"""
        assert self.package_name, "The 'package_name' was not set?"
        self.archive_name = self._ensure_ifw_archive_name()
        self._sanity_check()

    def _sanity_check(self) -> None:
        """Perform a sanity check on the payload archive configuration and append the errors"""
        if self.archive_action:
            script_path, _ = self.archive_action
            if not script_path.exists() and script_path.is_file():
                self.errors += [f"Unable to locate custom archive action script: {script_path}"]
        if not self.archive_uri:
            self.errors += [f"[{self.package_name}] is missing 'archive_uri'"]
        if self.package_strip_dirs is None:
            self.errors += [f"[{self.package_name}] is missing 'package_strip_dirs'"]
        if not self.archive_uri.endswith(self.supported_arch_formats) and self.requires_patching:
            if self.package_strip_dirs != 0:
                self.errors += [f"[{self.package_name}] package_strip_dirs!=0 for a non-archive"]
            if self.package_finalize_items:
                self.errors += [f"[{self.package_name}] package_finalize_items for a non-archive"]

    def validate(self) -> None:
        """
        Validate IfwPayloadItem, log the errors

        Raises:
            IfwSdkError: If there are errors in the payload item
        """
        log.info("[[%s]] - %s", self.package_name, "NOK" if self.errors else "OK")
        if self.errors:
            for err in self.errors:
                log.error(err)
            log.debug(self)  # Log also the details of the payload item with errors
            raise IfwSdkError(
                f"[[{self.package_name}]] Invalid payload configuration - check your configs!"
            )

    def validate_uri(self) -> None:
        """Validate that the uri location exists either on the file system or online"""
        log.info("[%s] Checking payload uri: %s", self.package_name, self.archive_uri)
        if not uri_exists(self.archive_uri):
            raise IfwSdkError(f"[{self.package_name}] Missing payload {self.archive_uri}")

    def _ensure_ifw_archive_name(self) -> str:
        """
        Get the archive name by splitting from its uri if a name doesn't already exist

        Returns:
            Name for the payload item
        """
        archive_name: str = self.archive_name or Path(self.archive_uri).name
        # make sure final archive format is supported by IFW (default: .7z)
        if not archive_name.endswith(self.ifw_arch_formats):
            archive_name += ".7z"
        return archive_name

    def get_archive_install_dir(self) -> Path:
        """
        Resolve archive install directory relative to root install directory based on config
        If does not exist in config, uses root install directory

        Returns:
            Resolved install directory for the archive
        """
        # Prioritizes archive's install base dir over parent's install base dir
        install_base = self.arch_target_install_base or self.parent_target_install_base
        # Join archive's install dir to install base dir
        return Path(install_base.strip(r"\/"), self.arch_target_install_dir.strip(r"\/"))

    @property
    def requires_patching(self) -> bool:
        """
        A property to determine whether the payload content needs to be patched.
        The value is calculated once and saved to _requires_patching.

        Returns:
            A boolean for whether patching the payload is needed.
        """
        if self._requires_patching is None:
            self._requires_patching = not (
                self.package_strip_dirs == 0
                and not self.package_finalize_items
                and not self.archive_action
                and not self.rpath_target
                and self.get_archive_install_dir() == Path(".")
            )
        return self._requires_patching

    @property
    def requires_extraction(self) -> bool:
        """
        A property to determine whether the archive needs to be extracted.
        The value is calculated once and saved to _requires_extraction.

        Returns:
            A boolean for whether extracting the payload is needed.
        """
        if self._requires_extraction is None:
            if self.archive_uri.endswith(self.ifw_arch_formats):
                # Extract IFW supported archives if patching required or archive has a sha1 file
                # Otherwise, use the raw CI artifact
                self._requires_extraction = bool(self.component_sha1) or self.requires_patching
                # If archive extraction is disabled, compress as-is (disable_extract_archive=False)
                if self.disable_extract_archive:
                    self._requires_extraction = False
            elif self.archive_uri.endswith(self.supported_arch_formats):
                # Repack supported archives to IFW friendly archive format
                self._requires_extraction = True
            else:
                # Payload not a supported archive type, use as-is
                self._requires_extraction = False
        return self._requires_extraction

    def __str__(self) -> str:
        return f"""
- Final payload archive name: {self.archive_name}
  Source payload URI: {self.archive_uri}
  Extract archive: {self.requires_extraction}
  Patch payload: {self.requires_patching}""" + (
            f""", config:
    Strip package dirs: {self.package_strip_dirs}
    Finalize items: {self.package_finalize_items}
    Action script: {self.archive_action}
    RPath target: {self.rpath_target}
    Target install dir: {str(self.get_archive_install_dir())}"""
            if self.requires_patching else ""
        )


class ArchiveResolver:
    """Resolver class for archive payload uris"""

    def __init__(self, file_share_base_url: str, pkg_template_folder: str) -> None:
        self.file_share_base_url = file_share_base_url
        self.pkg_template_folder = pkg_template_folder

    def absolute_url(self, url: str) -> str:
        """
        Append the given URL to resolver's file_share_base_url if doesn't start with http

        Args:
            url: A URL to check and convert if necessary

        Returns:
            An absolute URL starting with the file_share_base_url or the original absolute URL
        """
        if not url.startswith("http"):
            return self.file_share_base_url.rstrip("/") + "/" + url.lstrip("/")
        return url

    async def fetch_in_executor(self, url: str) -> Tuple[Any, List[Any]]:
        """Wrap fetch_listing in a Future and return it"""
        if sys.version_info < (3, 7):
            loop = asyncio.get_event_loop()  # keep for Python 3.6 compatibility
        else:
            loop = asyncio.get_running_loop()
        log.info("Crawl: %s", url)
        return await loop.run_in_executor(None, htmllistparse.fetch_listing, url, 30)

    async def resolve_uri_pattern(self, pattern: str, base_url: Optional[URL] = None) -> List[URL]:
        """
        Return payload URIs from remote tree, fnmatch pattern match for given arguments.
        Patterns will match arbitrary number of '/' allowing recursive search.

        Args:
            pattern: A fnmatch pattern starting with an absolute URL e.g. "http://foo.bar/dir/*"
            base_url: For recursive runs, specify the child directory to crawl

        Returns:
            The final list of matching URIs
        """
        # split base pattern from pattern (fnmatch chars *,[,],?)
        base_pattern = re.split(r'[\*\[\]\?]', pattern)[0]
        # base_url from base_pattern if not specified
        base_url = base_url or URL(base_pattern.rsplit("/", 1)[0])
        # get links from base_url
        _, links = await self.fetch_in_executor(base_url)
        # get fnmatch pattern matches from links recursively
        uri_list = []
        child_list = []
        for link in links:
            if link.name.endswith("/"):
                # match the directory with base_pattern
                if fnmatch(base_url / link.name, base_pattern + "*"):
                    child_list.append(base_url / link.name)
            else:
                if fnmatch(base_url / link.name, pattern):
                    uri_list.append(base_url / link.name)
        # recursively look for pattern matches inside the matching child directories
        coros = [self.resolve_uri_pattern(pattern, url) for url in child_list]
        results = await asyncio.gather(*coros)
        for item in results:
            uri_list.extend(item)
        return uri_list

    def resolve_payload_uri(self, unresolved_archive_uri: str) -> List[str]:
        """
        Resolves the given archive URI and resolves it based on the type of URI given
        Available URI types, in the order of priority:
            - fnmatch pattern for absolute or relative URL (recursive)
            - file system string paths, file system URIs and network locations e.g. HTTP URLs
            - file system string paths relative to data folder under package template root
            - network locations relative to file_share_base_url

        Args:
            unresolved_archive_uri: Original URI to resolve

        Returns:
            A resolved URI location for the payload
        """
        # is it a URL containing a fnmatch pattern
        if any(char in unresolved_archive_uri for char in ("*", "[", "]", "?")):
            pattern = self.absolute_url(unresolved_archive_uri)
            return [str(url) for url in asyncio_run(self.resolve_uri_pattern(pattern))]
        # is it a file system path or an absolute URL which can be downloaded
        if os.path.exists(unresolved_archive_uri) or URL(unresolved_archive_uri).netloc:
            return [unresolved_archive_uri]
        # is it relative to pkg template root dir, under the 'data' directory
        pkg_data_dir = os.path.join(self.pkg_template_folder, "data", unresolved_archive_uri)
        if os.path.exists(pkg_data_dir):
            return [pkg_data_dir]
        # ok, we assume this is a URL which can be downloaded
        return [self.absolute_url(unresolved_archive_uri)]


@dataclass
class IfwSdkComponent:
    """Installer framework sdk component class"""

    ifw_sdk_comp_name: str
    pkg_template_folder: str
    archive_resolver: ArchiveResolver
    downloadable_archives: List[IfwPayloadItem]
    archives_extract_dir: str
    target_install_base: str
    version: str
    version_tag: str
    package_default: str
    comp_sha1_uri: str
    include_filter: str
    component_sha1: Optional[str] = None
    temp_data_dir: Optional[Path] = None
    meta_dir_dest: Optional[Path] = None
    archive_skip: bool = False

    def __post_init__(self) -> None:
        """Post init: resolve component sha1 uri if it exists"""
        if self.comp_sha1_uri:
            match_uris = self.archive_resolver.resolve_payload_uri(self.comp_sha1_uri)
            assert len(match_uris) == 1, f"More than one match for component sha: {match_uris}"
            self.comp_sha1_uri = match_uris.pop()

    def validate(self, uri_check: bool = True, ignore_errors: bool = False) -> bool:
        """
        Perform validation on IfwSdkComponent, raise error if component not valid

        Args:
            uri_check: Whether to check that component's payload URIs are available
            ignore_errors: Does not raise caught errors

        Raises:
            AssertionError: When the component's package name doesn't exist
            IfwSdkError: When component with payload doesn't have target install base configured
        """
        try:
            assert self.ifw_sdk_comp_name, "Undefined package name?"
            if self.downloadable_archives and not self.target_install_base:
                raise IfwSdkError(f"[{self.ifw_sdk_comp_name}] is missing 'target_install_base'")
            if uri_check:
                for archive in self.downloadable_archives:
                    archive.validate_uri()
            return True
        except IfwSdkError as err:
            if not ignore_errors:
                raise
            log.exception("[%s] Ignored error in component: %s", self.ifw_sdk_comp_name, err)
        return False

    def generate_downloadable_archive_list(self) -> List[List[str]]:
        """
        Generate list that is embedded into package.xml

        Returns:
            Generated downloaded archive list
        """
        archive_list: List[str] = [a.archive_name for a in self.downloadable_archives]
        return [["<!--ONLINE_ARCHIVE_LIST-->", ", ".join(archive_list)]]

    def __str__(self) -> str:
        print_data = f"""
[{self.ifw_sdk_comp_name}]
Include filter:      {self.include_filter}
Target install base: {self.target_install_base}
Version:             {self.version}
Version tag:         {self.version_tag}
Package default:     {self.package_default}
Archives:"""
        for archive in self.downloadable_archives:
            print_data += str(archive)
        return print_data


class ConfigSubst:
    """Configuration file key substitutor and resolver"""

    def __init__(self, config: ConfigParser, section: str, substitutions: Dict[str, str]) -> None:
        if not config.has_section(section):
            raise IfwSdkError(f"Missing section in configuration file: {section}")
        self.config = config
        self.section = section
        self.substitutions: Dict[str, str] = substitutions
        self.resolved: Dict[str, str] = {}

    def get(self, key: str, default: str = "") -> str:
        """
        Perform substitutions for the given key and return resolved key value.
        The values are saved to self.resolved for future lookups.

        Args:
            key: The key to look up from already resolved dict or to resolve
            default: This value is used when key not found from config section

        Returns:
            A string value for the key or the given default (default=empty string)

        Raises:
            KeyError: When value for given key doesn't exist yet, handled
        """
        try:
            return self.resolved[key]
        except KeyError:
            tmp = self.config[self.section].get(key, default)
            for subst_key, subst_value in self.substitutions.items():
                tmp = tmp.replace(subst_key, subst_value)
                self.resolved[key] = tmp
        return self.resolved[key]


def locate_pkg_templ_dir(search_dirs: List[str], component_name: str) -> str:
    """
    Return one result for given component name from given search directories or fail

    Args:
        search_dirs: The list of string file system paths for the directories to look from
        component_name: The component's directory name to match for

    Returns:
        A matching file system string path to a component's template folder

    Raises:
        IfwSdkError: When there are more than one matches
    """
    # look up correct package template directory from list
    log.info("Searching pkg template '%s' folder from: %s", component_name, search_dirs)
    matches: List[str] = []
    for item in search_dirs:
        matches.extend([str(p) for p in Path(item).resolve(strict=True).rglob(component_name)])
    if len(matches) < 1:
        raise IfwSdkError(f"Expected to find one result for '{component_name}' from {search_dirs}")
    return matches.pop()


def parse_ifw_sdk_comp(
    config: ConfigParser,
    section: str,
    pkg_template_search_dirs: List[str],
    substitutions: Dict[str, str],
    file_share_base_url: str,
) -> IfwSdkComponent:
    """
    Parse IfwSdkComponent from the given config

    Args:
        config: The given config to parse via ConfigParser
        section: The section name for the component
        pkg_template_search_dirs: Paths that should contain the template folder for the component
        substitutions: String substitutions to apply for the config/template while parsing
        file_share_base_url: URL to the file share server containing the payload content

    Returns:
        An instance of the parsed IfwSdkComponent
    """
    log.info("Parsing section: %s", section)
    config_subst = ConfigSubst(config, section, substitutions)
    pkg_template_folder = locate_pkg_templ_dir(pkg_template_search_dirs, component_name=section)
    archive_resolver = ArchiveResolver(file_share_base_url, pkg_template_folder)
    archives = config[section].get("archives", "")
    archive_sections = [s.strip() for s in archives.split(",") if s.strip() != ""]
    archives_extract_dir = config_subst.get("archives_extract_dir")
    target_install_base = config_subst.get("target_install_base", "")
    version = config_subst.get("version")
    version_tag = config_subst.get("version_tag")
    package_default = config_subst.get("package_default", "false")
    comp_sha1_uri = config_subst.get("component_sha1_uri", "")
    include_filter = config_subst.get("include_filter")
    parsed_archives = parse_ifw_sdk_archives(
        config=config,
        archive_sections=archive_sections,
        archive_resolver=archive_resolver,
        parent_target_install_base=target_install_base,
        substitutions=substitutions,
    )
    return IfwSdkComponent(
        ifw_sdk_comp_name=section,
        pkg_template_folder=pkg_template_folder,
        archive_resolver=archive_resolver,
        downloadable_archives=parsed_archives,
        archives_extract_dir=archives_extract_dir,
        target_install_base=target_install_base,
        version=version,
        version_tag=version_tag,
        package_default=package_default,
        comp_sha1_uri=comp_sha1_uri,
        include_filter=include_filter,
    )


def parse_ifw_sdk_archives(
    config: ConfigParser,
    archive_sections: List[str],
    archive_resolver: ArchiveResolver,
    parent_target_install_base: str,
    substitutions: Dict[str, str],
) -> List[IfwPayloadItem]:
    """
    Parsed IfwPayloadItems for the given payload sections in config

    Args:
        config: The config containing the payload sections via ConfigParser
        archive_sections: The payload sections for the component
        archive_resolver: The resolver to use for payload URIs
        parent_target_install_base: The parent component's root install folder
        substitutions: The string substitutions to apply while parsing config/templates

    Returns:
        A list of parsed IfwPayloadItems for the component
    """
    parsed_archives = []
    for arch_section_name in archive_sections:
        config_subst = ConfigSubst(config, arch_section_name, substitutions)
        unresolved_archive_uri = config_subst.get("archive_uri")
        resolved_uris = archive_resolver.resolve_payload_uri(unresolved_archive_uri)
        archive_action_string = config_subst.get("archive_action", "")
        archive_action: Optional[Tuple[Path, str]] = None
        if archive_action_string:
            script_path, script_args = archive_action_string.split(",")
            archive_action = Path(__file__).parent / script_path, script_args.strip() or ""
        disable_extract_archive = bool(
            config_subst.get("disable_extract_archive", "no").lower() in ["yes", "true", "1"]
        )
        package_strip_dirs = int(config_subst.get("package_strip_dirs") or 0)
        package_finalize_items = config_subst.get("package_finalize_items")
        # in case the individual archive needs to be installed outside the root dir specified by
        # the parent component
        target_install_base = config_subst.get("target_install_base", "")
        # this is relative to:
        # 1) current archive's 'target_install_base'
        # 2) parent components 'target_install_base'. (1) takes priority
        target_install_dir = config_subst.get("target_install_dir", "")
        rpath_target = config_subst.get("rpath_target")
        if rpath_target and not rpath_target.startswith(os.sep):
            rpath_target = os.sep + rpath_target
        component_sha1_file = config_subst.get("component_sha1_file")
        archive_name = config_subst.get("archive_name")
        for resolved_archive_uri in resolved_uris:
            payload = IfwPayloadItem(
                package_name=arch_section_name,
                archive_uri=resolved_archive_uri,
                archive_action=archive_action,
                disable_extract_archive=disable_extract_archive,
                package_strip_dirs=package_strip_dirs,
                package_finalize_items=package_finalize_items,
                parent_target_install_base=parent_target_install_base,
                arch_target_install_base=target_install_base,
                arch_target_install_dir=target_install_dir,
                rpath_target=rpath_target,
                component_sha1=component_sha1_file,
                archive_name=archive_name,
            )
            payload.validate()
            parsed_archives.append(payload)
    return parsed_archives
