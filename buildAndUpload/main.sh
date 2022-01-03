#!/bin/bash

buildNumber=${1}
projectKey=${2}
flavor=${3}
buildType=${4}
app=${5}
appModuleDirectory=${6}
buildTask=${7}
runTestTask=${8}
runCrashlyticsNativeSymbolsUploadTask=${9}
gradleProps=${10}
uploadTarget=${11}
backendEndpoint=${12}

# Change to the app module directory if it exists
if [ -n "$appModuleDirectory" ]; then
  cd "$appModuleDirectory" || { echo "App module directory does not exist"; exit; }
fi

# Set build variables
gitBranch=$(git rev-parse --abbrev-ref HEAD)
buildUuid=$(cat /proc/sys/kernel/random/uuid)
iconFile="$(pwd)/tmp_icon_large_for_backend.png"
flavorCap=$(tr a-z A-Z <<< "${flavor:0:1}")${flavor:1}
buildType=$(tr a-z A-Z <<< "${buildType:0:1}")${buildType:1}

# Default to the assemble or bundle build task if no custom build command was set
if [ -z "$buildTask" ]; then
  if [ "$uploadTarget" == "playstore" ]; then
    buildTask="bundle${flavorCap}${buildType}"
  else
    buildTask="assemble${flavorCap}${buildType}"
  fi
fi

# Prepend the clean task
gradleTasks="clean $buildTask"

# Append the unit test gradle task if the flag is set
if [ "$runTestTask" = true ]; then
  gradleTasks="$gradleTasks test${flavorCap}DebugUnitTest"
fi

# Append the crashlytics native symbol upload gradle task if the flag is set
if [ "$runCrashlyticsNativeSymbolsUploadTask" = true ]; then
  gradleTasks="$gradleTasks uploadCrashlyticsSymbolFile${flavorCap}${buildType}"
fi

# Print the build parameters
echo "Running gradle build"
echo "Build-Number:   $buildNumber"
echo "Build UUID:     $buildUuid"
echo "Project Key:    $projectKey"
echo "App Identifier: $app"
echo "Flavor:         $flavor"
echo "Build Type:     $buildType"
echo "Git Branch:     $gitBranch"
echo "GradleProps:    $gradleProps"
echo "Upload Target:  $uploadTarget"
echo "Gradle Command: $gradleTasks -Pubappid=$buildUuid -Pbranch=$gitBranch -Pwebicon=$iconFile $gradleProps"
echo

# Execute the gradle tasks
chmod +x ../gradlew
../gradlew $gradleTasks -Pubappid=$buildUuid -Pbranch=$gitBranch -Pwebicon=$iconFile $gradleProps

# Upload the build to either the play store (if configured) or UBDiag
if [ "$uploadTarget" == "playstore" ]; then
  bundleDir="$(pwd)/$(dirname "$(find build/outputs -type f -name "*.aab" | head -n 1)")"

  echo "Uploading app bundle to play store"
  echo "Path to app bundle directory: $bundleDir"

  ../gradlew "publishBundle --artifact-dir $bundleDir $gradleProps"
elif [ "$uploadTarget" == "ubdiag" ]; then
  apkFile="$(pwd)/$(find build -type f -name "*.apk" | head -n 1)"
  desymFile="$(pwd)/build/outputs/mapping/${flavor}${buildType}/mapping.txt"

  echo "Uploading apk to UBDiag"
  echo "Path to apk:          $apkFile"
  echo "Path to mapping file: $desymFile"

  python3 /main.py --endpoint=$backendEndpoint --apk_file=$apkFile --desym_file=$desymFile --icon_file=$iconFile --configuration=$flavor --project_key=$projectKey --app=$app --branch=$gitBranch --uuid=$buildUuid --build_nr=$buildNumber
fi
