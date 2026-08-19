FROM golang:1.24.8-alpine3.22 AS build

ARG MINIO_VERSION=RELEASE.2025-10-15T17-29-55Z
RUN apk add --no-cache git
RUN git clone --branch "${MINIO_VERSION}" --depth 1 https://github.com/minio/minio.git /src
WORKDIR /src
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    release_version="${MINIO_VERSION#RELEASE.}" \
    && ldflags="$(MINIO_RELEASE=RELEASE go run buildscripts/gen-ldflags.go "${release_version}")" \
    && CGO_ENABLED=0 GOPROXY="https://proxy.golang.org|direct" \
       go build -tags kqueue -trimpath -ldflags "${ldflags}" -o /out/minio .

FROM alpine:3.22
RUN apk add --no-cache ca-certificates \
    && addgroup -g 10001 minio \
    && adduser -D -u 10001 -G minio minio \
    && mkdir -p /data \
    && chown -R minio:minio /data
COPY --from=build /out/minio /usr/local/bin/minio
USER 10001:10001
EXPOSE 9000 9001
VOLUME ["/data"]
ENTRYPOINT ["/usr/local/bin/minio"]
CMD ["server", "/data", "--console-address", ":9001"]
