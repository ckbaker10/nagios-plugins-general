# Nagios Plugins Ansible Deployment

Deploys the prebuilt nagios-plugins tarballs (created by `../build/build.sh`,
published by `../build/release.sh`) from the GitHub release to all hosts.
The hosts download the tarball themselves and need HTTPS access to github.com. Nothing is compiled on the hosts and no
build tools are installed there.

The role picks the tarball matching the host's distribution and major version,
installs the few runtime packages the plugins need (OpenSSL library, `uptime`,
`ping`, `dig`, `ssh`, Perl), downloads the tarball, checks it against the `.sha256`
file of the release and unpacks it to
`/opt/monitoring-nagios-git-2.4.12`.

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

A new OS needs a container image in `build/build.sh` and entries in
`nagios_plugins_targets` / `nagios_plugins_runtime_packages`.

## Usage

```bash
# Once: collections (community.general provides zypper for SUSE hosts;
# already included in the full "ansible" package)
ansible-galaxy collection install -r requirements.yml

# Deploy the release set in nagios_plugins_release_tag
ansible-playbook -i inventory.ini playbook.yml
ansible-playbook -i inventory.ini playbook.yml --limit myserver
```

New build: `../build/build.sh`, then `../build/release.sh v2.4.12-2` and set
`nagios_plugins_release_tag` accordingly.

Re-running the playbook changes nothing as long as the tarball is unchanged.
A new tarball replaces the whole installation directory.

## Variables

See `deploy-nagios-checks/defaults/main.yml`:

- `nagios_plugins_version`: version of the tarballs (default `2.4.12`)
- `nagios_plugins_install_prefix`: must match `PREFIX` of the build
- `nagios_plugins_release_tag`: GitHub release to deploy (default `v2.4.12-1`)
- `nagios_plugins_release_url`: download base URL of the release
- `nagios_plugins_targets`, `nagios_plugins_runtime_packages`: OS mapping

## Verify

```bash
/opt/monitoring-nagios-git-2.4.12/libexec/check_http -V
cat /opt/monitoring-nagios-git-2.4.12/BUILDINFO
```
