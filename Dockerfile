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

# Python dependencies
ADD requirements.txt requirements.txt
RUN pip3 install --no-cache-dir \
  -r requirements.txt && \
  rm requirements.txt && \
  pip3 install opencv-python-headless

# Fetch models
RUN mkdir -p /detectors/models/edgetpu/classification && \
  # EdgeTPU MobileNet SSD v2 Object Detection model
  wget https://dl.google.com/coral/canned_models/mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite -O /detectors/models/edgetpu/model.tflite --progress=bar:force:noscroll && \
  wget https://github.com/google-coral/edgetpu/raw/master/test_data/ssd_mobilenet_v2_coco_quant_postprocess.tflite -O /detectors/models/edgetpu/cpu_model.tflite --progress=bar:force:noscroll && \
  wget https://dl.google.com/coral/canned_models/coco_labels.txt -O /detectors/models/edgetpu/labels.txt --progress=bar:force:noscroll && \
  # Fetch models for YOLO darknet
  # We are using YOLOv3 since YOLOv4 has issues with OopenCL right now https://github.com/opencv/opencv/issues/17762
  mkdir -p /detectors/models/darknet && \
  wget https://pjreddie.com/media/files/yolov3-tiny.weights -O /detectors/models/darknet/yolo.weights --progress=bar:force:noscroll && \
  wget https://raw.githubusercontent.com/pjreddie/darknet/master/cfg/yolov3-tiny.cfg -O /detectors/models/darknet/yolo.cfg --progress=bar:force:noscroll && \
  wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/coco.names -O /detectors/models/darknet/coco.names --progress=bar:force:noscroll

VOLUME /recordings

WORKDIR /src/viseron
COPY ./src /src/viseron/

ENTRYPOINT ["python3", "-u"]
CMD ["viseron.py"]
