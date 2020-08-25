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
        curl \
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

# Python dependencies
ADD requirements.txt requirements.txt
RUN wget https://bootstrap.pypa.io/get-pip.py --progress=bar:force:noscroll && \
        python3 get-pip.py && \
        rm get-pip.py && \
        pip3 install --no-cache-dir \
        -r requirements.txt && \
        rm requirements.txt

# Fetch models for YOLOv4 darknet
RUN mkdir -p /detectors/models/darknet && \
        wget https://github.com/AlexeyAB/darknet/releases/download/darknet_yolo_v4_pre/yolov4-tiny.weights -O /detectors/models/darknet/yolo.weights --progress=bar:force:noscroll && \
        wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/yolov4-tiny.cfg -O /detectors/models/darknet/yolo.cfg --progress=bar:force:noscroll && \
        wget https://raw.githubusercontent.com/AlexeyAB/darknet/master/cfg/coco.names -O /detectors/models/darknet/coco.names --progress=bar:force:noscroll

# Cleanup
RUN apt-get autoremove -y && \
        apt-get clean && \
        rm -rf /libva /intel-vaapi-driver /libva-utils && \
        rm -rf /root/opencv.zip /root/opencv_contrib.zip /var/lib/apt/lists/*

ENV PATH=/root/bin:$PATH

ENV VISERON_CUDA_SUPPORTED=false
ENV VISERON_VAAPI_SUPPORTED=true
ENV VISERON_OPENCL_SUPPORTED=true
ENV VISERON_RASPBERRYPI3=false

WORKDIR /src/viseron
COPY ./src /src/viseron/

ENTRYPOINT ["python3", "-u"]
CMD ["viseron.py"]
