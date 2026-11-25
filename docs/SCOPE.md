# E64 V1 Release Scope

E64 (Enhanced 64) V1 is a bare-metal Commodore 64 emulator for the
Raspberry Pi 3B+.

E64 V1 is derived from upstream BMC64 5.2.6 and uses VICE and Circle.
This document describes the scope of the published E64 V1 release,
not the scope or policies of the upstream BMC64 project.

## Release Target

The published E64 V1 release targets:

- Raspberry Pi 3B+
- Commodore 64 emulation
- HDMI video output

The public source package documents the complete build target as
`pi3`.

Other inherited Raspberry Pi platforms and machine targets are not
validated as part of this release. Their presence in the source tree
does not constitute a claim of release support.

## Release and Maintenance Status

E64 V1 is provided as-is for independent community development.

The release does not include a commitment to:

- Future firmware or software updates.
- Ongoing development or maintenance.
- Technical support or troubleshooting services.
- Compatibility with future Raspberry Pi hardware or software.
- Acceptance or integration of independently developed changes.

Independent developers are welcome to study, modify, build and
experiment with the published source, subject to the applicable
third-party licenses and copyright notices.

## Hardware and Community Projects

Third-party hardware, adapters, peripherals, PCBs, cases and other
community projects are separate from the E64 V1 software release.

Their compatibility with E64 must not be assumed simply because
they were designed for BMC64 or another Commodore project.

Their authors are responsible for their designs, documentation,
maintenance and support.

The presence of a community project in the documentation does not
constitute E64 testing, certification, endorsement or a guarantee
of compatibility.

## Outside the Validated Release Configuration

The following are outside the validated configuration of this
E64 V1 release:

- Raspberry Pi models other than the Raspberry Pi 3B+.
- Emulated machine targets other than the Commodore 64.
- Alternative video-output configurations.

Inherited source code or build targets for these configurations
do not establish that they have been tested or supported by E64 V1.

## About This Scope

This document describes the published E64 V1 release and its
validated configuration. It is not a roadmap or a promise of
future development.

E64 is an independent project derived from BMC64. Upstream
BMC64 documentation and policies describe their respective
upstream project and must not be interpreted as E64 commitments.
