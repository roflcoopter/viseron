FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive

# OpenCV/ffmpeg dependencies
RUN apt-get update && \
        apt-get install --no-install-recommends -y \
        alien \
        build-essential \
        ca-certificates \
        clinfo \
        cmake \
        gfortran \
        git \
#        libass-dev \
        libatlas-base-dev \
        libavcodec-dev \
        libavformat-dev \
#        libfdk-aac-dev \
        libgtk2.0-dev \
        libgtk-3-dev \
        libjpeg-dev \
#        libmp3lame-dev \
#        libopus-dev \
        libpng-dev \
        libpq-dev \
        libswscale-dev \
        libtbb2 \
        libtbb-dev \
        libtiff-dev \
#        libtheora-dev \
        libv4l-dev \
        libx264-dev \
#        libxvidcore-dev \
        libvorbis-dev \
#        libvpx-dev \
#        libspeex-dev \
        mercurial \
        nano \
        pkg-config \
        python3-dev \
        python3-pil \
        python3-numpy \
        python-setuptools \
        sudo \
        unzip \
        wget \
        xz-utils \
        yasm \
        libavdevice-dev \
        libavutil-dev libswresample-dev libavfilter-dev \
#        libwebp-dev \
        libomxil-bellagio-dev \
        i965-va-driver \
        # Coral dependencies
        libusb-1.0-0 \
        python3-pip \
        libc++1 \
        libc++abi1 \
        libunwind8 \
        libgcc1

# Install Google Coral
RUN wget https://dl.google.com/coral/edgetpu_api/edgetpu_api_latest.tar.gz -O edgetpu_api.tar.gz --trust-server-names --progress=bar:force:noscroll \
  && tar xzf edgetpu_api.tar.gz

COPY script/install_edgetpu_cli.sh edgetpu_api/install.sh

RUN cd edgetpu_api \
  && /bin/bash install.sh

# Install ffmpeg from source
WORKDIR /
RUN git clone https://github.com/intel/libva && \
    git clone https://github.com/intel/intel-vaapi-driver && \
    git clone https://github.com/intel/libva-utils && \
    cd /libva && \
    bash autogen.sh && \
    ./configure --prefix=/usr && \
    make && \
    sudo make install && \
    cd /intel-vaapi-driver && \
    bash autogen.sh && \
    ./configure --prefix=/usr && \
    make && \
    sudo make install && \
    cd /libva-utils && \
    bash autogen.sh && \
    ./configure --prefix=/usr && \
    make && \
    sudo make install


# Install OpenCL
RUN mkdir /opencl &&\
    cd /opencl && \
    wget https://github.com/intel/compute-runtime/releases/download/19.31.13700/intel-gmmlib_19.2.3_amd64.deb --progress=bar:force:noscroll && \
    wget https://github.com/intel/compute-runtime/releases/download/19.31.13700/intel-igc-core_1.0.10-2364_amd64.deb --progress=bar:force:noscroll && \
    wget https://github.com/intel/compute-runtime/releases/download/19.31.13700/intel-igc-opencl_1.0.10-2364_amd64.deb --progress=bar:force:noscroll && \
    wget https://github.com/intel/compute-runtime/releases/download/19.31.13700/intel-opencl_19.31.13700_amd64.deb --progress=bar:force:noscroll && \
    wget https://github.com/intel/compute-runtime/releases/download/19.31.13700/intel-ocloc_19.31.13700_amd64.deb --progress=bar:force:noscroll && \
    dpkg -i *.deb && \
    rm -R /opencl

