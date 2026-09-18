#!/bin/sh
set -eu

context=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
# Both images are built for local use from the current source tree.
cd "$context/docker/jetson-orin"
./validate-input.sh

cd "$context"
# Use the same version map as the current aarch64 Compose build.
. "$context/azure-pipelines/.env"
docker build --pull=false --platform linux/arm64 -f docker/Dockerfile \
    -t viseron-aarch64:orin-local-base \
    --build-arg ARCH=aarch64 \
    --build-arg BASE_VERSION="$BASE_VERSION" \
    --build-arg OPENCV_VERSION="$OPENCV_VERSION" \
    --build-arg FFMPEG_VERSION="$FFMPEG_VERSION" \
    --build-arg WHEELS_VERSION="$WHEELS_VERSION" \
    --build-arg S6_OVERLAY_ARCH=aarch64 \
    --build-arg S6_OVERLAY_VERSION="$S6_OVERLAY_VERSION" \
    --build-arg UBUNTU_VERSION="$UBUNTU_VERSION" \
    --build-arg NODE_VERSION="$NODE_VERSION" \
    --build-arg GPAC_IMAGE="roflcoopter/aarch64-gpac:$GPAC_VERSION-$UBUNTU_VERSION" \
    --build-arg GO2RTC_VERSION="$GO2RTC_VERSION" \
    --build-arg VISERON_VERSION=dev .

cd "$context/docker/jetson-orin"
docker build --pull=false --platform linux/arm64 -f Dockerfile.viseron \
    -t viseron-jetson-orin:local .
