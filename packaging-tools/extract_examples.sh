#!/bin/sh
#############################################################################
##
## Copyright (C) 2014 Digia Plc and/or its subsidiary(-ies).
## Contact: http://www.qt-project.org/legal
##
## This file is part of the release tools of the Qt Toolkit.
##
## $QT_BEGIN_LICENSE:LGPL$
## Commercial License Usage
## Licensees holding valid commercial Qt licenses may use this file in
## accordance with the commercial license agreement provided with the
## Software or, alternatively, in accordance with the terms contained in
## a written agreement between you and Digia.  For licensing terms and
## conditions see http://qt.digia.com/licensing.  For further information
## use the contact form at http://qt.digia.com/contact-us.
##
## GNU Lesser General Public License Usage
## Alternatively, this file may be used under the terms of the GNU Lesser
## General Public License version 2.1 as published by the Free Software
## Foundation and appearing in the file LICENSE.LGPL included in the
## packaging of this file.  Please review the following information to
## ensure the GNU Lesser General Public License version 2.1 requirements
## will be met: http://www.gnu.org/licenses/old-licenses/lgpl-2.1.html.
##
## In addition, as a special exception, Digia gives you certain additional
## rights.  These rights are described in the Digia Qt LGPL Exception
## version 1.1, included in the file LGPL_EXCEPTION.txt in this package.
##
## GNU General Public License Usage
## Alternatively, this file may be used under the terms of the GNU
## General Public License version 3.0 as published by the Free Software
## Foundation and appearing in the file LICENSE.GPL included in the
## packaging of this file.  Please review the following information to
## ensure the GNU General Public License version 3.0 requirements will be
## met: http://www.gnu.org/copyleft/gpl.html.
##
##
## $QT_END_LICENSE$
##
#############################################################################

APPLICATION_NAME=''
LICENSE=''
APPLICATION_VERSION=''
PACKAGE_STORAGE_SERVER_USER=''
PACKAGE_STORAGE_SERVER=''
PACKAGE_STORAGE_SERVER_BASE_DIR=''
BUILD_NUMBER=''

if [ $# -lt 14 ]; then
    echo "Missing argument"
    exit 1
fi

# read the arguments
while test $# -gt 0; do
  case "$1" in
    -n|--appname)
      shift
      APPLICATION_NAME=$1
      shift
    ;;
    -l|--license)
      shift
      LICENSE=$1
      shift
    ;;
    -v|--version)
      shift
      APPLICATION_VERSION=$1
      shift
    ;;
    -u|--user)
      shift
      PACKAGE_STORAGE_SERVER_USER=$1
      shift
    ;;
    -s|--server)
      shift
      PACKAGE_STORAGE_SERVER=$1
      shift
    ;;
    -d|--directory)
      shift
      PACKAGE_STORAGE_SERVER_BASE_DIR=$1
      shift
    ;;
    -b|--build)
      shift
      BUILD_NUMBER=$1
      shift
    ;;
    esac
done

7z x $APPLICATION_NAME-$LICENSE-src-$APPLICATION_VERSION.7z -otemp
cd temp/$APPLICATION_NAME-$LICENSE-src-$APPLICATION_VERSION
rm examples/examples.pro
7z a examples_$APPLICATION_NAME.7z examples/*
tar -cvzf examples_$APPLICATION_NAME.tar.gz examples/*
scp examples_$APPLICATION_NAME.* $PACKAGE_STORAGE_SERVER_USER@$PACKAGE_STORAGE_SERVER:$PACKAGE_STORAGE_SERVER_BASE_DIR/$LICENSE/$APPLICATION_NAME/$APPLICATION_VERSION/latest/examples || exit 1
cd ..
