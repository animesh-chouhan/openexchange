# inspect current files
sudo ls -l /etc/nginx/sites-available/openexchange.conf /etc/nginx/sites-enabled/openexchange*

# if the available file is missing, copy your repo config
sudo cp /opt/openexchange/server/nginx.conf /etc/nginx/sites-available/openexchange.conf

# create the symlink nginx is looking for (non-.conf name)
sudo ln -sf /etc/nginx/sites-available/openexchange.conf /etc/nginx/sites-enabled/openexchange

# verify nginx config and reload
sudo nginx -t
sudo systemctl reload nginx

# install certbot and obtain SSL certificate for your domains
sudo apt install -y certbot python3-certbot-nginx
certbot --nginx -d stock.animeshchouhan.com
