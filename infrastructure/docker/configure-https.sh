#!/bin/bash
set -euo pipefail
test "$(hostname)" = fca-lab
export DEBIAN_FRONTEND=noninteractive
apt-get install -y nginx
install -d -m 0700 /etc/fca/tls
cd /etc/fca/tls
umask 077
if [ ! -f lab-ca.key ]; then
  openssl req -x509 -newkey rsa:3072 -nodes -keyout lab-ca.key -out lab-ca.crt -days 3650 -subj '/CN=FCA Private Lab CA' -addext 'basicConstraints=critical,CA:TRUE' -addext 'keyUsage=critical,keyCertSign,cRLSign' 2>/dev/null
fi
if [ ! -f server.crt ]; then
  openssl req -newkey rsa:3072 -nodes -keyout server.key -out server.csr -subj '/CN=fca-lab' 2>/dev/null
  printf '%s\n' 'basicConstraints=critical,CA:FALSE' 'keyUsage=critical,digitalSignature,keyEncipherment' 'extendedKeyUsage=serverAuth' 'subjectAltName=IP:10.0.1.189,DNS:fca-lab' > server.ext
  openssl x509 -req -in server.csr -CA lab-ca.crt -CAkey lab-ca.key -CAcreateserial -out server.crt -days 365 -sha256 -extfile server.ext 2>/dev/null
fi
chmod 0600 *.key
chmod 0644 *.crt
install -d -m 0755 /var/www/fca
install -m 0644 /opt/fca/frontend/index.html /opt/fca/frontend/styles.css /opt/fca/frontend/app.js /var/www/fca/
cat > /etc/nginx/sites-available/fca <<'EOF'
limit_req_zone $binary_remote_addr zone=fca_login:1m rate=6r/m;
server {
 listen 443 ssl default_server;
 server_name 10.0.1.189 fca-lab;
 ssl_certificate /etc/fca/tls/server.crt;
 ssl_certificate_key /etc/fca/tls/server.key;
 ssl_protocols TLSv1.2 TLSv1.3;
 allow 10.0.1.0/24;
 deny all;
 root /var/www/fca;
 index index.html;
 server_tokens off;
 client_max_body_size 16k;
 add_header Strict-Transport-Security 'max-age=86400' always;
 add_header X-Content-Type-Options nosniff always;
 add_header Referrer-Policy no-referrer always;
 add_header X-Frame-Options DENY always;
 add_header Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'" always;
 location = /api/auth/login {
  limit_req zone=fca_login burst=4 nodelay;
  limit_req_status 429;
  access_log off;
  proxy_pass http://127.0.0.1:8000;
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-Proto https;
  proxy_set_header X-Forwarded-For $remote_addr;
 }
 location /api/ {
  access_log off;
  proxy_pass http://127.0.0.1:8000;
  proxy_set_header Host $host;
  proxy_set_header X-Forwarded-Proto https;
  proxy_set_header X-Forwarded-For $remote_addr;
 }
 location / { try_files $uri $uri/ /index.html; }
}
EOF
ln -sfn /etc/nginx/sites-available/fca /etc/nginx/sites-enabled/fca
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl enable nginx
systemctl restart nginx
echo FCA_PRIVATE_HTTPS_CONFIGURED
