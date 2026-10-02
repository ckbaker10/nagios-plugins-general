# Versions

## Naming

| What | Scheme | Example |
|---|---|---|
| Upstream source | nagios-plugins tag | `release-2.5` |
| GitHub release | `v<upstream>-<build revision>` | `v2.5-1`, `v2.5-2` |
| Tarball | `nagios-plugins-<upstream>-<target>-<arch>.tar.gz` | `nagios-plugins-2.5-debian13-armhf.tar.gz` |
| Install prefix | `/opt/monitoring-nagios-git-<upstream>` | `/opt/monitoring-nagios-git-2.5` |
| Stable path | symlink to the active version | `/opt/monitoring-nagios-git` |

The build revision increases when the same upstream version is rebuilt with
changes on our side (new targets, libraries, build fixes). Releases are never
replaced; a fix gets a new revision.

## On the hosts

Versions are installed side by side. The Ansible role points
`/opt/monitoring-nagios-git` to `nagios_plugins_version`; the Icinga2
CheckCommands only use the stable path.

```
/opt/monitoring-nagios-git-2.4.12/
/opt/monitoring-nagios-git-2.5/
/opt/monitoring-nagios-git -> /opt/monitoring-nagios-git-2.5
```

- Upgrade: set `nagios_plugins_version` / `nagios_plugins_release_tag` (per
  host or group first, then globally) and run the playbook.
- Rollback: set the previous version and run the playbook again; the old
  prefix is still installed.
- Old prefixes are not removed automatically.

## New upstream version

1. Read the upstream NEWS for new or renamed options.
2. Build only what is needed: `NAGIOS_PLUGINS_TAG=release-X.Y build/build.sh`
   builds everything once; afterwards rebuild single failed targets with
   `build/build.sh TARGET:ARCH`, never the whole matrix.
3. Capture help, regenerate the CheckCommands, compare variable names against
   the previous file and note renames in `icinga-commands/NAGIOS-PLUGINS-IMPORT.md`.
4. Check `nagios-plugins-parser/manual_definitions.py` still applies.
5. `build/release.sh vX.Y-1`, set the role defaults, deploy to test hosts,
   then everywhere; import the CheckCommands in the Director.

Only the newest upstream version is maintained. Earlier releases stay
downloadable for rollback.
