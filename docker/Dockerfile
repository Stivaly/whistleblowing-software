# GlobaLeaks Unified Dockerfile
# Supports both production (remote) and testing (local) installs.
#
# Build Arguments:
#   BASE_IMAGE:     The base image for the OS (e.g., debian:trixie-slim@sha256:...)
#   DISTRIBUTION:   The target distribution codename (e.g., trixie)
#
# Veridy: dos etapas. El cliente Angular se compila en una imagen de Node aparte y a la
# imagen final solo pasa el resultado (sin Node.js, npm ni el código fuente del cliente).
# Contexto de construcción: la raíz del repo, filtrada por .dockerignore.
ARG BASE_IMAGE=debian:trixie-slim@sha256:f2306da7a8fb6440535937baed0ce0018736742d6dc5beec9d6a31355b259726
ARG DISTRIBUTION=trixie

# ---------------------------------------------------------------- etapa: cliente
FROM node:22-bookworm-slim AS cliente

RUN apt-get update -q && \
    apt-get install -y --no-install-recommends brotli && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /src/client
COPY client/package.json client/npm-shrinkwrap.json client/.npmrc ./
RUN npm ci --no-audit --no-fund
COPY LICENSE /src/LICENSE
COPY client ./
RUN ./node_modules/grunt/bin/grunt build

# ------------------------------------------------------------------ etapa: final
FROM ${BASE_IMAGE}

# Redeclare build arguments to make them available after FROM
ARG DISTRIBUTION=trixie

# Set environment for non-interactive installation
ENV DEBIAN_FRONTEND=noninteractive

COPY docker/files/* /tmp/

RUN groupadd -r globaleaks --gid=1000 && useradd -r -d /var/globaleaks -g globaleaks --uid=1000 globaleaks

RUN apt-get update -q && \
    apt-get dist-upgrade -y && \
    apt-get install -y --no-install-recommends lsb-release && \
    chmod +x /tmp/install.sh && \
    /tmp/install.sh && \
    apt-get install -y --no-install-recommends python3-psycopg2 ca-certificates \
      python3-h2 python3-priority python3-six && \
    rm -rf /usr/share/globaleaks/client/* && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/*

RUN mkdir -p /run/globaleaks && chown -R globaleaks:globaleaks /run/globaleaks

COPY --from=cliente /src/client/build/ /usr/share/globaleaks/client/
COPY backend/globaleaks /usr/lib/python3/dist-packages/globaleaks

WORKDIR /

EXPOSE 8080 8443

USER 1000:1000

CMD ["/usr/bin/python3", "/usr/bin/globaleaks", "--working-path=/var/globaleaks/", "-n"]
