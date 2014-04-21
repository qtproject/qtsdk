#!/bin/bash
# Copyright (C) 2013 Digia Plc and/or its subsidiary(-ies).
# Contact: http://www.qt-project.org/legal
#
# You may use this file under the terms of the 3-clause BSD license.
# See the file LICENSE from this package for details.
#
#
#
# Script for archiving qt5 repositories
#
# Usage:
# ./mksrc.sh -u <file url to local git clone> -v <version>
#  - Currently supporting only local clones, not direct git:// url's
# After running the script, one will get qt-everywhere-opensource-src-<version>.tar.gz
# and qt-everywhere-opensource-src-<version>.zip
#

# Gives an unbound variable error message at each attempt
# to use an undeclared parameter.
#
# $ packaging-tools/mksrc.sh -v
# packaging-tools/mksrc.sh: line 161: $1: unbound variable
set -u

# Exit immediately if a command exits with a non-zero status.
set -e

CUR_DIR=$PWD
SCRIPT=$(readlink -f $0)
SCRIPT_DIR=$(dirname $SCRIPT)
DO_FETCH=true
DO_TAG=false
IGNORE_LIST=
LICENSE=opensource
MULTIPACK=no
PACK_TIME=`date '+%Y-%m-%d'`
PACK_FILE=.release-timestamp
PATCH_FILE=''
QTGITTAG=.sha1s
QTSHORTVER=0.0
QTSYNCQTVER=0.0.0
QTVER=0.0.0
REPO_DIR=$CUR_DIR
REPO_NAME=''
REPO_TAG=HEAD
SINGLEMODULE=no
SKIPSYNCQT=no
STRICT=1

function usage()
{
  echo "Usage:"
  echo "./mksrc.sh -u <file_url_to_git_repo> -v <version> [-m][-N][--tag][-i sub][-l lic][-p patch][-r revision][--single-module][--skip-syncqt][-S]"
  echo "where -u is path to git repo and -v is version"
  echo "Optional parameters:"
  echo "-m              one is able to tar each sub module separately"
  echo "-N              don't use git fetch to update submodules"
  echo "--tag           also tag the repository"
  echo "-i submodule    will exclude the submodule from final package "
  echo "-l license      license type, will default to 'opensource', if set to 'enterprise' all the necessary patches will be applied for enterprise build"
  echo "-p patch file   patch file (.sh) to execute, example: change_licenses.sh"
  echo "-r revision     committish to pack (tag name, branch name or SHA-1)"
  echo "--single-module tar any single git repository (that might live outside the supermodule)"
  echo "--skip-syncqt   do not run syncqt by default"
  echo "-S              don't run in strict mode"
}

function cleanup()
{
  echo "Cleaning all tmp artifacts"
  rm -f _txtfiles
  rm -f __files_to_zip
  rm -f _tmp_mod
  rm -f _tmp_shas
  rm -rf $PACKAGE_NAME
}

function create_main_file()
{
  echo " - Creating tarballs -"
  # The trick below uses tee to feed the output of tar to
  # two additional files, which are actually bash/zsh
  # "Process substitution"
  # This will cause it to compress simultaneously, though
  # at the rate of the slowest of the processes (e.g.,
  # with xz at 100% CPU, and gzip 15%)
(  tar cf - $PACKAGE_NAME/ | \
      tee \
         >(xz -9 > $PACKAGE_NAME.tar.xz) | \
      gzip -9 > $PACKAGE_NAME.tar.gz

  echo " - Created tar.xz and tar.gz - "
) &
(  7z a $PACKAGE_NAME.7z $PACKAGE_NAME/ > /dev/null
  echo " - Created 7z - "
) &
(
  $SCRIPT_DIR/winzipdir.sh $PACKAGE_NAME.zip $PACKAGE_NAME
  echo " - Created single win zip - "
) &
wait
echo " - Done creating archives - "
}

