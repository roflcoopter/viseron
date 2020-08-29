# Generic Dockerfile.
FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive

# OpenCV/ffmpeg dependencies
RUN apt-get update && \
  apt-get install --no-install-recommends -y \
  software-properties-common \
  build-essential \
  gnupg \
  python3-dev \
  ffmpeg \
  wget \
  curl \
  # VAAPI drivers for Intel hardware accel
  libva-drm2 libva2 i965-va-driver vainfo && \
  # Google Coral
  echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" > /etc/apt/sources.list.d/coral-edgetpu.list && \
  wget -q -O - https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
  apt-get update && \
  echo "libedgetpu1-max libedgetpu/accepted-eula boolean true" | debconf-set-selections && \
  apt-get install --no-install-recommends -y \
  libedgetpu1-max && \
  rm -rf /var/lib/apt/lists/* && \
  apt-get autoremove -y && \
  apt-get autoclean -y

# Python dependencies
ADD requirements.txt requirements.txt
RUN wget -q https://bootstrap.pypa.io/get-pip.py && \
  python3 get-pip.py && \
  rm get-pip.py && \
  pip3 install --no-cache-dir \
  -r requirements.txt && \
  rm requirements.txt && \
  pip3 install opencv-python-headless

# Fetch models
RUN mkdir -p /detectors/models/edgetpu/classification && \
  # EdgeTPU MobileNet SSD v2 Object Detection model
  wget https://dl.google.com/coral/canned_models/mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite -O /detectors/models/edgetpu/model.tflite --progress=bar:force:noscroll && \
  wget https://dl.google.com/coral/canned_models/coco_labels.txt -O /detectors/models/edgetpu/labels.txt --progress=bar:force:noscroll && \
  # Fetch models for YOLO darknet
  mkdir -p /detectors/models/darknet && \
  wget https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v3_optimal/yolov3.weights -O /detectors/models/darknet/yolo.weights --progress=bar:force:noscroll && \
  wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov3.cfg -O /detectors/models/darknet/yolo.cfg --progress=bar:force:noscroll && \
  wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/coco.names -O /detectors/models/darknet/coco.names --progress=bar:force:noscroll

VOLUME /recordings

WORKDIR /src/viseron
COPY ./src /src/viseron/

ENTRYPOINT ["python3", "-u"]
CMD ["viseron.py"]
