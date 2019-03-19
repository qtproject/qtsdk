#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2019 The Qt Company Ltd.
## Contact: https://www.qt.io/licensing/
##
## This file is part of the release tools of the Qt Toolkit.
##
## $QT_BEGIN_LICENSE:GPL-EXCEPT$
## Commercial License Usage
## Licensees holding valid commercial Qt licenses may use this file in
## accordance with the commercial license agreement provided with the
## Software or, alternatively, in accordance with the terms contained in
## a written agreement between you and The Qt Company. For licensing terms
## and conditions see https://www.qt.io/terms-conditions. For further
## information use the contact form at https://www.qt.io/contact-us.
##
## GNU General Public License Usage
## Alternatively, this file may be used under the terms of the GNU
## General Public License version 3 as published by the Free Software
## Foundation with exceptions as appearing in the file LICENSE.GPL3-EXCEPT
## included in the packaging of this file. Please review the following
## information to ensure the GNU General Public License requirements will
## be met: https://www.gnu.org/licenses/gpl-3.0.html.
##
## $QT_END_LICENSE$
##
#############################################################################

import os
import sys
import argparse
import shutil
import tempfile
import multiprocessing
import re
import sh
from glob import glob
import distutils.dir_util
from distutils.errors import DistutilsFileError
from bldinstallercommon import retrieve_url, extract_file
from urllib2 import Request, urlopen
from bs4 import BeautifulSoup
from remote_uploader import RemoteUploader

qtLocationDir = "qtlocation"
qtPositioningDir = "qtpositioning"
geoservicesDir = "geoservices"
geoLocationHeaders = ['QGeoLocation',
                      'qgeolocation.h',
                      'qdeclarativegeolocation_p.h',
                      'qlocationutils_p.h',
                      'qgeolocation_p.h']

iOSQtLocationOnly = ['qt_plugin_qtgeoservices_nokia.pri',
                     'qt_plugin_qtgeoservices_osm.pri',
                     'qt_plugin_qtgeoservices_mapbox.pri',
                     'libpoly2tri_debug.a',
                     'libpoly2tri_iphonesimulator.prl',
                     'libpoly2tri_iphonesimulator.a',
                     'libpoly2tri_iphonesimulator_debug.prl',
                     'libpoly2tri_iphonesimulator_debug.a',
                     'libpoly2tri.a',
                     'libpoly2tri_debug.prl',
                     'libpoly2tri.prl']

qtPositioningOnly = ['qlocationdata_simulator_p.h']

archiver7z = sh.Command(sh.which("7z"))
remoteUploader = None


def qtLocationSplitRequired(artifactUrl):
    if 'qtlocation' in artifactUrl and "5.6" in artifactUrl:
        return True
    return False


def pysideSplitRequired(artifactUrl):
    if 'pyside' in artifactUrl:
        return True
    return False


def splitQtLocation(inputDir, outputDir, configurationName):
    print("Splitting QtLocation into qtlocation and qtpositioning: {0}".format(inputDir))
    # create temp directories for location & positioning
    baseTempDir = os.path.abspath(os.path.join(outputDir, os.pardir))
    locationPath = os.path.join(baseTempDir, qtLocationDir)
    positioningPath = os.path.join(baseTempDir, qtPositioningDir)
    os.makedirs(locationPath, exist_ok=True)
    os.makedirs(positioningPath, exist_ok=True)

    print("Copying: [{0}] into: [{1}]".format(inputDir, locationPath))
    shutil.copytree(inputDir, locationPath)
    print("Copying: [{0}] into: [{1}]".format(inputDir, positioningPath))
    shutil.copytree(inputDir, positioningPath)

    originalFileCount = getFileCount(locationPath)
    splitPathList = []

    # remove *qtpositioning* from qt5_qtlocation.7z
    locRegex = re.compile('\.*osition\.*')
    handleCleanup(locRegex, locationPath)
    splitPathList.append(locationPath)
    locFileCount = getFileCount(locationPath)
    # remove *qtlocation* from qt5_qtpositioning.7z
    posRegex = re.compile('\.*ocation\.*')
    handleCleanup(posRegex, positioningPath)
    splitPathList.append(positioningPath)
    posFileCount = getFileCount(positioningPath)

    if not (locFileCount + posFileCount) == originalFileCount:
        raise RuntimeError("qtlocation split failure: file count difference found.")

    results = []  # type: List[Tuple[str, str, str]]
    for pathItem in splitPathList:
        if 'qtlocation' in pathItem:
            finalArchiveName = "qtlocation-" + configurationName + ".7z"
            archiverWorkDir = os.path.join(outputDir, 'qtlocation', 'install')
            results.append((archiverWorkDir, "qtlocation", finalArchiveName))
        elif 'qtpositioning' in pathItem:
            finalArchiveName = "qtpositioning-" + configurationName + ".7z"
            archiverWorkDir = os.path.join(outputDir, 'qtpositioning', 'install')
            results.append((archiverWorkDir, "qtlocation", finalArchiveName))
        else:
            raise RuntimeError("Exiting, QtLocation split failed.")

    for workDir, moduleName, finalArchiveName in results:
        archiveAndUploadToRemote(workDir, finalArchiveName, moduleName)
        print("Project [{0}, {1}] split into: [{2}]".format(moduleName, finalArchiveName, remoteUploader.remoteTargetDir + '/' + moduleName))


