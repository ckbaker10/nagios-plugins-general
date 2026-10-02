#!/bin/bash
# Upload the tarballs from dist/ as a GitHub release. The Ansible role
# downloads them from there (nagios_plugins_release_tag).
#
# Usage: build/release.sh TAG     e.g. build/release.sh v2.4.12-1
# Requires an authenticated GitHub CLI (gh auth login).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
DIST_DIR="${DIST_DIR:-$REPO_DIR/dist}"

if [ $# -ne 1 ]; then
    echo "Usage: $0 TAG" >&2
    exit 1
fi
TAG="$1"

shopt -s nullglob
# Only tarballs of the version in the tag (v2.5-1 -> nagios-plugins-2.5-*)
VERSION="${TAG#v}"
VERSION="${VERSION%-*}"
assets=("$DIST_DIR"/nagios-plugins-"$VERSION"-*.tar.gz "$DIST_DIR"/nagios-plugins-"$VERSION"-*.tar.gz.sha256)
if [ ${#assets[@]} -eq 0 ]; then
    echo "ERROR: no tarballs in $DIST_DIR, run build/build.sh first" >&2
    exit 1
fi

(cd "$DIST_DIR" && sha256sum -c --quiet ./nagios-plugins-"$VERSION"-*.sha256)

notes="Prebuilt nagios-plugins, one tarball per target OS.

SHA-256:
\`\`\`
$(cat "$DIST_DIR"/nagios-plugins-"$VERSION"-*.sha256)
\`\`\`"

cd "$REPO_DIR"
gh release create "$TAG" --title "$TAG" --notes "$notes" "${assets[@]}"
