# Gamebox third-party software

The Gamebox build recipe and scripts use this repository's MIT license.
The images retain the licenses and notices of their components.

- **Ubuntu packages:** `/usr/share/doc/gamebox/apt-sources.tsv` records the
  installed binary and matching source package versions. Notices are in
  `/usr/share/doc/<package>/copyright` and `/usr/share/common-licenses`.
  Sources and packaging patches are in the [Ubuntu source archive](https://launchpad.net/ubuntu/+source).
- **LinuxServer and streaming stack:** See
  [LinuxServer's Selkies Ubuntu recipe](https://github.com/linuxserver/docker-baseimage-selkies/tree/ubunturesolute),
  [Ubuntu base recipe](https://github.com/linuxserver/docker-baseimage-ubuntu/tree/resolute),
  and [compiled Selkies layer recipes](https://github.com/linuxserver/selkies-layers).
  They identify the sources and releases of the upstream components.
- **Steam:** The Ubuntu `steam-installer` package is a free-software launcher
  with its notices in `/usr/share/doc/steam-installer/copyright`. It downloads
  the proprietary client directly from Valve into the user's home on first
  launch. Neither image ships the downloaded client, Proton, or game files.
  Their use is governed by the [Steam Subscriber Agreement](https://store.steampowered.com/subscriber_agreement/)
  and individual game terms.
- **Chrome:** The public target does not ship Google Chrome. The full local
  target and optional first-start installer fetch it from Google's signed
  APT repository, subject to the [Chrome terms](https://www.google.com/chrome/terms/).
