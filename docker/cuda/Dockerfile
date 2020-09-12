FROM roflcoopter/opencv-cuda:1.0 as opencv
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
    clinfo && \
    # Google Coral
    wget -q https://bootstrap.pypa.io/get-pip.py && \
    python3 get-pip.py && \
    rm get-pip.py && \
    echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" > /etc/apt/sources.list.d/coral-edgetpu.list && \
    wget -q -O - https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
    apt-get update && \
    echo "libedgetpu1-max libedgetpu/accepted-eula boolean true" | debconf-set-selections && \
    apt-get install --no-install-recommends -y \
    libedgetpu1-max && \
    pip3 install https://dl.google.com/coral/python/tflite_runtime-2.1.0.post1-cp36-cp36m-linux_x86_64.whl && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get autoremove -y && \
    apt-get autoclean -y

# Fetch models for YOLOv4 darknet
RUN mkdir -p /detectors/models/edgetpu/classification && \
    # EdgeTPU MobileNet SSD v2 Object Detection model
    wget https://dl.google.com/coral/canned_models/mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite -O /detectors/models/edgetpu/model.tflite --progress=bar:force:noscroll && \
    wget https://dl.google.com/coral/canned_models/coco_labels.txt -O /detectors/models/edgetpu/labels.txt --progress=bar:force:noscroll && \
    mkdir -p /detectors/models/darknet && \
    wget https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v3_optimal/yolov4.weights -O /detectors/models/darknet/yolo.weights --progress=bar:force:noscroll && \
    # wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4.cfg -O /detectors/models/darknet/yolo.cfg --progress=bar:force:noscroll && \
    wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/coco.names -O /detectors/models/darknet/coco.names --progress=bar:force:noscroll

ADD ./docker/cuda/yolov4.cfg /detectors/models/darknet/yolo.cfg

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
RUN pip3 install --no-cache-dir \
    -r requirements.txt && \
    rm requirements.txt

ENV VISERON_CUDA_SUPPORTED=true
ENV VISERON_VAAPI_SUPPORTED=false
ENV VISERON_OPENCL_SUPPORTED=true
ENV VISERON_RASPBERRYPI3=false

VOLUME /recordings

WORKDIR /src/viseron
COPY ./src /src/viseron/

ENTRYPOINT ["python3", "-u"]
CMD ["viseron.py"]
