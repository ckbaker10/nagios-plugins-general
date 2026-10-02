#!/usr/bin/env python3
"""
Motivation for this tool:
Ubuntu / Rocky provide different versions of nagios monitoring tooling
I didn't know that before and want to use the same tools on both systems, obviously.

I simply compiled them from source on Rocky and was confused why I get different results on ubuntu
So I will simply compile them on all systems and deploy them via the parsed config and kickstart import

Parse nagios-plugins source code to extract command-line options
and generate Icinga2 CheckCommand definitions.

Sources of information, in order of precedence:
  1. manual_definitions.py   corrections for plugins the parser cannot handle
  2. plugin source           getopt_long tables and getopt strings (C),
                             GetOptions (Perl), case labels (shell)
  3. --help output           option descriptions (from --help-dir, captured
                             from the built plugins), falling back to the
                             print_help() function in the C source
"""

import re
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

from manual_definitions import MANUAL

NO_ARG = 'no_argument'
REQ_ARG = 'required_argument'
OPT_ARG = 'optional_argument'

# Options every plugin has; not useful as CheckCommand arguments
SKIP_OPTIONS = {'help', 'version', 'usage', 'h', 'V', '?'}

HOST_OPTION_NAMES = {'hostname', 'host', 'Hostname'}


class PluginOption:
    def __init__(self, short: str = None, long: str = None,
                 has_arg: str = NO_ARG, description: str = ""):
        self.short = short
        self.long = long
        self.has_arg = has_arg
        self.description = description.strip()
        # Argument key as passed to the plugin; defaults to long form
        self.key: Optional[str] = None
        self.var: Optional[str] = None
        self.positional = False
        self.order: Optional[int] = None
        self.required = False
        self.fixed_value: Optional[str] = None

    def names(self) -> List[str]:
        return [n for n in (self.long, self.short) if n]

    def arg_key(self) -> str:
        if self.key:
            return self.key
        return f'--{self.long}' if self.long else f'-{self.short}'

    def __repr__(self):
        return f"Option(-{self.short}, --{self.long}, {self.has_arg})"


# --------------------------------------------------------------------------
# C source helpers
# --------------------------------------------------------------------------

def strip_c_comments(text: str) -> str:
    """Remove C comments while keeping string literals intact."""
    pattern = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*', re.DOTALL)
    return pattern.sub(lambda m: m.group(0) if m.group(0)[0] in '"\'' else ' ', text)


def c_string_literals(text: str) -> List[str]:
    """Return C string literals in text, adjacent literals concatenated."""
    result = []
    for m in re.finditer(r'(?:"(?:\\.|[^"\\])*"\s*)+', text):
        parts = re.findall(r'"((?:\\.|[^"\\])*)"', m.group(0))
        result.append(unescape_c(''.join(parts)))
    return result


def unescape_c(s: str) -> str:
    return (s.replace('\\\n', '').replace('\\n', '\n').replace('\\t', '\t')
             .replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\'))


def balanced(text: str, start: int, open_ch: str, close_ch: str) -> Optional[str]:
    """Return text between the bracket at text[start] and its partner."""
    depth = 0
    in_str = None
    i = start
    while i < len(text):
        ch = text[i]
        if in_str:
            if ch == '\\':
                i += 2
                continue
            if ch == in_str:
                in_str = None
        elif ch in '"\'':
            in_str = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start + 1:i]
        i += 1
    return None


def parse_getopt_string(optstring: str) -> Dict[str, str]:
    """Parse a getopt option string ("hVw:c:x::") into {char: has_arg}."""
    result = {}
    s = optstring.lstrip('+-:')
    i = 0
    while i < len(s):
        ch = s[i]
        if s[i + 1:i + 3] == '::':
            result[ch] = OPT_ARG
            i += 3
        elif s[i + 1:i + 2] == ':':
            result[ch] = REQ_ARG
            i += 2
        else:
            result[ch] = NO_ARG
            i += 1
    return result


