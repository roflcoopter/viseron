FROM roflcoopter/opencv-gpu:1.0 as opencv
FROM nvidia/cuda:10.2-cudnn7-devel-ubuntu18.04

COPY --from=opencv /usr/local /usr/local

ENV NVIDIA_DRIVER_CAPABILITIES all

# Add FFMPEG to PATH
ENV PATH=/usr/local/ffmpeg/bin:$PATH
# Specify FFMPEG library folder
ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/ffmpeg/lib

RUN apt-get update && apt-get install -y --no-install-recommends \
    cuda-npp-10-2 \
    curl \
    python3-dev \
    wget \
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

# Fetch models for YOLOv4 darknet
RUN mkdir -p /detectors/models/darknet && \
    wget https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v3_optimal/yolov4.weights -O /detectors/models/darknet/yolov4.weights --progress=bar:force:noscroll && \
    wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4.cfg -O /detectors/models/darknet/yolov4.cfg --progress=bar:force:noscroll && \
    wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/coco.names -O /detectors/models/darknet/coco.names --progress=bar:force:noscroll

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

# Python dependencies
ADD requirements.txt requirements.txt
RUN wget https://bootstrap.pypa.io/get-pip.py --progress=bar:force:noscroll && \
    python3 get-pip.py && \
    rm get-pip.py && \
    pip3 install --no-cache-dir \
    -r requirements.txt && \
    rm requirements.txt

COPY viseron.py /src/viseron/
COPY ./lib /src/viseron/lib

ENTRYPOINT ["python3"]

WORKDIR /src/viseron
CMD ["viseron.py"]
