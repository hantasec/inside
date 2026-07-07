#!/bin/bash
set -e

# ============================================================
# Rocky Linux 9.8 - Snort 3 V8 Final Install Script
# ============================================================
# Target:
#   - Snort 3.12.2.0 / LibDAQ 3.0.27 source build
#   - SafeCLib source build
#   - /usr/local/snort real install path
#   - /etc/snort symlink created at the end
#   - DAQ fixed to afpacket
#   - alert_fast file output
#   - systemd service registration
#   - logrotate policy
#
# Confirmed stable runtime choices:
#   - DAQ: afpacket
#   - Runtime config: /etc/snort/snort.lua
#   - Real config path: /usr/local/snort/etc/snort
#   - Log path: /var/log/snort
#   - Alert output: alert_fast = { file = true }
#   - Service option -A: not used
#   - Service option -U: not used
#   - Service user: root
#
# IMPORTANT:
#   Change SNORT_IFACE if your mirror/capture NIC is not ens224.
# ============================================================

SNORT_VER="3.12.2.0"
DAQ_VER="3.0.27"

SRC_DIR="/usr/local/src"
SNORT_PREFIX="/usr/local/snort"
SNORT_CONF_REAL="/usr/local/snort/etc/snort"
SNORT_CONF_LINK="/etc/snort"
SNORT_LOG_DIR="/var/log/snort"
SNORT_IFACE="ens224"

echo "============================================================"
echo "[1] System update"
echo "============================================================"
dnf -y update

echo "============================================================"
echo "[2] Enable EPEL / CRB"
echo "============================================================"
dnf -y install epel-release
dnf -y install dnf-plugins-core
dnf config-manager --set-enabled crb

echo "============================================================"
echo "[3] Install Development Tools"
echo "============================================================"
dnf -y groupinstall "Development Tools"

echo "============================================================"
echo "[4] Install base utilities"
echo "============================================================"
dnf -y install git wget curl tar xz unzip vim

echo "============================================================"
echo "[5] Install build dependencies"
echo "============================================================"
dnf -y install gcc gcc-c++ make cmake automake autoconf libtool pkgconf pkgconf-pkg-config flex bison

dnf -y install zlib zlib-devel xz xz-devel openssl openssl-devel readline readline-devel ncurses ncurses-devel

dnf -y install libpcap libpcap-devel tcpdump wireshark-cli ethtool net-tools iproute

dnf -y install pcre pcre-devel pcre2 pcre2-devel luajit luajit-devel hwloc hwloc-devel libdnet libdnet-devel libunwind libunwind-devel libuuid libuuid-devel

dnf -y install hyperscan hyperscan-devel flatbuffers flatbuffers-devel numactl numactl-devel

dnf -y install gperftools gperftools-devel jemalloc jemalloc-devel

dnf -y install perl python3 python3-pip systemd-devel rsyslog logrotate

echo "============================================================"
echo "[6] Verify LZMA replacement package"
echo "============================================================"
rpm -q xz-devel
ls -l /usr/include/lzma.h
ldconfig -p | grep lzma || true

echo "============================================================"
echo "[7] Prepare source and prefix directories"
echo "============================================================"
mkdir -p "$SRC_DIR"
mkdir -p "$SNORT_PREFIX"

echo "============================================================"
echo "[8] Install SafeCLib from source"
echo "============================================================"
cd "$SRC_DIR"

if [ -d safeclib ]; then
    mv safeclib "safeclib.bak.$(date +%Y%m%d_%H%M%S)"
fi

git clone https://github.com/rurban/safeclib.git
cd safeclib

./build-aux/autogen.sh
./configure --prefix=/usr/local
make -j"$(nproc)"
make install

echo "============================================================"
echo "[9] Temporary SafeCLib library path"
echo "============================================================"
cat > /etc/ld.so.conf.d/usr-local-lib.conf <<EOF
/usr/local/lib
/usr/local/lib64
EOF

ldconfig
ldconfig -p | grep safec || true
find /usr/local -name '*safec*' || true

export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig:/usr/local/lib64/pkgconfig:$PKG_CONFIG_PATH
pkg-config --list-all | grep -i safe || true

echo "============================================================"
echo "[10] Build and install LibDAQ $DAQ_VER"
echo "============================================================"
cd "$SRC_DIR"

if [ -d libdaq ]; then
    mv libdaq "libdaq.bak.$(date +%Y%m%d_%H%M%S)"
fi

git clone https://github.com/snort3/libdaq.git
cd libdaq
git checkout "v$DAQ_VER"

./bootstrap
./configure --prefix="$SNORT_PREFIX"
make -j"$(nproc)"
make install

echo "============================================================"
echo "[11] Register Snort / DAQ library paths"
echo "============================================================"
rm -f /etc/ld.so.conf.d/usr-local-lib.conf

cat > /etc/ld.so.conf.d/snort3.conf <<EOF
/usr/local/snort/lib
/usr/local/snort/lib64
/usr/local/snort/lib/daq
/usr/local/lib
/usr/local/lib64
EOF

ldconfig

