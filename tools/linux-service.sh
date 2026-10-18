#!/bin/bash
# Run inside the dedicated Lima guest, after copying sources to /app.
set -euo pipefail
cd /app
export PATH="$HOME/.cargo/bin:$PATH"
if [[ ! -x /usr/bin/cmake || ! -x /usr/bin/cc || ! -x /usr/bin/rsync ]]; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends build-essential cmake ninja-build ca-certificates curl rsync jq unzip
fi
if ! command -v cargo >/dev/null; then
    curl -fsSL https://sh.rustup.rs -o /tmp/wrapper-rustup.sh
    sh /tmp/wrapper-rustup.sh -y --profile minimal
fi
cmake -S . -B build/host -G Ninja -DWRAPPER_BUILD_DAEMON=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build build/host --parallel 4
cargo test --locked
cargo build --release --locked
sudo install -D -m 0644 /etc/ssl/certs/ca-certificates.crt rootfs/etc/ssl/certs/ca-certificates.crt
sudo tee /etc/systemd/system/wrapper-v2.service >/dev/null <<EOF
[Unit]
Description=wrapper-v2
After=network-online.target
Wants=network-online.target
[Service]
WorkingDirectory=/app
EnvironmentFile=/app/runtime.env
ExecStart=/app/target/release/wrapperd
Restart=on-failure
RestartSec=3
UMask=0077
PrivateMounts=yes
KillMode=control-group
[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable wrapper-v2
sudo systemctl restart wrapper-v2
