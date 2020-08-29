FROM roflcoopter/opencv-rpi:1.0 as opencv
FROM roflcoopter/ffmpeg-rpi:1.0 as ffmpeg

FROM debian:buster

COPY --from=opencv /usr/local /usr/local
COPY --from=ffmpeg /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg

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
  wget \
  usbutils \
  # OpenCV runtime deps
  libjpeg-dev libpng-dev libtiff-dev \
  # OpenCV video I/O
  libavcodec-dev libavformat-dev libswscale-dev libv4l-dev \
  libxvidcore-dev libx264-dev \
  # OpenCV Optimizations
  libatlas-base-dev gfortran libtbb-dev

# Google Coral
RUN echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" > /etc/apt/sources.list.d/coral-edgetpu.list && \
  wget -O - https://packages.cloud.google.com/apt/doc/apt-key.gpg --no-check-certificate | apt-key add - && \
  apt-get update && \
  echo "libedgetpu1-max libedgetpu/accepted-eula boolean true" | debconf-set-selections && \
  apt-get install --no-install-recommends -y \
  libedgetpu1-max && \
  pip3 install https://dl.google.com/coral/python/tflite_runtime-2.1.0.post1-cp37-cp37m-linux_armv7l.whl && \
  rm -rf /var/lib/apt/lists/* && \
  apt-get autoremove -y && \
  apt-get autoclean -y

# Fetch models
RUN mkdir -p /detectors/models/edgetpu/classification && \
  # EdgeTPU MobileNet SSD v2 Object Detection model
  wget https://dl.google.com/coral/canned_models/mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite -O /detectors/models/edgetpu/model.tflite --progress=bar:force:noscroll && \
  wget https://github.com/google-coral/edgetpu/raw/master/test_data/ssd_mobilenet_v2_coco_quant_postprocess.tflite -O /detectors/models/edgetpu/cpu_model.tflite --progress=bar:force:noscroll && \
  wget https://dl.google.com/coral/canned_models/coco_labels.txt -O /detectors/models/edgetpu/labels.txt --progress=bar:force:noscroll

# Python dependencies
ADD requirements.txt requirements.txt
RUN wget -q https://bootstrap.pypa.io/get-pip.py && \
  python3 get-pip.py && \
  rm get-pip.py && \
  pip3 install --no-cache-dir \
  -r requirements.txt && \
  rm requirements.txt

ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/opt/vc/lib
ENV VISERON_CUDA_SUPPORTED=false
ENV VISERON_VAAPI_SUPPORTED=false
ENV VISERON_RASPBERRYPI3=true

VOLUME /recordings

WORKDIR /src/viseron
COPY ./src /src/viseron/

ENTRYPOINT ["python3", "-u"]
CMD ["viseron.py"]
