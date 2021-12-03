#!/bin/bash

projectKey=$1
configuration=$2
app=$3
doUpload=$4
buildCommand=$5
appModuleDirectory=$6
gradleProps=$7
buildNumber=$8
backendEndpoint=$9

if [ -n "$appModuleDirectory" ]; then
  cd $appModuleDirectory
fi

echo "configuration"$configuration
flavor=`echo $(tr a-z A-Z <<< ${configuration:0:1})${configuration:1}`
echo "flavor"$flavor
if [ -z "$buildCommand" ]; then
  buildCommand="assemble"$flavor"Release"
fi

gitBranch=`git rev-parse --abbrev-ref HEAD`
echo $gitBranch

build_uuid=$(cat /proc/sys/kernel/random/uuid)
echo $build_uuid

iconFile=`pwd`'tmp_icon_large_for_backend.png'

chmod +x ../gradlew
echo "Build-Number: "$buildNumber
echo "GradleProps: "$gradleProps
echo clean $buildCommand -Pubappid=$build_uuid -Pbranch=$gitBranch -Pwebicon=$iconFile $gradleProps
../gradlew clean $buildCommand -Pubappid=$build_uuid -Pbranch=$gitBranch -Pwebicon=$iconFile $gradleProps

apkFile=`pwd`"/"`find build -type f -name "*.apk" | head -n 1`
echo $apkFile
desymFile=`pwd`'/build/outputs/mapping/'$configuration'Release/mapping.txt'

python3 /main.py --endpoint=$backendEndpoint --apk_file=$apkFile --desym_file=$desym_file --icon_file=$iconFile --configuration=$configuration --project_key=$projectKey --app=$app --branch=$gitBranch --uuid=$build_uuid --build_nr=$buildNumber