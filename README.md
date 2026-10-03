# nagios-plugins-general

Standard [nagios-plugins](https://github.com/nagios-plugins/nagios-plugins)
in one pinned version for all Linux hosts.

Distribution packages (Ubuntu, Rocky, ...) ship different plugin versions with
different parameters. This repository builds nagios-plugins from source in one
version (currently `release-2.5`) so every host runs identical plugins and
one set of Icinga2 CheckCommands fits all of them.

Current release: [v2.5-1](https://github.com/ckbaker10/nagios-plugins-general/releases/tag/v2.5-1),
27 tarballs for RHEL/Rocky/Alma 8–10, SLES/openSUSE Leap 15–16, Debian 12–13,
Ubuntu 22.04–26.04 (x86_64, aarch64, armhf) and Raspberry Pi OS 32-bit
(ARMv6), each with the same 66 plugins. Installed under
`/opt/monitoring-nagios-git-<version>`, linked as `/opt/monitoring-nagios-git`.

Related repositories:

- [nagios-plugins-custom](https://github.com/ckbaker10/nagios-plugins-custom):
  own plugins (Tapo, LTE router, SMS, …) as one x86_64 bundle
- [docker-compose-icinga](https://github.com/ckbaker10/docker-compose-icinga):
  Icinga master stack; the generated `icinga-commands/commands-nagios-plugins.conf`
  goes into its `global-zone/` directory

## Contents

| Path | Purpose |
|---|---|
| `build/` | Builds nagios-plugins once per target OS in a container and packages it as `dist/*.tar.gz` |
| `ansible-nagios-plugins-deploy/` | Ansible role/playbook: downloads the matching tarball from the GitHub release and installs it to `/opt/monitoring-nagios-git-<version>`, linked as `/opt/monitoring-nagios-git` |
| `nagios-plugins-parser/` | Parses the nagios-plugins sources and generates Icinga2 CheckCommand definitions |
| `icinga-commands/` | Generated CheckCommands (static and dynamic path) and import notes |
| `docs/` | [PLATFORMS.md](docs/PLATFORMS.md) (OS/CPU/hardware matrix), [VERSIONING.md](docs/VERSIONING.md) (release naming, upgrade, rollback) |

## Generate CheckCommands

```bash
git clone --branch release-2.5 --depth 1 https://github.com/nagios-plugins/nagios-plugins.git work/nagios-plugins
nagios-plugins-parser/capture-help.sh work/help
nagios-plugins-parser/parse_nagios_plugins.py -p work/nagios-plugins --help-dir work/help \
    -o icinga-commands/commands-nagios-plugins.conf.dynamic-path
```

See [icinga-commands/NAGIOS-PLUGINS-IMPORT.md](icinga-commands/NAGIOS-PLUGINS-IMPORT.md)
for the parsed plugin list, import steps and variable naming.

## Build

Targets and architectures are listed in `build/targets.conf`; see
[docs/PLATFORMS.md](docs/PLATFORMS.md) for the OS/hardware matrix.

```bash
build/build.sh                          # everything (27 tarballs, takes hours under emulation)
build/build.sh -j 2 debian13:armhf      # only one target/architecture
NAGIOS_PLUGINS_TAG=release-2.4.12 build/build.sh el9
```

**Rebuild only what failed or changed.** ARM targets run under QEMU user
emulation and take much longer than x86_64; never rebuild the whole matrix to
fix single targets. Logs are in `work/build-logs/`.

Requires podman or docker and, for ARM, `qemu-user-static` with binfmt. Each
target is built in a container of that OS from the same tag with the same
configure flags. RHEL targets are built on Rocky Linux, SLES targets on the
binary-compatible openSUSE Leap of the same version, Raspberry Pi OS 32-bit on
a Raspbian root filesystem created by `build/raspios-image.sh`. Each tarball
contains `BUILDINFO` (tag, commit, build OS) and `RUNTIME-PACKAGES` and gets a
`.sha256` file next to it.

Publish the tarballs as a GitHub release (requires `gh auth login`), see
[docs/VERSIONING.md](docs/VERSIONING.md):

```bash
build/release.sh v2.5-1
```

## Deploy

See [ansible-nagios-plugins-deploy/README.md](ansible-nagios-plugins-deploy/README.md).