function create_and_delete_submodule()
{
  mkdir submodules_tar
  mkdir submodules_zip
  cd $PACKAGE_NAME
  while read submodule submodule_sha1; do
    _file=$submodule-$LICENSE-src-$QTVER
    mv $submodule $_file
    echo " - Creating archives - "
    (   tar c $_file | tee \
            >(xz -9 > ../submodules_tar/$_file.tar.xz) | \
            gzip -9 > ../submodules_tar/$_file.tar.gz
        echo " - Done tarring $_file -"
    ) &
    (    7z a ../submodules_zip/$_file.7z $_file/ > /dev/null
        echo " - Done 7zipping $_file - "
    ) &
    (    $SCRIPT_DIR/winzipdir.sh ../submodules_zip/$_file.zip $_file
        echo " - Done zipping $_file -"
    ) &
    wait
    rm -rf $_file
  done < $MODULES
  cd ..
}

# read the arguments
while test $# -gt 0; do
  case "$1" in
    -h|--help)
      usage
      exit 0
    ;;
    -m|--modules)
      shift
      MULTIPACK=yes
    ;;
    --make-args)
      shift
      echo "************************************************"
      echo " --make-args switch has been depracated.        "
      echo " Doc creation was removed from mksrc.sh         "
      echo "************************************************"
      shift
    ;;
    --no-docs)
      shift
      echo "****************************************"
      echo " --no-docs switch has been depracated.  "
      echo " Doc creation was removed from mksrc.sh "
      echo "****************************************"
    ;;
    -t|--tag)
      shift
      DO_TAG=true
    ;;
    -N|--no-fetch)
      shift
      DO_FETCH=false
      ;;
    -i|--ignore)
      shift
      IGNORE_LIST=$IGNORE_LIST" "$1
      shift
    ;;
    -u|--url)
      shift
      REPO_DIR=/$1
      shift
    ;;
    -v|--version)
      shift
        QTVER=$1
        QTSHORTVER=$(echo $QTVER | cut -d. -f1-2)
        QTSYNCQTVER=$(echo $QTVER | cut -d- -f1)
      shift
    ;;
    -l|--license)
      shift
      LICENSE=$1
      shift
    ;;
    -p|--patch_file)
      shift
      PATCH_FILE=$1
      shift
    ;;
    -r|--revision)
      shift
      REPO_TAG=$1
      shift
    ;;
    --exit-after-docs)
      shift
      echo "************************************************"
      echo " --exit-after-docs switch has been depracated.  "
      echo " Doc creation was removed from mksrc.sh         "
      echo "************************************************"
    ;;
    --skip-syncqt)
      shift
      SKIPSYNCQT=yes
    ;;
    --single-module)
      shift
      SINGLEMODULE=yes
    ;;
    -S|--no-strict)
      shift
      STRICT=0
    ;;
    *)
      echo "Error: Unknown option $1"
      usage
      exit 0
    ;;
    esac
done

# Check if the DIR is valid git repository
cd $REPO_DIR
if ! git rev-parse --git-dir >/dev/null 2>/dev/null; then
  echo "$REPO_DIR is not a valid git repo"
  exit 2
fi
REPO_NAME=$(basename $REPO_DIR)

if [ $SINGLEMODULE = no ]; then
  PACKAGE_NAME=qt-everywhere-$LICENSE-src-$QTVER
else
  PACKAGE_NAME=$REPO_NAME-$LICENSE-src-$QTVER
fi
MODULES=$CUR_DIR/submodules.txt
_TMP_DIR=$CUR_DIR/$PACKAGE_NAME

#------------------------------------------------------------------
# Step 1, Find all submodules from main repo and archive them
#------------------------------------------------------------------

