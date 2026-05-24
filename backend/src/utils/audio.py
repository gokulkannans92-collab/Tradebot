import winsound
import threading
import logging

logger = logging.getLogger("AudioManager")

import queue
import time

class AudioManager:
    """
    Handles system audio notifications using winsound and pyttsx3.
    Includes a queue-based TTS system to prevent overlapping announcements.
    """
    
    # Standard Windows sound types
    SOUND_INFO = winsound.MB_ICONASTERISK
    SOUND_QUESTION = winsound.MB_ICONQUESTION
    SOUND_WARNING = winsound.MB_ICONEXCLAMATION
    SOUND_ERROR = winsound.MB_ICONHAND
    SOUND_OK = winsound.MB_OK
    
    _tts_queue = queue.Queue()
    _tts_thread = None
    _stop_tts = False
    
    @classmethod
    def _tts_worker(cls):
        """Worker thread to process TTS queue sequentially."""
        import pyttsx3
        try:
            engine = pyttsx3.init()
            # Try to find a male/robotic voice for Jarvis
            voices = engine.getProperty('voices')
            for voice in voices:
                if "Zira" not in voice.name: # Skip default female Zira on windows
                    engine.setProperty('voice', voice.id)
                    break
                    
            engine.setProperty('rate', 160) # Slightly faster, snappy
            engine.setProperty('volume', 1.0)
            
            while not cls._stop_tts:
                try:
                    text = cls._tts_queue.get(timeout=1.0)
                    if text:
                        engine.say(text)
                        engine.runAndWait()
                    cls._tts_queue.task_done()
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"TTS Worker Error: {e}")
                    time.sleep(1) # Wait before retry
        except Exception as e:
            logger.error(f"Failed to initialize TTS engine: {e}")

    @classmethod
    def _ensure_worker(cls):
        """Start the worker thread if not already running."""
        if cls._tts_thread is None or not cls._tts_thread.is_alive():
            cls._stop_tts = False
            cls._tts_thread = threading.Thread(target=cls._tts_worker, daemon=True)
            cls._tts_thread.start()

    @staticmethod
    def play_sound(sound_type=winsound.MB_OK):
        """Play a system sound in a background thread."""
        def _play():
            try:
                winsound.MessageBeep(sound_type)
            except Exception as e:
                logger.error(f"Failed to play sound: {e}")
        
        threading.Thread(target=_play, daemon=True).start()

    @staticmethod
    def speak(text: str):
        """Add text to the TTS queue for sequential announcement."""
        if not text:
            return
        AudioManager._ensure_worker()
        AudioManager._tts_queue.put(text)
        logger.debug(f"Queued TTS: {text}")

    @staticmethod
    def play_market_announcement(market_name: str):
        """Announce the selected market of the day."""
        text = f"Today's selected market for trading is {market_name}."
        AudioManager.speak(text)

    @staticmethod
    def play_signal_chime():
        """Standard chime for new signals."""
        AudioManager.play_sound(AudioManager.SOUND_INFO)

    @staticmethod
    def play_error_alarm():
        """Distinct alarm for errors."""
        AudioManager.play_sound(AudioManager.SOUND_ERROR)

    @staticmethod
    def play_click():
        """Soft click for UI actions like start/stop."""
        AudioManager.play_sound(AudioManager.SOUND_OK)

# ── Voice Recognition System ───────────────────────────────────────────────────

