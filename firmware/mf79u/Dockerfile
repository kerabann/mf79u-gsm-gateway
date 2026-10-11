FROM debian:bookworm-slim@sha256:7c7b2c966bc9ee8cedfeef67e0e279108992c77681fa595db4a9d65c06ccc587
RUN apt-get update -qq && apt-get install -y --no-install-recommends \
    gcc-arm-linux-gnueabi g++-arm-linux-gnueabi libc6-dev-armel-cross \
    binutils-arm-linux-gnueabi mtd-utils python3 ca-certificates make gcc libc6-dev cmake perl autoconf automake libtool pkg-config qemu-user bzip2 \
    && rm -rf /var/lib/apt/lists/*

RUN dpkg --add-architecture armel && apt-get update -qq && apt-get install -y --no-install-recommends libgmp-dev:armel libcrypt-dev:armel && rm -rf /var/lib/apt/lists/*
