#!/bin/bash
set -e

function sed_patch_value {
  sed -i -E 's/('"$2"')/\1\n'"$3"'/g' "$1"
}
function perl_patch_value {
  perl -i -0777 -pe 's/('"$2"')/\1'"$3"'/g' "$1"
}


# configure
FILE="./configure"
sed_patch_value \
$FILE \
"  --disable-videotoolbox   disable VideoToolbox code \[autodetect\]" \
"  --enable-nvmpi           enable nvmpi code"

perl_patch_value \
$FILE \
"    opencl\n" \
"    nvmpi\n"

sed_patch_value \
$FILE \
'h264_nvenc_encoder_deps="nvenc"' \
'h264_nvmpi_encoder_deps="nvmpi"'

sed_patch_value \
$FILE \
'h264_rkmpp_decoder_select="h264_mp4toannexb_bsf"' \
'h264_nvmpi_decoder_deps="nvmpi"\nh264_nvmpi_decoder_select="h264_mp4toannexb_bsf"'

sed_patch_value \
$FILE \
'hevc_nvenc_encoder_deps="nvenc"' \
'hevc_nvmpi_encoder_deps="nvmpi"'

sed_patch_value \
$FILE \
'hevc_rkmpp_decoder_select="hevc_mp4toannexb_bsf"' \
'hevc_nvmpi_decoder_deps="nvmpi"\nhevc_nvmpi_decoder_select="hevc_mp4toannexb_bsf"'

sed_patch_value \
$FILE \
'mpeg2_cuvid_decoder_deps="cuvid"' \
'mpeg2_nvmpi_decoder_deps="nvmpi"'

sed_patch_value \
$FILE \
'mpeg4_cuvid_decoder_deps="cuvid"' \
'mpeg4_nvmpi_decoder_deps="nvmpi"'

sed_patch_value \
$FILE \
'vp8_cuvid_decoder_deps="cuvid"' \
'vp8_nvmpi_decoder_deps="nvmpi"'

sed_patch_value \
$FILE \
'vp9_cuvid_decoder_deps="cuvid"' \
'vp9_nvmpi_decoder_deps="nvmpi"'

perl_patch_value \
$FILE \
'enabled vapoursynth       && require_pkg_config vapoursynth "vapoursynth-script >= 42" VSScript.h vsscript_init' \
'\nenabled nvmpi             && require_pkg_config nvmpi nvmpi nvmpi.h nvmpi_create_decoder'


# libavcodec/Makefile
FILE="./libavcodec/Makefile"
sed_patch_value \
$FILE \
'OBJS-\$\(CONFIG_NVENC_H264_ENCODER\)      \+\= nvenc_h264.o' \
'OBJS-\$\(CONFIG_H264_NVMPI_DECODER\)      \+\= nvmpi_dec.o\nOBJS-\$\(CONFIG_H264_NVMPI_ENCODER\)      \+\= nvmpi_enc.o'

sed_patch_value \
$FILE \
'OBJS-\$\(CONFIG_HEVC_V4L2M2M_DECODER\)    \+\= v4l2_m2m_dec.o' \
'OBJS-\$\(CONFIG_HEVC_NVMPI_DECODER\)      \+\= nvmpi_dec.o\nOBJS-\$\(CONFIG_HEVC_NVMPI_ENCODER\)      \+\= nvmpi_enc.o'

sed_patch_value \
$FILE \
'OBJS-\$\(CONFIG_MPEG2_CUVID_DECODER\)     \+\= cuviddec.o' \
'OBJS-\$\(CONFIG_MPEG2_NVMPI_DECODER\)     \+\= nvmpi_dec.o'

sed_patch_value \
$FILE \
'OBJS-\$\(CONFIG_MPEG4_CUVID_DECODER\)     \+\= cuviddec.o' \
'OBJS-\$\(CONFIG_MPEG4_NVMPI_DECODER\)     \+\= nvmpi_dec.o'

sed_patch_value \
$FILE \
'OBJS-\$\(CONFIG_VP8_CUVID_DECODER\)       \+\= cuviddec.o' \
'OBJS-\$\(CONFIG_VP8_NVMPI_DECODER\)       \+\= nvmpi_dec.o'

sed_patch_value \
$FILE \
'OBJS-\$\(CONFIG_VP9_CUVID_DECODER\)       \+\= cuviddec.o' \
'OBJS-\$\(CONFIG_VP9_NVMPI_DECODER\)       \+\= nvmpi_dec.o'

# libavcodec/allcodecs.c
FILE="./libavcodec/allcodecs.c"
sed_patch_value \
$FILE \
'extern AVCodec ff_h264_rkmpp_decoder;' \
'extern AVCodec ff_h264_nvmpi_decoder;\nextern AVCodec ff_h264_nvmpi_encoder;'

sed_patch_value \
$FILE \
'extern AVCodec ff_hevc_rkmpp_decoder;' \
'extern AVCodec ff_hevc_nvmpi_decoder;\nextern AVCodec ff_hevc_nvmpi_encoder;'

sed_patch_value \
$FILE \
'extern AVCodec ff_mpeg2_cuvid_decoder;' \
'extern AVCodec ff_mpeg2_nvmpi_decoder;'

sed_patch_value \
$FILE \
'extern AVCodec ff_mpeg4_cuvid_decoder;' \
'extern AVCodec ff_mpeg4_nvmpi_decoder;'

sed_patch_value \
$FILE \
'extern AVCodec ff_vp8_cuvid_decoder;' \
'extern AVCodec ff_vp8_nvmpi_decoder;'

sed_patch_value \
$FILE \
'extern AVCodec ff_vp9_cuvid_decoder;' \
'extern AVCodec ff_vp9_nvmpi_decoder;'
