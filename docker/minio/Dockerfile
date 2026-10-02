FROM alpine:3.20

ARG MINIO_VERSION=RELEASE.2025-09-07T16-13-09Z

RUN apk add --no-cache ca-certificates curl libc6-compat && \
    curl -fsSL -o /usr/bin/minio "https://github.com/minio/minio/releases/download/${MINIO_VERSION}/minio.linux-amd64.${MINIO_VERSION}" && \
    chmod +x /usr/bin/minio

EXPOSE 9000 9001
VOLUME ["/data"]

ENTRYPOINT ["minio"]
CMD ["server", "/data", "--console-address", ":9001"]
