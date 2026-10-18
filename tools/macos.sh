#!/bin/bash
# Docker-free macOS runner. Android ELF binaries still need a Linux kernel.
set -euo pipefail
cd "$(dirname "$0")/.."
repo="$PWD"
vm=wrapper-v2
command -v limactl >/dev/null || { echo 'Install Lima: brew install lima' >&2; exit 1; }
case "${1:-help}" in
    stop) limactl stop "$vm"; exit ;;
    logs) limactl shell "$vm" sudo journalctl -u wrapper-v2 -n 80 --no-pager; exit ;;
    status) limactl shell "$vm" sudo systemctl status wrapper-v2 --no-pager; exit ;;
    setup|start) action="$1"; shift ;;
    *) echo 'Usage: bash tools/macos.sh setup path/to/apple-music.apkm | start | stop | logs | status'; exit 2 ;;
esac
mkdir -p .local/downloads
if [[ "$action" == setup ]]; then
    [[ $# == 1 && -f "$1" ]] || { echo 'Supply an Apple Music 3.6.0-beta (1109) APK/APKM.' >&2; exit 2; }
    if [[ ! -d .local/android-ndk-r23b ]]; then
        if [[ ! -f .local/downloads/ndk.zip ]]; then
            curl -fL --retry 3 -C - -o .local/downloads/ndk.zip.part https://dl.google.com/android/repository/android-ndk-r23b-darwin.zip
            mv .local/downloads/ndk.zip.part .local/downloads/ndk.zip
        fi
        unzip -q .local/downloads/ndk.zip -d .local
    fi
    bash tools/build-native.sh "$1"
fi
[[ -f rootfs/system/bin/main ]] || { echo 'Run setup with a compatible APK first.' >&2; exit 1; }
if [[ ! -f .local/ports.json ]]; then
    python3 - <<'PY'
import json, secrets, socket
ports = []
while len(ports) < 2:
    port = 20000 + secrets.randbelow(40000)
    if port in ports:
        continue
    with socket.socket() as sock:
        try:
            sock.bind(('127.0.0.1', port))
        except PermissionError:
            raise
        except OSError:
            continue
    ports.append(port)
with open('.local/ports.json', 'x') as f:
    json.dump(dict(http=ports[0], decrypt=ports[1]), f)
PY
fi
http=$(jq -r .http .local/ports.json)
decrypt=$(jq -r .decrypt .local/ports.json)
if ! limactl list --json | jq -e --arg vm "$vm" 'select(.name == $vm)' >/dev/null; then
    limactl start --name="$vm" --vm-type=vz --containerd=none --cpus=4 --memory=4 --disk=20 \
        --mount-only="$repo" --tty=false tools/lima.yaml
else
    limactl start --tty=false "$vm"
fi
# Build/runtime/session files live on the Linux disk; source share is read-only.
limactl shell "$vm" bash -c 'sudo mkdir -p /app; sudo chown "$(id -u):$(id -g)" /app; command -v rsync >/dev/null || { sudo apt-get update && sudo apt-get install -y rsync; }'
limactl shell "$vm" sudo systemctl stop wrapper-v2.service 2>/dev/null || true
limactl shell "$vm" rsync -rlt --exclude=.git --exclude=.local --exclude=build --exclude=target \
    --exclude=data --exclude=runtime.env --exclude=wrapper --exclude=rootfs/data --exclude=rootfs/dev \
    --exclude=rootfs/proc --exclude=rootfs/etc "$repo/" /app/
limactl shell "$vm" bash -c 'umask 077; touch /app/runtime.env; sed -i -E "/^WRAPPER_(HOST|PORT|DECRYPT_HOST|DECRYPT_PORT)=/d" /app/runtime.env; printf "WRAPPER_HOST=127.0.0.1\nWRAPPER_PORT=%s\nWRAPPER_DECRYPT_HOST=127.0.0.1\nWRAPPER_DECRYPT_PORT=%s\n" "$1" "$2" >> /app/runtime.env' bash "$http" "$decrypt"
limactl shell "$vm" bash /app/tools/linux-service.sh
echo "Wrapper: http://127.0.0.1:$http"
echo "Decrypt: 127.0.0.1:$decrypt"
echo 'Ports are saved in .local/ports.json. Session data stays in the VM across restarts.'
for attempt in {1..30}; do
    if curl -fsS --max-time 3 "http://127.0.0.1:$http/health" > .local/health.json &&
        curl -fsS --max-time 5 "http://127.0.0.1:$http/me" |
            jq -e '{version, runtime, auth: {state: .auth.state}} | select(.runtime != null)' > .local/runtime.json; then
        cat .local/runtime.json
        printf '\n'
        if jq -e '.runtime.playback_ready == true' .local/runtime.json >/dev/null; then
            exit 0
        fi
        echo 'HTTP is running, but the Apple playback runtime is unavailable; inspect logs.' >&2
        exit 1
    fi
    sleep 2
done
echo 'Health check failed; inspect bash tools/macos.sh logs.' >&2
exit 1
