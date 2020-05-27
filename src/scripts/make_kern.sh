#!/usr/bin/env sh
cd /usr/src
make -j4 buildkernel KERNCONF=CUSTOM
make installkernel KERNCONF=CUSTOM
