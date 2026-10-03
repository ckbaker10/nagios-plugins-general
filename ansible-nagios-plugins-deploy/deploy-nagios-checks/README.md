deploy-nagios-checks
====================

Installs the prebuilt nagios-plugins tarball (see `build/build.sh` in this
repository) matching the host OS and userland architecture
(`tasks/detect.yml`), its runtime packages (`RUNTIME-PACKAGES`), and points
`/opt/monitoring-nagios-git` to the installed version. See `../README.md` for
usage and `defaults/main.yml` for variables.