class HandsFreeVoiceAssistant:
    """
    Continuous listening voice assistant using sounddevice (bypassing PyAudio limits).
    Waits for a wake word, records the command, and triggers a callback.
    """
    def __init__(self, command_callback, wake_word="jarvis"):
        self.callback = command_callback
        self.wake_word = wake_word.lower()
        self.is_listening = False
        self._thread = None
        self.sample_rate = 16000
        
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
        except ImportError:
            logger.error("speech_recognition not installed.")
            self.recognizer = None

    def start(self):
        if not self.recognizer:
            logger.error("Cannot start Voice Assistant: Dependencies missing.")
            return
        if self.is_listening: return
        self.is_listening = True
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        logger.info(f"🎙️ Jarvis Voice Assistant Online. Listening for wake word: '{self.wake_word}'")

    def stop(self):
        self.is_listening = False
        logger.info("🎙️ Jarvis Voice Assistant Offline.")

    def _listen_loop(self):
        import sounddevice as sd
        import numpy as np
        import queue
        import speech_recognition as sr

        q = queue.Queue()

        def audio_callback(indata, frames, time, status):
            if status:
                pass # Ignore minor underflows
            q.put(indata.copy())

        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, dtype='int16', blocksize=8000, callback=audio_callback):
                from src.utils.paths import get_path
                import json
                import os
                import time
                
                setup_file = get_path("voice_setup.json")
                is_setup_complete = False
                silence_threshold = 400
                
                if os.path.exists(setup_file):
                    try:
                        with open(setup_file, "r") as f:
                            data = json.load(f)
                            is_setup_complete = data.get("setup_complete", False)
                            silence_threshold = data.get("silence_threshold", 400)
                    except: pass
                
                if not is_setup_complete:
                    logger.info("Starting first-time voice setup...")
                    self.callback("setup_calibrating")
                    AudioManager.speak("Welcome to Jarvis Voice Setup. Please remain quiet for 3 seconds to calibrate ambient noise.")
                    
                    # Wait for TTS to finish speaking roughly
                    time.sleep(4)
                    
                    # Drain the queue to discard stale audio recorded while Jarvis was speaking
                    while not q.empty():
                        try:
                            q.get_nowait()
                        except:
                            break
                    
                    calibration_chunks = []
                    start_time = time.time()
                    while time.time() - start_time < 3.0 and self.is_listening:
                        try:
                            calibration_chunks.append(q.get(timeout=0.5))
                        except queue.Empty:
                            pass
                            
                    if calibration_chunks:
                        all_cal_data = np.concatenate(calibration_chunks)
                        ambient_rms = np.sqrt(np.mean(np.square(all_cal_data.astype(np.float32))))
                        # Use a dynamic threshold, capping it to prevent high sensitivity lockouts
                        silence_threshold = min(1200, max(200, int(ambient_rms) + 150))
                        logger.info(f"Calibrated silence threshold: {silence_threshold} (Ambient RMS: {ambient_rms:.2f})")
                    else:
                        silence_threshold = 400
                        logger.warning("No calibration data received, defaulting threshold to 400")
                        
                    self.callback("setup_listening")
                    AudioManager.speak(f"Calibration complete. Please say my name, {self.wake_word}, to verify voice activation.")
                    
                    setup_verified = False
                    audio_buffer = []
                    is_recording_command = False
                    silence_duration = 0
                    recording_duration = 0
                    
                    while self.is_listening and not setup_verified:
                        try:
                            data = q.get(timeout=1.0)
                        except queue.Empty:
                            continue
                            
                        rms = np.sqrt(np.mean(np.square(data.astype(np.float32))))
                        logger.debug(f"Setup audio level: {rms:.1f} (threshold: {silence_threshold})")
                        chunk_duration = len(data) / self.sample_rate
                        
                        if rms > silence_threshold:
                            is_recording_command = True
                            silence_duration = 0
                            audio_buffer.append(data)
                            recording_duration += chunk_duration
                        elif is_recording_command:
                            silence_duration += chunk_duration
                            audio_buffer.append(data)
                            recording_duration += chunk_duration
                            
                        if is_recording_command and (silence_duration > 1.5 or recording_duration > 5.0):
                            full_audio = np.concatenate(audio_buffer)
                            audio_buffer = []
                            is_recording_command = False
                            silence_duration = 0
                            recording_duration = 0
                            
                            if len(full_audio) < self.sample_rate: continue
                            
                            try:
                                a_data = sr.AudioData(full_audio.tobytes(), self.sample_rate, 2)
                                text = self.recognizer.recognize_google(a_data).lower()
                                logger.debug(f"Setup mic caught: {text}")
                                if self.wake_word in text:
                                    setup_verified = True
                            except:
                                pass
                                
                    if setup_verified:
                        try:
                            with open(setup_file, "w") as f:
                                json.dump({"setup_complete": True, "silence_threshold": silence_threshold}, f)
                        except: pass
                        AudioManager.speak("Voice profile recognized. Jarvis is now fully online.")
                        self.callback("setup_complete")
                        
                # --- Normal listen loop ---
                silence_duration = 0
                audio_buffer = []
                is_recording_command = False
                recording_duration = 0
                
                while self.is_listening:
                    try:
                        data = q.get(timeout=1.0)
                    except queue.Empty:
                        continue

                    # Calculate volume (Root Mean Square)
                    rms = np.sqrt(np.mean(np.square(data.astype(np.float32))))
                    chunk_duration = len(data) / self.sample_rate
                    
                    if rms > silence_threshold:
                        is_recording_command = True
                        silence_duration = 0
                        audio_buffer.append(data)
                        recording_duration += chunk_duration
                    elif is_recording_command:
                        silence_duration += chunk_duration
                        audio_buffer.append(data)
                        recording_duration += chunk_duration
                        
                    # Stop recording after 1.5 seconds of silence OR if recording exceeds 8 seconds
                    if is_recording_command and (silence_duration > 1.5 or recording_duration > 8.0):
                        # Process the buffer
                        full_audio = np.concatenate(audio_buffer)
                        audio_buffer = []
                        is_recording_command = False
                        silence_duration = 0
                        recording_duration = 0
                        
                        if len(full_audio) < self.sample_rate: 
                            continue # Ignore tiny noises
                            
                        def _process_audio(audio_data):
                            try:
                                a_data = sr.AudioData(audio_data.tobytes(), self.sample_rate, 2)
                                text = self.recognizer.recognize_google(a_data).lower()
                                logger.debug(f"Mic caught: {text}")
                                
                                if self.wake_word in text:
                                    AudioManager.play_sound(AudioManager.SOUND_OK) # Chime to acknowledge
                                    command = text.split(self.wake_word, 1)[-1].strip()
                                    if command:
                                        self.callback(command)
                                    else:
                                        self.callback("wake_only")
                            except sr.UnknownValueError:
                                pass # Inaudible speech
                            except sr.RequestError as e:
                                logger.error(f"Google API Error: {e}")
                            except Exception as e:
                                logger.error(f"Transcription error: {e}")
                                
                        # Run Google STT in a background thread to prevent blocking the listening loop
                        import threading
                        threading.Thread(target=_process_audio, args=(full_audio,), daemon=True).start()
                                
        except Exception as e:
            logger.error(f"Microphone access failed: {e}")
            self.is_listening = False
