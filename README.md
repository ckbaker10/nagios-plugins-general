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
| `ansible-nagios-plugins-deploy/` | Ansible role/playbook: build nagios-plugins from source and install to `/opt/monitoring-nagios-git-2.4.12` |
| `nagios-plugins-parser/` | Parses the nagios-plugins sources and generates Icinga2 CheckCommand definitions |
| `icinga-commands/` | Generated CheckCommands for 2.4.12 (static and dynamic path) and import notes |

## Generate CheckCommands

```bash
git clone --branch release-2.4.12 --depth 1 https://github.com/nagios-plugins/nagios-plugins.git work/nagios-plugins
python3 nagios-plugins-parser/parse_nagios_plugins.py -p work/nagios-plugins -o icinga-commands/commands-nagios-plugins-2.4.12.conf
```

See [icinga-commands/NAGIOS-PLUGINS-IMPORT.md](icinga-commands/NAGIOS-PLUGINS-IMPORT.md)
for the parsed plugin list, import steps and variable naming.

## Deploy

See [ansible-nagios-plugins-deploy/README.md](ansible-nagios-plugins-deploy/README.md).
