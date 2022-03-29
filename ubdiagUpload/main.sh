#!/bin/bash

buildNumber=${1}
projectKey=${2}
flavor=${3}
buildType=${4}
app=${5}
appModuleDirectory=${6}
buildUuid=${7}
webIconFile=${8}
backendEndpoint=${9}

# Change to the app module directory if it exists
if [ -n "$appModuleDirectory" ]; then
  cd "$appModuleDirectory" || { echo "App module directory does not exist"; exit; }
fi

# Set build variables
gitBranch=$(git rev-parse --abbrev-ref HEAD)
buildType=$(tr a-z A-Z <<< "${buildType:0:1}")${buildType:1}

apkFile="$(pwd)/$(find build -type f -name "*.apk" | head -n 1)"
desymFile="$(pwd)/build/outputs/mapping/${flavor}${buildType}/mapping.txt"
iconFile="$(pwd)/${webIconFile}"

echo "Uploading apk to UBDiag"
echo "Path to apk:            $apkFile"
if [ ! -f "$apkFile" ]; then
  echo "APK file not found!"
fi

echo "Path to mapping file:   $desymFile"
if [ ! -f "$desymFile" ]; then
  echo "Mapping file not found!"
fi

echo "Path to web icon file:  $iconFile"
if [ ! -f "$iconFile" ]; then
  echo "Web icon file not found!"
fi

python3 /main.py --endpoint="$backendEndpoint" --apk_file="$apkFile" --desym_file="$desymFile" --icon_file="$iconFile" --configuration="$flavor" --project_key="$projectKey" --app="$app" --branch="$gitBranch" --uuid="$buildUuid" --build_nr="$buildNumber"
