#!/usr/bin/env python
#############################################################################
##
## Copyright (C) 2017 The Qt Company Ltd.
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


import ConfigParser
import os
import shutil
import argparse
import re
import bldinstallercommon
import git  # pip install gitpython, pip install git+git://github.com/jkbr/httpie.git

currentDir = os.path.dirname(os.path.abspath(__file__))


class Pkg:

    def __init__(self, qtVersion, toolchain, splitComponentList):
        self.qtVersion = qtVersion
        self.toolchain = toolchain
        self.splitComponentList = splitComponentList



def validateFile(filePath):
    if not os.path.exists(filePath):
        raise ValueError('The given path does not point into a file: ' % filePath)
    else:
        return open(filePath, 'r')  # return an open file handle


def findAndReplaceText(directory, replacements):
    for dname, dirs, files in os.walk(directory):
        for fname in files:
            fpath = os.path.join(dname, fname)
            with open(fpath) as f:
                s = f.read()
            for find, replacement in replacements.iteritems():
                s = s.replace(find, replacement)
                with open(fpath, "w") as f:
                    f.write(s)


def trimAndSplit(value):
    valueTrimmed = re.sub('\s+', ' ', value).replace(' ', '')
    return valueTrimmed.split(",")


def readValueAsList(configParser, section, key):
    value = bldinstallercommon.safe_config_key_fetch(configParser, section, key)
    return trimAndSplit(value.rstrip(","))


def createSrcComponents(configParser, baseDir, pkgOutputBaseDirName, baseTemplate, splitTemplate, name, splitComponents, substitutionList):
    componentList = []
    srcBaseTemplateDir = os.path.join(currentDir, baseDir, "templates", baseTemplate)
    srcBasePkg = 'qt' + '.' + qtPkgName + '.' + name  # e.g. qt.qt5.5100.[src|doc|examples]
    destinationDir = os.path.join(pkgOutputBaseDirName, srcBasePkg)
    shutil.copytree(srcBaseTemplateDir, destinationDir)
    componentList.append(srcBasePkg)
    print(srcBasePkg)
    findAndReplaceText(destinationDir, substitutionList)
    # split src
    splitSrcBaseTemplateDir = os.path.join(currentDir, baseDir, "templates", splitTemplate)
    for splitComponent in splitComponents:
        splitSrcPkg = srcBasePkg + '.' + splitComponent
        destinationDir = os.path.join(pkgOutputBaseDirName, splitSrcPkg)
        shutil.copytree(splitSrcBaseTemplateDir, destinationDir)
        componentList.append(splitSrcPkg)
        print(splitSrcPkg)
        # substitutions
        splitSubstitutionList = {}
        splitSubstitutionList["%SPLIT_COMPONENT_PROJECT_NAME%"] = splitComponent
        findAndReplaceText(destinationDir, dict(substitutionList.items() + splitSubstitutionList.items()))
    # create the collection components
    collectionBaseTemplateDir = os.path.join(currentDir, baseDir, "templates", "src.collection.template")
    collectionBasePkg = 'qt' + '.' + qtPkgName + '.' + name + '_' + 'collection'
    destinationDir = os.path.join(pkgOutputBaseDirName, collectionBasePkg)
    shutil.copytree(collectionBaseTemplateDir, destinationDir)
    print(collectionBasePkg)
    finalDependencyList = ", ".join(componentList)
    collectionSubstitutionList = {}
    collectionSubstitutionList["%COLLECTION_COMPONENT_DEPENDENCY_LIST%"] = finalDependencyList
    collectionSubstitutionList["%COLLECTION_COMPONENT_NAME%"] = name
    findAndReplaceText(destinationDir, dict(substitutionList.items() + collectionSubstitutionList.items()))


