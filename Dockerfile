# syntax=docker/dockerfile:1
ARG NODE_IMAGE=node:26-bookworm-slim
ARG DOTNET_LTS_IMAGE=mcr.microsoft.com/dotnet/sdk:10.0
ARG DOTNET_CURRENT_IMAGE=mcr.microsoft.com/dotnet/sdk:11.0
ARG OLLAMA_IMAGE=ollama/ollama:latest
ARG DESKTOP_BASE=ghcr.io/linuxserver/baseimage-selkies:ubunturesolute

FROM ${NODE_IMAGE} AS node
FROM ${DOTNET_LTS_IMAGE} AS dotnet-lts
FROM ${DOTNET_CURRENT_IMAGE} AS dotnet-current
FROM ${OLLAMA_IMAGE} AS ollama
FROM ${DESKTOP_BASE} AS public

ARG TARGETARCH
ARG COPILOT_CLI_VERSION=latest
ARG REA_VERSION=latest

ENV DEBIAN_FRONTEND=noninteractive \
    DOTNET_ROOT=/usr/share/dotnet \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    POWERSHELL_TELEMETRY_OPTOUT=1

# Keep toolchain installation cached when only desktop defaults change.
RUN --mount=type=bind,source=install.sh,target=/build/install.sh \
    --mount=type=tmpfs,target=/tmp \
    --mount=from=node,source=/usr/local,target=/build-node \
    --mount=from=dotnet-lts,source=/usr/share/dotnet,target=/build-dotnet-lts \
    --mount=from=dotnet-current,source=/usr/share/dotnet,target=/build-dotnet-current \
    --mount=from=ollama,source=/bin/ollama,target=/build-ollama \
    /bin/bash /build/install.sh

# Install Cinnamon components without a separate graphical login manager.
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        cinnamon cinnamon-control-center cinnamon-desktop-data cinnamon-l10n \
        cinnamon-screensaver cinnamon-session cinnamon-settings-daemon \
        dconf-gsettings-backend desktop-base gnome-terminal muffin nemo \
        desktop-file-utils ffmpeg mkvtoolnix mkvtoolnix-gui qt6-qpa-plugins \
        xdg-desktop-portal xdg-desktop-portal-xapp && \
    rm -rf /var/lib/apt/lists/*

COPY --chmod=0755 root/ /
COPY --chmod=0644 THIRD_PARTY.md /usr/share/doc/devbox/THIRD_PARTY.md

# Let Cinnamon own XSettings so user theme changes reach GTK apps.
RUN --mount=type=bind,source=root,target=/image-root \
    find /image-root -type f -printf '/%P\0' | xargs -0 chmod 0644 && \
    chmod 0755 \
        /custom-cont-init.d/20-dev-desktop \
        /defaults/startwm.sh \
        /usr/local/bin/chrome \
        /usr/local/bin/code-desktop \
        /usr/local/bin/copilot-desktop \
        /usr/local/bin/devbox-session-init \
        /usr/local/bin/devbox-cinnamon-session \
        /usr/local/bin/wrapped-chromium \
        /usr/local/bin/desktop-healthcheck \
        /usr/local/bin/desktop-media-smoke-test \
        /usr/local/bin/desktop-smoke-test \
        /usr/local/sbin/devbox-install-vendor-apps \
        /etc/s6-overlay/s6-rc.d/svc-ollama-proxy/run && \
    rm /etc/s6-overlay/s6-rc.d/user/contents.d/svc-xsettingsd && \
    test -r /usr/share/desktop-base/lines-theme/wallpaper/gnome-background.xml && \
    glib-compile-schemas --strict /usr/share/glib-2.0/schemas && \
    desktop-file-edit --set-icon=folder /usr/share/applications/nemo.desktop && \
    dpkg-query -W -f='${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\n' \
        > /usr/share/doc/devbox/apt-sources.tsv && \
    /usr/local/bin/desktop-media-smoke-test

ENV HOME=/config \
    TITLE=devbox \
    PIXELFLUX_WAYLAND=false \
    XDG_CONFIG_HOME=/config/.config \
    NPM_CONFIG_PREFIX=/config/.local \
    OLLAMA_HOST=http://127.0.0.1:11434 \
    OLLAMA_SERVER_HOST=desktop-ollama \
    OLLAMA_SERVER_PORT=11434 \
    APP_SANDBOX=0 \
    PATH=/config/.local/bin:/config/.dotnet/tools:${PATH}

HEALTHCHECK --interval=30s --timeout=10s --start-period=10m --retries=3 \
    CMD ["/usr/local/bin/desktop-healthcheck"]

LABEL io.devbox.standalone.managed="true" \
    io.devbox.desktop="cinnamon" \
    io.devbox.variant="public" \
    org.opencontainers.image.source="https://github.com/long2know/devbox"

FROM public AS full
ARG COPILOT_APP_VERSION=latest

RUN --mount=type=tmpfs,target=/tmp \
    env -i HOME=/root PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
        /usr/local/sbin/devbox-install-vendor-apps "$COPILOT_APP_VERSION"

ENV BROWSER=/usr/local/bin/chrome
LABEL io.devbox.variant="full"
