# Nagios Plugins Ansible Deployment

Deploys the prebuilt nagios-plugins tarballs (created by `../build/build.sh`,
published by `../build/release.sh`) from the GitHub release to all hosts.
The hosts download the tarball themselves and need HTTPS access to github.com. Nothing is compiled on the hosts and no
build tools are installed there.

The role picks the tarball matching the host's distribution and major version,
downloads it, checks it against the `.sha256` file of the release, unpacks it
to `/opt/monitoring-nagios-git-2.4.12` and installs the packages listed in
`RUNTIME-PACKAGES` inside the tarball. The build writes that list: owners of
the shared libraries the plugins link against (OpenSSL, libpq, MariaDB/MySQL,
OpenLDAP, libdbi, ...) plus helper programs (`snmpget`, `fping`, `dig`, `ssh`,
...) and the Perl modules of the Perl plugins.

On RHEL/Rocky/Alma the role installs EPEL and enables CRB (PowerTools on 8,
CodeReady Builder on RHEL), where fping and the Perl modules live. Disable with
`nagios_plugins_enable_epel: false`.

Known gap: `Crypt::X509` is not packaged for SUSE, so `check_ssl_validity`
does not run there.

## Supported targets

| Host OS | Target |
|---|---|
| Rocky/RHEL/Alma 8 | `el8` |
| Rocky/RHEL/Alma 9 | `el9` |
| Rocky/RHEL/Alma 10 | `el10` |
| SLES / openSUSE Leap 15 (SP6+) | `sles15` |
| SLES / openSUSE Leap 16 | `sles16` |
| Ubuntu 22.04 | `ubuntu2204` |
| Ubuntu 24.04 | `ubuntu2404` |
| Debian 12 | `debian12` |

A new OS needs a container image in `build/build.sh`, its packages in
`build/container-build.sh` and an entry in `nagios_plugins_targets`.

## Usage

```bash
# Once: collections (community.general provides zypper for SUSE hosts;
# already included in the full "ansible" package)
ansible-galaxy collection install -r requirements.yml

# Deploy the release set in nagios_plugins_release_tag
ansible-playbook -i inventory.ini playbook.yml
ansible-playbook -i inventory.ini playbook.yml --limit myserver
```

New build: `../build/build.sh`, then `../build/release.sh v2.4.12-3` and set
`nagios_plugins_release_tag` accordingly.

Re-running the playbook changes nothing as long as the tarball is unchanged.
A new tarball replaces the whole installation directory.

## Variables

See `deploy-nagios-checks/defaults/main.yml`:

- `nagios_plugins_version`: version of the tarballs (default `2.4.12`)
- `nagios_plugins_install_prefix`: must match `PREFIX` of the build
- `nagios_plugins_release_tag`: GitHub release to deploy (default `v2.4.12-2`)
- `nagios_plugins_release_url`: download base URL of the release
- `nagios_plugins_targets`: OS to build target mapping
- `nagios_plugins_extra_packages`: additional packages to install
- `nagios_plugins_enable_epel`: EPEL + CRB on EL (default `true`)

## Verify

```bash
/opt/monitoring-nagios-git-2.4.12/libexec/check_http -V
cat /opt/monitoring-nagios-git-2.4.12/BUILDINFO
```
