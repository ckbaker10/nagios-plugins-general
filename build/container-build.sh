#!/bin/bash
# Runs inside the build container, called by build.sh.
# Expects REPO, TAG, PREFIX and ARCHIVE in the environment and /dist mounted.

set -euo pipefail

. /etc/os-release

# Runtime packages besides the linked libraries: helper programs the plugins
# were configured against and Perl modules used by the Perl plugins. Written
# to RUNTIME-PACKAGES together with the owners of the linked libraries; the
# Ansible role installs exactly this list.
case "$ID" in
    rocky|rhel|almalinux|centos)
        RUNTIME_EXTRA="perl procps-ng iputils bind-utils openssh-clients net-snmp-utils fping
            perl-Net-SNMP perl-Crypt-X509 perl-libwww-perl perl-TimeDate perl-Text-Glob perl-Digest-MD5"
        ;;
    opensuse-leap|sles)
        # Crypt::X509 (check_ssl_validity) is not packaged for SUSE
        RUNTIME_EXTRA="perl procps iputils bind-utils openssh-clients net-snmp fping
            perl-Net-SNMP perl-libwww-perl perl-TimeDate perl-Text-Glob"
        if [ "${VERSION_ID%%.*}" -ge 16 ]; then
            RUNTIME_EXTRA="$RUNTIME_EXTRA coreutils-systemd"
        fi
        ;;
    ubuntu|debian|raspbian)
        RUNTIME_EXTRA="perl procps iputils-ping bind9-dnsutils openssh-client snmp fping
            libnet-snmp-perl libcrypt-x509-perl libwww-perl libtimedate-perl libtext-glob-perl"
        ;;
esac

case "$ID" in
    rocky|rhel|almalinux|centos)
        # Rocky mirrors are sometimes out of sync between BaseOS and AppStream;
        # retry with fresh metadata (likely a different mirror).
        # EPEL (fping, Perl modules) and CRB/PowerTools (libdbi-devel)
        dnf -y -q install epel-release dnf-plugins-core >/dev/null
        dnf config-manager --set-enabled crb 2>/dev/null ||
            dnf config-manager --set-enabled powertools
        for attempt in 1 2 3; do
            if dnf -y -q upgrade >/dev/null &&
                dnf -y -q install git m4 gettext gettext-devel automake autoconf gcc make \
                    openssl-devel perl perl-devel tar gzip procps-ng iputils bind-utils which openssh-clients \
                    net-snmp-utils fping libpq-devel libdbi-devel openldap-devel \
                    mariadb-connector-c-devel >/dev/null; then
                break
            fi
            [ "$attempt" -eq 3 ] && exit 1
            dnf clean all >/dev/null
            sleep 10
        done
        ;;
    opensuse-leap|sles)
        zypper -q -n install git m4 gettext-tools automake autoconf gcc make \
            libopenssl-devel perl tar gzip procps iputils bind-utils which openssh-clients \
            net-snmp fping postgresql-devel libdbi-devel libmariadb-devel >/dev/null
        # Leap/SLES 16 moved uptime (used by check_load) to coreutils-systemd
        # and renamed the OpenLDAP headers
        if [ "${VERSION_ID%%.*}" -ge 16 ]; then
            zypper -q -n install coreutils-systemd openldap2_6-devel >/dev/null
        else
            zypper -q -n install openldap2-devel >/dev/null
        fi
        ;;
    ubuntu|debian|raspbian)
        export DEBIAN_FRONTEND=noninteractive
        apt-get -qq update
        apt-get -qq install -y git m4 gettext autopoint automake autoconf gcc make \
            libssl-dev perl libperl-dev procps iputils-ping bind9-dnsutils openssh-client \
            snmp fping libpq-dev libdbi-dev libldap-dev default-libmysqlclient-dev \
            >/dev/null
        ;;
    *)
        echo "ERROR: unsupported build OS $ID" >&2
        exit 1
        ;;
esac

git -c advice.detachedHead=false clone -q --depth 1 --branch "$TAG" "$REPO" /src
cd /src
./tools/setup >/dev/null
# check_radius needs freeradius-client, which only SUSE still ships; disabled
# so that all targets contain the same plugins
./configure -q --prefix="$PREFIX" --with-cgiurl=/nagios/cgi-bin --without-radius
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

# Packages owning the shared libraries the plugins link against
libs=$(find "/stage$PREFIX/libexec" -type f -perm -u+x -exec ldd {} \; 2>/dev/null |
    awk '/=> \// {print $3}' | sort -u)
for lib in $libs; do
    case "$ID" in
        ubuntu|debian|raspbian)
            # usrmerge: dpkg may know the file under /lib or /usr/lib
            { dpkg -S "$lib" 2>/dev/null || dpkg -S "${lib#/usr}" 2>/dev/null ||
                dpkg -S "$(realpath "$lib")"; } | head -1 | cut -d: -f1
            ;;
        *)
            rpm -qf --qf '%{NAME}\n' "$lib"
            ;;
    esac
done > /tmp/lib-packages
# shellcheck disable=SC2086 # word splitting of the package list is intended
printf '%s\n' $RUNTIME_EXTRA | cat - /tmp/lib-packages | sort -u > "/stage$PREFIX/RUNTIME-PACKAGES"

# GNU tar of newer distributions (Ubuntu 26.04) uses a stat call the host's
# QEMU user emulation does not implement; build.sh then packs the copied tree
if ! tar -C /stage --numeric-owner -czf "/dist/$ARCHIVE.tar.gz" "${PREFIX#/}" 2>/tmp/tar.err; then
    cat /tmp/tar.err
    echo "tar failed, leaving the tree for build.sh to pack"
    rm -f "/dist/$ARCHIVE.tar.gz"
    cp -a /stage "/dist/$ARCHIVE.stage"
fi
