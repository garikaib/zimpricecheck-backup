#!/bin/bash
set -e

DOMAIN="wp.zimpricecheck.com"
EMAIL="admin@zimpricecheck.com"
LEGO_VERSION="v4.14.0"

echo "[*] Setting up Production Web Layer..."

# 1. Install Nginx
if ! command -v nginx &> /dev/null; then
    echo "  -> Installing Nginx..."
    sudo apt-get update
    sudo apt-get install -y nginx
fi

# 2. Install Lego
if ! command -v lego &> /dev/null; then
    echo "  -> Installing Lego..."
    wget -q "https://github.com/go-acme/lego/releases/download/${LEGO_VERSION}/lego_${LEGO_VERSION}_linux_amd64.tar.gz"
    tar -xzf "lego_${LEGO_VERSION}_linux_amd64.tar.gz" lego
    sudo mv lego /usr/local/bin/lego
    rm "lego_${LEGO_VERSION}_linux_amd64.tar.gz"
fi

# 3. Get Certificates
# Note: Lego needs port 80. Stop Nginx briefly.
echo "  -> Requesting Certificates for $DOMAIN..."
if sudo lsof -Pi :80 -sTCP:LISTEN -t >/dev/null; then
    sudo systemctl stop nginx
fi

sudo lego --email="$EMAIL" --domains="$DOMAIN" --http :80 run

# 4. Apply Nginx Config
echo "  -> Configuring Nginx..."
sudo cp master/nginx/nginx.conf.template /etc/nginx/sites-available/$DOMAIN.conf
sudo ln -sf /etc/nginx/sites-available/$DOMAIN.conf /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# 5. Restart Nginx
sudo systemctl start nginx
sudo systemctl reload nginx

# 6. Setup Renewal Cron
echo "  -> Setting up Auto-Renewal..."
(crontab -l 2>/dev/null; echo "0 0 1 * * /usr/local/bin/lego --domains=$DOMAIN --email=$EMAIL --http :80 renew && systemctl reload nginx") | crontab -

echo ""
echo "[+] Web Layer Active!"
echo "    URL: https://$DOMAIN:8081"