if [ $SINGLEMODULE = no ]; then
  echo " -- Finding submodules from $REPO_DIR -- "

  rm -f $MODULES
  rm -rf $_TMP_DIR
  mkdir $_TMP_DIR

  # detect the submodules to be archived
  git ls-tree $REPO_TAG | while read mode type sha1 name; do
      test "$type" = "commit" || continue
      test -d "$name" || {
          echo >&2 "Warning: submodule '$name' is not present"
          continue
      }
      case " $IGNORE_LIST " in
          *" $name "*)
              # Ignored module, skip
              continue
              ;;
      esac
      echo $name $sha1
  done >> $MODULES

  #tag the master repo, maybe
  if $DO_TAG && test "v$QTVER" != "$REPO_TAG"; then
      git tag -f -a -m "Qt $QTVER Release" v$QTVER $REPO_TAG || \
          { echo >&2 "Unable to tag master repository"; exit 1; }
      REPO_TAG=v$QTVER
  fi

  cd $REPO_DIR

  #archive the main repo
  git archive --format=tar $REPO_TAG | tar -x -C $_TMP_DIR
  _SHA=`git rev-parse $REPO_TAG`
  MASTER_SHA=$_SHA
  rm -f $_TMP_DIR/$QTGITTAG
  echo "$REPO_NAME=$_SHA">$_TMP_DIR/$QTGITTAG

  echo " -- From dir $PWD, let's pack the master repo at $MASTER_SHA --"

  #archive all the submodules and generate file from sha1's
  while read submodule _SHA; do
    echo " -- From dir $PWD/$submodule, lets pack $submodule at $_SHA --"
    cd $submodule
    _file=$(echo "$submodule" | cut -d'/' -f1).tar.gz
    #check that _SHA exists
    if ! git cat-file -e $_SHA; then
        $DO_FETCH && git fetch >/dev/null
        if ! git cat-file -e $_SHA; then
            echo >&2 "Commit $_SHA does not exist in submodule $submodule"
            echo >&2 "and could not be fetched. Cannot continue."
            exit 1
        fi
    fi
    #tag me, maybe
    if $DO_TAG; then
        git tag -f -a -m "Qt $QTVER Release" v$QTVER $_SHA || \
            { echo >&2 "Unable to tag submodule $submodule"; exit 1; }
        _SHA=v$QTVER
    fi
    #export the repository contents
    git archive --format=tar --prefix=$submodule/ $_SHA | \
        tar -x -C $_TMP_DIR
    #store the sha1
    echo "$(echo $(echo $submodule|sed 's/-/_/g') | cut -d/ -f1)=$_SHA" >>$_TMP_DIR/$QTGITTAG
    #add QT_PACKAGEDATE_STR for enterprise license key check
    if [ $LICENSE = enterprise -a $submodule = qtbase ]; then
        rm -f $_TMP_DIR/$submodule/$PACK_FILE
        echo "QT_PACKAGEDATE_STR=$PACK_TIME">$_TMP_DIR/$submodule/$PACK_FILE
    fi
    cd $REPO_DIR
  done < $MODULES
  #mv $MODULES $CUR_DIR

  cd $CUR_DIR/$PACKAGE_NAME
  __skip_sub=no
  rm -f _tmp_mod
  rm -f _tmp_shas

  # read the shas
  echo "$REPO_NAME was archived from $MASTER_SHA" >$CUR_DIR/_tmp_shas
  echo "------------------------------------------------------------------------">>$CUR_DIR/_tmp_shas
  echo "Fixing shas"
  while read submodule submodule_sha1; do
      echo $submodule >>$CUR_DIR/_tmp_mod
      echo "$submodule was archived from $submodule_sha1"
      echo "------------------------------------------------------------------------"
  done < $MODULES >>$CUR_DIR/_tmp_shas
  cat $CUR_DIR/_tmp_mod > $MODULES
  rm -f $CUR_DIR/$PACKAGE_NAME/$QTGITTAG
  cat $CUR_DIR/_tmp_shas > $CUR_DIR/$PACKAGE_NAME/$QTGITTAG

  # remove possible empty directories in case of some submodules ignored
  for IDIR in $IGNORE_LIST ; do
    rm -rf $CUR_DIR/$PACKAGE_NAME/$IDIR
  done
else
  rm -rf $_TMP_DIR
  mkdir $_TMP_DIR

  cd $REPO_DIR

  #archive the single repo
  git archive --format=tar $REPO_TAG | tar -x -C $_TMP_DIR
  _SHA=`git rev-parse $REPO_TAG`
  SINGLEMODULE_SHA=$_SHA

  echo " -- From dir $PWD, let's pack the $REPO_NAME repo at $SINGLEMODULE_SHA --"