def splitPyside(inputDir):
    print("Collecting *.whl from pyside package: {0}".format(inputDir))
    # We should fix the dir name below if we change the package name.
    for pip_file in glob(os.path.join(inputDir, "dist", "*.whl")):
        remoteUploader.copyToRemote(pip_file, "pyside2")


def getFileCount(packagePath):
    return sum([len(files) for r, d, files in os.walk(packagePath)])


def handleCleanup(regExp, pkgLocation):
    print("QtLocation split cleanup: {0}".format(pkgLocation))
    oldwd = os.getcwd()
    try:
        os.chdir(pkgLocation)
        for root, dirs, files in os.walk(pkgLocation):
            for dirName in dirs:
                if regExp.findall(dirName):
                    shutil.rmtree(os.path.join(root, dirName))
                if geoservicesDir in dirName and qtPositioningDir in pkgLocation:
                    shutil.rmtree(os.path.join(root, dirName))
            for fileName in files:
                if regExp.findall(fileName):
                    if os.path.islink(os.path.join(root, fileName)):
                        os.unlink(os.path.join(root, fileName))
                    if os.path.isfile(os.path.join(root, fileName)):
                        if fileName in geoLocationHeaders and qtPositioningDir in pkgLocation:
                            pass
                        elif fileName in qtPositioningOnly and qtPositioningDir in pkgLocation:
                            pass
                        else:
                            print("Removing file: {0}".format(os.path.join(root, fileName)))
                            os.remove(os.path.join(root, fileName))
            # get rid of iOS specific files in QtPositioning
            for fileName in files:
                if fileName in iOSQtLocationOnly and qtPositioningDir in pkgLocation:
                    print("iOS specific QtLocation file, removing: {0}".format(os.path.join(root, fileName)))
                    os.remove(os.path.join(root, fileName))
    except Exception:
        print("Failed to cleanup QtLocation split: {0}".format(pkgLocation))
        raise
    finally:
        os.chdir(oldwd)


def collectDebugSymbolFiles(inputDir, outputDir, configurationName, projectName, platform):
    """Collect debug symbol files to a separate archives."""

    def getDebugFileList(platform, tempWorkDirName):
        fileList = []   # type: List[str]
        if platform == "windows":
            findFiles = ('*.pdb', )
        if platform == "linux":
            findFiles = ('*.debug', )
        if platform == "macos":
            findFiles = ('*.dSYM', )

        # On Windows and Linux debug symbols are distributed as files
        if platform == "windows" or platform == "linux":
            for x in os.walk(tempWorkDirName):
                for file in findFiles:
                    fileList.extend(glob(os.path.join(x[0], file)))

        # On macOS debug symbols are distributed inside folder bundles instead of files
        if platform == "macos":
            for root, dirs, files in os.walk(tempWorkDirName):
                for d in dirs:
                    if d.endswith('dSYM'):
                        fileList.append(os.path.join(root, d))
        return fileList

    files = getDebugFileList(platform, inputDir)
    if not files:
        print("No debug files available for: {0}".format(projectName + "-" + configurationName))
        return

    debugFileArchiveDir = os.path.join(outputDir, configurationName + '-debug-symbols')
    if not os.path.exists(debugFileArchiveDir):
        os.makedirs(debugFileArchiveDir)
    for debugFile in files:
        debugFileInstallRoot = debugFile.split('install')[-1]
        debugDir, file = os.path.split(debugFileInstallRoot)
        finalArchiveDir = os.path.join(debugFileArchiveDir, debugDir.strip('/'))
        if not os.path.exists(finalArchiveDir):
            os.makedirs(finalArchiveDir)
        # There is a bug QTQAINFRA-1959
        # Sometimes the debugFile path is incorrect, causing the export to fail.
        try:
            if platform == "windows" or platform == "linux":
                shutil.copy(debugFile, finalArchiveDir)
            if platform == "macos":
                # Documentation of shutil.copytree explicitly state that destination directory should not exist.
                # But we have multiple *.dSYM folders under same root folder.
                # Therefore we need to use distutils copy_tree and add *.dSYM folder name to target directory.
                finalArchiveDir = os.path.join(finalArchiveDir, os.path.basename(debugFile))
                distutils.dir_util.copy_tree(debugFile, finalArchiveDir)
        except (IOError, DistutilsFileError):
            print("Skipping as can't copy: {0} to: {1}".format(debugFile, finalArchiveDir))
            if not os.path.exists(debugFile):
                print("File does not exist: {0}".format(debugFile))
            if not os.path.exists(finalArchiveDir):
                print("Directory does not exist: {0}".format(finalArchiveDir))
            raise
    finalArchiveName = projectName + "-" + configurationName + '-debug-symbols' + ".7z"
    archiveAndUploadToRemote(debugFileArchiveDir, finalArchiveName, remoteUploader.releaseSymbolsDir.strip('/'))
    shutil.rmtree(debugFileArchiveDir)


