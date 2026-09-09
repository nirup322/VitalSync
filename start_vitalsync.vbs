Set WshShell = CreateObject("WScript.Shell")

WshShell.CurrentDirectory = "C:\Users\DELL\Desktop\VITALSYNC project"

WshShell.Run "cmd /c python -m streamlit run app.py", 0, False