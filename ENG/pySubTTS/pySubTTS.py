# pySubTTS
# V 1.0 rev22
# By MoonDragon (https://github.com/MoonDragon-MD/pySubTTS)
# Dependencies
# pip install pyttsx3 PyQt5 srt chardet pydub edge-tts
# Start on Windows with
# python pySubTTS.py
# Start on Linux with
# python3 pySubTTS.py

import sys
import os
import platform
import pyttsx3
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QLineEdit, QFileDialog, QComboBox, QCheckBox, QSpinBox, QMessageBox, QSlider
from PyQt5.QtCore import Qt
import srt
import chardet
from pydub import AudioSegment
from pydub.effects import compress_dynamic_range
import tempfile
import asyncio
import edge_tts
import subprocess
import json
import shutil

# Configuration FFmpeg portable, logging e loudnorm
ffmpegportable = "no"  # Change in "no/yes" to use FFmpeg global or FFmpeg portable
logging = "off"  # Use "On" for debug
use_loudnorm = True  # Use loudnorm for the final file (avoid the constant increase in volume)
use_dynaudnorm_for_batches = False if use_loudnorm else True  # Skip Dynaudnorm for Batch if Loudnorm is active

# Directory of script
script_dir = os.path.dirname(os.path.abspath(__file__))
pytemp_dir = os.path.join(script_dir, 'pytemp')
os.makedirs(pytemp_dir, exist_ok=True)

def log(*args, **kwargs):
    """Print Log messages only if logging is enabled."""
    if logging.lower() == "on":
        print(*args, **kwargs)

def cleanup_pytemp():
    """Clean the pytemp folder."""
    if os.path.exists(pytemp_dir):
        for temp_file in os.listdir(pytemp_dir):
            try:
                os.remove(os.path.join(pytemp_dir, temp_file))
            except Exception as e:
                log(f"Warning: Could not delete {temp_file}: {e}")

def get_ffmpeg_path():
    """Returns the path of FFmpeg based on the operating system and the flag ffmpegportabile."""
    log(f"Script directory: {script_dir}")
    
    if ffmpegportable.lower() == "yes":
        if platform.system() == "Windows":
            ffmpeg_path = os.path.join(script_dir, "ffmpeg", "windows", "ffmpeg.exe")
        else:  # Linux/Ubuntu
            ffmpeg_path = os.path.join(script_dir, "ffmpeg", "ubuntu", "ffmpeg")
        
        ffmpeg_path = os.path.normpath(ffmpeg_path)
        log(f"FFmpeg path: {ffmpeg_path}")
        
        if not os.path.isfile(ffmpeg_path):
            error_msg = (
                f"FFmpeg portable not found in {ffmpeg_path}. "
                "Make sure the file exists in the correct or set directory ffmpegportabile = 'no'."
            )
            log(error_msg)
            raise FileNotFoundError(error_msg)
        
        if platform.system() != "Windows":
            try:
                os.chmod(ffmpeg_path, 0o755)
                log(f"Set executable permissions for {ffmpeg_path}")
            except Exception as e:
                log(f"Warning: Could not set permissions for {ffmpeg_path}: {e}")
        
        return ffmpeg_path
    else:
        log("Using global FFmpeg")
        return "ffmpeg"

def run_subprocess(ffmpeg_cmd, capture_output=True, text=True, check=True):
    """Performs a subprocess command compatible with Python 3.6."""
    log(f"Executing FFmpeg command: {' '.join(ffmpeg_cmd)}")
    try:
        if capture_output:
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=text,
                encoding='utf-8' if text else None
            )
            stdout, stderr = process.communicate()
            returncode = process.returncode
        else:
            process = subprocess.Popen(
                ffmpeg_cmd,
                universal_newlines=text,
                encoding='utf-8' if text else None
            )
            stdout, stderr = None, None
            returncode = process.wait()

        if check and returncode != 0:
            raise subprocess.CalledProcessError(returncode, ffmpeg_cmd, output=stdout, stderr=stderr)
        
        return subprocess.CompletedProcess(ffmpeg_cmd, returncode, stdout, stderr)
    except Exception as e:
        log(f"Subprocess error: {str(e)}")
        raise subprocess.CalledProcessError(1, ffmpeg_cmd, stderr=str(e))

async def generate_edge_tts(text, output_file, voice="it-IT-ElsaNeural"):
    """Generates audio with edge-tts (online) and converts to WAV."""
    try:
        temp_mp3 = os.path.join(pytemp_dir, f'temp_{os.urandom(8).hex()}.mp3')
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(temp_mp3)
        audio = AudioSegment.from_mp3(temp_mp3)
        audio = audio.set_frame_rate(24000).set_channels(1)
        audio.export(output_file, format="wav")
        os.remove(temp_mp3)
    except Exception as e:
        raise Exception(f"Error in the generation with edge-tts: {str(e)}")

