#! /bin/sh

cd /home/regis/git/autolog/scripts
./periodlog.py > logs/`date -I`.log
cd /data/www/twoptwo.com
./sync.sh
