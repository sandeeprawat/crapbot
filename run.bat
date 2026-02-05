@echo off
cd /d %~dp0
pip install -r requirements.txt --quiet
cd src
python agent.py
