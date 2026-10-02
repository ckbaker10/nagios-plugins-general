"""
Manual definitions for nagios-plugins 2.4.12 where the source code cannot be
parsed into a usable CheckCommand, or the parsed result needs corrections.

Each entry is keyed by plugin name. Supported keys:

  options       Full option list replacing the parsed result. Each option is a
                dict with: key (argument as passed, e.g. "--tns" or "-w"),
                var (variable suffix), has_arg ("no_argument",
                "required_argument", "optional_argument"), and optionally
                positional (True: value only, no key), order, required,
                description.
  var_names     Variable suffixes by short option: {"w": "warning"}.
  order         Icinga2 argument order per option name (long or short).
  host_var      Variable suffix set to "$address$" by default.
  fixed_values  Options passed with a constant value when their (boolean)
                variable is set: {"O": "1"}.

All entries were checked against the 2.4.12 sources and the --help output of
the built plugins.
"""

MANUAL = {
    # Positional arguments only: check_dummy <integer state> [optional text]
    "check_dummy": {
        "options": [
            {"key": "state", "var": "state", "has_arg": "required_argument",
             "positional": True, "order": 1, "required": True,
             "description": "Integer state to return (0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN)"},
            {"key": "text", "var": "text", "has_arg": "required_argument",
             "positional": True, "order": 2,
             "description": "Optional text to return"},
        ],
    },

    # Shell script with a single optional flag checked via "$1" comparison
    "check_sensors": {
        "options": [
            {"key": "--ignore-fault", "var": "ignore_fault", "has_arg": "no_argument",
             "description": "Ignore sensors reporting a FAULT"},
        ],
    },

    # Mode switch followed by positional arguments, e.g.
    #   check_oracle --tablespace <SID> <USER> <PASS> <TABLESPACE> <CRITICAL> <WARNING>
    #   check_oracle --cache <SID> <USER> <PASS> <CRITICAL> <WARNING>
    "check_oracle": {
        "options": [
            {"key": "mode", "var": "mode", "has_arg": "required_argument",
             "positional": True, "order": 1, "required": True,
             "description": "Check mode: --tns, --db, --login, --connect, --cache, --tablespace or --oranames"},
            {"key": "sid", "var": "sid", "has_arg": "required_argument",
             "positional": True, "order": 2,
             "description": "ORACLE_SID, or hostname/IP for --tns and --oranames"},
            {"key": "user", "var": "user", "has_arg": "required_argument",
             "positional": True, "order": 3,
             "description": "Oracle user (--cache, --tablespace)"},
            {"key": "password", "var": "password", "has_arg": "required_argument",
             "positional": True, "order": 4,
             "description": "Oracle password (--cache, --tablespace)"},
            {"key": "tablespace", "var": "tablespace", "has_arg": "required_argument",
             "positional": True, "order": 5,
             "description": "Tablespace name (--tablespace only)"},
            {"key": "critical", "var": "critical", "has_arg": "required_argument",
             "positional": True, "order": 6,
             "description": "Critical threshold (--cache, --tablespace)"},
            {"key": "warning", "var": "warning", "has_arg": "required_argument",
             "positional": True, "order": 7,
             "description": "Warning threshold (--cache, --tablespace)"},
        ],
    },

    # check_icmp uses plain getopt() without long options
    "check_icmp": {
        "var_names": {
            "w": "warning", "c": "critical", "R": "rta_mode", "P": "packet_loss_mode",
            "J": "jitter_mode", "M": "mos_mode", "S": "score_mode", "O": "out_of_order",
            "4": "ipv4", "6": "ipv6", "H": "host", "s": "source", "n": "num_packets",
            "p": "packets", "i": "packet_interval", "I": "target_interval",
            "m": "min_hosts_alive", "l": "ttl", "t": "timeout", "b": "data_bytes",
            "f": "perfdata_separator", "F": "perfdata_instances", "v": "verbose",
        },
        "host_var": "host",
        # getopt string declares "O:" but the value is ignored; pass a dummy
        # value so -O does not consume the next argument
        "fixed_values": {"O": "1"},
    },

    # -H/--hostname is the virtual host (Host header); the address to connect
    # to is -I/--IP-address
    "check_http": {
        "var_names": {"H": "vhost"},
        "host_var": "IP_address",
    },

    # GetOptions declares "f=s" but "file" without "=s", so only -f takes the
    # file name; keep the variable name of earlier versions
    "check_file_age": {
        "var_names": {"f": "file"},
    },

    # Thresholds only apply to paths given after them, so they must come first
    "check_disk": {
        "order": {
            "warning": -1, "critical": -1, "iwarning": -1, "icritical": -1,
            "units": -1, "kilobytes": -1, "megabytes": -1,
        },
    },
}
