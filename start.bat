@echo off
echo Installing required libraries...
pip install flask flask-cors google-generativeai python-dotenv
echo.
echo Starting the Bahasa Semai AI App...
start index.html
python app.py
pause