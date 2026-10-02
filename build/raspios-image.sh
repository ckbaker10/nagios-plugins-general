#!/bin/bash
# Create a Raspberry Pi OS 32-bit (Raspbian armhf, ARMv6) container image
# localhost/raspios:CODENAME. There is no official image, so the root
# filesystem is bootstrapped with mmdebstrap from the Raspbian and Raspberry Pi
# archives inside a native Debian container (foreign maintainer scripts run
# via QEMU user emulation).
#
# Usage: build/raspios-image.sh CODENAME [--force]    e.g. trixie, bookworm

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 CODENAME [--force]" >&2
    exit 1
fi
CODENAME="$1"
IMAGE="localhost/raspios:$CODENAME"

if command -v podman >/dev/null; then
    RUNTIME=podman
else
    RUNTIME=docker
fi

if [ "${2:-}" != "--force" ] && "$RUNTIME" image exists "$IMAGE" 2>/dev/null; then
    echo "$IMAGE exists"
    exit 0
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Debian 12 on purpose: its gpgv still accepts the SHA1 self-signatures of the
# published Raspbian/Raspberry Pi keys, which the sqv verifier of Debian 13
# rejects. The image then uses the current keyrings from the
# raspbian-archive-keyring/raspberrypi-archive-keyring packages, which are
# verified through the signed repository metadata.
"$RUNTIME" pull -q --platform linux/amd64 docker.io/library/debian:12 >/dev/null
"$RUNTIME" run --rm --privileged --platform linux/amd64 \
    -v "$WORK:/out:Z" \
    -e CODENAME="$CODENAME" \
    docker.io/library/debian:12 bash -c '
        set -e
        export DEBIAN_FRONTEND=noninteractive
        apt-get -qq update
        apt-get -qq install -y mmdebstrap gpg ca-certificates curl qemu-user-static >/dev/null
        curl -fsSL http://raspbian.raspberrypi.com/raspbian.public.key | gpg --dearmor > /tmp/raspbian.gpg
        curl -fsSL https://archive.raspberrypi.com/debian/raspberrypi.gpg.key | gpg --dearmor > /tmp/raspberrypi.gpg
        # mmdebstrap uses only one --keyring, so combine both keys
        cat /tmp/raspbian.gpg /tmp/raspberrypi.gpg > /tmp/keyring.gpg
        mmdebstrap --quiet --architectures=armhf --variant=apt \
            --keyring=/tmp/keyring.gpg \
            --include=ca-certificates,raspbian-archive-keyring,raspberrypi-archive-keyring \
            --customize-hook="echo \"deb [signed-by=/usr/share/keyrings/raspbian-archive-keyring.gpg] http://raspbian.raspberrypi.com/raspbian $CODENAME main contrib non-free rpi\" > \$1/etc/apt/sources.list" \
            --customize-hook="echo \"deb [signed-by=/usr/share/keyrings/raspberrypi-archive-keyring.gpg] http://archive.raspberrypi.com/debian $CODENAME main\" > \$1/etc/apt/sources.list.d/raspi.list" \
            "$CODENAME" /out/rootfs.tar \
            "deb http://raspbian.raspberrypi.com/raspbian $CODENAME main contrib non-free rpi" \
            "deb http://archive.raspberrypi.com/debian $CODENAME main"
    '

"$RUNTIME" import --arch arm --variant v6 --change 'CMD ["/bin/bash"]' "$WORK/rootfs.tar" "$IMAGE" >/dev/null
echo "Created $IMAGE"
