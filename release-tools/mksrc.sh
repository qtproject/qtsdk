#!/bin/bash
# Copyright (C) 2012 Digia Plc and/or its subsidiary(-ies).
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
# $ release-tools/mksrc.sh -v
# release-tools/mksrc.sh: line 161: $1: unbound variable
set -u

CUR_DIR=$PWD
DO_FETCH=true
DO_TAG=false
DOCS=generate
EXIT_AFTER_DOCS=false
IGNORE_LIST=
LICENSE=opensource
MAKEARGS=''
MULTIPACK=no
PACK_TIME=`date '+%Y-%m-%d'`
PATCH_FILE=''
QTGITTAG=.sha1s
QTSHORTVER=0.0
QTVER=0.0.0
REPO_DIR=$CUR_DIR
REPO_NAME=''
REPO_TAG=HEAD
STRICT=0

function usage()
{
  echo "Usage:"
  echo "./mksrc.sh -u <file_url_to_git_repo> -v <version> [-m][-N][--make-args][--no-docs][--tag][-i sub][-l lic][-p patch][-r revision][--strict]"
  echo "where -u is path to git repo and -v is version"
  echo "Optional parameters:"
  echo "-m             one is able to tar each sub module separately"
  echo "-N             don't use git fetch to update submodules"
  echo "--make-args    extra arguments passed to 'make' command (e.g. --make-args '-j4 -s')"
  echo "--no-docs      skip generating documentation"
  echo "--tag          also tag the repository"
  echo "-i submodule   will exclude the submodule from final package "
  echo "-l license     license type, will default to 'opensource', if set to 'commercial' all the necessary patches will be applied for commercial build"
  echo "-p patch file  patch file (.sh) to execute, example: change_licenses.sh"
  echo "-r revision    committish to pack (tag name, branch name or SHA-1)"
  echo "--strict       strict mode, execution will fail on any error"
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
  tar cf - $PACKAGE_NAME/ | \
      tee \
         >(xz -9 > $PACKAGE_NAME.tar.xz) | \
      gzip -9 > $PACKAGE_NAME.tar.gz

  echo " - Creating single 7z file - "
  7z a $PACKAGE_NAME.7z $PACKAGE_NAME/ > /dev/null

  echo " - Creating single win zip - "
  # ZIP
  find $PACKAGE_NAME/ > __files_to_zip
  # zip binfiles
  file -f __files_to_zip | fgrep -f _txtfiles -v | cut -d: -f1 | zip -9q $PACKAGE_NAME.zip -@
  #zip ascii files with win line endings
  file -f __files_to_zip | fgrep -f _txtfiles | cut -d: -f1 | zip -l9q $PACKAGE_NAME.zip -@
}

function create_and_delete_submodule()
{
  mkdir submodules_tar
  mkdir submodules_zip
  cd $PACKAGE_NAME
  while read submodule submodule_sha1; do
    _file=$submodule-$LICENSE-src-$QTVER
    echo " - tarring $_file -"
    mv $submodule $_file
    tar c $_file | tee \
        >(xz -9 > ../submodules_tar/$_file.tar.xz) | \
        gzip -9 > ../submodules_tar/$_file.tar.gz
    echo " - 7zipping $_file - "
    7z a ../submodules_zip/$_file.7z $_file/ > /dev/null
    echo " - zippinging $_file -"
    find $_file > __files_to_zip
    # zip binfiles
    file -f __files_to_zip | fgrep -f ../_txtfiles -v | cut -d: -f1 | zip -9q ../submodules_zip/$_file.zip -@
    #zip ascii files with win line endings
    file -f __files_to_zip | fgrep -f ../_txtfiles | cut -d: -f1 | zip -l9q ../submodules_zip/$_file.zip -@
    rm -rf $_file
    rm -rf __files_to_zip
  done < $MODULES
  cd ..
}

#read machine config
. $(dirname $0)/default_src.config

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
      MAKEARGS=$1
      shift
    ;;
    --no-docs)
      shift
      DOCS=skip
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
      EXIT_AFTER_DOCS=true
    ;;
    --strict)
      shift
      STRICT=1
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

PACKAGE_NAME=qt-everywhere-$LICENSE-src-$QTVER
MODULES=$CUR_DIR/submodules.txt
_TMP_DIR=$CUR_DIR/$PACKAGE_NAME

#------------------------------------------------------------------
# Step 1, Find all submodules from main repo and archive them
#------------------------------------------------------------------

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

#------------------------------------------------------------------
# Step 3,  replace version strings with correct version, and
# patch Qt_PACKAGE_TAG and QT_PACKAGEDATE_STR defines
#------------------------------------------------------------------
echo " -- Patching %VERSION% etc. defines --"
cd $CUR_DIR/$PACKAGE_NAME/
find . -type f -print0 | xargs -0 sed -i -e "s/%VERSION%/$QTVER/g" -e "s/%SHORTVERSION%/$QTSHORTVER/g"

