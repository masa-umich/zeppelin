#!/usr/bin/env bash

# Fetch the pinned Synnax C++ client dependency sources and build a host protoc.
# Invoke as: fetch-dependencies.sh <destination> <cmake-config-output> [--full]

set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 || ( $# -eq 3 && "$3" != --full ) ]]; then
    echo "usage: $0 <destination> <cmake-config-output> [--full]" >&2
    exit 2
fi

destination=$(mkdir -p "$1" && cd "$1" && pwd -P)
config_output=$2
if [[ "$config_output" != /* ]]; then
    config_output="$PWD/$config_output"
fi

downloads="$destination/downloads"
build="$destination/build/native-protobuf"
mkdir -p "$downloads" "$build"

fetch_archive() {
    local name=$1 url=$2 expected_sha=$3 archive="$downloads/$1"
    if [[ ! -f "$archive" ]]; then
        local partial="$archive.part"
        rm -f "$partial"
        if command -v curl >/dev/null 2>&1; then
            curl --fail --location --retry 3 --silent --show-error "$url" --output "$partial"
        elif command -v wget >/dev/null 2>&1; then
            wget --tries=3 --output-document="$partial" "$url"
        else
            echo "error: curl or wget is required to fetch $name" >&2
            exit 1
        fi
        mv "$partial" "$archive"
    fi

    local actual_sha
    if command -v sha256sum >/dev/null 2>&1; then
        actual_sha=$(sha256sum "$archive" | awk '{print $1}')
    elif command -v shasum >/dev/null 2>&1; then
        actual_sha=$(shasum -a 256 "$archive" | awk '{print $1}')
    else
        echo "error: sha256sum or shasum is required to verify $name" >&2
        exit 1
    fi
    if [[ "$actual_sha" != "$expected_sha" ]]; then
        echo "error: SHA-256 mismatch for $name (expected $expected_sha, got $actual_sha)" >&2
        rm -f "$archive"
        exit 1
    fi
}

extract_archive() {
    local name=$1 archive=$2 expected_sha=$3 strip_components=$4
    local source="$destination/$name"
    local stamp="$source/.codex-source-sha256"
    if [[ -f "$stamp" ]] && [[ "$(cat "$stamp")" == "$expected_sha" ]]; then
        return
    fi

    local temporary="$destination/.$name.extracting"
    rm -rf "$temporary"
    mkdir -p "$temporary"
    tar -xf "$archive" --strip-components="$strip_components" -C "$temporary"
    printf '%s\n' "$expected_sha" > "$temporary/.codex-source-sha256"
    rm -rf "$source"
    mv "$temporary" "$source"
}

fetch_archive \
    synnax-37e28149a4dba24c191e6bc7f45bf6a6fb49c5d2.tar.gz \
    https://codeload.github.com/synnaxlabs/synnax/tar.gz/37e28149a4dba24c191e6bc7f45bf6a6fb49c5d2 \
    d712c27013e99cd769238851bea58f4e43bf003b06fc0d8181fde6a0c4e6ea78
fetch_archive \
    protobuf-v21.12.tar.gz \
    https://codeload.github.com/protocolbuffers/protobuf/tar.gz/refs/tags/v21.12 \
    22fdaf641b31655d4b2297f9981fa5203b2866f8332d3c6333f6b0107bb320de
fetch_archive \
    abseil-20250127.1.tar.gz \
    https://codeload.github.com/abseil/abseil-cpp/tar.gz/refs/tags/20250127.1 \
    b396401fd29e2e679cace77867481d388c807671dc2acc602a0259eeb79b7811
fetch_archive \
    nlohmann-json-v3.12.0.tar.gz \
    https://codeload.github.com/nlohmann/json/tar.gz/refs/tags/v3.12.0 \
    4b92eb0c06d10683f7447ce9406cb97cd4b453be18d7279320f7b2f025c10187
fetch_archive \
    boost-1.88.0.tar.bz2 \
    https://archives.boost.io/release/1.88.0/source/boost_1_88_0.tar.bz2 \
    46d9d2c06637b219270877c9e16155cbd015b6dc84349af064c088e9b5b12f7b

extract_archive \
    synnax \
    "$downloads/synnax-37e28149a4dba24c191e6bc7f45bf6a6fb49c5d2.tar.gz" \
    d712c27013e99cd769238851bea58f4e43bf003b06fc0d8181fde6a0c4e6ea78 \
    1
extract_archive protobuf "$downloads/protobuf-v21.12.tar.gz" \
    22fdaf641b31655d4b2297f9981fa5203b2866f8332d3c6333f6b0107bb320de 1
extract_archive abseil_cpp "$downloads/abseil-20250127.1.tar.gz" \
    b396401fd29e2e679cace77867481d388c807671dc2acc602a0259eeb79b7811 1
extract_archive nlohmann_json "$downloads/nlohmann-json-v3.12.0.tar.gz" \
    4b92eb0c06d10683f7447ce9406cb97cd4b453be18d7279320f7b2f025c10187 1
extract_archive boost "$downloads/boost-1.88.0.tar.bz2" \
    46d9d2c06637b219270877c9e16155cbd015b6dc84349af064c088e9b5b12f7b 1

if [[ "${3:-}" == --full ]]; then
    fetch_archive grpc-v1.51.3.tar.gz \
        https://codeload.github.com/grpc/grpc/tar.gz/refs/tags/v1.51.3 \
        feaeeb315133ea5e3b046c2c0231f5b86ef9d297e536a14b73e0393335f8b157
    fetch_archive re2-2022-12-01.tar.gz \
        https://codeload.github.com/google/re2/tar.gz/refs/tags/2022-12-01 \
        665b65b6668156db2b46dddd33405cd422bd611352c5052ab3dae6a5fbac5506
    fetch_archive zlib-v1.2.13.tar.gz \
        https://codeload.github.com/madler/zlib/tar.gz/refs/tags/v1.2.13 \
        1525952a0a567581792613a9723333d7f8cc20b87a81f920fb8bc7e3f2251428
    extract_archive grpc "$downloads/grpc-v1.51.3.tar.gz" \
        feaeeb315133ea5e3b046c2c0231f5b86ef9d297e536a14b73e0393335f8b157 1
    extract_archive re2 "$downloads/re2-2022-12-01.tar.gz" \
        665b65b6668156db2b46dddd33405cd422bd611352c5052ab3dae6a5fbac5506 1
    extract_archive zlib "$downloads/zlib-v1.2.13.tar.gz" \
        1525952a0a567581792613a9723333d7f8cc20b87a81f920fb8bc7e3f2251428 1
fi

native_cc=$(command -v cc || command -v clang)
native_cxx=$(command -v c++ || command -v clang++)
if [[ -z "$native_cc" || -z "$native_cxx" ]]; then
    echo "error: a native C and C++ compiler is required to build protoc" >&2
    exit 1
fi

cmake \
    -S "$destination/protobuf" \
    -B "$build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_COMPILER="$native_cc" \
    -DCMAKE_CXX_COMPILER="$native_cxx" \
    -Dprotobuf_BUILD_TESTS=OFF \
    -Dprotobuf_BUILD_SHARED_LIBS=OFF \
    -Dprotobuf_BUILD_PROTOC_BINARIES=ON \
    -Dprotobuf_WITH_ZLIB=OFF
cmake --build "$build" --target protoc --parallel 4

protoc="$build/protoc"
if [[ ! -x "$protoc" ]]; then
    echo "error: native protoc was not produced at $protoc" >&2
    exit 1
fi

cmake_quote() {
    local value=$1
    value=${value//\\/\\\\}
    value=${value//\"/\\\"}
    value=${value//;/\\;}
    printf '"%s"' "$value"
}

mkdir -p "$(dirname "$config_output")"
temporary_config="$config_output.tmp"
{
    printf 'set(FETCHCONTENT_SOURCE_DIR_SYNNAX %s)\n' "$(cmake_quote "$destination/synnax")"
    printf 'set(FETCHCONTENT_SOURCE_DIR_PROTOBUF %s)\n' "$(cmake_quote "$destination/protobuf")"
    printf 'set(FETCHCONTENT_SOURCE_DIR_ABSEIL %s)\n' "$(cmake_quote "$destination/abseil_cpp")"
    printf 'set(FETCHCONTENT_SOURCE_DIR_NLOHMANN_JSON %s)\n' "$(cmake_quote "$destination/nlohmann_json")"
    printf 'set(FETCHCONTENT_SOURCE_DIR_BOOST_HEADERS %s)\n' "$(cmake_quote "$destination/boost")"
    printf 'set(SYNNAX_PROTOC_EXECUTABLE %s)\n' "$(cmake_quote "$protoc")"
} > "$temporary_config"
mv "$temporary_config" "$config_output"

printf 'Verified dependency sources: %s\n' "$destination"
printf 'Native protoc: %s\n' "$protoc"
printf 'CMake dependency config: %s\n' "$config_output"