RUN mkdir ~/ffmpeg; cd ~/ffmpeg && \
    hg clone https://bitbucket.org/multicoreware/x265 && \
    cd x265/build/linux && \
    PATH="$HOME/bin:$PATH" cmake -G "Unix Makefiles" -DCMAKE_INSTALL_PREFIX="$HOME/ffmpeg_build" -DENABLE_SHARED:bool=off ../../source && PATH="$HOME/bin:$PATH" && \
    make -j"$(nproc)" && make install && \
    cd ~/ffmpeg && \
    wget -O- http://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2 --progress=bar:force:noscroll | tar xj && \
    cd ~/ffmpeg/ffmpeg && \
    PATH="$HOME/bin:$PATH" PKG_CONFIG_PATH="$HOME/ffmpeg_build/lib/pkgconfig" \
      ./configure \
      --prefix="$HOME/ffmpeg_build" \
      --pkg-config-flags="--static" \
      --extra-cflags="-I$HOME/ffmpeg_build/include" \
      --extra-ldflags="-L$HOME/ffmpeg_build/lib" \
      --extra-libs="-lpthread -lm" \
      --bindir="$HOME/bin" \
      --enable-nonfree \
      --enable-version3 \
#      --enable-libass \
#      --enable-libmp3lame \
#      --enable-libopus \
#      --enable-libfdk-aac \
#      --enable-libtheora \
#      --enable-libvpx \
#      --enable-libwebp \
#      --enable-libxcb \
      --enable-opengl \
      --cpu=native \
      --enable-vaapi \
#      --enable-libspeex \
#      --enable-libxvid \
      --enable-libx264 \
      --enable-libx265 \
#      --enable-omx \
      --enable-gpl && \
    PATH="$HOME/bin:$PATH" make -j"$(nproc)" && make install

WORKDIR /

# OpenCV
ENV opencv=4.1.1
RUN cd ~ \
&& wget -O opencv.zip https://github.com/opencv/opencv/archive/$opencv.zip \
&& wget -O opencv_contrib.zip https://github.com/opencv/opencv_contrib/archive/$opencv.zip \
&& unzip opencv.zip \
&& unzip opencv_contrib.zip \
&& cd ~/opencv-$opencv/ \
&& mkdir build \
&& cd build \
&& cmake -D CMAKE_BUILD_TYPE=RELEASE \
  -DBUILD_TIFF=ON \
  -DBUILD_opencv_java=OFF \
  -D WITH_OPENGL=ON \
  -D WITH_OPENCL=ON \
  -D WITH_OPENMP=ON \
  -D WITH_IPP=ON \
  -D WITH_TBB=ON \
  -D WITH_EIGEN=ON \
  -D WITH_V4L=ON \
  -D WITH_GTK=OFF \
  -D WITH_GTK_2_X=OFF \
  -D WITH_FFMPEG=ON \
  -D WITH_GSTREAMER=ON \
  -D WITH_GSTREAMER_0_10=OFF \
  -D WITH_LIBV4L=ON \
  -D WITH_NVCUVID=ON \
  -D WITH_CSTRIPES=ON \
  -D BUILD_TESTS=OFF \
  -D BUILD_PERF_TESTS=OFF \
  -D BUILD_opencv_python2=OFF \
  -D BUILD_opencv_python3=ON \
  -D CMAKE_BUILD_TYPE=RELEASE \
	-D CMAKE_INSTALL_PREFIX=/usr/local \
	-D INSTALL_PYTHON_EXAMPLES=OFF \
	-D INSTALL_C_EXAMPLES=OFF \
	-D OPENCV_EXTRA_MODULES_PATH=~/opencv_contrib-$opencv/modules \
  -D BUILD_DOCS=OFF \
	-D BUILD_EXAMPLES=OFF .. \
&& make -j"$(nproc)" \
&& make install

#ENV OPENCV_OCL4DNN_CONFIG_PATH=/root/.cache/opencv/4.0/opencl_cache/

WORKDIR /

RUN  wget https://bootstrap.pypa.io/get-pip.py --progress=bar:force:noscroll && \
     python3 get-pip.py && \
     rm get-pip.py && \
     pip3 install retrying \
     apscheduler \
     paho-mqtt \
     path.py \
     numpy \
     imutils \
     Cython \
     Flask \
     line_profiler \
     tenacity \
     pyyaml \
     voluptuous \
     python-slugify