echo "============================================================"
echo "[12] Verify LibDAQ install"
echo "============================================================"
ldconfig -p | grep daq
find /usr/local/snort/lib -type f -o -type l | grep daq

echo "============================================================"
echo "[13] Prepare environment variables for Snort build"
echo "============================================================"
export PKG_CONFIG_PATH=/usr/local/snort/lib/pkgconfig:/usr/local/lib/pkgconfig:/usr/local/lib64/pkgconfig:$PKG_CONFIG_PATH
export LD_LIBRARY_PATH=/usr/local/snort/lib:/usr/local/lib:/usr/local/lib64:$LD_LIBRARY_PATH

pkg-config --modversion libdaq
pkg-config --libs libdaq

echo "============================================================"
echo "[14] Build and install Snort $SNORT_VER"
echo "============================================================"
cd "$SRC_DIR"

if [ -d snort3 ]; then
    mv snort3 "snort3.bak.$(date +%Y%m%d_%H%M%S)"
fi

git clone https://github.com/snort3/snort3.git
cd snort3
git checkout "$SNORT_VER"

./configure_cmake.sh --prefix="$SNORT_PREFIX" \
  --with-daq-includes="$SNORT_PREFIX/include" \
  --with-daq-libraries="$SNORT_PREFIX/lib"

cd build
make -j"$(nproc)"
make install

echo "============================================================"
echo "[15] Register runtime environment"
echo "============================================================"
cat > /etc/profile.d/snort3.sh <<'EOF'
# Snort 3 environment
export SNORT_HOME=/usr/local/snort
export PATH=$SNORT_HOME/bin:$PATH
export PKG_CONFIG_PATH=$SNORT_HOME/lib/pkgconfig:/usr/local/lib/pkgconfig:/usr/local/lib64/pkgconfig:$PKG_CONFIG_PATH
EOF

source /etc/profile.d/snort3.sh

ln -sf /usr/local/snort/bin/snort /usr/local/bin/snort

echo "============================================================"
echo "[16] Basic verification"
echo "============================================================"
echo "$SNORT_HOME"
which snort
snort -V
snort --daq-list
snort --daq-list --daq-dir /usr/local/snort/lib/daq

echo "============================================================"
echo "[17] Configure Snort real config directory layout"
echo "============================================================"
mkdir -p "$SNORT_CONF_REAL/rules" "$SNORT_CONF_REAL/lists" "$SNORT_CONF_REAL/builtin_rules" "$SNORT_CONF_REAL/so_rules"

cat > "$SNORT_CONF_REAL/rules/local.rules" <<'EOF'
alert icmp any any -> any any (msg:"ICMP Test Detected"; sid:1000001; rev:1;)
EOF

ls -al "$SNORT_CONF_REAL"
ls -al "$SNORT_CONF_REAL/rules"
cat "$SNORT_CONF_REAL/rules/local.rules"

echo "============================================================"
echo "[18] Normalize snort_defaults.lua path variables"
echo "============================================================"
sed -i "s#^RULE_PATH = .*#RULE_PATH = '/usr/local/snort/etc/snort/rules'#" "$SNORT_CONF_REAL/snort_defaults.lua"
sed -i "s#^BUILTIN_RULE_PATH = .*#BUILTIN_RULE_PATH = '/usr/local/snort/etc/snort/builtin_rules'#" "$SNORT_CONF_REAL/snort_defaults.lua"
sed -i "s#^PLUGIN_RULE_PATH = .*#PLUGIN_RULE_PATH = '/usr/local/snort/etc/snort/so_rules'#" "$SNORT_CONF_REAL/snort_defaults.lua"
sed -i "s#^WHITE_LIST_PATH = .*#WHITE_LIST_PATH = '/usr/local/snort/etc/snort/lists'#" "$SNORT_CONF_REAL/snort_defaults.lua"
sed -i "s#^BLACK_LIST_PATH = .*#BLACK_LIST_PATH = '/usr/local/snort/etc/snort/lists'#" "$SNORT_CONF_REAL/snort_defaults.lua"

grep -n "RULE_PATH\|BUILTIN_RULE_PATH\|PLUGIN_RULE_PATH\|WHITE_LIST_PATH\|BLACK_LIST_PATH" "$SNORT_CONF_REAL/snort_defaults.lua"

echo "============================================================"
echo "[19] Configure snort.lua once: IPS rules include + alert_fast file output"
echo "============================================================"
cp "$SNORT_CONF_REAL/snort.lua" "$SNORT_CONF_REAL/snort.lua.bak.final.$(date +%Y%m%d_%H%M%S)"

python3 - <<'PY'
from pathlib import Path

path = Path("/usr/local/snort/etc/snort/snort.lua")
text = path.read_text()

start_marker = "ips =\n{"
end_marker = "\n}\n\n-- use these to configure additional rule actions"

start = text.find(start_marker)
if start == -1:
    raise SystemExit("ERROR: ips block start not found")

end = text.find(end_marker, start)
if end == -1:
    raise SystemExit("ERROR: ips block end not found")

end += len("\n}")

