# Building E64 V1

## Target Platform

The E64 V1 public release targets the Commodore 64 emulator
on the Raspberry Pi 3B+ using HDMI video output.

Other inherited platform and machine targets are not validated
as part of this release.

## Build Host

The published source package was independently built on a 64-bit
Devuan Linux system on 24 November 2026.

Install the required development packages on Debian-compatible
Linux distributions:

    sudo apt-get install build-essential git automake autoconf \
        libtool pkg-config autoconf-archive autotools-dev \
        xa65 make cmake m4 bison byacc flex texinfo \
        python3 curl wget xz-utils unzip patch

## Toolchains

The release preparation build used:

- ARM GNU Toolchain 15.2.rel1
- arm-none-eabi-gcc 15.2.1
- Node.js 24.21.0

Node.js 22.12 or newer is required.

The get_gnu_toolchain.sh script locates compatible installed
toolchains or downloads the required versions when necessary.

## Source Preparation

Extract the E64 V1 source archive into a directory of your choice.

The included third-party source already incorporates the patches
used by E64. Do not reset it to upstream revisions or reapply
historical patches indiscriminately.

No Commodore ROM files are required for the normal firmware build.

## Complete Build

From the E64 V1 source root, run:

    bash make_all.sh pi3

This builds the required third-party libraries, runs the applicable
regression checks and builds the E64 kernel.

## Incremental Build

After completing the dependency build:

    source get_gnu_toolchain.sh
    BOARD=pi3 make -f Makefile-C64

## Build Output

The resulting Raspberry Pi kernel is:

    kernel8-32.img

Calculate its SHA256 checksum with:

    sha256sum kernel8-32.img

## Stage an SD Card Package

From the source root:

    python3 tools/stage_e64.py --destination build/e64-release

The destination must not already exist.

This prepares the installation files without accessing or modifying
a physical SD card.

Required proprietary Commodore ROMs must be supplied separately.

See INSTALLATION.md for installation instructions and THIRD_PARTY.md
for dependency attribution and firmware licensing.

## Development and Maintenance

E64 V1 is supplied as-is for independent community development.

Inherited diagnostic build modes, alternative machine targets and
alternative Raspberry Pi models are outside the validated release
configuration.

An independent build of the corresponding source tree was completed
on 24 November 2026. The resulting Raspberry Pi 3B+ kernel SHA-256 was:

    576beee8e8619d889b53d8fc5c389653f7323884dcb4b4662c98dd5e59c662d6

## E64 V1.0.1 Build Verification

The maintenance release was built on Devuan Linux on 26 November 2026.

- ARM GNU Toolchain 15.2.rel1
- arm-none-eabi-gcc 15.2.1
- Node.js 24.21.0
- Regression suite: 278 passed, 0 failed
- Embedded Web UI assets verified
- Raspberry Pi 3B+ startup verified
- Native and Web UI version displays verified
- Config deletion and automatic refresh verified

This was targeted maintenance-release hardware verification,
not a complete retest of every E64 feature.

Published kernel SHA-256:

    2e44b647c06c1776c4652f098cb38330c1b7a212caa664e87363ee32262f5d9c
