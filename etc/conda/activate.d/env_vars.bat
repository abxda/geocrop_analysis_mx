@echo off
:: This script is executed when the Conda environment is activated.
:: It prepends the project's scripts directory to the PATH to provide the 'test' command for rsgislib compatibility on Windows.

set "PATH=%CONDA_PREFIX%\..\..\scripts;%PATH%"
