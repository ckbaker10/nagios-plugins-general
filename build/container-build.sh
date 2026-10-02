#!/bin/bash
# Runs inside the build container, called by build.sh.
# Expects REPO, TAG, PREFIX and ARCHIVE in the environment and /dist mounted.

set -euo pipefail

. /etc/os-release
case "$ID" in
    rocky|rhel|almalinux|centos)
        # Rocky mirrors are sometimes out of sync between BaseOS and AppStream;
        # retry with fresh metadata (likely a different mirror).
        for attempt in 1 2 3; do
            if dnf -y -q upgrade >/dev/null &&
                dnf -y -q install git m4 gettext gettext-devel automake autoconf gcc make \
                    openssl-devel perl perl-devel tar gzip procps-ng iputils bind-utils which openssh-clients \
                    >/dev/null; then
                break
            fi
            [ "$attempt" -eq 3 ] && exit 1
            dnf clean all >/dev/null
            sleep 10
        done
        ;;
    opensuse-leap|sles)
        zypper -q -n install git m4 gettext-tools automake autoconf gcc make \
            libopenssl-devel perl tar gzip procps iputils bind-utils which openssh-clients >/dev/null
        # Leap/SLES 16 moved uptime (used by check_load) to coreutils-systemd
        if [ "${VERSION_ID%%.*}" -ge 16 ]; then
            zypper -q -n install coreutils-systemd >/dev/null
        fi
        ;;
    ubuntu|debian)
        export DEBIAN_FRONTEND=noninteractive
        apt-get -qq update
        apt-get -qq install -y git m4 gettext autopoint automake autoconf gcc make \
            libssl-dev perl libperl-dev procps iputils-ping dnsutils openssh-client >/dev/null
        ;;
    *)
        echo "ERROR: unsupported build OS $ID" >&2
        exit 1
        ;;
esac

git -c advice.detachedHead=false clone -q --depth 1 --branch "$TAG" "$REPO" /src
cd /src
./tools/setup >/dev/null
./configure -q --prefix="$PREFIX" --with-cgiurl=/nagios/cgi-bin
make -s -j"$(nproc)"
make -s install DESTDIR=/stage
make -s install-root DESTDIR=/stage

cat > "/stage$PREFIX/BUILDINFO" <<EOF
source=$REPO
tag=$TAG
commit=$(git rev-parse HEAD)
build_os=$PRETTY_NAME
prefix=$PREFIX
EOF

tar -C /stage --numeric-owner -czf "/dist/$ARCHIVE.tar.gz" "${PREFIX#/}"
