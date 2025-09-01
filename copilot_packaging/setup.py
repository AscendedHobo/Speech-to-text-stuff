from setuptools import setup

setup(
    name="Gemini_Whisper_TkUI",
    version="1.0",
    description="Speech to Text Application with Whisper",
    author="AscendedHobo",
    install_requires=[
        'whisper',
        'tkinter',
        'ttkbootstrap',
        'tkinterdnd2'
    ],
    python_requires='>=3.8',
)