class Progress(git.remote.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        print 'update(%s, %s, %s, %s)'%(op_code, cur_count, max_count, message)


def parseGitModules(branch, checkoutDir):
    import StringIO
    # fetch qt5:.gitmodules
    print("Reading remote qt5.git " + branch)
    repo = git.Repo.init(checkoutDir)
    origin = repo.create_remote('origin', "https://codereview.qt-project.org/qt/qt5.git")
    origin.fetch(progress=Progress())
    origin.pull(branch)
    gitModulesFile = os.path.join(checkoutDir, ".gitmodules")
    data = '\n'.join(line.strip(' \t\r') for line in open(gitModulesFile))
    buf = StringIO.StringIO(data)
    config = ConfigParser.ConfigParser()
    config.readfp(buf)

    print("")
    modulesList = []
    for section in config.sections():
        if not section.startswith('submodule "'):
            continue
        module = section[len('submodule "'):][:-1]
        status = config.get(section, 'status')
        if not status or status in ["ignore"]:
            print("Skipping module: " + module)
            continue
        modulesList.append(module)

    return modulesList


def generateConfFile(modulesList, splitBinList, outputDir, outputFileName, templateFile, rootComponentName, qtPkgName, tcName, targetInstallBase, qtVersion, artifactConfigurationName):
    config = ConfigParser.ConfigParser()

    mainBinarySectionName = rootComponentName + "." + qtPkgName + "." + tcName  # e.g. [qt.qt5.5100.gcc_64]
    archivesList = ", ".join(modulesList)
    installDir = '/' + qtVersion + '/' + targetInstallBase  # e.g. /%QT_VERSION%/gcc_64
    config.add_section(mainBinarySectionName)
    config.set(mainBinarySectionName, 'archives', archivesList)
    config.set(mainBinarySectionName, 'target_install_base', installDir)
    for module in modulesList:
        config.add_section(module)
        archiveUri = "/qt" + "/" + qtVersion + "/latest/" + module + "/" + module + "-" + artifactConfigurationName + ".7z"
        config.set(module, 'archive_uri', archiveUri)

    # split components
    for item in splitBinList:
        splitComponentBaseName = rootComponentName + "." + qtPkgName + "." + item  # e.g. [qt.qt5.5100.qtcharts]
        config.add_section(splitComponentBaseName)
        splitComponentTCName = splitComponentBaseName + "." + tcName
        config.add_section(splitComponentTCName)
        archiveComponentName = item + "." + tcName
        config.set(splitComponentTCName, 'archives', archiveComponentName)
        config.set(splitComponentTCName, 'target_install_base', installDir)
        config.add_section(archiveComponentName)
        splitArchiveUri = "/qt" + "/" + qtVersion + "/latest/" + item + "/" + item + "-" + artifactConfigurationName + ".7z"
        config.set(archiveComponentName, 'archive_uri', splitArchiveUri)

    if not os.path.exists(outputDir):
        os.makedirs(outputDir)
    shutil.copyfile(templateFile, outputFileName)
    #print(outputFileName)
    with open(outputFileName, "a") as f:
        config.write(f)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--input', required=True, help="Path to config file")
    args = parser.parse_args()
    if not os.path.isfile(args.input):
        raise ValueError('The given path does not point into a file: ' % filePath)

    configFile = open(args.input, 'r')
    configParser = ConfigParser.ConfigParser()
    configParser.readfp(configFile)

    # base dir for pkg templates sources
    baseDir = os.path.dirname(args.input)
    qtVersion = bldinstallercommon.safe_config_key_fetch(configParser, 'common', 'qt_version')
    qtVersionTag = bldinstallercommon.safe_config_key_fetch(configParser, 'common', 'qt_version_tag')
    qtPkgName = bldinstallercommon.safe_config_key_fetch(configParser, 'common', 'qt_pkg_name')  # e.g. "59" or "qt5.5100"
    qt5Branch = bldinstallercommon.safe_config_key_fetch(configParser, 'common', 'qt5_branch')
    # output dir
    outputBaseDirName = os.path.join(currentDir, "pkg_generator_output")
    qt5CheckoutDir = os.path.join(outputBaseDirName, "qt5")
    pkgOutputBaseDirName = os.path.join(outputBaseDirName, "pkg")
    confFilesBaseOutputDir = os.path.join(outputBaseDirName, "configurations")
    shutil.rmtree(outputBaseDirName, ignore_errors=True)
    os.makedirs(pkgOutputBaseDirName)
    os.makedirs(qt5CheckoutDir)
    os.makedirs(confFilesBaseOutputDir)

    # fetch qt5:.gitmodules
    modules = parseGitModules(qt5Branch, qt5CheckoutDir)

    # common key/value substitution list
    commonSubstitutionList = {}
    commonSubstitutionList["%QT_VERSION%"] = qtVersion
    commonSubstitutionList["%QT_VERSION_TAG%"] = qtVersionTag
    commonSubstitutionList["%BASE_DEPENDENCY_PKG_NAME%"] = qtPkgName
    commonSubstitutionList["%QT_VERSION_PKG_SORTING_PRIO%"] = qtVersion.replace(".", "")

    # split binary components
    splitBinaryComponents = readValueAsList(configParser, 'split_binary_components', 'list')
    # toolchains
    toolchains = readValueAsList(configParser, 'toolchains', 'list')

    # split excludes by toolchain
    splitBinaryComponentsExcludeByTcKeys = bldinstallercommon.config_section_map(configParser, 'split_binary_component_excludes')
    splitExcludeDict = {}
    for key, value in splitBinaryComponentsExcludeByTcKeys.iteritems():
        splitExcludeDict[key] = trimAndSplit(value)

    # generate qt root component
    finalPkgTemlateName = "qt"
    qtRootPkgTemplate = os.path.join(currentDir, baseDir, "templates", "qt")
    destinationDir = os.path.join(pkgOutputBaseDirName, finalPkgTemlateName)
    shutil.copytree(qtRootPkgTemplate, destinationDir)
    print(finalPkgTemlateName)

    # generate qt.qt_version component
    finalPkgTemlateName = "qt" + "." + qtPkgName
    qtRootPkgTemplate = os.path.join(currentDir, baseDir, "templates", "qt.qt_version")
    destinationDir = os.path.join(pkgOutputBaseDirName, finalPkgTemlateName)
    shutil.copytree(qtRootPkgTemplate, destinationDir)
    print(finalPkgTemlateName)

    # generate toolchain pkg templates
    for toolchain in toolchains:
        pkgTemplateName = 'qt' + '.' + qtPkgName + '.' + toolchain
        templateSourceDir = os.path.join(currentDir, baseDir, "templates", toolchain)
        if not os.path.isdir(templateSourceDir):
            raise Exception('The given path does not contain template sources: %s' % templateSourceDir)
        destinationDir = os.path.join(pkgOutputBaseDirName, pkgTemplateName)
        shutil.copytree(templateSourceDir, destinationDir)
        print(pkgTemplateName)

    # substitute before split components
    findAndReplaceText(pkgOutputBaseDirName, commonSubstitutionList)

    # generate plain split pkg templates
    splitBaseTemplateDir = os.path.join(currentDir, baseDir, "templates", "split.basetemplate")  # e.g. qt.qt5.5100.qtcharts
    splitTCTemplateDir = os.path.join(currentDir, baseDir, "templates", "split.toolchain")  # e.g. qt.qt5.5100.qtcharts.gcc_64
    if not os.path.isdir(splitTCTemplateDir):
        raise Exception('The given path does not contain template sources: %s' % splitTCTemplateDir)
    for splitComponent in splitBinaryComponents:
        # generate base split pkg template
        splitPkgBase = 'qt' + '.' + qtPkgName + '.' + splitComponent
        destinationDir = os.path.join(pkgOutputBaseDirName, splitPkgBase)
        shutil.copytree(splitBaseTemplateDir, destinationDir)
        print(splitPkgBase)
        # substitutions
        splitComponentSubstitutions = {}
        splitComponentSubstitutions["%SPLIT_COMPONENT_PROJECT_NAME%"] = splitComponent
        splitComponentSubstitutions["%SPLIT_COMPONENT_DISPLAY_NAME%"] = bldinstallercommon.safe_config_key_fetch(configParser, splitComponent, "split_component_display_name")
        splitComponentSubstitutions["%SPLIT_COMPONENT_DESCRIPTION%"] = bldinstallercommon.safe_config_key_fetch(configParser, splitComponent, "split_component_description")
        findAndReplaceText(destinationDir, dict(commonSubstitutionList.items() + splitComponentSubstitutions.items()))
        # generate split components per toolchain
        excludeList = splitExcludeDict.get(splitComponent, [])
        for toolchain in toolchains:
            if toolchain in excludeList:
                continue
            splitPkgTC = splitPkgBase + '.' + toolchain
            destinationDir = os.path.join(pkgOutputBaseDirName, splitPkgTC)
            shutil.copytree(splitTCTemplateDir, destinationDir)
            print(splitPkgTC)
            # TODO: substitute strings
            splitComponentTCSubstitutions = {}
            splitComponentTCSubstitutions['%TOOLCHAIN_PKG_NAME%'] = toolchain
            filesToPatch = "qt5"
            if re.findall(r'android|winrt|winphone|ios|qnx', toolchain):
                filesToPatch = "emb-arm-qt5"
            splitComponentTCSubstitutions['%FILES_TO_PATCH_FILENAME%'] = filesToPatch
            findAndReplaceText(destinationDir, dict(commonSubstitutionList.items() + splitComponentSubstitutions.items() + splitComponentTCSubstitutions.items()))

    # generate src components
    substitutionList = {}
    substitutionList["%QT_VERSION%"] = qtVersion
    substitutionList["%BASE_DEPENDENCY_PKG_NAME%"] = qtPkgName
    createSrcComponents(configParser, baseDir, pkgOutputBaseDirName, "src.base", "src.split", "src", readValueAsList(configParser, 'split_src_components', 'list'), substitutionList)
    # generate doc components
    substitutionList = {}
    substitutionList["%QT_VERSION%"] = qtVersion
    substitutionList["%SPLIT_COMPONENT_PROJECT_NAME%"] = qtVersion
    createSrcComponents(configParser, baseDir, pkgOutputBaseDirName, "doc.base", "doc.split", "doc", splitBinaryComponents, substitutionList)
    # generate examples components
    substitutionList = {}
    substitutionList["%QT_VERSION%"] = qtVersion
    createSrcComponents(configParser, baseDir, pkgOutputBaseDirName, "examples.base", "examples.split", "examples", splitBinaryComponents, substitutionList)

    print("")
    print("Pkg templates generated into: " + pkgOutputBaseDirName)
    print("")

    rootComponent = "qt"
    confFileTemplate = os.path.join(currentDir, baseDir, "templates", "template-conf")
    for tc in toolchains:
        supportedPlatforms = readValueAsList(configParser, tc, 'platforms')
        for platform in ["linux/x64", "mac/x64", "windows/x64", "windows/x86"]:
            if platform not in supportedPlatforms:
                continue

            outputDir = os.path.join(confFilesBaseOutputDir, platform)
            targetInstallBase = bldinstallercommon.safe_config_key_fetch(configParser, tc, 'target_install_base')
            artifactConfigurationName = bldinstallercommon.safe_config_key_fetch(configParser, tc, 'artifact_configuration_name')
            # file name for the conf file
            fileName = platform.replace("/", "_") + "-" + qtPkgName + "-" + tc
            outputFileName = os.path.join(outputDir, fileName)
            generateConfFile(modules, splitBinaryComponents, outputDir, outputFileName, confFileTemplate, rootComponent, qtPkgName, tc, targetInstallBase, qtVersion, artifactConfigurationName)


