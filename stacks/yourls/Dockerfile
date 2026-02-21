# Add vhost fix so "/" is served (avoids 403). No bind mount needed for Portainer/Git deploy.
FROM yourls:1.10.3-apache
COPY vhost.conf /etc/apache2/sites-available/000-default.conf
