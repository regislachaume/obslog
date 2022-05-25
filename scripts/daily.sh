#! /bin/zsh

MAINDIR=/home/regis/git/autolog
SCRIPTDIR=${MAINDIR}/scripts
WWWDIR=/data/www/twoptwo.com
DATE=`date -I`
TIME=`date -Iseconds`
LOG=${SCRIPTDIR}/logs/${DATE}.log
ERR=${SCRIPTDIR}/logs/${DATE}.err


touch $LOG
touch $ERR
cat<<EOF  >> $LOG >>& $ERR

daily.sh at $TIME
-------------------------------------

EOF

cd ${MAINDIR}
echo "github pull in ${MAINDIR}" >> $LOG >>& $ERR
git pull >> $LOG 2>> $ERR
echo ""  >> $LOG >>& $ERR

cd ${WWWDIR}
echo "github pull in ${WWWDIR}" >> $LOG >>& $ERR
git pull >> $LOG 2>> $ERR
echo ""  >> $LOG >>& $ERR

cd ${SCRIPTDIR}
echo "executing periodlog.py in ${SCRIPTDIR}" >> $LOG >>& $ERR
./periodlog.py >> $LOG 2>> $ERR
echo ""  >> $LOG >>& $ERR

cd ${MAINDIR}
echo "git add * in ${MAINDIR}" >> $LOG >>& $ERR
git add * >> $LOG 2>> $ERR
echo "git commit" >> $LOG  >>& $ERR
git commit -m"automatic update of ${DATE}" >> $LOG 2>> $ERR
echo "git push" >> $LOG  >>& $ERR
git push >> $LOG 2>> $ERR
echo ""  >> $LOG >>& $ERR

cd ${WWWDIR}
echo  "sync ${WWWDIR} to live website http://www.astro.puc.cl/2.2m" >> $LOG
./sync.sh >> $LOG 2>> $LOG
echo ""  >> $LOG >>& $ERR

echo "git add * in ${WWWDIR}" >> $LOG >>& $ERR
git add * >> $LOG 2>> $LOG
echo "git commit" >> $LOG >>& $ERR
git commit -m"automatic update of ${DATE}" >> $LOG 2>> $ERR
git push >> $LOG 2>> $ERR
echo ""  >> $LOG >>& $ERR
