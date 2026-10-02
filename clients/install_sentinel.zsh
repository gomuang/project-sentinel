#!/bin/zsh

# --- CONFIGURATION ---
# Replace with your actual server IP
SERVER_IP="10.0.0.135"
# Must match the server's ENROLLMENT_SECRET (deliver via MDM, don't commit a real one)
ENROLLMENT_SECRET="CHANGE_ME"
BINARY_NAME="sentinel_agent"
INSTALL_PATH="/Library/Sentinel"
PLIST_NAME="com.sentinel.telemetry.plist"
LABEL="com.sentinel.telemetry.agent"

echo "🛡️  Sentinel Telemetry: Starting Installation..."

# 1. Check for binary
if [[ ! -f "./$BINARY_NAME" ]]; then
    echo "❌ Error: $BINARY_NAME not found in current folder."
    exit 1
fi

# 2. Create directory and move binary
echo "📁 Preparing system folders..."
sudo mkdir -p "$INSTALL_PATH"
sudo cp "./$BINARY_NAME" "$INSTALL_PATH/"
sudo chmod +x "$INSTALL_PATH/$BINARY_NAME"

# 3. Create the LaunchAgent Plist
echo "📝 Creating service configuration..."
cat <<EOF > /tmp/$PLIST_NAME
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$INSTALL_PATH/$BINARY_NAME</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>SENTINEL_API_URL</key>
        <string>http://$SERVER_IP:8000/api</string>
        <key>SENTINEL_ENROLLMENT_SECRET</key>
        <string>$ENROLLMENT_SECRET</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/sentinel.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/sentinel.err</string>
</dict>
</plist>
EOF

# 4. Move Plist to the correct location
mkdir -p ~/Library/LaunchAgents
mv /tmp/$PLIST_NAME ~/Library/LaunchAgents/

# 5. Load the service
echo "🚀 Loading Sentinel background service..."
# Unload first in case it's already running
launchctl unload ~/Library/LaunchAgents/$PLIST_NAME 2>/dev/null
launchctl load ~/Library/LaunchAgents/$PLIST_NAME

echo "✅ Sentinel Telemetry is now running in the background."
echo "📜 Logs can be found at /tmp/sentinel.log"