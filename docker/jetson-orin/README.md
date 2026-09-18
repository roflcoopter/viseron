# Local Viseron build for Jetson Orin Nano

This build was tested on a Jetson Orin Nano with ARM64 Ubuntu 24.04 (Noble), L4T R39.2.1, and a JetPack 7 environment. Other Orin models and host versions have not been validated.

## Supply and validate NVIDIA FFmpeg

Supply `ffmpeg_7%3a8.0.1-nvidia_arm64.deb` locally at `docker/jetson-orin/input/`. The package must be `ffmpeg` version `7:8.0.1-nvidia` for `arm64`, with SHA256 `a0f70349e7894b8ada4e5d8e5e9065183970d9634ee3542c822e8efa3f52f003`. The input directory is Git-ignored; the binary is not included in this repository.

From the repository root:

```sh
cd docker/jetson-orin
./validate-input.sh
./build-viseron-local.sh
```

The helper validates the local package before building a generic Noble ARM64 Viseron base from the current source tree and layering the NVIDIA package on it. It reads version values from `azure-pipelines/.env`. The final local image is `viseron-jetson-orin:local`. Live external package and image inputs mean a later build may resolve different dependencies. No prebuilt Orin image is provided, and this local workflow does not imply permission to redistribute an image containing NVIDIA FFmpeg.

## Run on a matching host

The tested runtime uses NVIDIA CDI with `--runtime=runc --device=nvidia.com/gpu=all`. Supply the normal Viseron configuration and storage mounts for your installation. For example, with those host directories already prepared:

```sh
docker run -d --name viseron-orin --pull=never \
  --runtime=runc --device=nvidia.com/gpu=all \
  --mount type=bind,src=/path/to/config,dst=/config \
  --mount type=bind,src=/path/to/segments,dst=/segments \
  --mount type=bind,src=/path/to/event_clips,dst=/event_clips \
  --mount type=bind,src=/path/to/thumbnails,dst=/thumbnails \
  --mount type=bind,src=/path/to/snapshots,dst=/snapshots \
  viseron-jetson-orin:local
```

The image sets `VISERON_FFMPEG_BACKEND=jetson_orin_r39`. Its startup selects the installed `/usr/bin/ffmpeg` through `VISERON_FFMPEG_PATH`. The backend checks that this FFmpeg exposes the NVIDIA H.264 and HEVC decoders with NV12 output. The host must provide matching NVIDIA multimedia libraries and devices through CDI. A stop timeout of 90 seconds allowed the tested container to shut down cleanly: `docker stop -t 90 viseron-orin`.

## Limits and troubleshooting

Arbitrary Orin `raw_command` configurations are unsupported. Color matrix, range, and NV12/NV21 interpretation were outside the tested scope. Support is limited to the platform above and a matching NVIDIA host/CDI environment.

- If validation rejects the package, check its filename, `dpkg-deb -f` package/version/architecture fields, and `sha256sum`. Do not substitute a different architecture or hash.
- If FFmpeg fails to load NVIDIA libraries, check that the host CDI specification is current and the container has `--runtime=runc --device=nvidia.com/gpu=all`. Missing `libnvbufsurface.so.1.0.0` indicates the required runtime libraries were not injected.
- If capability validation fails, check `docker run --rm --pull=never --runtime=runc --device=nvidia.com/gpu=all viseron-jetson-orin:local /usr/bin/ffmpeg -decoders` for `h264_nvv4l2dec` and `hevc_nvv4l2dec`; also check `-h decoder=h264_nvv4l2dec` for NV12 output.
- If shutdown times out, allow the longer stop timeout shown above.
