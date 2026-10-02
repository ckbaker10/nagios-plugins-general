# Nagios Plugins Ansible Deployment

Deploys the prebuilt nagios-plugins tarballs (created by `../build/build.sh`,
published by `../build/release.sh`) from the GitHub release to all hosts.
The hosts download the tarball themselves and need HTTPS access to github.com. Nothing is compiled on the hosts and no
build tools are installed there.

The role picks the tarball matching the host's distribution and major version,
downloads it, checks it against the `.sha256` file of the release, unpacks it
to `/opt/monitoring-nagios-git-<version>`, points the symlink
`/opt/monitoring-nagios-git` to it and installs the packages listed in
`RUNTIME-PACKAGES` inside the tarball. The build writes that list: owners of
the shared libraries the plugins link against (OpenSSL, libpq, MariaDB/MySQL,
OpenLDAP, libdbi, ...) plus helper programs (`snmpget`, `fping`, `dig`, `ssh`,
...) and the Perl modules of the Perl plugins.

On RHEL/Rocky/Alma the role installs EPEL and enables CRB (PowerTools on 8,
CodeReady Builder on RHEL), where fping and the Perl modules live. Disable with
`nagios_plugins_enable_epel: false`.

Known gap: `Crypt::X509` is not packaged for SUSE, so `check_ssl_validity`
does not run there.

## Target detection

The role reads `/etc/os-release` (`ID`, `VERSION_ID`) and the userland
architecture (`dpkg --print-architecture` on Debian/Ubuntu, otherwise
`uname -m`), so Armbian maps to its Debian/Ubuntu base and 32-bit Raspberry Pi
OS with a 64-bit kernel still gets the 32-bit build. Raspberry Pi OS 32-bit
(`ID=raspbian` or `/etc/rpi-issue` on armhf) always uses the ARMv6 `raspios*`
build. All targets, architectures and supported boards are listed in
[../docs/PLATFORMS.md](../docs/PLATFORMS.md).

Ansible requirements on the hosts: Python 3.8+ for current ansible-core (EL8:
install `python3.12` or use ansible-core 2.16 on the controller).

## Usage

```bash
# Once: collections (community.general provides zypper for SUSE hosts;
# already included in the full "ansible" package)
ansible-galaxy collection install -r requirements.yml

# Deploy the release set in nagios_plugins_release_tag
ansible-playbook -i inventory.ini playbook.yml
ansible-playbook -i inventory.ini playbook.yml --limit myserver
```

New build: `../build/build.sh` (only the changed targets), then
`../build/release.sh v2.5-2` and set `nagios_plugins_release_tag` accordingly.
Upgrade and rollback between versions: see [../docs/VERSIONING.md](../docs/VERSIONING.md).

Re-running the playbook changes nothing as long as the tarball is unchanged.
A new tarball of the same version replaces that version's directory; other
versions stay installed.

## Variables

See `deploy-nagios-checks/defaults/main.yml`:

- `nagios_plugins_version`: version to install and link (default `2.5`)
- `nagios_plugins_link`: stable path used by the CheckCommands (default `/opt/monitoring-nagios-git`)
- `nagios_plugins_install_prefix`: must match `PREFIX` of the build
- `nagios_plugins_release_tag`: GitHub release to deploy (default `v2.5-1`)
- `nagios_plugins_release_url`: download base URL of the release
- `nagios_plugins_targets`: OS to build target mapping
- `nagios_plugins_extra_packages`: additional packages to install
- `nagios_plugins_enable_epel`: EPEL + CRB on EL (default `true`)

## Verify

```bash
/opt/monitoring-nagios-git/libexec/check_http -V
cat /opt/monitoring-nagios-git/BUILDINFO
```
