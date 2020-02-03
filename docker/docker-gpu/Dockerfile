# docker build -t viseron-gpu . --file ./docker/docker-gpu/Dockerfile
# docker run --runtime=nvidia -ti --rm --tmpfs /tmp viseron-gpu
# docker run --runtime=nvidia -ti --rm viseron-gpu bash
# docker run --runtime=nvidia -ti --rm --device=/dev/dri --privileged=true --entrypoint bash viseron-gpu
# RUN TESTS
# docker run --runtime=nvidia -ti --rm --entrypoint kernprof viseron-gpu -l -v /src/viseron/benchmarks/benchmarks.py
# https://github.com/Borda/docker_python-opencv-ffmpeg/blob/master/gpu/Dockerfile
FROM opencv-gpu as opencv
FROM nvidia/cuda:10.2-cudnn7-devel-ubuntu18.04

COPY --from=opencv /usr/local /usr/local

ENV NVIDIA_DRIVER_CAPABILITIES all

# Add FFMPEG to PATH
ENV PATH=/usr/local/ffmpeg/bin:$PATH
# Specify FFMPEG library folder
ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/ffmpeg/lib

RUN apt-get update && apt-get install -y --no-install-recommends \
        cuda-npp-10-2 \
        python3-dev \
        wget \
        git \
        # gcc needed for line_profiler
        gcc \
        # OpenCV runtime deps
        libjpeg-dev libpng-dev libtiff-dev \
        # OpenCV video I/O
        libavcodec-dev libavformat-dev libswscale-dev libv4l-dev \
        libxvidcore-dev libx264-dev \
        # OpenCV Optimizations
        libatlas-base-dev gfortran libtbb-dev \
        # OpenCL
        ocl-icd-libopencl1 \
        clinfo \
    && rm -rf /var/lib/apt/lists/*

# Add NVIDIA to OpenCL runtime
RUN mkdir -p /etc/OpenCL/vendors && \
    echo "libnvidia-opencl.so.1" > /etc/OpenCL/vendors/nvidia.icd

# OpenCL
RUN mkdir /opencl &&\
    cd /opencl && \
    wget https://github.com/intel/compute-runtime/releases/download/19.31.13700/intel-gmmlib_19.2.3_amd64.deb --progress=bar:force:noscroll && \
    wget https://github.com/intel/compute-runtime/releases/download/19.31.13700/intel-igc-core_1.0.10-2364_amd64.deb --progress=bar:force:noscroll && \
    wget https://github.com/intel/compute-runtime/releases/download/19.31.13700/intel-igc-opencl_1.0.10-2364_amd64.deb --progress=bar:force:noscroll && \
    wget https://github.com/intel/compute-runtime/releases/download/19.31.13700/intel-opencl_19.31.13700_amd64.deb --progress=bar:force:noscroll && \
    wget https://github.com/intel/compute-runtime/releases/download/19.31.13700/intel-ocloc_19.31.13700_amd64.deb --progress=bar:force:noscroll && \
    dpkg -i *.deb && \
    rm -R /opencl

RUN wget https://bootstrap.pypa.io/get-pip.py --progress=bar:force:noscroll && \
    python3 get-pip.py && \
    rm get-pip.py && \
    pip3 install retrying \
    apscheduler \
    imutils \
    paho-mqtt \
    numpy \
    # Cython needed for line_profiler
    Cython \
    line_profiler \
    pyyaml \
    path.py \
    voluptuous \
    python-slugify \
    tensorflow-gpu

ADD /docker/docker-gpu/Video_Codec_SDK_9.1.23.zip /
RUN apt-get update &&  apt-get install -y --no-install-recommends unzip cmake git && \
    unzip -q Video_Codec_SDK_9.1.23.zip -d /usr/local/lib/ && \
    rm Video_Codec_SDK_9.1.23.zip && \
    cd / && \
        git clone https://github.com/NVIDIA/VideoProcessingFramework.git && \
        cd VideoProcessingFramework && \
        # Currently the CMake file is incorrect for UNIX
        #sed -i 's/nvidia-encode/libnvidia-encode/' ./PyNvCodec/TC/CMakeLists.txt && \
        mkdir build && \
        cd build && \
        cmake \
            -DFFMPEG_DIR:PATH="/usr/local/ffmpeg" \
            -DVIDEO_CODEC_SDK_DIR:PATH="/usr/local/lib/Video_Codec_SDK_9.1.23" \
            -DGENERATE_PYTHON_BINDINGS:BOOL="1" \
            -DCMAKE_INSTALL_PREFIX:PATH="/usr/local/vpf"\
            -DCMAKE_VERBOSE_MAKEFILE:BOOL=ON \
            -DAVCODEC_INCLUDE_DIR:PATH="/usr/local/ffmpeg/include" \
            -DAVFORMAT_INCLUDE_DIR:PATH="/usr/local/ffmpeg/include" \
            -DAVUTIL_INCLUDE_DIR:PATH="/usr/local/ffmpeg/include" \
            -DSWRESAMPLE_LIBRARY="/usr/local/ffmpeg/lib/libswresample.so" \
            -DAVFORMAT_LIBRARY="/usr/local/ffmpeg/lib/libavformat.so" \
            -DAVCODEC_LIBRARY="/usr/local/ffmpeg/lib/libavcodec.so" \
            -DAVUTIL_LIBRARY="/usr/local/ffmpeg/lib/libavutil.so" \
            .. &&\
        make -j$(nproc) && \
        make install && \
    apt-get purge --autoremove -y unzip curl git
ENV PYTHONPATH="${PYTHONPATH}:/usr/local/vpf/bin"

# Fetch models for YOLO darknet
RUN mkdir -p /detectors/models/darknet && \
    wget https://pjreddie.com/media/files/yolov3.weights -O /detectors/models/darknet/yolov3.weights --progress=bar:force:noscroll && \
    wget https://raw.githubusercontent.com/pjreddie/darknet/master/cfg/yolov3.cfg -O /detectors/models/darknet/yolov3.cfg --progress=bar:force:noscroll && \
    wget https://raw.githubusercontent.com/pjreddie/darknet/master/data/coco.names -O /detectors/models/darknet/coco.names --progress=bar:force:noscroll

COPY app.py /src/viseron/
COPY ./lib /src/viseron/lib
COPY ./benchmarks /src/viseron/benchmarks

ENTRYPOINT ["python3"]

WORKDIR /src/viseron
CMD ["app.py"]
# CMD ["-y", "-hwaccel", "cuvid", "-c:v", "h264_cuvid", "-vsync", "0", "-i", \
#      "http://distribution.bbb3d.renderfarming.net/video/mp4/bbb_sunflower_1080p_30fps_normal.mp4", \
#      "-vf", "scale_npp=1280:720", "-vcodec", "h264_nvenc", "-t", "00:02:00", "output.mp4"]
