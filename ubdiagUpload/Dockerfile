FROM openjdk:17

# Set environment variables
ENV ANDROID_SDK_URL https://dl.google.com/android/repository/commandlinetools-linux-7583922_latest.zip
ENV ANDROID_BUILD_TOOLS_VERSION 30.0.1
ENV ANDROID_HOME /usr/local/android-sdk-linux
ENV ANDROID_VERSION 30
ENV PATH ${PATH}:${ANDROID_HOME}/cmdline-tools/bin:${ANDROID_HOME}/platform-tools

# Install required packages
RUN apt-get update
RUN apt-get install -y imagemagick git python3 python3-distutils unzip
RUN wget https://bootstrap.pypa.io/get-pip.py
RUN python3 get-pip.py --user

# Install python dependencies
COPY requirements.txt requirements.txt
RUN python3 -m pip install -r requirements.txt

# Download and unpack Android SDK
RUN mkdir "$ANDROID_HOME" .android && \
    cd "$ANDROID_HOME" && \
    curl -o sdk.zip $ANDROID_SDK_URL && \
    unzip sdk.zip && \
    rm sdk.zip

# Copy the file of SDK packages to be installed
# This file should contain:
# - The platform tools
# - The latest SDK platforms our apps target (https://developer.android.com/studio/releases/platforms)
# - The default build tools version of the latest gradle plugin (https://developer.android.com/studio/releases/gradle-plugin)
# - The default CMake version (https://developer.android.com/studio/projects/install-ndk#vanilla_cmake)
# - NDK versions should not be included because that would make the docker image too large
COPY android_sdk_packages.txt $ANDROID_HOME/packages.txt

# Accept all SDK licenses and install the specified version for build and platform tools as well as all CMake and NDK versions
RUN yes | ${ANDROID_HOME}/cmdline-tools/bin/sdkmanager --sdk_root=$ANDROID_HOME --licenses
RUN $ANDROID_HOME/cmdline-tools/bin/sdkmanager --sdk_root=$ANDROID_HOME --update
RUN $ANDROID_HOME/cmdline-tools/bin/sdkmanager --sdk_root=$ANDROID_HOME --package_file=$ANDROID_HOME/packages.txt

# Copy the script files
COPY main.sh /main.sh
COPY main.py /main.py