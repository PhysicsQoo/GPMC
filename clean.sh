#!/bin/sh
# Remove generated build trees and legacy binary copies.
set -eu
rm -rf build build-debug build-static bin
