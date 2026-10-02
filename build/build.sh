#!/bin/bash
# Build nagios-plugins once per target OS in a container and package the
# installed prefix as a tarball for deployment to all hosts of that OS.
#
# Every target uses the same source tag and the same configure flags, so the
# plugins and their parameters are identical everywhere. One build per OS is
# still needed because the plugins link against system libraries (OpenSSL,
# libc), whose ABI differs between distributions.
#
# Usage: build/build.sh [TARGET...]   (default: all targets)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="${DIST_DIR:-$REPO_DIR/dist}"

NAGIOS_PLUGINS_REPO="${NAGIOS_PLUGINS_REPO:-https://github.com/nagios-plugins/nagios-plugins.git}"
NAGIOS_PLUGINS_TAG="${NAGIOS_PLUGINS_TAG:-release-2.4.12}"
VERSION="${NAGIOS_PLUGINS_TAG#release-}"
PREFIX="${PREFIX:-/opt/monitoring-nagios-git-$VERSION}"
ARCH="$(uname -m)"

declare -A IMAGES=(
    [el8]=docker.io/library/rockylinux:8
    [el9]=docker.io/library/rockylinux:9
    [el10]=quay.io/rockylinux/rockylinux:10
    [ubuntu2204]=docker.io/library/ubuntu:22.04
    [ubuntu2404]=docker.io/library/ubuntu:24.04
    [debian12]=docker.io/library/debian:12
    # openSUSE Leap is binary compatible with SLES of the same version
    [sles15]=registry.opensuse.org/opensuse/leap:15.6
    [sles16]=registry.opensuse.org/opensuse/leap:16.0
)

if command -v podman >/dev/null; then
    RUNTIME=podman
elif command -v docker >/dev/null; then
    RUNTIME=docker
else
    echo "ERROR: podman or docker required" >&2
    exit 1
fi

if [ $# -eq 0 ]; then
    set -- "${!IMAGES[@]}"
fi

mkdir -p "$DIST_DIR"

for target in "$@"; do
    image="${IMAGES[$target]:-}"
    if [ -z "$image" ]; then
        echo "ERROR: unknown target '$target' (known: ${!IMAGES[*]})" >&2
        exit 1
    fi

    name="nagios-plugins-$VERSION-$target-$ARCH"
    echo "=== Building $name in $image"

    "$RUNTIME" run --rm \
        -v "$SCRIPT_DIR/container-build.sh:/build.sh:ro,Z" \
        -v "$DIST_DIR:/dist:Z" \
        -e REPO="$NAGIOS_PLUGINS_REPO" \
        -e TAG="$NAGIOS_PLUGINS_TAG" \
        -e PREFIX="$PREFIX" \
        -e ARCHIVE="$name" \
        "$image" bash /build.sh

    (cd "$DIST_DIR" && sha256sum "$name.tar.gz" > "$name.tar.gz.sha256")
    echo "=== $DIST_DIR/$name.tar.gz"
done
