# nagios-plugins-general

Standard [nagios-plugins](https://github.com/nagios-plugins/nagios-plugins)
in one pinned version for all Linux hosts.

Distribution packages (Ubuntu, Rocky, ...) ship different plugin versions with
different parameters. This repository builds nagios-plugins from source in one
version (currently `release-2.4.12`) so every host runs identical plugins and
one set of Icinga2 CheckCommands fits all of them.

Custom plugins live in [nagios-plugins](https://github.com/ckbaker10/nagios-plugins).

## Contents

| Path | Purpose |
|---|---|
| `build/` | Builds nagios-plugins once per target OS in a container and packages it as `dist/*.tar.gz` |
| `ansible-nagios-plugins-deploy/` | Ansible role/playbook: downloads the matching tarball from the GitHub release and installs it to `/opt/monitoring-nagios-git-2.4.12` |
| `nagios-plugins-parser/` | Parses the nagios-plugins sources and generates Icinga2 CheckCommand definitions |
| `icinga-commands/` | Generated CheckCommands for 2.4.12 (static and dynamic path) and import notes |

## Generate CheckCommands

```bash
git clone --branch release-2.4.12 --depth 1 https://github.com/nagios-plugins/nagios-plugins.git work/nagios-plugins
python3 nagios-plugins-parser/parse_nagios_plugins.py -p work/nagios-plugins -o icinga-commands/commands-nagios-plugins-2.4.12.conf
```

See [icinga-commands/NAGIOS-PLUGINS-IMPORT.md](icinga-commands/NAGIOS-PLUGINS-IMPORT.md)
for the parsed plugin list, import steps and variable naming.

## Build

```bash
build/build.sh                 # all targets: el8 el9 el10 sles15 sles16 ubuntu2204 ubuntu2404 debian12
build/build.sh el8 ubuntu2404  # selected targets
```

Requires podman or docker. Each target is built in a container of that OS from
the same tag with the same configure flags. RHEL targets are built on Rocky
Linux, SLES targets on the binary-compatible openSUSE Leap of the same version. One build per OS is needed because
the plugins link against the system OpenSSL and libc; plugins and parameters
are identical on all targets. Each tarball contains a `BUILDINFO` file
(tag, commit, build OS) and gets a `.sha256` file next to it.

Publish the tarballs as a GitHub release (requires `gh auth login`):

```bash
build/release.sh v2.4.12-1
```

## Deploy

See [ansible-nagios-plugins-deploy/README.md](ansible-nagios-plugins-deploy/README.md).
