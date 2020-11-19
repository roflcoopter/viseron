FROM ubuntu:18.04

ENV DEBIAN_FRONTEND=noninteractive

# OpenCV/ffmpeg dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
        wget gnupg2 ca-certificates && \
        wget https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS-2019.PUB && \
        apt-key add GPG-PUB-KEY-INTEL-SW-PRODUCTS-2019.PUB && \
        sh -c 'echo deb https://apt.repos.intel.com/mkl all main > /etc/apt/sources.list.d/intel-mkl.list' && \
        apt-get update && apt-get install -y --no-install-recommends \
        alien \
        autoconf \
        autogen \
        automake \
        build-essential \
        clinfo \
        cmake \
        curl \
        git \
        mercurial \
        nano \
        pkgconf \
        python3-dev \
        python3-pil \
        python3-numpy \
        python-setuptools \
        sudo \
        unzip \
        xz-utils \
        tzdata \
        # Intel MKL
        intel-mkl-64bit-2020.3-111 \
        # ffmpeg
        yasm \
        libavcodec-dev \
        libavformat-dev \
        libgtk2.0-dev \
        libgtk-3-dev \
        libjpeg-dev \
        libpng-dev \
        libpq-dev \
        libswscale-dev \
        libtbb2 \
        libtiff-dev \
        libv4l-dev \
        libx264-dev \
        libx265-dev \
        libnuma-dev \
        libvorbis-dev \
        libavdevice-dev \
        libavutil-dev libswresample-dev libavfilter-dev \
        libomxil-bellagio-dev \
        # dlib Optimizations
        libatlas3-base libgfortran3 \
        # OpenCV Optimizations
        libatlas-base-dev libtbb-dev \
        # VA-API
        i965-va-driver \
        # Google Coral
        libusb-1.0-0 \
        libc++1 \
        libc++abi1 \
        libunwind8 \
        libgcc1 && \
        wget -q https://bootstrap.pypa.io/get-pip.py && \
        python3 get-pip.py && \
        rm get-pip.py && \
        echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" > /etc/apt/sources.list.d/coral-edgetpu.list && \
        wget -q -O - https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - && \
        apt-get update && \
        echo "libedgetpu1-max libedgetpu/accepted-eula boolean true" | debconf-set-selections && \
        apt-get install --no-install-recommends -y \
        libedgetpu1-max && \
        pip3 install https://dl.google.com/coral/python/tflite_runtime-2.1.0.post1-cp36-cp36m-linux_x86_64.whl

# Install VA-API
WORKDIR /
RUN git clone https://github.com/intel/libva && \
        git clone https://github.com/intel/intel-vaapi-driver && \
        git clone https://github.com/intel/libva-utils && \
        cd /libva && \
        bash autogen.sh && \
        ./configure --prefix=/usr && \
        make && \
        make install && \
        cd /intel-vaapi-driver && \
        bash autogen.sh && \
        ./configure --prefix=/usr && \
        make && \
        make install && \
        cd /libva-utils && \
        bash autogen.sh && \
        ./configure --prefix=/usr && \
        make && \
        make install


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

# Install ffmpeg
RUN git clone --depth 1 --branch n4.3 https://github.com/ffmpeg/ffmpeg ffmpeg && \
        cd ffmpeg && \
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
        --enable-opengl \
        --cpu=native \
        --enable-vaapi \
        --enable-libx264 \
        --enable-libx265 \
        --enable-gpl && \
        PATH="$HOME/bin:$PATH" make -j"$(nproc)" && make install

WORKDIR /

# OpenCV
ENV opencv=master
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

# Install dlib 
RUN git clone https://github.com/davisking/dlib.git && \
        cd /dlib; python3 /dlib/setup.py install

# Fetch models
RUN mkdir -p /detectors/models/edgetpu/classification && \
        # EdgeTPU MobileNet SSD v2 Object Detection model
        wget https://dl.google.com/coral/canned_models/mobilenet_ssd_v2_coco_quant_postprocess_edgetpu.tflite -O /detectors/models/edgetpu/model.tflite --progress=bar:force:noscroll && \
        wget https://github.com/google-coral/edgetpu/raw/master/test_data/ssd_mobilenet_v2_coco_quant_postprocess.tflite -O /detectors/models/edgetpu/cpu_model.tflite --progress=bar:force:noscroll && \
        wget https://dl.google.com/coral/canned_models/coco_labels.txt -O /detectors/models/edgetpu/labels.txt --progress=bar:force:noscroll && \
        # Fetch models for YOLO darknet
        # We are using YOLOv3 since YOLOv4 has issues with OopenCL right now https://github.com/opencv/opencv/issues/17762
        mkdir -p /detectors/models/darknet && \
        wget https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v3_optimal/yolov3.weights -O /detectors/models/darknet/yolo.weights --progress=bar:force:noscroll && \
        wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov3.cfg -O /detectors/models/darknet/yolo.cfg --progress=bar:force:noscroll && \
        wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/coco.names -O /detectors/models/darknet/coco.names --progress=bar:force:noscroll && \
        # Also supply tiny version
        wget https://pjreddie.com/media/files/yolov3-tiny.weights -O /detectors/models/darknet/yolov3-tiny.weights --progress=bar:force:noscroll && \
        wget https://raw.githubusercontent.com/pjreddie/darknet/master/cfg/yolov3-tiny.cfg -O /detectors/models/darknet/yolov3-tiny.cfg --progress=bar:force:noscroll

# Python dependencies
ADD requirements.txt requirements.txt
ADD requirements.txt requirements.txt
RUN pip3 install --no-cache-dir \
        -r requirements.txt && \
        rm requirements.txt

# Cleanup
RUN apt-get autoremove -y && \
        apt-get clean && \
        rm -rf /libva /intel-vaapi-driver /libva-utils && \
        rm -rf /root/opencv.zip /root/opencv_contrib.zip /var/lib/apt/lists/* && \
        apt-get autoremove -y && \
        apt-get autoclean -y
# Cleanup
RUN apt-get remove -y \
        autoconf \
        autogen \
        automake \
        cmake \
        curl \
        git \
        libtool \
        pkgconf \
        wget && \
        rm -rf /var/lib/apt/lists/* && \
        apt-get autoremove -y && \
        apt-get autoclean -y && \
        rm -rf /libva /intel-vaapi-driver /libva-utils && \
        rm -rf /root/opencv.zip /root/opencv_contrib.zip

ENV PATH=/root/bin:$PATH

ENV VISERON_CUDA_SUPPORTED=false
ENV VISERON_VAAPI_SUPPORTED=true
ENV VISERON_OPENCL_SUPPORTED=true
ENV VISERON_RASPBERRYPI3=false

VOLUME /recordings

WORKDIR /src/viseron
COPY ./src /src/viseron/

ENTRYPOINT ["python3", "-u"]
CMD ["viseron.py"]
