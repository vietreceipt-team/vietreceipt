# MinIO removed its legacy Docker Hub/Quay images in 2026. Build the two local
# images from the original GitHub Release binaries and verify their immutable
# release-asset SHA-256 digests. TARGETARCH is supplied by BuildKit.

FROM alpine:3.20 AS server

ARG TARGETARCH
ARG MINIO_VERSION=RELEASE.2024-07-16T23-46-41Z
ARG MINIO_AMD64_SHA256=c119ba4b7293ecbe8b0dc49ff92d3a63738a006edd4a65af6c0333a9a3fee826
ARG MINIO_ARM64_SHA256=cf807d7cd3bf2766a699cded7fb09f421161df4df5f8a4cc9e7c4edb22455bfe

RUN apk add --no-cache ca-certificates curl \
    && case "$TARGETARCH" in \
         amd64) artifact_arch=amd64; artifact_sha="$MINIO_AMD64_SHA256" ;; \
         arm64) artifact_arch=arm64; artifact_sha="$MINIO_ARM64_SHA256" ;; \
         *) echo "Unsupported TARGETARCH: $TARGETARCH" >&2; exit 1 ;; \
       esac \
    && curl --fail --location --retry 5 --output /usr/local/bin/minio \
       "https://github.com/minio/minio/releases/download/${MINIO_VERSION}/minio.linux-${artifact_arch}.${MINIO_VERSION}" \
    && echo "${artifact_sha}  /usr/local/bin/minio" | sha256sum -c - \
    && chmod 0755 /usr/local/bin/minio \
    && minio --version

EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["/usr/local/bin/minio"]

FROM alpine:3.20 AS client

ARG TARGETARCH
ARG MC_VERSION=RELEASE.2024-07-15T17-46-06Z
ARG MC_AMD64_SHA256=1dcbce9714826032247ed753f4b9a77e5982f918d5109c721df9ddfe5712bfa2
ARG MC_ARM64_SHA256=dcc84167bf585b94b4f281f6bbc20bef5357c5dd9854cbf7c7796b88eee3b5b4

RUN apk add --no-cache ca-certificates \
    && case "$TARGETARCH" in \
         amd64) artifact_arch=amd64; artifact_sha="$MC_AMD64_SHA256" ;; \
         arm64) artifact_arch=arm64; artifact_sha="$MC_ARM64_SHA256" ;; \
         *) echo "Unsupported TARGETARCH: $TARGETARCH" >&2; exit 1 ;; \
       esac \
    && wget -O /usr/local/bin/mc \
       "https://github.com/minio/mc/releases/download/${MC_VERSION}/mc.linux-${artifact_arch}.${MC_VERSION}" \
    && echo "${artifact_sha}  /usr/local/bin/mc" | sha256sum -c - \
    && chmod 0755 /usr/local/bin/mc \
    && mc --version

ENTRYPOINT ["/usr/local/bin/mc"]
