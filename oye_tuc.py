"""
OYE TUC — prueba bruta de wake word
Stream de audio persistente → Google STT → detecta "oye tuc".
Ctrl+C para salir.
"""
import io
import sys
import wave
import subprocess
import numpy as np
import sounddevice as sd
import speech_recognition as sr

WAKE_WORDS  = ["tuc", "tuk", "took", "tuc tuc", "oye tú", "oye tu", "hey tú", "hey tu"]
SAMPLE_RATE = 44100
CHUNK_SECS  = 3
CHANNELS    = 1

r = sr.Recognizer()


def numpy_a_audio(audio_np):
    """Convierte numpy int16 → sr.AudioData (via WAV en memoria)"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio_np.tobytes())
    buf.seek(0)
    with sr.AudioFile(buf) as source:
        return r.record(source)


def detectar_wake_word(texto):
    return any(w in texto.lower() for w in WAKE_WORDS)


def notificar(texto):
    # Escapar comillas dobles para PowerShell
    texto_safe = texto.replace('"', "'")
    script = f'''
Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.ShowBalloonTip(3000, "Oye Tuc!", "{texto_safe}", [System.Windows.Forms.ToolTipIcon]::Info)
Start-Sleep -Milliseconds 3500
$n.Dispose()
'''
    subprocess.Popen(["powershell", "-WindowStyle", "Hidden", "-Command", script])


frames_por_chunk = int(CHUNK_SECS * SAMPLE_RATE)
print("🎤 Escuchando... di 'Oye Tuc' (Ctrl+C para salir)")

# Stream persistente — se abre una vez y queda abierto
with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16") as stream:
    while True:
        try:
            audio_np, _ = stream.read(frames_por_chunk)
            audio = numpy_a_audio(audio_np)
            try:
                texto = r.recognize_google(audio, language="es-CO")
                print(f"  [{texto}]")
                if detectar_wake_word(texto):
                    print("🟢 ¡Wake word detectado!")
                    notificar(f'Te escuché: "{texto}"')
            except sr.UnknownValueError:
                print("  [...]")
            except sr.RequestError as e:
                print(f"  Error STT: {e}", file=sys.stderr)
        except KeyboardInterrupt:
            print("\nSaliendo.")
            break