def archiveAndUploadToRemote(workDir, archiveName, projectName):
    oldwd = os.getcwd()
    try:
        os.chdir(workDir)
        # Options added for faster compression
        archiver7z('a', '-m0=lzma2', '-mmt=16', archiveName, '*')
    except Exception as e:
        print(e)
        raise
    finally:
        os.chdir(oldwd)
    remoteUploader.copyToRemote(os.path.join(workDir, archiveName), projectName)


def readArtifactsFromUrlRecursive(url, results):
    print("Reading build artifacts from: {0}".format(url))

    if not url.endswith("/"):
        url += "/"

    def _isDirectory(item):
        return item[-1] == '/' and item[0] != '.'

    def _isExcluded(item):
        excludeDirectoryList = ["doc", "src", "examples", "build_logs", "test_logs", "debug_information", "provisioning_logs"]
        parts = item.rstrip("/").split("/")
        if parts[-1] in excludeDirectoryList:
            return True
        return False

    url = url.replace(" ", "%20")
    req = Request(url)
    a = urlopen(req).read()
    soup = BeautifulSoup(a, 'html.parser')
    x = (soup.find_all('a'))
    for i in x:
        file_name = i.extract().get_text()
        url_new = url + file_name
        url_new = url_new.replace(" ", "%20")

        if _isExcluded(url_new):
            continue
        if _isDirectory(url_new):
            readArtifactsFromUrlRecursive(url_new, results)

        # we expect .tar.gz extension for all build artifacts
        if url_new.endswith(".tar.gz"):
            results.append(url_new)


def prepareBuildArtifacts(data):
    (artifactUrl, args) = data
    print("Preparing build artifact: {0}".format(artifactUrl))
    tempDir = tempfile.mkdtemp(prefix="prepare_build_artifact_", dir=os.getcwd())
    extractDir = os.path.join(tempDir, "install")
    outputDir = os.path.join(tempDir, "output")

    try:
        os.makedirs(extractDir)
        os.makedirs(outputDir)
        artifactFileName = artifactUrl.split("/")[-1]
        saveAsFilePath = os.path.join(tempDir, artifactFileName)
        if args.dry_run:
            return

        retrieve_url(artifactUrl, saveAsFilePath)
        extract_file(saveAsFilePath, extractDir)
        os.remove(saveAsFilePath)

        platform = getPlatformFromArtifactName(artifactFileName)
        configurationName = getConfigurationNameFromArtifactName(artifactFileName)
        projectName = getProjectNameFromArtifactName(artifactFileName)

        # qtlocation split
        if qtLocationSplitRequired(artifactUrl):
            splitQtLocation(extractDir, outputDir, configurationName)

        if pysideSplitRequired(artifactUrl):
            splitPyside(extractDir)

        if args.skip_collect_debug_symbols:
            return

        # collect debug symbols
        collectDebugSymbolFiles(extractDir, outputDir, configurationName, projectName, platform)
    except Exception as e:
        print("Failed preparing build artifact: {0}".format(artifactUrl))
        print(e)
        raise
    finally:
        shutil.rmtree(tempDir, ignore_errors=True)


def prepareArtifacts(args):
    """Build artifacts from CI system need to be patched and
    some build artifacts are further split into smaller peaces"""
    artifactsList = []
    readArtifactsFromUrlRecursive(args.artifacts_url, artifactsList)

    dataForMp = ()
    for item in artifactsList:
        dataForMp = dataForMp + ([item, args],)

    # use count of logical processors
    p = multiprocessing.Pool(multiprocessing.cpu_count())
    try:
        p.map_async(prepareBuildArtifacts, dataForMp).get(9999999)
    except KeyboardInterrupt:
        p.terminate()
        print("Task terminated")
        sys.exit(1)
    finally:
        p.close()
        p.join()