new_ips_block = """ips =
{
    -- use this to enable decoder and inspector alerts
    --enable_builtin_rules = true,

    -- use include for rules files; be sure to set your path
    -- note that rules files can include other rules files
    -- (see also related path vars at the top of snort_defaults.lua)

    rules = [[
        include /usr/local/snort/etc/snort/rules/local.rules
    ]],

    variables = default_variables
}"""

text = text[:start] + new_ips_block + text[end:]

text = text.replace("alert_fast = { flie = true }", "alert_fast = { file = true }")

lines = text.splitlines()
new_lines = []
active_alert_fast_seen = False

for line in lines:
    stripped = line.strip()

    if stripped.startswith("alert_fast ="):
        if not active_alert_fast_seen:
            new_lines.append("alert_fast = { file = true }")
            active_alert_fast_seen = True
        else:
            new_lines.append("--" + line)
        continue

    if stripped == "--alert_fast = { }" and not active_alert_fast_seen:
        new_lines.append("alert_fast = { file = true }")
        active_alert_fast_seen = True
        continue

    if stripped == "--alert_fast = { file = true }" and not active_alert_fast_seen:
        new_lines.append("alert_fast = { file = true }")
        active_alert_fast_seen = True
        continue

    new_lines.append(line)

text = "\n".join(new_lines) + "\n"

if "alert_fast = { file = true }" not in text:
    marker = "-- event logging"
    idx = text.find(marker)
    if idx == -1:
        raise SystemExit("ERROR: output section marker not found")
    insert_at = text.find("\n", idx) + 1
    text = text[:insert_at] + "alert_fast = { file = true }\n" + text[insert_at:]

path.write_text(text)
PY

echo "[Check] ips block"
sed -n '/^ips =/,/^}/p' "$SNORT_CONF_REAL/snort.lua"

echo "[Check] alert_fast"
grep -n "alert_fast" "$SNORT_CONF_REAL/snort.lua"

echo "============================================================"
echo "[20] Configure log directory"
echo "============================================================"
mkdir -p "$SNORT_LOG_DIR"
chown root:root "$SNORT_LOG_DIR"
chmod 755 "$SNORT_LOG_DIR"
ls -ld "$SNORT_LOG_DIR"

echo "============================================================"
echo "[21] Create Snort service runner with afpacket"
echo "============================================================"
cat > "$SNORT_CONF_REAL/snort_service.sh" <<EOF
#!/bin/bash
exec /usr/local/snort/bin/snort \
  -c /etc/snort/snort.lua \
  -i $SNORT_IFACE \
  --daq afpacket \
  --daq-dir /usr/local/snort/lib/daq \
  -l /var/log/snort \
  -k none \
  -q
EOF

chmod +x "$SNORT_CONF_REAL/snort_service.sh"

cat "$SNORT_CONF_REAL/snort_service.sh"
ls -l "$SNORT_CONF_REAL/snort_service.sh"

echo "============================================================"
echo "[22] Register systemd service"
echo "============================================================"
cat > /etc/systemd/system/snort.service <<'EOF'
[Unit]
Description=Snort 3 IDS Service
After=network.target

[Service]
Type=simple
User=root
Group=root
ExecStart=/usr/local/snort/etc/snort/snort_service.sh
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl cat snort

echo "============================================================"
echo "[23] Configure logrotate for Snort alert log"
echo "============================================================"
cat > /etc/logrotate.d/snort <<'EOF'
/var/log/snort/alert_fast.txt {
    daily
    rotate 14
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
    dateext
    create 0644 root root
}
EOF

cat /etc/logrotate.d/snort
logrotate -d /etc/logrotate.d/snort || true

echo "============================================================"
echo "[24] Create /etc/snort symlink at the end"
echo "============================================================"
if [ -e "$SNORT_CONF_LINK" ] && [ ! -L "$SNORT_CONF_LINK" ]; then
    mv "$SNORT_CONF_LINK" "$SNORT_CONF_LINK.bak.$(date +%Y%m%d_%H%M%S)"
fi

ln -sfn "$SNORT_CONF_REAL" "$SNORT_CONF_LINK"

ls -al "$SNORT_CONF_LINK"
readlink -f "$SNORT_CONF_LINK"
ls -al "$SNORT_CONF_LINK/rules"
cat "$SNORT_CONF_LINK/rules/local.rules"

echo "============================================================"
echo "[25] Final configuration verification"
echo "============================================================"
snort -c /etc/snort/snort.lua -T

echo "============================================================"
echo "[OK] Snort 3 V8 final install completed."
echo ""
echo "Service is registered but not started automatically by this script."
echo ""
echo "Manual start:"
echo "  systemctl enable --now snort"
echo ""
echo "Status:"
echo "  systemctl status snort --no-pager"
echo ""
echo "Alert log:"
echo "  tail -f /var/log/snort/alert_fast.txt"
echo ""
echo "If your mirror/capture NIC is not '$SNORT_IFACE', edit:"
echo "  /usr/local/snort/etc/snort/snort_service.sh"
echo ""
echo "Current stable runtime:"
echo "  DAQ: afpacket"
echo "  -U : not used"
echo "  -A : not used in service"
echo "============================================================"
