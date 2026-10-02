# Nagios Plugins Ansible Deployment

Deploys the prebuilt nagios-plugins tarballs from `../dist/` (created by
`../build/build.sh`) to all hosts. Nothing is compiled on the hosts and no
build tools are installed there.

The role picks the tarball matching the host's distribution and major version,
installs the few runtime packages the plugins need (OpenSSL library, `uptime`,
`ping`, `dig`, Perl), checks the tarball's SHA-256 and unpacks it to
`/opt/monitoring-nagios-git-2.4.12`.

## Supported targets

| Host OS | Target |
|---|---|
| Rocky/RHEL/Alma 8 | `el8` |
| Rocky/RHEL/Alma 9 | `el9` |
| Ubuntu 22.04 | `ubuntu2204` |
| Ubuntu 24.04 | `ubuntu2404` |
| Debian 12 | `debian12` |

A new OS needs a container image in `build/build.sh` and entries in
`nagios_plugins_targets` / `nagios_plugins_runtime_packages`.

## Usage

```bash
# 1. Build the tarballs once (podman or docker)
../build/build.sh

# 2. Deploy
ansible-playbook -i inventory.ini playbook.yml
ansible-playbook -i inventory.ini playbook.yml --limit myserver
```

Re-running the playbook changes nothing as long as the tarball is unchanged.
A new tarball replaces the whole installation directory.

## Variables

See `deploy-nagios-checks/defaults/main.yml`:

- `nagios_plugins_version`: version of the tarballs (default `2.4.12`)
- `nagios_plugins_install_prefix`: must match `PREFIX` of the build
- `nagios_plugins_dist_dir`: tarball directory on the controller (default `../dist`)
- `nagios_plugins_targets`, `nagios_plugins_runtime_packages`: OS mapping

## Verify

```bash
/opt/monitoring-nagios-git-2.4.12/libexec/check_http -V
cat /opt/monitoring-nagios-git-2.4.12/BUILDINFO
```
