#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

log_info() {
  echo -e "${GREEN}${1}${NC}"
}
log_warning() {
  echo -e "${YELLOW}${1}${NC}"
}
log_error() {
  echo -e "${RED}${1}${NC}"
}
