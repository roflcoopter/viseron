ARG ARCH
ARG BASE_VERSION
ARG OPENCV_VERSION
ARG FFMPEG_VERSION
ARG WHEELS_VERSION
FROM roflcoopter/${ARCH}-opencv:${OPENCV_VERSION} as opencv
FROM roflcoopter/${ARCH}-ffmpeg:${FFMPEG_VERSION} as ffmpeg
FROM roflcoopter/${ARCH}-wheels:${WHEELS_VERSION} as wheels
FROM roflcoopter/${ARCH}-base:${BASE_VERSION}

WORKDIR /src

COPY --from=opencv /opt/opencv /usr/local/
COPY --from=ffmpeg /usr/local /usr/local/
COPY --from=wheels /wheels /wheels

ARG S6_OVERLAY_ARCH
ARG S6_OVERLAY_VERSION

ENV \
  DEBIAN_FRONTEND=noninteractive \
  S6_KEEP_ENV=1 \
  S6_SERVICES_GRACETIME=10000 \
  PATH=$PATH:/home/abc/bin \
  OPENCV_OPENCL_CACHE_ENABLE=false

ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_OVERLAY_ARCH}-installer /tmp/s6-overlay-installer

RUN \
  apt-get update && apt-get install -y --no-install-recommends \
  curl \
  gnupg \
  tzdata \
  python3 \
  python3-pip \
  python3-sklearn \
  usbutils \
  # OpenCV and FFmpeg Dependencies
  libgomp1 \
  # dlib Dependencies
  libopenblas-base \
  && rm -rf /var/lib/apt/lists/* \
  \
  && pip3 install /wheels/*.whl \
  && rm -r /wheels \
  \
  && echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" | tee /etc/apt/sources.list.d/coral-edgetpu.list \
  && curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | apt-key add - \
  && echo "libedgetpu1-max libedgetpu/accepted-eula select true" | debconf-set-selections \
  && apt-get -qq update && apt-get -qq install --no-install-recommends -y \
  libedgetpu1-max \
  python3-pycoral \
  \
  && chmod +x /tmp/s6-overlay-installer && /tmp/s6-overlay-installer / \
  && apt-get autoremove -y \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/* \
  && rm -rf /wheels \
  && rm -r /tmp/s6-overlay-installer \
  && useradd --uid 911 --user-group --create-home abc \
  && mkdir -p /home/abc/bin /segments

VOLUME /config
VOLUME /recordings

ENTRYPOINT ["/init"]

COPY rootfs/ /
COPY viseron /src/viseron/