# Fetch models for Google Coral
RUN mkdir -p /detectors/models/edgetpu/classification && \
    apt-get update --fix-missing && \
    apt-get install --no-install-recommends -y curl && \
    # EdgeTPU MobileNet SSD v2 Object Detection model
    wget https://dl.google.com/coral/canned_models/mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite -O /detectors/models/edgetpu/model.tflite --trust-server-names --progress=bar:force:noscroll && \
    wget https://dl.google.com/coral/canned_models/coco_labels.txt -O /detectors/models/edgetpu/labels.txt --trust-server-names --progress=bar:force:noscroll && \
    # Model based on VOC
    wget https://raw.githubusercontent.com/PINTO0309/TPU-MobilenetSSD/master/voc_labels.txt -O /detectors/models/edgetpu/voc-labels.txt --trust-server-names --progress=bar:force:noscroll && \
    wget https://github.com/PINTO0309/TPU-MobilenetSSD/raw/master/mobilenet_ssd_v2_voc_quant_postprocess_edgetpu.tflite -O /detectors/models/edgetpu/voc-model.tflite --trust-server-names --progress=bar:force:noscroll && \
    # PoseNet model
    wget https://github.com/google-coral/project-posenet/raw/master/models/posenet_mobilenet_v1_075_721_1281_quant_decoder_edgetpu.tflite -O /detectors/models/edgetpu/posenet.tflite --trust-server-names --progress=bar:force:noscroll && \
    # Deeplab model
    curl -sc /tmp/cookie "https://drive.google.com/uc?export=download&id=1mdUKcwFTckmoStQpS4SUihGaz7eUt-Xt" > /dev/null && \
    CODE="$(awk '/_warning_/ {print $NF}' /tmp/cookie)"  && \
    curl -Lb /tmp/cookie "https://drive.google.com/uc?export=download&confirm=${CODE}&id=1mdUKcwFTckmoStQpS4SUihGaz7eUt-Xt" -o deeplabv3.zip  && \
    unzip deeplabv3.zip -d /detectors/models/edgetpu  && \
    rm deeplabv3.zip  && \
    # EfficientNet-EdgeTpu (L)
    wget https://dl.google.com/coral/canned-models/efficientnet-edgetpu-L_quant_edgetpu.tflite -O /detectors/models/edgetpu/classification/efficientnet_large.tflite --trust-server-names --progress=bar:force:noscroll && \
    wget https://dl.google.com/coral/canned_models/imagenet_labels.txt -O /detectors/models/edgetpu/classification/imagenet_labels.txt --trust-server-names --progress=bar:force:noscroll && \
    # Fetch models for YOLO darknet
    mkdir -p /detectors/models/darknet && \
    wget https://pjreddie.com/media/files/yolov3.weights -O /detectors/models/darknet/yolov3.weights --progress=bar:force:noscroll && \
    wget https://raw.githubusercontent.com/pjreddie/darknet/master/cfg/yolov3.cfg -O /detectors/models/darknet/yolov3.cfg --progress=bar:force:noscroll && \
    wget https://raw.githubusercontent.com/pjreddie/darknet/master/data/coco.names -O /detectors/models/darknet/coco.names --progress=bar:force:noscroll

# Cleanup
RUN apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /libva /intel-vaapi-driver /libva-utils && \
    rm -rf /edgetpu_api.tar.gz /root/opencv.zip /root/opencv_contrib.zip /var/lib/apt/lists/*

ENV PATH=/root/bin:$PATH

COPY ./lib /src/app/lib
COPY ./app.py /src/app/
WORKDIR /src/app

#CMD ["/bin/bash"]
#CMD ["/usr/local/bin/kernprof", "-l", "app.py", "-o", "/src/app/"]
CMD ["python3", "app.py"]