#------------------------------------------------------------------
# Step 4,  generate docs
#------------------------------------------------------------------
if [ $DOCS = generate ]; then
  echo "DOC: Starting documentation generation.."
  # Make a copy of the source tree
  DOC_BUILD=$CUR_DIR/doc-build
  mkdir -p $DOC_BUILD
  echo "DOC: copying sources to $DOC_BUILD"
  cp -R $CUR_DIR/$PACKAGE_NAME $DOC_BUILD
  cd $DOC_BUILD/$PACKAGE_NAME
  # Build bootstrapped qdoc
  echo "DOC: configuring build"
  if [ $REPO_NAME = qtsdk ]; then
    ( cd qtbase ; ./configure -developer-build -opensource -confirm-license -nomake examples -nomake tests -release -fast -no-pch -no-qpa-platform-guard -silent)
  else
    ./configure -developer-build -opensource -confirm-license -nomake examples -nomake tests -release -fast -no-pch -no-qpa-platform-guard -silent
  fi
  # Run qmake in each module, as this generates the .pri files that tell qdoc what docs to generate
  QMAKE=$PWD/qtbase/bin/qmake
  echo "DOC: running $QMAKE and qmake_all for submodules"
  for i in `cat $MODULES` ; do if [ -d $i -a -e $i/*.pro ] ; then (cd $i ; $QMAKE ; make $MAKEARGS qmake_all ) ; fi ; done
  # Build libQtHelp.so and qhelpgenerator
  echo "DOC: Build libQtHelp.so and qhelpgenerator"
  (cd qtbase && make $MAKEARGS)
  (cd qtxmlpatterns ; make $MAKEARGS)
  (cd qttools ; make $MAKEARGS)
  (cd qttools/src/assistant/help ; make $MAKEARGS)
  (cd qttools/src/assistant/qhelpgenerator ; make $MAKEARGS)
  # Generate the offline docs and qt.qch
  echo "DOC: Generate the offline docs and qt.qch"
  (cd qtdoc ; $QMAKE ; make $MAKEARGS qmake_all ; LD_LIBRARY_PATH=$PWD/../qttools/lib make $MAKEARGS qch_docs)
  (cd qtdoc ; $QMAKE ; LD_LIBRARY_PATH=$PWD/../qttools/lib make $MAKEARGS online_docs)

  # exit if so wanted, to speed up
  if [ $EXIT_AFTER_DOCS = true ]; then
    cd $DOC_BUILD/$PACKAGE_NAME/qtdoc/doc
    # store the sha1 file into tar files
    cp $CUR_DIR/$PACKAGE_NAME/$QTGITTAG html/
    cp $CUR_DIR/$PACKAGE_NAME/$QTGITTAG qch/
    tar cJf $CUR_DIR/online_doc.tar.xz html/
    tar cJf $CUR_DIR/offline_doc.tar.xz qch/
    cd $CUR_DIR
    rm -rf $DOC_BUILD
    cleanup
    exit
  fi # $EXIT_AFTER_DOCS

# Put the generated docs back into the clean source directory
  echo "DOC: Put the generated docs back into the clean source directory"
  if [ ! -d $DOC_BUILD/$PACKAGE_NAME/qtdoc/doc/html ]; then
    echo "DOC: *** Error: $DOC_BUILD/$PACKAGE_NAME/qtdoc/doc/html not found!"
    if [ $STRICT -eq 1 ]; then
      echo "  -> exiting.."
      exit 2
    fi
  else
    mv $DOC_BUILD/$PACKAGE_NAME/qtdoc/doc/html $CUR_DIR/$PACKAGE_NAME/qtdoc/doc
  fi
  if [ ! -d $DOC_BUILD/$PACKAGE_NAME/qtdoc/doc/qch ]; then
    echo "DOC: *** Error: $DOC_BUILD/$PACKAGE_NAME/qtdoc/doc/qch not found"
    if [ $STRICT -eq 1 ]; then
      echo "  -> exiting.."
      exit 2
    fi
  else
    mv $DOC_BUILD/$PACKAGE_NAME/qtdoc/doc/qch $CUR_DIR/$PACKAGE_NAME/qtdoc/qch
  fi
  # Cleanup
  cd $CUR_DIR/$PACKAGE_NAME/
  #rm -rf $DOC_BUILD
else
  echo " -- Creating src files without generated offline documentation --"
fi

#------------------------------------------------------------------
# Step 5,  check which license type is selected, and run patches
# if needed
#------------------------------------------------------------------
if [ $PATCH_FILE ]; then
  if [ $LICENSE = commercial ]; then
    # when doing commercial build, patch file needs src folder and qt version no as parameters
    $PATCH_FILE $CUR_DIR/$PACKAGE_NAME/ $QTVER
  else
    $PATCH_FILE
  fi
fi

#------------------------------------------------------------------
# Step 6,  create zip file and tar files
#------------------------------------------------------------------
# list text file regexp keywords, if you find something obvious missing, feel free to add
cd $CUR_DIR
echo "ASCII
directory
empty
POSIX
html
text" > _txtfiles

echo " -- Create B I G tars -- "
create_main_file

# Create tar/submodule
if [ $MULTIPACK = yes ]; then
  mkdir single
  mv $PACKAGE_NAME.* single/
  echo " -- Creating tar per submodule -- "
  create_and_delete_submodule
fi
cleanup

echo "Done!"

