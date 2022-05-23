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
git pull >> $LOG 2>> $LOG

cd ${WWWDIR}
echo "github pull in ${WWWDIR}" >> $LOG
git pull >> $LOG 2>> $LOG

cd ${SCRIPTDIR}
./periodlog.py >> $LOG 2>> $LOG

cd ${MAINDIR}
echo "git add * in ${MAINDIR}" >> $LOG
git add * >> $LOG 2>> $LOG
echo "git commit" >> $LOG
git commit -m"automatic update of ${DATE}" >> $LOG 2>> $LOG
echo "git push" >> $LOG
git push >> $LOG 2>> $LOG

cd /data/www/twoptwo.com
echo  "sync ${WWWDIR} to live website http://www.astro.puc.cl/2.2m" >> $LOG
./sync.sh >> $LOG 2>> $LOG

echo "git add * in ${WWWDIR}" >> $LOG
git add * >> $LOG 2>> $LOG
echo "git commit"
git commit -m"automatic update of ${DATE}" >> $LOG 2>> $LOG
git "push"
git push >> $LOG 2>> $LOG
