FROM alceasan/opencv-arm64:latest as opencv
FROM alceasan/ffmpeg-arm64:latest as ffmpeg

FROM debian:buster

COPY --from=opencv /usr/local /usr/local
COPY --from=ffmpeg /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg /usr/local/bin/ffprobe /usr/local/bin/ffprobe

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
  apt-get install --no-install-recommends -y \
  software-properties-common \
  build-essential \
  apt-transport-https ca-certificates \
  gnupg \
  python3-dev \
  python3-numpy \
  python3-pip \
  python3-sklearn \
  python3-setuptools \
  wget \
  cmake \
  git \
  tzdata \
  # OpenCV runtime deps
  libjpeg-dev libpng-dev libtiff-dev \
  # OpenCV video I/O
  libavcodec-dev libavformat-dev libswscale-dev libv4l-dev \
  libxvidcore-dev libx264-dev \
  # OpenCV Optimizations
  libatlas-base-dev gfortran libtbb-dev \
  # dlib Optimizations
  libatlas3-base libopenblas-dev liblapack-dev libboost-all-dev && \
  # Google Coral
  echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" > /etc/apt/sources.list.d/coral-edgetpu.list && \
  wget -O - https://packages.cloud.google.com/apt/doc/apt-key.gpg --no-check-certificate | apt-key add - && \
  apt-get update && \
  echo "libedgetpu1-max libedgetpu/accepted-eula boolean true" | debconf-set-selections && \
  apt-get install --no-install-recommends -y \
  libedgetpu1-max usbutils python3-pycoral && \
  pip3 install https://dl.google.com/coral/python/tflite_runtime-2.1.0.post1-cp37-cp37m-linux_aarch64.whl && \
  rm -rf /var/lib/apt/lists/* && \
  apt-get autoremove -y && \
  apt-get autoclean -y

# Install dlib 
RUN git clone https://github.com/davisking/dlib.git && \
  cd /dlib; python3 /dlib/setup.py install --compiler-flags "-O3"
  # Not needed on aarch64: --compiler-flags "-mfpu=neon"

# Fetch models
RUN mkdir -p /detectors/models/edgetpu/classification && \
  # EdgeTPU MobileNet SSD v2 Object Detection model
  wget https://dl.google.com/coral/canned_models/mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite -O /detectors/models/edgetpu/model.tflite --progress=bar:force:noscroll && \
  wget https://github.com/google-coral/edgetpu/raw/master/test_data/ssd_mobilenet_v2_coco_quant_postprocess.tflite -O /detectors/models/edgetpu/cpu_model.tflite --progress=bar:force:noscroll && \
  wget https://dl.google.com/coral/canned_models/coco_labels.txt -O /detectors/models/edgetpu/labels.txt --progress=bar:force:noscroll

# Python dependencies
ADD rpi_requirements.txt requirements.txt
RUN wget -q https://bootstrap.pypa.io/get-pip.py && \
  python3 get-pip.py && \
  rm get-pip.py && \
  pip3 install --no-cache-dir \
  -r requirements.txt && \
  rm requirements.txt

ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/vc/lib
ENV VISERON_CUDA_SUPPORTED=false
ENV VISERON_VAAPI_SUPPORTED=false
ENV VISERON_RASPBERRYPI3=false
ENV VISERION_RASPBERRYPI_ARM64=true

VOLUME /recordings

WORKDIR /src/viseron
COPY ./src /src/viseron/

ENTRYPOINT ["python3", "-u"]
CMD ["viseron.py"]
