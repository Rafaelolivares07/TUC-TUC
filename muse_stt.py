# -*- coding: utf-8 -*-
"""muse_stt: voz -> texto con faster-whisper local (CPU int8, español).
Decodifica con PyAV propio (faster-whisper 1.2.1 + av 19 son incompatibles
en decode_audio). Modelo 'small', lazy singleton.
"""
import numpy as np

_MODEL = None


def decode_audio(path, sr=16000):
    """MP3/OGG -> numpy float32 mono 16k."""
    import av
    c = av.open(path)
    streams = [s for s in c.streams if s.type == 'audio']
    if not streams:
        raise ValueError('sin pista de audio: %s' % path)
    st = streams[0]
    rs = av.AudioResampler(format='flt', layout='mono', rate=sr)
    out = []
    for frame in c.decode(st):
        for f2 in rs.resample(frame):
            out.append(np.frombuffer(f2.planes[0], dtype=np.float32))
    c.close()
    if not out:
        raise ValueError('audio vacio: %s' % path)
    return np.concatenate(out)


def transcribe(path, lang='es'):
    """Transcribe archivo de audio -> texto (str, sin espacios extra)."""
    global _MODEL
    if _MODEL is None:
        from faster_whisper import WhisperModel
        _MODEL = WhisperModel('small', device='cpu', compute_type='int8')
    audio = decode_audio(path)
    segs, _info = _MODEL.transcribe(audio, language=lang)
    return ' '.join(s.text for s in segs).strip()