def generate_silence(duration_ms, output_file):
    """Genera un file di silenzio con sample rate 24000 Hz."""
    silence = AudioSegment.silent(duration=duration_ms)
    silence = silence.set_frame_rate(24000).set_channels(1)
    silence.export(output_file, format="wav")

def normalize_audio(audio_segment, target_dbfs=-20.0):
    """Normalizza l'audio a un livello costante in dBFS."""
    change_in_dbfs = target_dbfs - audio_segment.dBFS
    return audio_segment.apply_gain(change_in_dbfs)

def compress_audio(audio_segment):
    """Applies dynamic compression to reduce volume variations."""
    return compress_dynamic_range(
        audio_segment,
        threshold=-24.0,
        ratio=4.0,
        attack=5.0,
        release=50.0
    )

def loudnorm_audio(input_file, output_file):
    """Apply loudnorm with FFmpeg for advanced normalization."""
    log(f"Applying loudnorm: {input_file} -> {output_file}")
    # First step: analysis
    ffmpeg_cmd = [
        get_ffmpeg_path(), '-i', input_file,
        '-af', 'loudnorm=I=-23:TP=-1.5:LRA=11:print_format=json',
        '-f', 'null', '-'
    ]
    try:
        result = run_subprocess(ffmpeg_cmd, capture_output=True, text=True, check=True)
        stats_output = result.stderr
        json_start = stats_output.find('{')
        json_end = stats_output.rfind('}') + 1
        if json_start == -1 or json_end == -1:
            raise ValueError("Impossibile trovare output JSON da loudnorm")
        stats = json.loads(stats_output[json_start:json_end])
        measured_I = float(stats['input_i'])
        measured_TP = float(stats['input_tp'])
        measured_LRA = float(stats['input_lra'])
        measured_thresh = float(stats['input_thresh'])
        # Second step: normalization
        ffmpeg_cmd = [
            get_ffmpeg_path(), '-i', input_file,
            '-af', f'loudnorm=I=-23:TP=-1.5:LRA=11:measured_I={measured_I}:measured_TP={measured_TP}:measured_LRA={measured_LRA}:measured_thresh={measured_thresh}:linear=true',
            '-ar', '24000', '-ac', '1', output_file, '-y'
        ]
        run_subprocess(ffmpeg_cmd, capture_output=True, text=True, check=True)
        log(f"Applied loudnorm to {output_file}")
    except Exception as e:
        log(f"Error applying loudnorm: {e}. Falling back to pydub normalization.")
        audio_segment = AudioSegment.from_file(input_file)
        compressed_segment = compress_audio(audio_segment)
        normalized_segment = normalize_audio(compressed_segment, target_dbfs=-20.0)
        normalized_segment.export(output_file, format="wav")

def detect_encoding(file_path):
    with open(file_path, 'rb') as f:
        result = chardet.detect(f.read())
    return result['encoding']

def read_srt_with_correct_encoding(file_path):
    encoding = detect_encoding(file_path)
    with open(file_path, 'r', encoding=encoding) as f:
        return f.read()

def validate_srt(subs):
    for i, sub in enumerate(subs):
        if sub.end <= sub.start:
            log(f"Invalid subtitle {i}: end ({sub.end}) <= start ({sub.start})")
            return False
        if i > 0 and sub.start < subs[i-1].end:
            log(f"Overlapping subtitle {i}: start ({sub.start}) < previous end ({subs[i-1].end})")
            return False
    return True

