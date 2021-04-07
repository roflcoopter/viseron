ARG ARCH
ARG BASE_VERSION
ARG OPENCV_VERSION
ARG FFMPEG_VERSION
ARG WHEELS_VERSION
FROM roflcoopter/${ARCH}-opencv:${OPENCV_VERSION} as opencv
FROM roflcoopter/${ARCH}-ffmpeg:${FFMPEG_VERSION} as ffmpeg
FROM roflcoopter/${ARCH}-wheels:${WHEELS_VERSION} as wheels
FROM roflcoopter/${ARCH}-base:${BASE_VERSION}

COPY --from=opencv /opt/opencv /usr/local/
COPY --from=ffmpeg /usr/local /usr/local/
COPY --from=wheels /wheels /wheels

ARG S6_OVERLAY_ARCH
ARG S6_OVERLAY_VERSION

ENV S6_SERVICES_GRACETIME=10000
ENV S6_KEEP_ENV=1

RUN \
  apt-get update && apt-get install -y --no-install-recommends \
  gnupg \
  tzdata \
  python3 \
  python3-pip \
  python3-numpy \
  python3-sklearn \
  # OpenCV and FFmpeg Dependencies
  libgomp1 \
  # dlib Dependencies
  libopenblas-base \
  && rm -rf /var/lib/apt/lists/* \
  \
  && pip3 install /wheels/*.whl \
  && rm -r /wheels \
  \
  && APT_KEY_DONT_WARN_ON_DANGEROUS_USAGE=DontWarn apt-key adv --fetch-keys https://packages.cloud.google.com/apt/doc/apt-key.gpg \
  && echo "deb https://packages.cloud.google.com/apt coral-edgetpu-stable main" > /etc/apt/sources.list.d/coral-edgetpu.list \
  && echo "libedgetpu1-max libedgetpu/accepted-eula select true" | debconf-set-selections \
  && apt-get -qq update && apt-get -qq install --no-install-recommends -y \
  libedgetpu1-max=15.0 \
  \
  && apt-get autoremove -y \
  && apt-get clean -y \
  && rm -rf /var/lib/apt/lists/* \
  && rm -rf /wheels

ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_OVERLAY_ARCH}.tar.gz /tmp/s6-overlay.tar.gz
RUN \
  tar xfz /tmp/s6-overlay.tar.gz -C / \
  && rm -r /tmp/s6-overlay.tar.gz

VOLUME /config
VOLUME /recordings

RUN useradd -u 911 -U abc && \
  mkdir -p /segments

WORKDIR /src
COPY viseron /src/viseron/
COPY rootfs/ /

ENTRYPOINT ["/init"]