def getPlatformFromArtifactName(artifactName):
    if "windows" in artifactName.lower():
        return "windows"
    if "linux" in artifactName.lower():
        return "linux"
    if "macos" in artifactName.lower():
        return "macos"
    raise ValueError("Can not deduce host platform from artifact name: {0}".format(artifactName))


def getConfigurationNameFromArtifactName(artifactName):
    tmp = artifactName.split(".")[0]
    parts = tmp.split("-")
    return "-".join(parts[1:])


def getProjectNameFromArtifactName(artifactName):
    return artifactName.split("-")[0]


def getBuildIdFromArtifactsBaseUrl(url):
    parts = url.rstrip("/").split("/")
    return parts[-1]  # let if fail if index out of bounds as this means bogus url anyways


def getProjectBranchFromArtifactsBaseUrl(url):
    parts = url.rstrip("/").split("/")
    return parts[-2]  # let if fail if index out of bounds as this means bogus url anyways


def getProjectNameFromArtifactsBaseUrl(url):
    parts = url.rstrip("/").split("/")
    return parts[-3]  # let if fail if index out of bounds as this means bogus url anyways


def _readBuildTriggerFile(args):
    import urllib2
    from urllib2 import HTTPError
    import urlparse
    url = args.artifacts_url if args.artifacts_url.endswith("/") else args.artifacts_url + "/"
    ciExportBuildTriggerFile = urlparse.urljoin(url, "SHA1")
    try:
        data = urllib2.urlopen(ciExportBuildTriggerFile).read(1000)  # read only 1000 chars
        data = data.split("\n")
        for line in data:
            return line  # we are interested only about the first line
    except HTTPError as err:
        if err.code == 404:
            print("The given CI Export Build Trigger file does not exist: " + ciExportBuildTriggerFile)
        raise


def updateBuildTrigger(args):
    # Reads the SHA1 build trigger file written by CI/ExportTool per integration to given network file path,
    # uses the contents of that file to write downstream build trigger file. This indicates that the artifacts
    # from the latest integration are pre-processed and ready for packaging.
    data = _readBuildTriggerFile(args)
    sha1PrepareArtifactsFile = os.path.join(os.getcwd(), "SHA1_PREPARE_ARTIFACTS")
    with open(sha1PrepareArtifactsFile, "w") as f:
        f.write(data + "\n")
    remoteUploader.copyToRemote(fileName="SHA1_PREPARE_ARTIFACTS", destDirName="")
    print("SHA1_PREPARE_ARTIFACTS: {0} written to: {1}".format(data, args.artifacts_url))


def trimArtifactsUrl(args):
    if args.artifacts_url.endswith("/"):
        return
    parts = args.artifacts_url.split("/")
    if parts[-1].startswith("SHA1"):
        args.artifacts_url = args.artifacts_url.rstrip("SHA1")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-url", dest="artifacts_url", type=str, required=True, help="Input for build artifacts")
    parser.add_argument("--remote-server", dest="remote_server", type=str, default=os.getenv("PACKAGE_STORAGE_SERVER"), required=True, help="Output server for build artifacts")
    parser.add_argument("--username", dest="username", required=True, type=str, default=os.getenv("PACKAGE_STORAGE_SERVER_USER"), help="Username for the output server")
    parser.add_argument("--remote-base-path", dest="remote_base_path", type=str, required=True, default=os.getenv("PACKAGE_STORAGE_SERVER_BASE_DIR"), help="Base path for output")
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=False, help="")
    parser.add_argument("--skip-collect-debug-symbols", dest="skip_collect_debug_symbols", action="store_true", default=False, help="Do not collect debug symbols.")
    args = parser.parse_args(sys.argv[1:])

    # make sure the format is correct
    trimArtifactsUrl(args)

    buildId = getBuildIdFromArtifactsBaseUrl(args.artifacts_url)
    projectName = getProjectNameFromArtifactsBaseUrl(args.artifacts_url)
    projectBranch = getProjectBranchFromArtifactsBaseUrl(args.artifacts_url)
    remoteUploader = RemoteUploader(args.dry_run, args.remote_server, args.username, args.remote_base_path, projectBranch, projectName)
    remoteUploader.initRemoteSnapshotDir(buildId)

    prepareArtifacts(args)
    updateBuildTrigger(args)