def load_ut_macros(source_root: Path) -> Dict[str, str]:
    """Load the UT_* help text macros from plugins/utils.h."""
    macros = {}
    utils_h = source_root / 'plugins' / 'utils.h'
    if not utils_h.exists():
        return macros
    text = utils_h.read_text(encoding='utf-8', errors='ignore')
    for m in re.finditer(r'#define\s+(UT_\w+)\s+_\(\s*((?:"(?:\\.|[^"\\])*"\s*)+)\)', text):
        macros[m.group(1)] = unescape_c(''.join(re.findall(r'"((?:\\.|[^"\\])*)"', m.group(2))))
    return macros


def load_option_macros(source_root: Path) -> Dict[str, str]:
    """Load macros used inside option tables, e.g. STD_LONG_OPTS in plugins/utils.h."""
    macros = {}
    utils_h = source_root / 'plugins' / 'utils.h'
    if not utils_h.exists():
        return macros
    text = utils_h.read_text(encoding='utf-8', errors='ignore').replace('\\\n', ' ')
    for m in re.finditer(r'^#define\s+(\w+)\s+(\{\s*".*)$', text, re.MULTILINE):
        macros[m.group(1)] = m.group(2)
    return macros


def c_help_text(content: str, ut_macros: Dict[str, str]) -> str:
    """Render print_help() of a C plugin into approximate --help output."""
    m = re.search(r'\bvoid\s+print_help\s*\(\s*(?:void)?\s*\)\s*\{', content)
    if not m:
        return ''
    body = balanced(content, m.end() - 1, '{', '}') or ''
    lines = []
    for call in re.finditer(r'\bprintf\s*\(', body):
        args_text = balanced(body, call.end() - 1, '(', ')')
        if args_text is None:
            continue
        macro = re.match(r'\s*(UT_\w+)', args_text)
        if macro:
            fmt = ut_macros.get(macro.group(1), '')
            args = c_string_literals(args_text)
        else:
            literals = c_string_literals(args_text)
            if not literals:
                continue
            fmt, args = literals[0], literals[1:]
        # Substitute %s with the following string arguments, other
        # conversions (%c, %d) with a placeholder
        arg_iter = iter(args)
        fmt = re.sub(r'%(-?\d*)s', lambda _: next(arg_iter, ''), fmt)
        fmt = re.sub(r'%[-\d.]*[cdiuflx]', 'N', fmt)
        lines.append(fmt)
    return ''.join(lines)


# --------------------------------------------------------------------------
# --help text parsing (descriptions)
# --------------------------------------------------------------------------

OPTION_HEADER = re.compile(r'^(\s{0,8})\(?(-{1,2}[A-Za-z0-9][\w-]*)')
OPTION_NAME = re.compile(r'^(-{1,2}[A-Za-z0-9][\w-]*)')
# Value placeholders in option headers: PATH, INTEGER, <STRING>, [section]
PLACEHOLDER = re.compile(r'^[<\[{]|^[A-Z0-9_|/:.%+-]+$')


def split_option_header(header: str):
    """Split "-w, --warning=INT  text" into (["-w", "--warning"], "text").

    Handles "-w (--max_warning) text" and "-w, Warning threshold" too.
    """
    names = []
    tokens = header.split()
    i = 0
    while i < len(tokens):
        token = tokens[i].strip(',()')
        m = OPTION_NAME.match(token)
        if m:
            names.append(m.group(1))
        elif not PLACEHOLDER.match(token):
            break
        i += 1
    return names, ' '.join(tokens[i:])


