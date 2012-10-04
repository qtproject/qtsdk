#!/bin/bash
############################################################################
##
## Copyright (C) 2012 Digia Plc and/or its subsidiary(-ies).
## Contact: http://www.qt-project.org/legal
##
## This file is part of the FOO module of the Qt Toolkit.
##
## $QT_BEGIN_LICENSE:BSD$
## You may use this file under the terms of the BSD license as follows:
##
## "Redistribution and use in source and binary forms, with or without
## modification, are permitted provided that the following conditions are
## met:
##   * Redistributions of source code must retain the above copyright
##     notice, this list of conditions and the following disclaimer.
##   * Redistributions in binary form must reproduce the above copyright
##     notice, this list of conditions and the following disclaimer in
##     the documentation and/or other materials provided with the
##     distribution.
##   * Neither the name of Digia Plc and its Subsidiary(-ies) nor the names
##     of its contributors may be used to endorse or promote products derived
##     from this software without specific prior written permission.
##
##
## THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
## "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
## LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
## A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
## OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
## SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
## LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
## DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
## THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
## (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
## OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE."
##
## $QT_END_LICENSE$
##
############################################################################
#
# Script for shadow building and installing qt5 on linux.
#
# Usage:
#  - Extract qt sources into ../qt-everywhere-opensource-src-5.0.0
#  - run this script ./buildme_linux.sh
#

OLD_PATH=$PATH
export PATH=$PWD/Desktop/Qt/5.0.0/gcc/bin:$PWD/qtbase/bin:$PWD/../qt-everywhere-opensource-src-5.0.0/qtbase/bin:$PATH
CUR_DIR=$PWD
export QMAKEPATH=$PWD/Desktop/Qt/5.0.0/gcc
# Configuring shadow build.
../qt-everywhere-opensource-src-5.0.0/configure -opensource -confirm-license -prefix $PWD/Desktop/Qt/5.0.0/gcc -make examples -nomake tests -release -no-gtkstyle

# Reading the build order from Makefile.
MODULES=$(grep "^make_first:" Makefile| cut -d: -f2)

export IFS=" "

function failure_m()
{
    echo " *************** Make Error in $1 submodule ******************"
}

function failure_i()
{
    echo " *************** Install Error in $1 submodule ******************"
}

for MODULE in $MODULES; do
    if [ $MODULE == sub-qtwebkit-pri-make_first ]; then
        MODULE=qtwebkit
    else
        mod=${MODULE:7}
        MODULE=${mod%%-make_default}
    fi

    if [ "$MODULE" != "" ]; then
        echo "***************************************"
        echo "Now making and installing $MODULE"
        echo "***************************************"
        if [ $MODULE == qtwebkit ]; then
            make module-$MODULE -j4 || failure_m $MODULE
            # we can't install webkit just yet
        else
            make module-$MODULE -j4 || failure_m $MODULE
            pushd $MODULE
            make install || failure_i $MODULE
            popd
        fi
    fi
done
# There is some dependency so that one can't install qtwebkit right after its built
# so we are doing it here.
make -f Makefile.qtwebkit install || failure_i "qtwebkit"

export PATH=$OLD_PATH

exit 0
