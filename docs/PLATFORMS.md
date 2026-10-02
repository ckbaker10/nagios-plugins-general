# Platforms and Hardware

Which build target runs on which operating system, CPU architecture and
hardware. All targets are built from the same nagios-plugins tag with the same
configure flags and contain the same plugins.

Status: **built** = part of the current release (`v2.5-1`, 27 tarballs).

## Build targets

| Target | OS | x86_64 | aarch64 | armhf (ARMv7) | armv6hf (ARMv6) |
|---|---|---|---|---|---|
| `el8` | RHEL / Rocky / Alma 8 | built | built | – | – |
| `el9` | RHEL / Rocky / Alma 9 | built | built | – | – |
| `el10` | RHEL / Rocky / Alma 10 | built | built | – | – |
| `sles15` | SLES / openSUSE Leap 15 (SP6+) | built | built | – | – |
| `sles16` | SLES / openSUSE Leap 16 | built | built | – | – |
| `debian12` | Debian 12 bookworm, Armbian bookworm, Raspberry Pi OS 64-bit bookworm | built | built | built | – |
| `debian13` | Debian 13 trixie, Armbian trixie, Raspberry Pi OS 64-bit trixie | built | built | built | – |
| `ubuntu2204` | Ubuntu 22.04, Armbian jammy | built | built | built | – |
| `ubuntu2404` | Ubuntu 24.04, Armbian noble | built | built | built | – |
| `ubuntu2604` | Ubuntu 26.04 | built | built | built | – |
| `raspios12` | Raspberry Pi OS 32-bit bookworm (Raspbian) | – | – | – | built |
| `raspios13` | Raspberry Pi OS 32-bit trixie (Raspbian) | – | – | – | built |

`–`: the OS is not available for that architecture (no 32-bit ARM for
RHEL/SUSE; Raspbian exists only as ARMv6 hard-float).

Architecture names as reported by `uname -m` / Ansible `ansible_architecture`:

| Tarball suffix | `uname -m` | ABI |
|---|---|---|
| `x86_64` | `x86_64` | 64-bit x86 |
| `aarch64` | `aarch64` | 64-bit ARMv8 |
| `armhf` | `armv7l` | 32-bit ARMv7, hard-float (Debian/Ubuntu `armhf`) |
| `armv6hf` | `armv6l` (also `armv7l` on newer Pis with 32-bit OS) | 32-bit ARMv6, hard-float (Raspbian `armhf`) |

Raspberry Pi OS 32-bit always uses the `raspios*` (ARMv6) build, also on Pi 2
and newer: it runs on every Pi and matches the Raspbian libraries. Raspberry
Pi OS 64-bit is Debian arm64 and uses `debian12`/`debian13` aarch64.

## Hardware

### Raspberry Pi

| Model | SoC / CPU | Arch | RAM | 32-bit OS → target | 64-bit OS → target |
|---|---|---|---|---|---|
| Pi 1 A, B, A+, B+ | BCM2835 / ARM1176JZF-S | ARMv6 | 256–512 MB | `raspios12/13` armv6hf | – |
| Pi Zero, Zero W | BCM2835 / ARM1176JZF-S | ARMv6 | 512 MB | `raspios12/13` armv6hf | – |
| Pi 2 B v1.1 | BCM2836 / Cortex-A7 | ARMv7 | 1 GB | `raspios12/13` armv6hf | – |
| Pi 2 B v1.2 | BCM2837 / Cortex-A53 | ARMv8 | 1 GB | `raspios12/13` armv6hf | `debian12/13` aarch64 |
| Pi 3 B, B+, A+ | BCM2837(B0) / Cortex-A53 | ARMv8 | 512 MB–1 GB | `raspios12/13` armv6hf | `debian12/13` aarch64 |
| Pi Zero 2 W | RP3A0 / Cortex-A53 | ARMv8 | 512 MB | `raspios12/13` armv6hf | `debian12/13` aarch64 |
| Pi 4 B, 400, CM4 | BCM2711 / Cortex-A72 | ARMv8 | 1–8 GB | `raspios12/13` armv6hf | `debian12/13` aarch64 |
| Pi 5, 500, CM5 | BCM2712 / Cortex-A76 | ARMv8 | 2–16 GB | – (64-bit only) | `debian12/13` aarch64 |

### FriendlyELEC NanoPi (Armbian)

| Model | SoC / CPU | Arch | RAM | Target |
|---|---|---|---|---|
| NanoPi NEO, NEO Air | Allwinner H3 / Cortex-A7 | ARMv7 | 256–512 MB | `debian12/13`, `ubuntu2204/2404/2604` armhf |
| NanoPi M1 | Allwinner H3 / Cortex-A7 | ARMv7 | 512 MB–1 GB | `debian12/13`, `ubuntu2204/2404/2604` armhf |
| NanoPi NEO2, NEO Plus2 | Allwinner H5 / Cortex-A53 | ARMv8 | 512 MB–1 GB | `debian12/13`, `ubuntu2204/2404/2604` aarch64 |
| NanoPi R4S, R5S, R6S, M4 | Rockchip RK3399 / RK3568 / RK3588 | ARMv8 | 1–8 GB | `debian12/13`, `ubuntu2204/2404/2604` aarch64 |

### Sinovoip Banana Pi (Armbian)

| Model | SoC / CPU | Arch | RAM | Target |
|---|---|---|---|---|
| BPI-M1, M1+, R1 | Allwinner A20 / Cortex-A7 | ARMv7 | 1 GB | `debian12/13`, `ubuntu2204/2404/2604` armhf |
| BPI-M2+, M2 Zero | Allwinner H3 / Cortex-A7 | ARMv7 | 512 MB–1 GB | `debian12/13`, `ubuntu2204/2404/2604` armhf |
| BPI-M64 | Allwinner A64 / Cortex-A53 | ARMv8 | 2 GB | `debian12/13`, `ubuntu2204/2404/2604` aarch64 |
| BPI-M5, M2 Pro, M7 | Amlogic S905X3 / Rockchip RK3588 | ARMv8 | 2–16 GB | `debian12/13`, `ubuntu2204/2404/2604` aarch64 |

Armbian keeps the `/etc/os-release` of the underlying Debian/Ubuntu release, so the role selects the
matching Debian/Ubuntu target. 32-bit Armbian images on 64-bit boards use the
armhf target.

## How ARM targets are built

The build host emulates ARM with QEMU user mode (`qemu-user-static`, binfmt
with fix-binary flag), so the existing container build runs unchanged with
`--platform linux/arm64`, `linux/arm/v7` or, for Raspbian, an ARMv6 root
filesystem bootstrapped from `raspbian.raspberrypi.com`. ARMv6 builds are
checked for the ARM build attribute `Tag_CPU_arch: v6` and run with
`QEMU_CPU=arm1176` (the Pi 1 CPU) to catch ARMv7-only instructions.

Known gaps:

- `check_ssl_validity` needs `Crypt::X509`, which is not packaged for SUSE.
- `check_radius` is not built (needs freeradius-client, only on SUSE).