def parse_help_descriptions(help_text: str) -> Dict[str, str]:
    """Map option names ("-w", "--warning") to their description."""
    descriptions: Dict[str, str] = {}
    lines = help_text.splitlines()
    i = 0
    while i < len(lines):
        m = OPTION_HEADER.match(lines[i])
        if not m:
            i += 1
            continue
        indent = len(m.group(1))
        names, inline = split_option_header(lines[i].strip())
        desc = [inline] if inline else []
        i += 1
        while i < len(lines):
            line = lines[i]
            if not line.strip() or OPTION_HEADER.match(line):
                break
            if len(line) - len(line.lstrip()) <= indent:
                break
            desc.append(line.strip())
            i += 1
        text = re.sub(r'\s+', ' ', ' '.join(desc)).strip()
        for name in names:
            if text and name not in descriptions:
                descriptions[name] = text
    return descriptions


# --------------------------------------------------------------------------
# Plugin parser
# --------------------------------------------------------------------------

class PluginParser:
    def __init__(self, source_file: Path, plugin_dir: str = None, command_prefix: str = None,
                 plugin_name: str = None, ut_macros: Dict[str, str] = None,
                 help_text: str = None, option_macros: Dict[str, str] = None):
        self.source_file = source_file
        self.plugin_name = plugin_name or source_file.name.split('.')[0]  # check_apt
        self.plugin_dir = plugin_dir  # Optional static path prefix
        self.command_prefix = command_prefix  # Optional command name prefix
        self.options: List[PluginOption] = []
        self.content = ""
        self.ut_macros = ut_macros or {}
        self.option_macros = option_macros or {}
        self.help_text = help_text
        self.host_var: Optional[str] = None
        self.manual = MANUAL.get(self.plugin_name, {})

    def parse(self) -> bool:
        """Parse the source file and extract options."""
        try:
            self.content = self.source_file.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            print(f"Error reading {self.source_file}: {e}")
            return False

        if 'options' in self.manual:
            self.load_manual_options()
            return True

        suffix = self.source_file.name.split('.', 1)[1] if '.' in self.source_file.name else ''
        if suffix.startswith('c'):
            ok = self.parse_c_file()
        elif suffix.startswith('pl'):
            ok = self.parse_perl_file()
        elif suffix.startswith('sh'):
            ok = self.parse_shell_file()
        else:
            ok = False
        if ok:
            self.apply_manual_corrections()
            self.add_descriptions()
        return ok

    def load_manual_options(self):
        for spec in self.manual['options']:
            opt = PluginOption(has_arg=spec['has_arg'], description=spec.get('description', ''))
            opt.key = spec['key']
            opt.var = spec['var']
            opt.positional = spec.get('positional', False)
            opt.order = spec.get('order')
            opt.required = spec.get('required', False)
            self.options.append(opt)

    def parse_c_file(self) -> bool:
        """Parse getopt_long option tables and getopt strings."""
        code = strip_c_comments(self.content)
        by_short: Dict[str, PluginOption] = {}

        # All "struct option NAME[] = { ... }" tables, any variable name
        for m in re.finditer(r'struct\s+option\s+\w+\s*\[\s*\]\s*=\s*\{', code):
            table = balanced(code, m.end() - 1, '{', '}') or ''
            for name, body in self.option_macros.items():
                table = re.sub(rf'\b{name}\b', lambda _: body, table)
            entry = re.compile(
                r'\{\s*"([^"]+)"\s*,\s*(no_argument|required_argument|optional_argument|[012])'
                r'\s*,\s*[^,]+,\s*([^}]+?)\s*\}')
            for e in entry.finditer(table):
                long_name, has_arg, val = e.group(1), e.group(2), e.group(3)
                has_arg = {'0': NO_ARG, '1': REQ_ARG, '2': OPT_ARG}.get(has_arg, has_arg)
                if long_name in SKIP_OPTIONS:
                    continue
                short = None
                char = re.fullmatch(r"'(.)'", val)
                if char:
                    short = char.group(1)
                opt = PluginOption(short=short, long=long_name, has_arg=has_arg)
                self.options.append(opt)
                if short and short not in by_short:
                    by_short[short] = opt

        # Short options from the getopt / getopt_long option string; adds
        # options that have no long form (e.g. check_icmp)
        for m in re.finditer(r'\bgetopt(?:_long)?\s*\(', code):
            args = balanced(code, m.end() - 1, '(', ')') or ''
            literals = c_string_literals(args)
            if not literals:
                continue
            for short, has_arg in parse_getopt_string(literals[0]).items():
                if short in SKIP_OPTIONS or short in by_short:
                    continue
                opt = PluginOption(short=short, has_arg=has_arg)
                self.options.append(opt)
                by_short[short] = opt

        if self.help_text is None:
            self.help_text = c_help_text(self.content, self.ut_macros)

        return len(self.options) > 0

    def parse_perl_file(self) -> bool:
        """Parse Getopt::Long GetOptions() calls."""
        m = re.search(r'GetOptions\s*\(', self.content)
        if not m:
            print(f"  No GetOptions found in {self.plugin_name}")
            return False
        getopts_content = balanced(self.content, m.end() - 1, '(', ')') or ''
        getopts_content = re.sub(r'#[^\n]*', '', getopts_content)

        # "w=s" => \$opt_w, "warning|w=s" => \$opt_w, "file" => \$opt_f
        forms_by_var: Dict[str, List] = {}
        for spec, var in re.findall(r'["\']([^"\']+)["\']\s*=>\s*\\?\$(\w+)', getopts_content):
            spec_m = re.fullmatch(r'([\w|-]+)([=:][sif][@%]?|!|\+)?', spec)
            if not spec_m:
                continue
            type_spec = spec_m.group(2) or ''
            has_arg = REQ_ARG if type_spec.startswith('=') else OPT_ARG if type_spec.startswith(':') else NO_ARG
            for name in spec_m.group(1).split('|'):
                if name in SKIP_OPTIONS:
                    continue
                forms_by_var.setdefault(var, []).append((name, has_arg))

        for var, forms in forms_by_var.items():
            ranks = {NO_ARG: 0, OPT_ARG: 1, REQ_ARG: 2}
            has_arg = max((f[1] for f in forms), key=lambda a: ranks[a])
            # Only keep forms that accept the argument, e.g. check_file_age
            # declares "f=s" but "file" without "=s"
            usable = [f for f in forms if f[1] == has_arg]
            opt = PluginOption(has_arg=has_arg)
            for name, _ in usable:
                if len(name) == 1 and not opt.short:
                    opt.short = name
                elif len(name) > 1 and not opt.long:
                    opt.long = name
            self.options.append(opt)

        return len(self.options) > 0

    def parse_shell_file(self) -> bool:
        """Parse 'case "$1" in --opt) var=$2; shift ;;' option loops."""
        by_var: Dict[str, PluginOption] = {}
        for label, body in re.findall(r'^\s*([-\w|]+)\)\s*\n(.*?);;', self.content, re.DOTALL | re.MULTILINE):
            names = [n for n in label.split('|') if n.startswith('-')]
            if not names:
                continue
            assign = re.search(r'(\w+)=\$\{?2\}?', body)
            var = assign.group(1) if assign else f'flag_{names[0].lstrip("-")}'
            for name in names:
                bare = name.lstrip('-')
                if bare in SKIP_OPTIONS:
                    continue
                opt = by_var.setdefault(var, PluginOption(has_arg=REQ_ARG if assign else NO_ARG))
                if name.startswith('--'):
                    opt.long = opt.long or bare
                else:
                    opt.short = opt.short or bare
        self.options = list(by_var.values())
        return len(self.options) > 0

    def apply_manual_corrections(self):
        var_names = self.manual.get('var_names', {})
        order = self.manual.get('order', {})
        fixed = self.manual.get('fixed_values', {})
        for opt in self.options:
            if opt.short in var_names:
                opt.var = var_names[opt.short]
            for name in opt.names():
                if name in order:
                    opt.order = order[name]
                if name in fixed:
                    opt.fixed_value = fixed[name]
        self.host_var = self.manual.get('host_var')

    def add_descriptions(self):
        if not self.help_text:
            return
        descriptions = parse_help_descriptions(self.help_text)
        for opt in self.options:
            if opt.description:
                continue
            for key in ([f'--{opt.long}'] if opt.long else []) + ([f'-{opt.short}'] if opt.short else []):
                if key in descriptions:
                    opt.description = descriptions[key]
                    break

    def var_suffix(self, opt: PluginOption) -> str:
        if opt.var:
            return opt.var
        return (opt.long or opt.short).replace('-', '_')

    def generate_icinga_command(self) -> str:
        """Generate Icinga2 CheckCommand definition."""
        lines = []
        # Apply command prefix if specified
        command_name = f"{self.command_prefix}_{self.plugin_name}" if self.command_prefix else self.plugin_name
        lines.append(f'object CheckCommand "{command_name}" {{')
        lines.append('  import "plugin-check-command"')

        # Use static path if provided, otherwise use PluginDir variable
        if self.plugin_dir:
            lines.append(f'  command = [ "{self.plugin_dir}/{self.plugin_name}" ]')
        else:
            lines.append(f'  command = [ PluginDir + "/{self.plugin_name}" ]')

        lines.append('')
        lines.append('  arguments = {')

        hostname_var = f'{self.plugin_name}_{self.host_var}' if self.host_var else None
        seen_keys = set()

        for opt in self.options:
            if not (opt.long or opt.short or opt.key):
                continue
            arg_key = opt.arg_key()
            if arg_key in seen_keys:
                continue
            seen_keys.add(arg_key)

            var = f'{self.plugin_name}_{self.var_suffix(opt)}'
            takes_value = opt.has_arg in (REQ_ARG, OPT_ARG)

            # Track hostname parameter for later vars assignment
            if (not hostname_var and takes_value and not opt.positional
                    and (opt.long in HOST_OPTION_NAMES or (not opt.long and opt.short == 'H'))):
                hostname_var = var

            lines.append(f'    "{arg_key}" = {{')
            if opt.positional:
                lines.append(f'      value = "${var}$"')
                lines.append('      skip_key = true')
            elif opt.fixed_value is not None:
                lines.append(f'      value = "{opt.fixed_value}"')
                lines.append(f'      set_if = "${var}$"')
            elif opt.has_arg == OPT_ARG:
                # Optional arguments must be attached ("--ssl=1.2"); a value of
                # true passes the bare option
                sep = '=' if arg_key.startswith('--') else ''
                lines.append('      value = {{')
                lines.append(f'        var v = macro("${var}$")')
                lines.append(f'        if (v == true) {{ return "{arg_key}" }}')
                lines.append(f'        if (v != false && v != "") {{ return "{arg_key}{sep}" + v }}')
                lines.append('      }}')
                lines.append('      skip_key = true')
                lines.append('      set_if = {{')
                lines.append(f'        var v = macro("${var}$")')
                lines.append('        return v != false && v != "" && v != null')
                lines.append('      }}')
            elif takes_value:
                lines.append(f'      value = "${var}$"')
            else:
                # Boolean flag
                lines.append(f'      set_if = "${var}$"')
            if opt.order is not None:
                lines.append(f'      order = {opt.order}')
            if opt.required:
                lines.append('      required = true')
            if opt.description:
                lines.append(f'      description = "{icinga_escape(opt.description)}"')
            lines.append('    }')

        lines.append('  }')

        # Add default vars assignment for hostname parameter
        if hostname_var:
            lines.append('')
            lines.append(f'  vars.{hostname_var} = "$address$"')

        lines.append('}')
        lines.append('')

        return '\n'.join(lines)