class TTSApp(QWidget):
    def __init__(self):
        super().__init__()
        self.engine = pyttsx3.init()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('SRT to TTS audio mp3')
        self.setMinimumWidth(400)
        self.layout = QVBoxLayout()

        # writing elaboration
        self.loading_label = QLabel("", self)
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("font-weight: bold; color: blue;")
        self.loading_label.setVisible(False)
        self.layout.addWidget(self.loading_label)

        self.useEdgeTTSCheck = QCheckBox("Use Edge TTS (online) instead of pyttsx3 (offline)", self)
        self.useEdgeTTSCheck.setChecked(False)
        self.useEdgeTTSCheck.stateChanged.connect(self.updateVoiceCombo)
        self.layout.addWidget(self.useEdgeTTSCheck)

        self.voiceLabel = QLabel('TTS voice selection:')
        self.layout.addWidget(self.voiceLabel)
        self.voiceCombo = QComboBox(self)
        self.updateVoiceCombo()
        self.layout.addWidget(self.voiceCombo)

        self.srtLabel = QLabel('SRT subtitle file:')
        self.layout.addWidget(self.srtLabel)
        self.srtInput = QLineEdit(self)
        self.layout.addWidget(self.srtInput)
        self.srtButton = QPushButton('Choose file')
        self.srtButton.clicked.connect(self.browseSRT)
        self.layout.addWidget(self.srtButton)

        self.dictionaryLabel = QLabel('TXT Dictionary File:')
        self.layout.addWidget(self.dictionaryLabel)
        self.dictionaryInput = QLineEdit(self)
        self.layout.addWidget(self.dictionaryInput)
        self.dictionaryButton = QPushButton('Choose file')
        self.dictionaryButton.clicked.connect(self.browseDictionary)
        self.layout.addWidget(self.dictionaryButton)

        self.modifyAudioCheck = QCheckBox('Change in time duration')
        self.modifyAudioCheck.setChecked(True)
        self.layout.addWidget(self.modifyAudioCheck)
        self.autoAdjustCheck = QCheckBox('Auto Accelerate/Decelerate')
        self.autoAdjustCheck.setChecked(True)
        self.layout.addWidget(self.autoAdjustCheck)
        self.slowdownCheck = QCheckBox('Enable slowdown threshold (30%)')
        self.slowdownCheck.setChecked(True)
        self.layout.addWidget(self.slowdownCheck)
        self.slowdownThresholdLabel = QLabel('Slowdown threshold (30%):')
        self.layout.addWidget(self.slowdownThresholdLabel)
        self.slowdownThreshold = QSpinBox(self)
        self.slowdownThreshold.setRange(0, 100)
        self.slowdownThreshold.setValue(30)
        self.layout.addWidget(self.slowdownThreshold)
        self.speedupCheck = QCheckBox('Enable acceleration threshold (50%)')
        self.speedupCheck.setChecked(True)
        self.layout.addWidget(self.speedupCheck)
        self.speedupThresholdLabel = QLabel('Acceleration threshold (50%):')
        self.layout.addWidget(self.speedupThresholdLabel)
        self.speedupThreshold = QSpinBox(self)
        self.speedupThreshold.setRange(0, 100)
        self.speedupThreshold.setValue(50)
        self.layout.addWidget(self.speedupThreshold)

        self.convertButton = QPushButton('Convert')
        self.convertButton.clicked.connect(self.convert)
        self.layout.addWidget(self.convertButton)

        self.faseIIBtn = QPushButton('Phase II - Show/Hide', self)
        self.faseIIBtn.clicked.connect(self.toggleFaseII)
        self.layout.addWidget(self.faseIIBtn)
        self.faseIIIBtn = QPushButton('Phase III - Show/Hide', self)
        self.faseIIIBtn.clicked.connect(self.toggleFaseIII)
        self.layout.addWidget(self.faseIIIBtn)

        self.blockII = QWidget(self)
        blockII_layout = QVBoxLayout()
        self.originalAudioLabel = QLabel('Select original video/audio:')
        blockII_layout.addWidget(self.originalAudioLabel)
        self.originalAudioInput = QLineEdit(self)
        blockII_layout.addWidget(self.originalAudioInput)
        self.originalAudioButton = QPushButton('Choose file')
        self.originalAudioButton.clicked.connect(self.browseOriginalAudio)
        blockII_layout.addWidget(self.originalAudioButton)
        self.balanceLabel = QLabel('Audio balance (L/R):')
        blockII_layout.addWidget(self.balanceLabel)
        self.balance = QSlider(Qt.Horizontal, self)
        self.balance.setRange(-100, 100)
        self.balance.setValue(0)
        self.balance.setTickPosition(QSlider.TicksBelow)
        self.balance.setTickInterval(10)
        blockII_layout.addWidget(self.balance)
        self.originalVolumeLabel = QLabel('Original audio volume (dB):')
        self.originalVolumeLabel.setToolTip('Recommended value: -6 dB')
        blockII_layout.addWidget(self.originalVolumeLabel)
        self.originalVolume = QSpinBox(self)
        self.originalVolume.setRange(-100, 100)
        self.originalVolume.setValue(-6)
        blockII_layout.addWidget(self.originalVolume)
        self.dubbedVolumeLabel = QLabel('Audio volume dubbed (dB):')
        self.dubbedVolumeLabel.setToolTip('Recommended value: +7 dB')
        blockII_layout.addWidget(self.dubbedVolumeLabel)
        self.dubbedVolume = QSpinBox(self)
        self.dubbedVolume.setRange(-100, 100)
        self.dubbedVolume.setValue(7)
        blockII_layout.addWidget(self.dubbedVolume)
        self.generateButton = QPushButton('Generate')
        self.generateButton.clicked.connect(self.generate)
        blockII_layout.addWidget(self.generateButton)
        self.blockII.setLayout(blockII_layout)
        self.blockII.setVisible(False)

        self.blockIIa = QWidget(self)
        blockIIa_layout = QVBoxLayout()
        self.mergeButton = QPushButton('Merge audio and video')
        self.mergeButton.clicked.connect(self.merge_audio_video)
        blockIIa_layout.addWidget(self.mergeButton)
        self.blockIIa.setLayout(blockIIa_layout)
        self.blockIIa.setVisible(False)

        self.layout.addWidget(self.blockII)
        self.layout.addWidget(self.blockIIa)

        self.infoButton = QPushButton('Information')
        self.infoButton.clicked.connect(self.showInfo)
        self.layout.addWidget(self.infoButton)

        self.setLayout(self.layout)
        
    # Voices for Edge-tts (Manually add for your language)
    def updateVoiceCombo(self):
        self.voiceCombo.clear()
        if self.useEdgeTTSCheck.isChecked():
            edge_tts_voices = [
                {"FriendlyName": "Italian - Elsa (Female)", "Name": "it-IT-ElsaNeural"},
                {"FriendlyName": "Italian - Isabella (Female)", "Name": "it-IT-IsabellaNeural"},
                {"FriendlyName": "Italian - Diego (Male)", "Name": "it-IT-DiegoNeural"},
                {"FriendlyName": "Italian - Giuseppe (Male)", "Name": "it-IT-GiuseppeNeural"},
                {"FriendlyName": "English - Jenny (Female)", "Name": "en-US-JennyNeural"},
                {"FriendlyName": "English - Aria (Female)", "Name": "en-US-AriaNeural"},
                {"FriendlyName": "English - Guy (Male)", "Name": "en-US-GuyNeural"},
                {"FriendlyName": "English - Christopher (Male)", "Name": "en-US-ChristopherNeural"},
            ]
            for voice in edge_tts_voices:
                self.voiceCombo.addItem(voice["FriendlyName"], voice["Name"])
        else:
            voices = self.engine.getProperty('voices')
            for voice in voices:
                self.voiceCombo.addItem(voice.name, voice.id)

    def toggleFaseII(self):
        current_visibility = self.blockII.isVisible()
        self.blockII.setVisible(not current_visibility)
        self.faseIIBtn.setText("Hide Block II" if self.blockII.isVisible() else "Show Block II")
        self.adjustSize()

    def toggleFaseIII(self):
        current_visibility = self.blockIIa.isVisible()
        self.blockIIa.setVisible(not current_visibility)
        self.faseIIIBtn.setText("Hide Block III" if self.blockIIa.isVisible() else "Show Block III")
        self.adjustSize()

    def browseSRT(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Select SRT File", "", "SRT Files (*.srt);;All Files (*)")
        if fileName:
            self.srtInput.setText(fileName)

    def browseDictionary(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Dictionary File", "", "Text Files (*.txt);;All Files (*)")
        if fileName:
            self.dictionaryInput.setText(fileName)

    def browseOriginalAudio(self):
        fileName, _ = QFileDialog.getOpenFileName(self, "Select Original Audio/Video File", "", "Audio/Video Files (*.mp3 *.wav *.mp4 *.mkv);;All Files (*)")
        if fileName:
            self.originalAudioInput.setText(fileName)

    def showInfo(self):
        info_text = "Version: 1.0\nRevision: 22\nAuthor: MoonDragon\nWebSite: https://github.com/MoonDragon-MD/pySubTTS"
        msg = QMessageBox(self)
        msg.setWindowTitle("Information")
        msg.setText(info_text)
        msg.setTextInteractionFlags(Qt.TextSelectableByMouse)
        msg.exec_()

    def convert(self):
        # Show text and Disable Gui
        self.loading_label.setText("Elaboration in progress...")
        self.loading_label.setVisible(True)
        self.setEnabled(False)
        QApplication.processEvents()

        try:
            srt_file = self.srtInput.text()
            if not srt_file or not os.path.exists(srt_file):
                QMessageBox.warning(self, "Errore", "Select a valid SRT file.")
                return

            try:
                srt_content = read_srt_with_correct_encoding(srt_file)
                subs = list(srt.parse(srt_content))
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error in reading the SRT file: {str(e)}")
                return

            if not validate_srt(subs):
                QMessageBox.warning(self, "Error", "The SRT file contains errors in the TimesTamp.")
                return

            voice_id = self.voiceCombo.currentData()
            dictionary_file = self.dictionaryInput.text()
            modify_audio = self.modifyAudioCheck.isChecked()
            auto_adjust = self.autoAdjustCheck.isChecked()
            use_edge_tts = self.useEdgeTTSCheck.isChecked()
            slowdown_enabled = self.slowdownCheck.isChecked()
            speedup_enabled = self.speedupCheck.isChecked()
            slowdown_threshold = self.slowdownThreshold.value() / 100
            speedup_threshold = self.speedupThreshold.value() / 100
            shift_delay = 0.5
            MAX_INPUTS = 100

            log(f"Using TTS engine: {'edge-tts' if use_edge_tts else 'pyttsx3'} with voice: {voice_id}")

            if not use_edge_tts:
                self.engine.setProperty('voice', voice_id)

            dictionary = {}
            if dictionary_file and os.path.exists(dictionary_file):
                try:
                    with open(dictionary_file, 'r', encoding='utf-8') as file:
                        dictionary = dict(line.strip().split('=') for line in file if '=' in line)
                except Exception as e:
                    QMessageBox.warning(self, "Errore", f"Error in reading the dictionary file: {str(e)}")
                    return

            audio_files = []
            output_dir = os.path.join(script_dir, 'audio_segments')
            os.makedirs(output_dir, exist_ok=True)

            last_end_time = 0

            if subs and subs[0].start.total_seconds() > 0:
                silence_duration = subs[0].start.total_seconds()
                output_silence = os.path.join(output_dir, 'silence_initial.wav')
                generate_silence(silence_duration * 1000, output_silence)
                audio_files.append((output_silence, 0, silence_duration))
                log(f"Generated initial silence: {silence_duration}s")

            for i, sub in enumerate(subs):
                text = sub.content
                if sub.end <= sub.start:
                    log(f"Skipping subtitle {i} due to invalid timing (start: {sub.start}, end: {sub.end})")
                    last_end_time = sub.end.total_seconds()
                    continue

                duration = (sub.end - sub.start).total_seconds()
                log(f"Processing subtitle {i}: '{text}' (start: {sub.start}, end: {sub.end}, duration: {duration}s)")

                if not text.strip():
                    log(f"Generating silence for empty subtitle {i} (duration: {duration}s)")
                    output_silence = os.path.join(output_dir, f'silence_empty_{i}.wav')
                    generate_silence(duration * 1000, output_silence)
                    audio_files.append((output_silence, sub.start.total_seconds(), sub.end.total_seconds()))
                    last_end_time = sub.end.total_seconds()
                    continue

                for k, v in dictionary.items():
                    text = text.replace(k, v)

                output_audio = os.path.join(output_dir, f'output_{i}.wav')
                try:
                    if use_edge_tts:
                        asyncio.run(generate_edge_tts(text, output_audio, voice=voice_id))
                    else:
                        self.engine.save_to_file(text, output_audio)
                        self.engine.runAndWait()
                except Exception as e:
                    log(f"Error generating TTS for subtitle {i}: {e}")
                    continue

                audio_file = output_audio
                if auto_adjust:
                    try:
                        audio_segment = AudioSegment.from_file(output_audio)
                        audio_duration = audio_segment.duration_seconds
                        log(f"Segment {i} audio duration: {audio_duration}s")

                        min_duration = 0.1
                        if audio_duration < min_duration or duration <= 0:
                            log(f"Skipping speed adjustment for segment {i} due to invalid duration")
                            audio_files.append((output_audio, sub.start.total_seconds(), sub.end.total_seconds()))
                            continue

                        max_duration = duration + 0.5
                        speed = max_duration / audio_duration if audio_duration > 0 else 1
                        log(f"Segment {i} initial speed: {speed}")

                        if speedup_enabled and speed > (1 + speedup_threshold):
                            speed = 1 + speedup_threshold
                            log(f"Applied speedup threshold for segment {i}: speed adjusted to {speed}")
                        if slowdown_enabled and speed < (1 - slowdown_threshold):
                            speed = 1 - slowdown_threshold
                            log(f"Applied slowdown threshold for segment {i}: speed adjusted to {speed}")

                        target_duration = audio_duration * speed
                        log(f"Segment {i} target duration: {target_duration}s")
                        if target_duration < 0.5:
                            speed = audio_duration / 0.5
                            target_duration = 0.5
                            log(f"Adjusted speed for segment {i} to ensure minimum duration of 0.5s")

                        output_adjusted = os.path.join(output_dir, f'adjusted_{i}.wav')
                        atempo = 1 / speed
                        ffmpeg_cmd = [
                            get_ffmpeg_path(), '-i', output_audio,
                            '-filter:a', f'atempo={atempo},rubberband=pitch=1.0,volume=1.0',
                            '-ar', '24000', '-ac', '1', output_adjusted, '-y'
                        ]
                        log(f"FFmpeg command for segment {i}: {' '.join(ffmpeg_cmd)}")
                        result = run_subprocess(ffmpeg_cmd, capture_output=True, text=True, check=True)
                        audio_file = output_adjusted
                        log(f"Segment {i} adjusted duration: {AudioSegment.from_file(output_adjusted).duration_seconds}s")
                    except Exception as e:
                        log(f"Error adjusting speed for segment {i}: {e}. Using original audio.")
                        audio_file = output_audio

                # Normalizes the audio segment
                try:
                    audio_segment = AudioSegment.from_file(audio_file)
                    normalized_segment = normalize_audio(audio_segment, target_dbfs=-20.0)
                    normalized_segment.export(audio_file, format="wav")
                    log(f"Segment {i} normalized to -20 dBFS")
                except Exception as e:
                    log(f"Error normalizing segment {i}: {e}. Using unnormalized audio.")

                start_time = sub.start.total_seconds()
                if i > 0 and (start_time - last_end_time) < 0.5:
                    start_time += shift_delay
                    log(f"Applied shift delay of {shift_delay}s for segment {i}: start_time adjusted to {start_time}s")

                audio_files.append((audio_file, start_time, sub.end.total_seconds()))

                if i > 0:
                    silence_duration = sub.start.total_seconds() - last_end_time
                    if silence_duration > 0:
                        output_silence = os.path.join(output_dir, f'silence_{i}.wav')
                        generate_silence(silence_duration * 1000, output_silence)
                        audio_files.append((output_silence, last_end_time, sub.start.total_seconds()))

                last_end_time = sub.end.total_seconds()

            if not audio_files:
                QMessageBox.warning(self, "Errore", "Nessun file audio valido da concatenare.")
                return

            output_final = os.path.join(script_dir, 'final_output.wav')
            batch_files = []
            batch_size = MAX_INPUTS

            for batch_idx in range(0, len(audio_files), batch_size):
                batch = audio_files[batch_idx:batch_idx + batch_size]
                batch_output = os.path.join(output_dir, f'batch_{batch_idx // batch_size}.wav')
                filter_complex_parts = []
                ffmpeg_cmd = [get_ffmpeg_path()]

                for i, (audio_file, start_time, end_time) in enumerate(batch):
                    segment_duration = end_time - start_time
                    audio_file = audio_file.replace('\\', '/')
                    ffmpeg_cmd.extend(['-i', audio_file])
                    delay_ms = int(start_time * 1000)
                    filter_complex_parts.append(f"[{i}:a]adelay={delay_ms}|{delay_ms}[a{i}];")
                    log(f"Batch {batch_idx // batch_size}, Input {i}: {audio_file}, start_time: {start_time}s, end_time: {end_time}s, duration: {segment_duration}s")

                weights = ' '.join(['1'] * len(batch))
                filter_complex = "".join(filter_complex_parts)
                filter_complex += "".join(f"[a{i}]" for i in range(len(batch))) + f"amix=inputs={len(batch)}:duration=longest:dropout_transition=0:weights={weights}:normalize=0,volume=0.25[outa]"
                ffmpeg_cmd.extend(['-filter_complex', filter_complex, '-map', '[outa]', '-ac', '1', '-ar', '24000', batch_output, '-y'])

                log(f"Batch {batch_idx // batch_size} filter complex: {filter_complex}")
                log(f"Batch {batch_idx // batch_size} FFmpeg command: {' '.join(ffmpeg_cmd)}")

                try:
                    result = run_subprocess(ffmpeg_cmd, capture_output=True, text=True, check=True)
                    if use_dynaudnorm_for_batches:
                        # Verifica che il file batch esista
                        if not os.path.exists(batch_output):
                            raise FileNotFoundError(f"Batch file {batch_output} not found after creation.")
                        # Applica dynaudnorm al batch
                        temp_batch = os.path.join(pytemp_dir, f'temp_batch_{batch_idx // batch_size}.wav')
                        ffmpeg_cmd = [
                            get_ffmpeg_path(), '-i', batch_output,
                            '-filter:a', 'dynaudnorm', '-ar', '24000', '-ac', '1',
                            temp_batch, '-y'
                        ]
                        run_subprocess(ffmpeg_cmd, capture_output=True, text=True, check=True)
                        shutil.move(temp_batch, batch_output)
                        log(f"Batch {batch_idx // batch_size} normalized with dynaudnorm: {batch_output}")
                    batch_files.append(batch_output)
                    log(f"Batch {batch_idx // batch_size} generated: {batch_output}")
                except subprocess.CalledProcessError as e:
                    error_msg = f"Errore FFmpeg per batch {batch_idx // batch_size}: {e.stderr}"
                    log(error_msg)
                    QMessageBox.critical(self, "Errore", error_msg)
                    return
                except Exception as e:
                    log(f"Error processing batch {batch_idx // batch_size}: {e}")
                    return

            if len(batch_files) == 1:
                ffmpeg_cmd = [get_ffmpeg_path(), '-i', batch_files[0], '-c:a', 'copy', output_final, '-y']
                try:
                    run_subprocess(ffmpeg_cmd, capture_output=True, text=True, check=True)
                    # Normalize and (optionally) compress the final file
                    if use_loudnorm:
                        temp_final = os.path.join(pytemp_dir, f'temp_final_{os.urandom(8).hex()}.wav')
                        loudnorm_audio(batch_files[0], temp_final)
                        shutil.move(temp_final, output_final)
                    else:
                        final_segment = AudioSegment.from_file(batch_files[0])
                        compressed_final = compress_audio(final_segment)
                        normalized_final = normalize_audio(compressed_final, target_dbfs=-20.0)
                        normalized_final.export(output_final, format="wav")
                    log(f"File finale generato e processato: {output_final}")
                except subprocess.CalledProcessError as e:
                    error_msg = f"Error FFmpeg during the copy of the Batch: {e.stderr}"
                    log(error_msg)
                    QMessageBox.critical(self, "Error", error_msg)
                    return
            else:
                filter_complex_parts = []
                ffmpeg_cmd = [get_ffmpeg_path()]
                for i, batch_file in enumerate(batch_files):
                    batch_file = batch_file.replace('\\', '/')
                    ffmpeg_cmd.extend(['-i', batch_file])
                    filter_complex_parts.append(f"[{i}:a]adelay=0|0[a{i}];")
                weights = ' '.join(['1'] * len(batch_files))
                filter_complex = "".join(filter_complex_parts)
                filter_complex += "".join(f"[a{i}]" for i in range(len(batch_files))) + f"amix=inputs={len(batch_files)}:duration=longest:dropout_transition=0:weights={weights}:normalize=0,volume=0.25[outa]"

                total_duration = max(end_time for _, _, end_time in audio_files)
                max_segment_duration = max(AudioSegment.from_file(af).duration_seconds for af, _, _ in audio_files)
                total_duration = max(total_duration, total_duration + max_segment_duration)
                total_duration = int(total_duration) + 1

                ffmpeg_cmd.extend(['-filter_complex', filter_complex, '-map', '[outa]', '-ac', '1', '-ar', '24000', '-t', str(total_duration), output_final, '-y'])

                log(f"Final filter complex: {filter_complex}")
                log(f"Number of batch files: {len(batch_files)}")
                log(f"Total duration: {total_duration}s")
                log(f"Final FFmpeg command: {' '.join(ffmpeg_cmd)}")

                try:
                    result = run_subprocess(ffmpeg_cmd, capture_output=True, text=True, check=True)
                    # Normalize and (optionally) compress the final file
                    if use_loudnorm:
                        temp_final = os.path.join(pytemp_dir, f'temp_final_{os.urandom(8).hex()}.wav')
                        loudnorm_audio(output_final, temp_final)
                        shutil.move(temp_final, output_final)
                    else:
                        final_segment = AudioSegment.from_file(output_final)
                        compressed_final = compress_audio(final_segment)
                        normalized_final = normalize_audio(compressed_final, target_dbfs=-20.0)
                        normalized_final.export(output_final, format="wav")
                    log(f"File finale generato e processato: {output_final}")
                except subprocess.CalledProcessError as e:
                    error_msg = f"Error FFmpeg during the union of the batch: {e.stderr}"
                    log(error_msg)
                    QMessageBox.critical(self, "Error", error_msg)
                    return

            output_mp3 = os.path.join(script_dir, 'final_output.mp3')
            ffmpeg_cmd = [get_ffmpeg_path(), '-i', output_final, '-c:a', 'mp3', '-b:a', '192k', output_mp3, '-y']
            try:
                run_subprocess(ffmpeg_cmd, capture_output=True, text=True, check=True)
                log(f"File MP3 generato: {output_mp3}")
            except subprocess.CalledProcessError as e:
                error_msg = f"Error FFmpeg during conversion to mp3: {e.stderr}"
                log(error_msg)
                QMessageBox.critical(self, "Error", error_msg)
                return

            QMessageBox.information(self, "Success", "Conversion successfully completed!")
            print('Conversion completed!')

        finally:
            cleanup_pytemp()
            self.loading_label.setVisible(False)
            self.setEnabled(True)

    def generate(self):
        self.loading_label.setText("Elaboration in progress...")
        self.loading_label.setVisible(True)
        self.setEnabled(False)
        QApplication.processEvents()

        try:
            original_audio = self.originalAudioInput.text()
            dubbed_audio = os.path.join(script_dir, 'final_output.wav')
            original_volume = self.originalVolume.value()
            dubbed_volume = self.dubbedVolume.value()
            balance = self.balance.value()

            if not original_audio or not os.path.exists(original_audio):
                QMessageBox.warning(self, "Error", "Select a valid original audio/video file.")
                return
            if not os.path.exists(dubbed_audio):
                QMessageBox.warning(self, "Error", "The dubbed audio file 'final_output.wav' does not exist. Run the conversion first.")
                return

            try:
                original_segment = AudioSegment.from_file(original_audio)
                dubbed_segment = AudioSegment.from_file(dubbed_audio)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error in uploading audio files: {str(e)}")
                return

            if abs(original_segment.dBFS - (-20.0)) > 3:
                original_segment = normalize_audio(original_segment, target_dbfs=-20.0)
                log("Normalized original_segment to -20 dBFS")

            original_segment = original_segment + original_volume
            dubbed_segment = dubbed_segment + dubbed_volume

            if balance != 0:
                balance_value = balance / 100
                dubbed_segment = dubbed_segment.pan(balance_value)
                original_segment = original_segment.pan(-balance_value)
            else:
                original_segment = original_segment.pan(0)
                dubbed_segment = dubbed_segment.pan(0)

            mixed_audio = original_segment.overlay(dubbed_segment)
            temp_wav = os.path.join(pytemp_dir, f'temp_mixed_{os.urandom(8).hex()}.wav')
            mixed_audio.export(temp_wav, format="wav")
            if use_loudnorm:
                temp_mp3 = os.path.join(pytemp_dir, f'temp_mp3_{os.urandom(8).hex()}.mp3')
                loudnorm_audio(temp_wav, temp_mp3)
                shutil.move(temp_mp3, os.path.join(script_dir, 'final_mix.mp3'))
            else:
                ffmpeg_cmd = [
                    get_ffmpeg_path(), '-i', temp_wav,
                    '-c:a', 'mp3', '-b:a', '192k',
                    os.path.join(script_dir, 'final_mix.mp3'), '-y'
                ]
                run_subprocess(ffmpeg_cmd, capture_output=True, text=True, check=True)
            os.remove(temp_wav)

            log(f'File finale generato: final_mix.mp3')
            QMessageBox.information(self, "Success", f"Generated audio file: final_mix.mp3")
            print(f'Generated audio file: final_mix.mp3')

        finally:
            cleanup_pytemp()
            self.loading_label.setVisible(False)
            self.setEnabled(True)

    def merge_audio_video(self):
        self.loading_label.setText("Elaboration in progress...")
        self.loading_label.setVisible(True)
        self.setEnabled(False)
        QApplication.processEvents()

        try:
            original_video = self.originalAudioInput.text()
            dubbed_audio = os.path.join(script_dir, 'final_mix.mp3')

            if not original_video or not os.path.exists(dubbed_audio):
                QMessageBox.warning(self, "Error", "Select the original video and make sure you have generated dubbed audio.")
                return

            output_video = os.path.join(script_dir, 'final_video.mp4')

            try:
                ffmpeg_cmd = [
                    get_ffmpeg_path(), '-i', original_video, '-i', dubbed_audio,
                    '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                    '-map', '0:v:0', '-map', '1:a:0', output_video, '-y'
                ]
                run_subprocess(ffmpeg_cmd, capture_output=True, text=True, check=True)
                log(f'File video finale generato: {output_video}')
                QMessageBox.information(self, "Success", f"Video file generated: {output_video}")
                print(f'File video generato: {output_video}')
            except subprocess.CalledProcessError as e:
                error_msg = f"Errore FFmpeg: {e.stderr}"
                log(error_msg)
                QMessageBox.critical(self, "Error", f"Error during file merge: {error_msg}")
                return

        finally:
            cleanup_pytemp()
            self.loading_label.setVisible(False)
            self.setEnabled(True)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = TTSApp()
    ex.show()
    sys.exit(app.exec_())
