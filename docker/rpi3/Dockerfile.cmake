# No CI setup for this image, build locally
ARG UBUNTU_VERSION
FROM balenalib/raspberrypi3-ubuntu:${UBUNTU_VERSION}-build as build
RUN [ "cross-build-start" ]
ENV DEBIAN_FRONTEND=noninteractive

ARG MAKEFLAGS="-j2"
ARG CMAKE_VERSION

## Some libraries fail to compile using the distributed CMake
## Recompiling CMake with the below flags fixes this
## Related to https://gitlab.kitware.com/cmake/cmake/-/issues/20568
ENV PATH=/usr/local/bin:$PATH \
  CFLAGS="-D_FILE_OFFSET_BITS=64" \
  CXXFLAGS="-D_FILE_OFFSET_BITS=64"

RUN \
  DIR=/tmp/cmake && \
  mkdir -p ${DIR} && \
  cd ${DIR} && \
  git clone --depth 1 --single-branch --branch v${CMAKE_VERSION} https://gitlab.kitware.com/cmake/cmake.git/ . && \
  ./bootstrap -- -DCMAKE_BUILD_TYPE:STRING=Release && \
  make && \
  make install && \
  rm -rf ${DIR}

RUN [ "cross-build-end" ]

FROM scratch as scratch
COPY --from=build /usr/local/bin /usr/custom_cmake/bin/
COPY --from=build /usr/local/share /usr/custom_cmake/share/
