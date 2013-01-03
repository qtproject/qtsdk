#!/usr/bin/env bash

#echo "Patcher arguments: $1"
if [ $# -lt 1 ]; then
    exit 1
fi

#echo "Grepping matches.."
tmpfilenames=()
while read -r FILENAME; do
    tmpfilenames+=("$FILENAME")
done < <(grep -riIl -e 'icu_install' $1)
#echo "Grepping matches..done"

#echo "Sedding.."
sed -i -e 's/-[I|L]\"*\/data\/bamboo\/xml-data\/build-dir.*icu_install\/.*[\" $]//g' "${tmpfilenames[@]}"