fi # SINGLEMODULE


#------------------------------------------------------------------
# Step 2, run syncqt
#------------------------------------------------------------------
if [ $SKIPSYNCQT = no ]; then
  PACKAGE_DIR=$CUR_DIR/$PACKAGE_NAME
  echo "Running syncqt.pl"
  if [ $SINGLEMODULE = no ]; then
    while read submodule; do
      if [ $submodule != qtbase ]; then
        RESULT=$(grep "MODULE_VERSION" $PACKAGE_DIR/$submodule/.qmake.conf)
        QTSYNCQTVER=$(echo $RESULT | sed 's/.[^=]*=\(.[^ \t]*\)[ \t]*/\1/')
      fi
      echo " - Running syncqt.pl for $submodule with -version $QTSYNCQTVER"
      if [ $submodule = qtwebkit ]; then
        SYNC_PROFILE_DIR=$PACKAGE_DIR/$submodule/Source
      else
        SYNC_PROFILE_DIR=$PACKAGE_DIR/$submodule
      fi
      $PACKAGE_DIR/qtbase/bin/syncqt.pl -version $QTSYNCQTVER -outdir $PACKAGE_DIR/$submodule $SYNC_PROFILE_DIR
    done < $MODULES
  else
    RESULT=$(grep "MODULE_VERSION" $PACKAGE_DIR/.qmake.conf)
    QTSYNCQTVER=$(echo $RESULT | sed 's/.[^=]*=\(.[^ \t]*\)[ \t]*/\1/')
    echo " - Running syncqt.pl for $REPO_NAME with -version $QTSYNCQTVER"
    $CUR_DIR/../qtbase/bin/syncqt.pl -version $QTSYNCQTVER -outdir $PACKAGE_DIR $PACKAGE_DIR
  fi
fi

#------------------------------------------------------------------
# Step 3,  replace version strings with correct version, and
# patch Qt_PACKAGE_TAG and QT_PACKAGEDATE_STR defines
#------------------------------------------------------------------
echo " -- Patching %VERSION% etc. defines --"
cd $CUR_DIR/$PACKAGE_NAME/
find . -type f -print0 | xargs -0 sed -i -e "s/%VERSION%/$QTVER/g" -e "s/%SHORTVERSION%/$QTSHORTVER/g"

#------------------------------------------------------------------
# Step 4,  check which license type is selected, and run patches
# if needed
#------------------------------------------------------------------
if [ $PATCH_FILE ]; then
  if [ $LICENSE = enterprise]; then
    # when doing enterprise build, patch file needs src folder and qt version no as parameters
    $PATCH_FILE $CUR_DIR/$PACKAGE_NAME/ $QTVER
  else
    $PATCH_FILE
  fi
fi

#------------------------------------------------------------------
# Step 5,  create zip file and tar files
#------------------------------------------------------------------

cd $CUR_DIR

echo " -- Create B I G archives -- "
create_main_file

# Create tar/submodule
if [ $MULTIPACK = yes -a $SINGLEMODULE = no ]; then
  mkdir single
  mv $PACKAGE_NAME.* single/
  echo " -- Creating archives per submodule -- "
  create_and_delete_submodule
  echo " -- Creating archive from super repository"
  create_main_file
  for POSTFIX in "7z" "zip" "tar.gz" "tar.xz"; do
    if [ -f $PACKAGE_NAME.$POSTFIX ]; then
      if [[ $POSTFIX == *"tar"* ]]; then
        mv $PACKAGE_NAME.$POSTFIX submodules_tar/$REPO_NAME-$LICENSE-src-$QTVER.$POSTFIX
      else
        mv $PACKAGE_NAME.$POSTFIX submodules_zip/$REPO_NAME-$LICENSE-src-$QTVER.$POSTFIX
      fi
    fi
  done
fi
cleanup

echo "Done!"

