ARG ARCH
ARG BASE_VERSION
ARG OPENCV_VERSION
ARG FFMPEG_VERSION
ARG WHEELS_VERSION
ARG UBUNTU_VERSION
FROM roflcoopter/${ARCH}-opencv:${OPENCV_VERSION} as opencv
FROM roflcoopter/${ARCH}-ffmpeg:${FFMPEG_VERSION} as ffmpeg
FROM roflcoopter/${ARCH}-wheels:${WHEELS_VERSION} as wheels

# Build GPAC
FROM ubuntu:${UBUNTU_VERSION} AS gpac

ENV \
  DEBIAN_FRONTEND=noninteractive

RUN \
  apt-get update && apt-get install -y --no-install-recommends \
  build-essential \
  ca-certificates \
  pkg-config \
  g++ \
  git \
  cmake \
  yasm \
  zlib1g-dev

RUN \
  git clone https://github.com/gpac/gpac.git
RUN \
  cd gpac && \
  ./configure --static-bin / && \
  make -j$(nproc)


# Build frontend
FROM node:20.10.0 as frontend

WORKDIR /frontend

COPY frontend/package.json ./
COPY frontend/package-lock.json ./
# npm 10+ fails to install in Docker for some reason
RUN npm install -g npm@9
RUN npm ci --legacy-peer-deps

COPY frontend/ ./
RUN npm run build


# Build Viseron
FROM roflcoopter/${ARCH}-base:${BASE_VERSION}

WORKDIR /src

COPY --from=wheels /wheels /wheels

ARG S6_OVERLAY_ARCH
ARG S6_OVERLAY_VERSION
ARG EXTRA_APT_PACKAGES

ENV \
  DEBIAN_FRONTEND=noninteractive \
  S6_KEEP_ENV=1 \
  S6_SERVICES_GRACETIME=30000 \
  S6_KILL_GRACETIME=30000 \
  S6_KILL_FINISH_MAXTIME=30000 \
  PATH=$PATH:/home/abc/bin \
  LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/usr/local/lib \
  PYTHONPATH=$PYTHONPATH:/usr/local/lib/python3.8/site-packages \
  OPENCV_OPENCL_CACHE_ENABLE=false \
  PGDATA=/config/postgresql \
  PG_COLOR="always"

ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_OVERLAY_ARCH}-installer /tmp/s6-overlay-installer

RUN \
  apt-get update && apt-get install -y --no-install-recommends \
  software-properties-common \
  curl \
  gnupg \
  tzdata \
  python3 \
  python3-pip \
  usbutils \
  # OpenCV and FFmpeg Dependencies
  libgomp1 \
  # dlib Dependencies
  libopenblas-base \
  # PostgreSQL
  postgresql \
  postgresql-contrib \
  # Install extra apt packages from build-arg
  ${EXTRA_APT_PACKAGES} \
  # GStreamer
  libgstreamer1.0-dev \
  libgstreamer-plugins-base1.0-dev \
  libgstreamer-plugins-bad1.0-dev \
  gstreamer1.0-alsa \
  gstreamer1.0-libav \
  gstreamer1.0-plugins-base \
  gstreamer1.0-plugins-good \
  gstreamer1.0-plugins-bad \
  gstreamer1.0-plugins-ugly \
  gstreamer1.0-tools \
  gstreamer1.0-vaapi \
  gstreamer1.0-gl \
  gstreamer1.0-pulseaudio \
  python3-gst-1.0 \
  && rm -rf /var/lib/apt/lists/* \
  \
  && python3 -m pip install --upgrade pip \
  && python3 -m pip install install /wheels/*.whl \
  && rm -r /wheels \
  \
  # Install Coral Edge TPU
  && echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | tee /etc/apt/sources.list.d/coral-edgetpu.list \
  && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - \
  && echo "libedgetpu1-max libedgetpu/accepted-eula select true" | debconf-set-selections \
  && add-apt-repository -y ppa:deadsnakes/ppa \
  && apt-get -qq update && apt-get -qq install -y --no-install-recommends \
  libedgetpu1-max \
  python3.9 \
  python3.9-distutils \
  && curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py \
  && python3.9 get-pip.py \
  && python3.9 -m pip install \
  --extra-index-url https://google-coral.github.io/py-repo/ \
  pycoral~=2.0 \
  \
  && chmod +x /tmp/s6-overlay-installer && /tmp/s6-overlay-installer / \
  && apt-get autoremove -y \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/* \
  && rm -rf /wheels \
  && rm -r /tmp/s6-overlay-installer \
  && rm get-pip.py \
  && useradd --uid 911 --user-group --create-home abc \
  && mkdir -p /home/abc/bin /segments

VOLUME /config
VOLUME /recordings
VOLUME /segments
VOLUME /snapshots
VOLUME /thumbnails

ENTRYPOINT ["/init"]

COPY docker/ffprobe_wrapper /home/abc/bin/ffprobe
COPY docker/ffmpeg_wrapper /home/abc/bin/ffmpeg
COPY --from=opencv /opt/opencv /usr/local/
COPY --from=ffmpeg /usr/local /ffmpeg/
COPY --from=gpac /gpac/bin/gcc /usr/bin
COPY rootfs/ /
COPY --from=frontend /frontend/dist /src/viseron/frontend/
COPY viseron /src/viseron/

ARG VISERON_VERSION="dev"
ARG VISERON_GIT_COMMIT="unknown"
ENV VISERON_VERSION=${VISERON_VERSION}
ENV VISERON_GIT_COMMIT=${VISERON_GIT_COMMIT}