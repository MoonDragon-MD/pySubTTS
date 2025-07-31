# pySubTTS
Program for voice dubbing with TTS (native or online) video from SRT subtitles, lightweight without heavy dependencies, both for Windows and GNU/Linux (Debian, Ubuntu etc)

Allows subtitles to be transformed into audio while respecting timestamps and then perform quick dubbing into another language. 

You can also set various parameters including maximum or minimum speed so that you always have a good listening experience. 

It will strictly respect the subtitle timestamps if you want it to.

The offline version uses the native tts of the operating system you are using, on linux it uses the preinstalled "espeak" but since it sounds bad I recommend using the online version, while for windows it is fine and you can also install nicer voices from third party companies

### Dependencies
FFMPEG installed in the system or portable. If portable, copy the executables:

for linux to ```../pySubTTS/ffmpeg/ubuntu/ffmpeg/ffmpeg```

for windows ```..\pySubTTS\ffmpeg\windows\ffmpeg.exe```

For both operating systems (on linux the installer takes care of it):

```pip install pyttsx3 PyQt5 srt chardet pydub edge-tts```

### Usage
On linux if you used the installer you will find it in the main menu.

If you want to start it manually type in the terminal

```python3 pySubTTS.py```

On windows just make two clicks on "RunWindows.bat" or in Italian "AvviaWindows.bat"

If you want to start it manually type in the cmd

```python pySubTTS.py```

### ScreenShot
![alt text](https://github.com/MoonDragon-MD/pySubTTS/blob/main/img/eng.jpg?raw=true)

![alt text](https://github.com/MoonDragon-MD/pySubTTS/blob/main/img/ita.jpg?raw=true)

### Advanced use
You can change a few variables:

1) use ffmpeg portable
   
```ffmpegportable = "yes"```

2) see detailed debugging
   
```logging = "on"```

3) do not use loudnorm to normalize audio (not recommended as on long videos you will notice the volume increase as you go)
   
```use_loudnorm = False```

### Note
If you want to run with python 3.6 (on windows) you have to comment out line 23 making it look like this

```# import edge_tts```

Of course then you have to use only the native windows tts and not the online tts

### EXTRA
There are some srt files (I found this problem on some automatic srt files from YouTube) that have two tracks at the same time, which causes an error in my program.

To fix this, you can use this script: [fix_srt_timestamps.py](https://github.com/MoonDragon-MD/pySubTTS/blob/main/EXTRA/fix_srt_timestamps.py)

```python3 fix_srt_timestamps.py -i input.srt -o output.srt```
