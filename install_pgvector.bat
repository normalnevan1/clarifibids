@echo off
echo ========================================================
echo Installing pgvector for PostgreSQL 18 on Windows...
echo ========================================================

set "STAGING=c:\Users\NormalNevan\Desktop\New folder\pgvector_staging"
set "PG_LIB=C:\Program Files\PostgreSQL\18\lib"
set "PG_EXT=C:\Program Files\PostgreSQL\18\share\extension"

copy /Y "%STAGING%\lib\vector.dll" "%PG_LIB%\"
copy /Y "%STAGING%\share\extension\*" "%PG_EXT%\"

echo Restarting PostgreSQL Service...
net stop postgresql-x64-18
net start postgresql-x64-18

echo ========================================================
echo pgvector installation completed successfully!
echo ========================================================
pause