def icinga_escape(text: str) -> str:
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\t', ' ')


# --------------------------------------------------------------------------
# Source tree helpers
# --------------------------------------------------------------------------

def source_version(source_root: Path) -> str:
    configure_ac = source_root / 'configure.ac'
    if configure_ac.exists():
        m = re.search(r'AC_INIT\(\s*\[?nagios-plugins\]?\s*,\s*\[?([\w.]+)',
                      configure_ac.read_text(errors='ignore'))
        if m:
            return m.group(1)
    return 'unknown'


def source_commit(source_root: Path) -> Optional[str]:
    try:
        return subprocess.run(['git', '-C', str(source_root), 'rev-parse', 'HEAD'],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def tcp_aliases(source_root: Path) -> List[str]:
    """check_tcp is installed under several names (symlinks), see plugins/Makefile.am."""
    makefile = source_root / 'plugins' / 'Makefile.am'
    if not makefile.exists():
        return []
    text = makefile.read_text(errors='ignore').replace('\\\n', ' ')
    m = re.search(r'^check_tcp_programs\s*=\s*(.*)$', text, re.MULTILINE)
    if not m:
        return []
    names = m.group(1).split()
    configure_ac = source_root / 'configure.ac'
    ssl_names = []
    if configure_ac.exists():
        ssl = re.search(r'check_tcp_ssl="([^"]*)"', configure_ac.read_text(errors='ignore'))
        if ssl:
            ssl_names = ssl.group(1).split()
    result = []
    for name in names:
        result.extend(ssl_names if name == '@check_tcp_ssl@' else [name])
    return result


def update_progress(filename: str, status: str, notes: str = "", progress_file: Optional[Path] = None):
    """Update parseprogress.txt with parsing status."""
    if not progress_file:
        return

    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Create progress file if it doesn't exist
    if not progress_file.exists():
        progress_file.write_text(f"{filename}|{status}|{timestamp}|{notes}\n")
        return

    # Read all lines
    lines = progress_file.read_text().split('\n')

    # Update the matching line
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(filename + '|'):
            lines[i] = f"{filename}|{status}|{timestamp}|{notes}"
            updated = True
            break

    # Add new line if not found
    if not updated:
        lines.append(f"{filename}|{status}|{timestamp}|{notes}")

    # Write back
    progress_file.write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser(
        description='Parse Nagios plugins source code and generate Icinga2 CheckCommand definitions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -p /path/to/nagios-plugins -o commands.conf
  %(prog)s -p ./nagios-plugins -o commands.conf --help-dir ./help
  %(prog)s -p ./plugins -o commands.conf --plugin-path /opt/monitoring-nagios-git-2.4.12/libexec
  %(prog)s -p ./plugins -o commands-git.conf --command-prefix git --plugin-path /opt/monitoring-git/libexec
        """
    )

    parser.add_argument(
        '-p', '--plugins-dir',
        required=True,
        type=Path,
        help='Path to nagios-plugins source directory containing check_*.c and check_*.pl files'
    )

    parser.add_argument(
        '-o', '--output',
        required=True,
        type=Path,
        help='Output file path for generated Icinga2 CheckCommand definitions'
    )

    parser.add_argument(
        '--help-dir',
        type=Path,
        help='Directory with CHECK.txt files containing the --help output of the built plugins '
             '(see capture-help.sh). Used for descriptions; plugins without a file are not built '
             'and are skipped.'
    )

    parser.add_argument(
        '--track-progress',
        action='store_true',
        help='Enable progress tracking (creates parseprogress.txt in script directory)'
    )

    parser.add_argument(
        '--plugin-path',
        type=str,
        help='Static plugin path prefix (e.g., /opt/monitoring-nagios-git-2.4.12/libexec). If not specified, uses PluginDir variable.'
    )

    parser.add_argument(
        '--command-prefix',
        type=str,
        help='Prefix for CheckCommand object names (e.g., "git" produces "git_check_http"). Useful for distinguishing plugin versions.'
    )

    args = parser.parse_args()

    plugins_dir = args.plugins_dir.resolve()
    output_file = args.output.resolve()

    # Setup progress file if requested
    progress_file = None
    if args.track_progress:
        script_dir = Path(__file__).parent
        progress_file = script_dir / 'parseprogress.txt'
        print(f"Progress tracking enabled: {progress_file}")

    # Validate plugins directory
    if not plugins_dir.is_dir():
        print(f"Error: Plugins directory does not exist: {plugins_dir}")
        sys.exit(1)
    if args.help_dir and not args.help_dir.is_dir():
        print(f"Error: Help directory does not exist: {args.help_dir}")
        sys.exit(1)

    # Find all check sources: C, Perl and shell (*.pl/*.sh may be *.pl.in/*.sh.in templates)
    sources = [f for f in plugins_dir.rglob('check_*')
               if f.is_file() and re.fullmatch(r'check_[\w-]+\.(c|pl|sh)(\.in)?', f.name)
               and '/t/' not in str(f) and '/tests/' not in str(f)]
    # Prefer C over Perl over shell for the same name, and real files over .in templates
    priority = {'c': 0, 'pl': 1, 'sh': 2}
    sources.sort(key=lambda f: (f.name.split('.')[0], priority[f.name.split('.')[1]], f.name.endswith('.in')))

    version = source_version(plugins_dir)
    commit = source_commit(plugins_dir)
    ut_macros = load_ut_macros(plugins_dir)
    option_macros = load_option_macros(plugins_dir)

    print(f"Plugins directory: {plugins_dir} (nagios-plugins {version})")
    print(f"Output file: {output_file}")
    if args.plugin_path:
        print(f"Plugin path: {args.plugin_path} (static)")
    else:
        print("Plugin path: PluginDir (variable)")
    if args.command_prefix:
        print(f"Command prefix: {args.command_prefix}")
    print(f"Found {len(sources)} plugin source files")

    all_commands = [
        f'# Nagios Plugins {version} - Icinga2 CheckCommand Definitions',
        '# Auto-generated by parse_nagios_plugins.py, do not edit by hand',
        f'# Source: nagios-plugins {version}' + (f' ({commit})' if commit else ''),
        '',
    ]

    def help_for(name: str) -> Optional[str]:
        if not args.help_dir:
            return None
        f = args.help_dir / f'{name}.txt'
        return f.read_text(errors='ignore') if f.exists() else None

    jobs = []
    seen = set()
    for f in sources:
        name = f.name.split('.')[0]
        if name in seen:
            print(f"  Skipping {f.name}: {name} already provided by another source")
            continue
        seen.add(name)
        jobs.append((name, f))
        if name == 'check_tcp':
            jobs.extend((alias, f) for alias in tcp_aliases(plugins_dir))

    processed = 0
    skipped_missing = []
    failed = []
    for name, plugin_file in jobs:
        print(f"\nParsing {name} ({plugin_file.name})...")
        help_text = help_for(name)
        if args.help_dir and help_text is None:
            print("  Not built (no help file), skipping")
            skipped_missing.append(name)
            update_progress(name, 'skipped', 'not built', progress_file=progress_file)
            continue

        update_progress(name, 'in-progress', progress_file=progress_file)
        parser_instance = PluginParser(plugin_file, plugin_dir=args.plugin_path,
                                       command_prefix=args.command_prefix, plugin_name=name,
                                       ut_macros=ut_macros, help_text=help_text,
                                       option_macros=option_macros)
        if parser_instance.parse():
            print(f"  Found {len(parser_instance.options)} options")
            for opt in parser_instance.options:
                print(f"    {opt}")
            all_commands.append(parser_instance.generate_icinga_command())
            update_progress(name, 'completed', f'{len(parser_instance.options)} options', progress_file=progress_file)
            processed += 1
        else:
            failed.append(name)
            update_progress(name, 'error', 'Failed to parse', progress_file=progress_file)

    # Write output
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text('\n'.join(all_commands))

    print(f"\n✓ Generated {processed} CheckCommands: {output_file}")
    if skipped_missing:
        print(f"  Not built, skipped: {', '.join(skipped_missing)}")
    if failed:
        print(f"✗ Failed to parse: {', '.join(failed)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
