#!/bin/bash
# Build the same worker as Dockerfile; Linux also builds the host binaries.
set -euo pipefail
cd "$(dirname "$0")/.."
case "$(uname -m)" in
    arm64|aarch64) arch=arm64-v8a ;;
    x86_64) arch=x86_64 ;;
    *) echo "Unsupported architecture" >&2; exit 1 ;;
esac
ndk="${ANDROID_NDK_HOME:-${NDK_PATH:-$PWD/.local/android-ndk-r23b}}"
[[ -f "$ndk/build/cmake/android.toolchain.cmake" ]] || {
    echo "Set ANDROID_NDK_HOME to an NDK r23b installation." >&2; exit 1;
}
if [[ $# -gt 0 ]]; then
    bash tools/extract-libs.sh --bundle "$1" --arch "$arch"
fi
bash tools/stage-system.sh --arch "$arch"
cmake -S src/daemon -B "build/daemon-$arch" -G Ninja \
    -DCMAKE_TOOLCHAIN_FILE="$ndk/build/cmake/android.toolchain.cmake" \
    -DANDROID_ABI="$arch" -DANDROID_PLATFORM=android-21 \
    -DANDROID_STL=c++_shared -DCMAKE_BUILD_TYPE=Release \
    -DLIBS_DIR="$PWD/rootfs/system/lib64"
cmake --build "build/daemon-$arch" --parallel 4
install -m 0755 "build/daemon-$arch/main" rootfs/system/bin/main
if [[ "$(uname -s)" == Linux ]]; then
    cmake -S . -B build/host -G Ninja -DWRAPPER_BUILD_DAEMON=OFF -DCMAKE_BUILD_TYPE=Release
    cmake --build build/host --parallel 4
    cargo build --release --locked
fi
