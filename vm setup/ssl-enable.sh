#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=== Starting GCE VM SSL Reverse Proxy Setup ==="

# 1. Update system and install Nginx
echo "--> Installing Nginx..."
sudo apt-get update -y
sudo apt-get install nginx -y

# 2. Create directory for SSL certs if they don't exist
sudo mkdir -p /etc/ssl/private
sudo mkdir -p /etc/ssl/certs

# 3. Generate Self-Signed SSL Certificate automatically
# -subj provides the certificate details without prompting you for input
echo "--> Generating Self-Signed SSL Certificate..."
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout /etc/ssl/private/nginx-selfsigned.key \
  -out /etc/ssl/certs/nginx-selfsigned.crt \
  -subj "/C=US/ST=State/L=City/O=Organization/OU=Web/CN=localhost"

# 4. Create the Nginx Reverse Proxy Configuration
echo "--> Configuring Nginx reverse proxy to port 8000..."
sudo tee /etc/nginx/sites-available/docker-proxy > /dev/null << 'EOF'
server {
    listen 80;
    listen [::]:80;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    listen [::]:443 ssl;

    ssl_certificate /etc/ssl/certs/nginx-selfsigned.crt;
    ssl_certificate_key /etc/ssl/private/nginx-selfsigned.key;

    # Optional: Optimizations for SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Allow larger image uploads from mobile devices
    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Enable WebSockets support (Useful for modern Python apps)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

# 5. Enable configuration and disable Nginx default landing page
echo "--> Enabling site configuration..."
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/docker-proxy /etc/nginx/sites-enabled/

# 6. Test configuration and restart Nginx
echo "--> Testing Nginx configuration..."
sudo nginx -t

echo "--> Restarting Nginx service..."
sudo systemctl restart nginx
sudo systemctl enable nginx

echo "=== Setup Complete! ==="