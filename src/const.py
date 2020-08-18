ENV_CUDA_SUPPORTED = "VISERON_CUDA_SUPPORTED"
ENV_OPENCL_SUPPORTED = "VISERON_OPENCL_SUPPORTED"
ENV_RASPBERRYPI3 = "VISERON_RASPBERRYPI3"

CAMERA_GLOBAL_ARGS = ["-hide_banner", "-loglevel", "panic"]

CAMERA_INPUT_ARGS = [
    "-avoid_negative_ts",
    "make_zero",
    "-fflags",
    "nobuffer",
    "-flags",
    "low_delay",
    "-strict",
    "experimental",
    "-fflags",
    "+genpts",
    "-stimeout",
    "5000000",
    "-use_wallclock_as_timestamps",
    "1",
    "-vsync",
    "0",
]

CAMERA_HWACCEL_ARGS = []

CAMERA_OUTPUT_ARGS = ["-f", "rawvideo", "-pix_fmt", "nv12"]

HWACCEL_CUDA_DECODER = ["-c:v", "h264_cuvid"]
HWACCEL_OPENCL_DECODER = ["-hwaccel", "vaapi", "-vaapi_device", "/dev/dri/renderD128"]
HWACCEL_RPI3_DECODER = ["-c:v", "h264_mmal"]
