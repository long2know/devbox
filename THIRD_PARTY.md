# Devbox third-party software

The Devbox recipes, scripts, and documentation are MIT-licensed. Components in
the Devbox image retain their own licenses, copyright, and source notices.
Devbox is not an official release of its upstream projects.

The public image does not include Google Chrome, Microsoft Visual Studio Code,
or the GitHub Copilot desktop app. The local/full build and the optional runtime
installer get those packages directly from their vendors, under their terms.

## Installed packages and corresponding sources

* **Ubuntu packages:** `/usr/share/doc/devbox/apt-sources.tsv` lists the binary
  package, binary version, source package, and source version for the public
  root filesystem. Copyright and license files are in
  `/usr/share/doc/<binary-package>/copyright` and `/usr/share/common-licenses`.
  The matching source packages and distro patches are available by source
  package and version in [Ubuntu's source archive](https://launchpad.net/ubuntu/+source)
  and the archive configured in `/etc/apt/sources.list.d/`.
* **LinuxServer and streaming stack:** See the [tagged Selkies base build
  recipes](https://github.com/linuxserver/docker-baseimage-selkies),
  [base Ubuntu recipes](https://github.com/linuxserver/docker-baseimage-ubuntu),
  and [compiled Selkies layers](https://github.com/linuxserver/selkies-layers).
  They identify the upstream sources for the base layers, including
  [Selkies](https://github.com/selkies-project/selkies/releases),
  [pixelflux](https://github.com/selkies-project/pixelflux/releases),
  [pcmflux](https://github.com/selkies-project/pcmflux/releases),
  [selkies-desktop](https://github.com/selkies-project/selkies-desktop/releases),
  [proot-apps](https://github.com/linuxserver/proot-apps/releases), and
  [Pelorus](https://github.com/linuxserver/pelorus/releases). The upstream image
  build details and component versions appear in image history and the release
  workflow log.
* **Toolchains:** [Node.js](https://nodejs.org/dist/) publishes source downloads
  for the version printed by `node --version`; npm's license is installed next
  to its package. The [.NET SDK images](https://github.com/dotnet/dotnet-docker)
  include product licenses and third-party notices under `/usr/share/dotnet`.
  [.NET source releases](https://github.com/dotnet/dotnet/releases) and
  [PowerShell source releases](https://github.com/PowerShell/PowerShell/releases)
  correspond to the runtime versions in the image. PowerShell includes its
  license under `/opt/microsoft/powershell/7`.
* **CLI tools:** [GitHub CLI](https://github.com/cli/cli/releases),
  [Ollama](https://github.com/ollama/ollama/releases), and
  [REA](https://github.com/morluto/rea) publish their sources. REA's package and
  third-party notices are under `/usr/local/lib/node_modules/rea-agents`.
* **GitHub Copilot CLI:** This image bundles the unmodified npm distribution as
  one tool in the separate Devbox application. Its license and notices remain
  alongside the package in `/usr/local/lib/node_modules/@github/copilot`
  and the `@github/copilot-linux-x64` platform dependency. The CLI's license
  and terms for online services are separate from Devbox's MIT license.

To report a missing notice or a problem locating corresponding source for a
specific image digest, open an issue on the Devbox repository.
