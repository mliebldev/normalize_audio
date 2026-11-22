# normalize_audio

Script for handling all kinds of media files
- convert to most compatible format - mp3, 128kbit/s, fixed audio rate
- set to LUFS value -14.0


## Workspace contents

- normalize_audio.py

## Purpose


## Requirements (Prompt)
standard requirements
- language: python
- accept one or more files or also a directory as input parameter
- if directory is given, take all the files within that directory
- define a config on top of the py file for including and excluding file extensions
- print a warning for files begin excluded by the filter and for unknown file types
- on end of the script show if the script was successful or not, and ask for user input, so that one can see that result
- make a temp directory $temp\YYYY-MM-DD-hh:mm-<scriptname>, put a copy of the unprocessed original file there, plus a file __log.txt containing all the output you write. In case of file conflicts add a numbering to the filename
- replace the original file with the processed one at the original location
processing:
- take audio input files (*.m4a, *.wav, *.mp3) and video files (*.mp4)
- if it isn't mp3, convert to mp3 with 128kbps & CBR
- normalize to LUFS value -14.0


## Quick start



