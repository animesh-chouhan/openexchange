ln -s /etc/nginx/sites-available/openexchange /etc/nginx/sites-enabled/openexchange
rm /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

apt install -y certbot python3-certbot-nginx
certbot --nginx -d stock.animeshchouhan.com
