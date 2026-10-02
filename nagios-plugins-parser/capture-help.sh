#!/bin/bash
# Capture the --help output of every built plugin into OUTDIR/CHECK.txt,
# used by parse_nagios_plugins.py --help-dir for descriptions and to skip
# plugins that are not part of the build.
#
# Runs the ubuntu2404 tarball from dist/ in a container with the Perl modules
# the Perl plugins need, so their help text can be printed.
#
# Usage: nagios-plugins-parser/capture-help.sh OUTDIR

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="${DIST_DIR:-$REPO_DIR/dist}"
VERSION="${VERSION:-2.5}"
TARBALL="nagios-plugins-$VERSION-ubuntu2404-x86_64.tar.gz"

if [ $# -ne 1 ]; then
    echo "Usage: $0 OUTDIR" >&2
    exit 1
fi
OUTDIR="$1"

if [ ! -f "$DIST_DIR/$TARBALL" ]; then
    echo "ERROR: $DIST_DIR/$TARBALL missing, run build/build.sh ubuntu2404" >&2
    exit 1
fi

if command -v podman >/dev/null; then
    RUNTIME=podman
else
    RUNTIME=docker
fi

mkdir -p "$OUTDIR"
rm -f "$OUTDIR"/check_*.txt

# Explicit platform: the local ubuntu:24.04 tag may point to another
# architecture after multi-arch builds
"$RUNTIME" pull -q --platform linux/amd64 docker.io/library/ubuntu:24.04 >/dev/null
"$RUNTIME" run --rm --platform linux/amd64 \
    -v "$DIST_DIR:/dist:ro,Z" \
    -v "$(cd "$OUTDIR" && pwd):/out:Z" \
    -e TARBALL="$TARBALL" \
    docker.io/library/ubuntu:24.04 bash -c '
        set -e
        export DEBIAN_FRONTEND=noninteractive
        apt-get -qq update
        apt-get -qq install -y perl procps iputils-ping dnsutils openssh-client \
            libnet-snmp-perl libcrypt-x509-perl libwww-perl libtimedate-perl \
            libtext-glob-perl >/dev/null
        tar -C / -xzf "/dist/$TARBALL"
        cd /opt/monitoring-nagios-git-*/libexec
        for p in check_*; do
            timeout 10 "./$p" --help > "/out/$p.txt" 2>&1 || true
        done
    '

echo "Captured $(find "$OUTDIR" -name 'check_*.txt' | wc -l) help files in $OUTDIR"
if grep -l "Can't locate" "$OUTDIR"/check_*.txt; then
    echo "WARNING: plugins above could not load Perl modules" >&2
fi
