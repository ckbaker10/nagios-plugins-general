#!/bin/bash
# Build nagios-plugins once per target OS and architecture in a container and
# package the installed prefix as a tarball for deployment to all hosts of that
# OS/architecture. Targets and architectures are listed in build/targets.conf;
# non-native architectures run under QEMU user emulation.
#
# Every target uses the same source tag and the same configure flags, so the
# plugins and their parameters are identical everywhere. One build per OS is
# still needed because the plugins link against system libraries (OpenSSL,
# libc), whose ABI differs between distributions.
#
# Usage: build/build.sh [-j JOBS] [TARGET[:ARCH]...]   (default: everything)
#   build/build.sh                      all targets and architectures
#   build/build.sh debian13 el9:x86_64  all archs of debian13, el9 only x86_64
#   NAGIOS_PLUGINS_TAG=release-2.4.12 build/build.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="${DIST_DIR:-$REPO_DIR/dist}"
LOG_DIR="${LOG_DIR:-$REPO_DIR/work/build-logs}"

NAGIOS_PLUGINS_REPO="${NAGIOS_PLUGINS_REPO:-https://github.com/nagios-plugins/nagios-plugins.git}"
NAGIOS_PLUGINS_TAG="${NAGIOS_PLUGINS_TAG:-release-2.5}"
VERSION="${NAGIOS_PLUGINS_TAG#release-}"
PREFIX="${PREFIX:-/opt/monitoring-nagios-git-$VERSION}"

JOBS=4
if [ "${1:-}" = "-j" ]; then
    JOBS="$2"
    shift 2
fi

if command -v podman >/dev/null; then
    RUNTIME=podman
elif command -v docker >/dev/null; then
    RUNTIME=docker
else
    echo "ERROR: podman or docker required" >&2
    exit 1
fi

# Read targets.conf into "target arch platform image" entries
matrix=()
while read -r target image platforms; do
    for p in $platforms; do
        matrix+=("$target ${p%%=*} ${p#*=} $image")
    done
done < <(grep -v '^[[:space:]]*\(#\|$\)' "$SCRIPT_DIR/targets.conf")

selected=()
if [ $# -eq 0 ]; then
    selected=("${matrix[@]}")
else
    for want in "$@"; do
        found=0
        for entry in "${matrix[@]}"; do
            read -r target arch _ _ <<< "$entry"
            if [ "$want" = "$target" ] || [ "$want" = "$target:$arch" ]; then
                selected+=("$entry")
                found=1
            fi
        done
        if [ "$found" -eq 0 ]; then
            echo "ERROR: unknown target '$want', see build/targets.conf" >&2
            exit 1
        fi
    done
fi

mkdir -p "$DIST_DIR" "$LOG_DIR"

# Pull every image for its platform and tag it per target/arch first. A tag
# like debian:13 can only point to one architecture locally, so parallel
# builds must not share it.
echo "=== Preparing ${#selected[@]} build images"
for entry in "${selected[@]}"; do
    read -r target arch platform image <<< "$entry"
    case "$image" in
        localhost/raspios:*)
            "$SCRIPT_DIR/raspios-image.sh" "${image#localhost/raspios:}" >/dev/null
            ;;
        *)
            "$RUNTIME" pull -q --platform "$platform" "$image" >/dev/null
            ;;
    esac
    "$RUNTIME" tag "$image" "localhost/nagios-plugins-build:$target-$arch"
done

build_one() {
    local target="$1" arch="$2" platform="$3"
    local name="nagios-plugins-$VERSION-$target-$arch"
    local log="$LOG_DIR/$name.log"
    local start
    start=$(date +%s)
    rm -rf "$DIST_DIR/$name.tar.gz" "$DIST_DIR/$name.tar.gz.sha256" "$DIST_DIR/$name.stage"
    if "$RUNTIME" run --rm --platform "$platform" \
        -v "$SCRIPT_DIR/container-build.sh:/build.sh:ro,Z" \
        -v "$DIST_DIR:/dist:Z" \
        -e REPO="$NAGIOS_PLUGINS_REPO" \
        -e TAG="$NAGIOS_PLUGINS_TAG" \
        -e PREFIX="$PREFIX" \
        -e ARCHIVE="$name" \
        "localhost/nagios-plugins-build:$target-$arch" bash /build.sh > "$log" 2>&1; then
        if [ -d "$DIST_DIR/$name.stage" ]; then
            tar -C "$DIST_DIR/$name.stage" --numeric-owner --owner=0 --group=0 \
                -czf "$DIST_DIR/$name.tar.gz" "${PREFIX#/}"
            rm -rf "$DIST_DIR/$name.stage"
        fi
        (cd "$DIST_DIR" && sha256sum "$name.tar.gz" > "$name.tar.gz.sha256")
        echo "OK     $name ($(( $(date +%s) - start ))s)"
    else
        echo "FAILED $name ($(( $(date +%s) - start ))s), see $log"
        return 1
    fi
}

echo "=== Building $NAGIOS_PLUGINS_TAG, $JOBS parallel jobs, logs in $LOG_DIR"
failed=0
running=0
for entry in "${selected[@]}"; do
    read -r target arch platform _ <<< "$entry"
    if [ "$running" -ge "$JOBS" ]; then
        wait -n || failed=$((failed + 1))
        running=$((running - 1))
    fi
    build_one "$target" "$arch" "$platform" &
    running=$((running + 1))
done
while [ "$running" -gt 0 ]; do
    wait -n || failed=$((failed + 1))
    running=$((running - 1))
done

if [ "$failed" -gt 0 ]; then
    echo "=== $failed of ${#selected[@]} builds failed" >&2
    exit 1
fi
echo "=== All ${#selected[@]} builds done: $DIST_DIR"
