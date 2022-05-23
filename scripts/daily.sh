#! /bin/sh

MAINDIR=/home/regis/git/autolog
SCRIPTDIR=${MAINDIR}/scripts
WWWDIR=/data/www/twoptwo.com
DATE=`date -I`
TIME=`date -Iseconds`
LOG=${SCRIPTDIR}/logs/${DATE}.log


touch $LOG
echo "" >> $LOG
echo "daily.sh at $TIME" >> $LOG
echo "-------------------------------------" >> $LOG
echo "" >> $LOG

cd ${MAINDIR}
echo "github pull in ${MAINDIR}" >> $LOG
git pull >> $LOG

cd ${WWWDIR}
echo "github pull in ${WWWDIR}" >> $LOG
git pull >> $LOG 

cd ${SCRIPTDIR}
./periodlog.py >> $LOG

cd ${MAINDIR}
echo "github push in ${MAINDIR}" > $LOG
git add * >> $LOG 
git commit -m"automatic update of ${DATE}" >> $LOG
git push >> $LOG

cd /data/www/twoptwo.com
echo  "sync ${WWWDIR} to live website http://www.astro.puc.cl/2.2m" >> $LOG
./sync.sh >> $LOG

echo "github push in ${WWWDIR}" > $LOG
git add * >> $LOG
git commit -m"automatic update of ${DATE}" >> $LOG
git push >> $LOG
