#!/bin/sh
# Compatibility wrapper for the documented CMake presets.
set -eu

mode=${1:-r}
case "$mode" in
  r)
    cmake --preset release
    cmake --build --preset release --parallel 2
    source_path=build/gpmc
    ;;
  d)
    cmake --preset debug
    cmake --build --preset debug --parallel 2
    source_path=build-debug/gpmc
    ;;
  rs)
    cmake -S . -B build-static -G Ninja -DCMAKE_BUILD_TYPE=Release -DGPMC_STATIC_BUILD=ON
    cmake --build build-static --parallel 2
    source_path=build-static/gpmc
    ;;
  clean)
    for directory in build build-debug build-static; do
      if [ -f "$directory/build.ninja" ]; then
        cmake --build "$directory" --target clean
      fi
    done
    exit 0
    ;;
  *)
    printf 'Usage: %s [r|d|rs|clean]\n' "$0" >&2
    exit 2
    ;;
esac

mkdir -p bin
cp "$source_path" bin/gpmc
