#!/bin/sh
set -eu

package=${1:-input/ffmpeg_7%3a8.0.1-nvidia_arm64.deb}
expected_hash=${2:-a0f70349e7894b8ada4e5d8e5e9065183970d9634ee3542c822e8efa3f52f003}

if [ ! -f "$package" ]; then
    echo "INPUT BLOCKED: missing local package: $package" >&2
    exit 1
fi

name=$(dpkg-deb -f "$package" Package) || exit 1
version=$(dpkg-deb -f "$package" Version) || exit 1
arch=$(dpkg-deb -f "$package" Architecture) || exit 1
if [ "$name" != ffmpeg ] || [ "$version" != '7:8.0.1-nvidia' ] || [ "$arch" != arm64 ]; then
    echo "INPUT BLOCKED: expected ffmpeg 7:8.0.1-nvidia arm64; found $name $version $arch" >&2
    exit 1
fi

actual_hash=$(sha256sum "$package" | cut -d ' ' -f 1)
if [ "$actual_hash" != "$expected_hash" ]; then
    echo "INPUT BLOCKED: SHA256 mismatch: $actual_hash" >&2
    exit 1
fi

echo "filename: $(basename "$package")"
echo "SHA256: $actual_hash"
dpkg-deb -f "$package" Package Version Architecture Depends
