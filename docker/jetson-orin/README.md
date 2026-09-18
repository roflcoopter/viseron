# Local Viseron build for Jetson Orin Nano

This build was tested on a Jetson Orin Nano with ARM64 Ubuntu 24.04 (Noble), L4T R39.2.1, and a JetPack 7 environment. Other Orin models and host versions have not been validated.

## Prerequisites

Use a matching Jetson host with Docker Engine running and accessible to your user, plus NVIDIA Container Toolkit configured for Docker with a current CDI specification that exposes `nvidia.com/gpu=all` and the host multimedia libraries. See [Docker's Ubuntu installation guide](https://docs.docker.com/engine/install/ubuntu/), [NVIDIA's Jetson Orin Nano Docker setup](https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/setup_docker.html), and [NVIDIA's Jetson CDI setup](https://docs.nvidia.com/vpi/install_in_docker.html) if the host is not ready. The build also needs access to the upstream image and package sources used by `docker/Dockerfile`; the package check uses `dpkg-deb` and `sha256sum` on the host.

## Obtain and validate NVIDIA FFmpeg

Get the **exact** `ffmpeg` version `7:8.0.1-nvidia` for `arm64` from NVIDIA's [Jetson FFmpeg APT repository](https://repo.download.nvidia.com/jetson/ffmpeg) (`r39.2/main`). On the matching Jetson host, ensure the NVIDIA APT source `deb https://repo.download.nvidia.com/jetson/ffmpeg r39.2 main` is configured and trusted; see [NVIDIA's Jetson package repository guide](https://docs.nvidia.com/jetson/archives/r39.2/DeveloperGuide/SD/SoftwarePackagesAndTheUpdateMechanism.html). Then, from the repository root, download the pinned version into the local input directory without installing it on the host:

```sh
mkdir -p docker/jetson-orin/input
cd docker/jetson-orin/input
sudo apt update
apt-get download 'ffmpeg=7:8.0.1-nvidia'
cd ..
./validate-input.sh
```

The expected local file is `docker/jetson-orin/input/ffmpeg_7%3a8.0.1-nvidia_arm64.deb`, with SHA256 `a0f70349e7894b8ada4e5d8e5e9065183970d9634ee3542c822e8efa3f52f003`. The validator checks its filename, package fields, and hash. If APT selects or downloads a different version, do not substitute it. The input directory is Git-ignored; the binary is not included in this repository.

## Build the local image

From `docker/jetson-orin` after validation:

```sh
./build-viseron-local.sh
```

The helper validates the local package before building a generic Noble ARM64 Viseron base from the current source tree and layering the NVIDIA package on it. It reads version values from `azure-pipelines/.env`. The final local image is `viseron-jetson-orin:local`. Live external package and image inputs mean a later build may resolve different dependencies. No prebuilt Orin image is provided, and this local workflow does not imply permission to redistribute an image containing NVIDIA FFmpeg.

## Run on a matching host

The tested runtime uses NVIDIA CDI with `--runtime=runc --device=nvidia.com/gpu=all`. Supply the normal Viseron configuration and storage mounts for your installation. Put a real H.264 or H.265 RTSP camera in the host configuration file that will be mounted as `/config/config.yaml`. For example, adapt the address, path, and credentials to your camera (see the [FFmpeg camera configuration](../../docs/src/pages/components-explorer/components/ffmpeg/index.mdx) for more options):

```yaml
ffmpeg:
  camera:
    camera_one:
      name: Camera 1
      host: 192.0.2.10
      port: 554
      path: /Streaming/Channels/101/
      username: your-camera-user
      password: your-camera-password
      stream_format: rtsp
```

With the host directories prepared, start the image:

```sh
docker run -d --name viseron-orin --pull=never \
  --runtime=runc --device=nvidia.com/gpu=all \
  --shm-size=1024mb -p 8888:8888 \
  --mount type=bind,src=/path/to/config,dst=/config \
  --mount type=bind,src=/path/to/segments,dst=/segments \
  --mount type=bind,src=/path/to/event_clips,dst=/event_clips \
  --mount type=bind,src=/path/to/thumbnails,dst=/thumbnails \
  --mount type=bind,src=/path/to/snapshots,dst=/snapshots \
  viseron-jetson-orin:local
```

The image sets `VISERON_FFMPEG_BACKEND=jetson_orin_r39`. Its startup selects the installed `/usr/bin/ffmpeg` through `VISERON_FFMPEG_PATH`. The backend checks that this FFmpeg exposes the NVIDIA H.264 and HEVC decoders with NV12 output. The host must provide matching NVIDIA multimedia libraries and devices through CDI. A stop timeout of 90 seconds allowed the tested container to shut down cleanly: `docker stop -t 90 viseron-orin`.

## Verify with a camera

With the container running, check the selected backend, the decoder capabilities, and the active camera process:

```sh
docker inspect viseron-orin --format '{{range .Config.Env}}{{println .}}{{end}}' | grep '^VISERON_FFMPEG_BACKEND=jetson_orin_r39$'
docker logs viseron-orin 2>&1 | grep 'FFmpeg path: /usr/bin/ffmpeg'
docker exec viseron-orin /usr/bin/ffmpeg -hide_banner -decoders | grep -E 'h264_nvv4l2dec|hevc_nvv4l2dec'
docker exec viseron-orin /usr/bin/ffmpeg -hide_banner -h decoder=h264_nvv4l2dec | grep -A 1 'Supported pixel formats:'
docker exec viseron-orin /usr/bin/ffmpeg -hide_banner -h decoder=hevc_nvv4l2dec | grep -A 1 'Supported pixel formats:'
docker top viseron-orin -eo args | grep -E 'h264_nvv4l2dec|hevc_nvv4l2dec'
```

Both decoder help outputs should include `nv12`. For an H.264 camera, the active FFmpeg decoder process should include `-c:v h264_nvv4l2dec`; for H.265 it should include `-c:v hevc_nvv4l2dec`. Confirm that the camera shows live frames in Viseron's Web UI on port `8888` and that `docker logs viseron-orin` shows no camera or FFmpeg errors. Keep `docker top` output private because its command line can contain camera credentials. The decoder listing checks capability; the running process and live frames check actual use.

## Limits and troubleshooting

Arbitrary Orin `raw_command` configurations are unsupported. Color matrix, range, and NV12/NV21 interpretation were outside the tested scope. Support is limited to the platform above and a matching NVIDIA host/CDI environment.

- If validation rejects the package, check its filename, `dpkg-deb -f` package/version/architecture fields, and `sha256sum`. Do not substitute a different architecture or hash.
- If FFmpeg fails to load NVIDIA libraries, check that the host CDI specification is current and the container has `--runtime=runc --device=nvidia.com/gpu=all`. Missing `libnvbufsurface.so.1.0.0` indicates the required runtime libraries were not injected.
- If capability validation fails, use the `docker exec` decoder checks above on the running container; both decoders must report NV12 output.
- If shutdown times out, allow the longer stop timeout shown above.
