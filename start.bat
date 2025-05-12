@echo off
color 0F
echo ===========================
echo         LSVM v0.2
echo ===========================
echo.

:start1
echo Please select an option:
echo 1.Start
echo 2.Settings
echo 3.End
echo.

SET /P INPUT="Enter the number of your choice (e.g. 1): "
echo.

if "%INPUT%"=="1" goto start2
if "%INPUT%"=="2" goto settings
if "%INPUT%"=="3" goto end

:: Handle invalid input
echo Invalid input. Please run the program again and choose a valid option.
echo.
goto start1

:start2
echo ===========================
echo         Layer Setup
echo ===========================
echo.

echo How many layers do you want to create?
SET /P LAYER="Enter exponent (e.g., 3 for 4^3 = 64): "

echo %LAYER% > input/settings.txt
echo Your input has been saved to input/settings.txt.

call ..\env\Scripts\activate.bat
py LSVM.py
pause
exit

:settings
echo ===========================
echo        Settings Menu
echo ===========================
echo (This section is not implemented yet.)
echo.
goto start1

:end
exit
