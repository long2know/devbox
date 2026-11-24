# syntax=docker/dockerfile:1
ARG DESKTOP_BASE=ghcr.io/linuxserver/baseimage-selkies:ubunturesolute
FROM ${DESKTOP_BASE} AS public

ARG TARGETARCH
RUN if [ "$TARGETARCH" != amd64 ]; then echo "Gamebox targets linux/amd64." >&2; exit 1; fi && \
    export DEBIAN_FRONTEND=noninteractive && \
    dpkg --add-architecture i386 && \
    apt-get update --error-on=any && \
    apt-get install -y --no-install-recommends \
        bubblewrap ca-certificates cinnamon cinnamon-control-center \
        cinnamon-desktop-data cinnamon-l10n cinnamon-screensaver cinnamon-session \
        cinnamon-settings-daemon dbus-x11 dconf-gsettings-backend desktop-base \
        desktop-file-utils gnome-keyring gnome-terminal libsecret-tools mesa-utils \
        mesa-vulkan-drivers mesa-vulkan-drivers:i386 muffin nemo steam-installer \
        xdg-desktop-portal xdg-desktop-portal-xapp xdg-utils && \
    dpkg-divert --local --rename --add /usr/games/steam && \
    ln -sfn /usr/games/steam /usr/local/bin/steam && \
    install -m 0644 /opt/lib/libudev.so.1.0.0-fake /opt/lib/libudev.so.1.0.0-fake_32 /usr/lib/ && \
    apt-get clean && \
    find /var/lib/apt/lists -mindepth 1 -delete

COPY --chmod=0755 root/defaults/startwm.sh /defaults/startwm.sh
COPY --chmod=0755 root/usr/local/bin/chrome root/usr/local/bin/devbox-cinnamon-session \
    root/usr/local/bin/devbox-session-init root/usr/local/bin/desktop-healthcheck /usr/local/bin/
COPY --chmod=0644 root/usr/share/glib-2.0/schemas/99-devbox-appearance.gschema.override /usr/share/glib-2.0/schemas/
COPY --chmod=0644 root/usr/local/share/dev-desktop/vendor-launchers/dev-chrome.desktop /usr/local/share/gamebox/
COPY --chmod=0644 gaming/THIRD_PARTY.md /usr/share/doc/gamebox/THIRD_PARTY.md
COPY --chmod=0755 gaming/root/usr/local/sbin/ /usr/local/sbin/
COPY --chmod=0755 gaming/root/custom-cont-init.d/ /custom-cont-init.d/
COPY --chmod=0755 gaming/root/usr/games/steam /usr/games/steam

# Selkies ships its own developer tools; the gaming desktop does not need them.
RUN DEBIAN_FRONTEND=noninteractive apt-get purge -y --autoremove \
        cmake containerd.io docker-buildx-plugin docker-ce docker-ce-cli \
        docker-compose-plugin g++ gcc git make && \
    rm -f /etc/apt/sources.list.d/docker.list \
        /etc/apt/sources.list.d/nodesource.list /etc/apt/sources.list.d/nodesource.sources && \
    rm /etc/s6-overlay/s6-rc.d/user/contents.d/svc-xsettingsd && \
    glib-compile-schemas --strict /usr/share/glib-2.0/schemas && \
    desktop-file-edit --set-icon=folder /usr/share/applications/nemo.desktop && \
    dpkg-query -W -f='${binary:Package}\t${Version}\t${source:Package}\t${source:Version}\n' \
        > /usr/share/doc/gamebox/apt-sources.tsv

ENV HOME=/config \
    TITLE=gamebox \
    SUBFOLDER=/gamebox/ \
    PIXELFLUX_WAYLAND=false \
    START_DOCKER=false \
    XDG_CONFIG_HOME=/config/.config \
    XDG_DATA_HOME=/config/.local/share \
    XDG_CACHE_HOME=/config/.cache \
    APP_SANDBOX=0 \
    GAMEBOX_INSTALL_VENDOR_APPS=0

VOLUME /config
ENTRYPOINT ["/usr/local/sbin/gamebox-entrypoint"]
HEALTHCHECK --interval=30s --timeout=10s --start-period=10m --retries=3 \
    CMD ["/usr/bin/with-contenv", "/usr/local/bin/desktop-healthcheck"]

LABEL io.gamebox.variant="public" \
    org.opencontainers.image.source="https://github.com/long2know/devbox"

FROM public AS full
RUN --mount=type=tmpfs,target=/tmp /usr/local/sbin/gamebox-install-chrome
LABEL io.gamebox.variant="full"
