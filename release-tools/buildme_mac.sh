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
# Script for building and installing qt5 on mac.
#
# Usage:
#  - run this script ./buildme_mac.sh in root of your qt5 src tree
#

OLD_PATH=$PATH
export PATH=$PWD/qtbase/bin:$PATH
export DYLD_FRAMEWORK_PATH=$PWD/qtbase/lib:$DYLD_FRAMEWORK_PATH
export IFS=" "
CUR_DIR=$PWD
export LDFLAGS="-L$PWD/qtbase/lib"
./configure -opensource -confirm-license -prefix $PWD/qtbase -make examples -make libs -nomake tests -release

# Reading correct build order from Makefile.
MODULES=$(grep "^make_first:" Makefile| cut -d: -f2)

function failure_m()
{
    echo " *************** Make Error in $1 submodule ******************"
    # one might want to exit from here later...
}

function failure_i()
{
    echo " *************** Install Error in $1 submodule ******************"
    # one might want to exit from here later...
}

for MODULE in $MODULES; do
    if [ $MODULE == sub-qtwebkit-pri-make_first ]; then
        MODULE=qtwebkit
    else
        mod=${MODULE:7}
        MODULE=${mod%%-make_first}
    fi

    if [ "$MODULE" != "" ]; then
        echo "***************************************"
        echo "Now making and installing $MODULE"
        echo "***************************************"
        if [ $MODULE == something_you_dont_want_to_build ]; then
            echo "***************************************"
            echo "Skipping $MODULE"
            echo "***************************************"
        elif [ $MODULE == qtwebkit-examples-and-demos ]; then
            echo "***************************************"
            echo "Skipping $MODULE"
            echo "***************************************"
        else
            make -j4 module-$MODULE || failure_m $MODULE
        fi
    fi
done

# Disble install all for now
# make install INSTALL_ROOT=$PWD/Desktop || failure_i "All modules"

export PATH=$OLD_PATH

# Exit with success so that we get the bins.
exit 0
