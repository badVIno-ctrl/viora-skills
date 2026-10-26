# -*- coding: utf-8 -*-
"""Minimal ctypes wrapper around libespeak-ng (GPL-3.0, bundled as a separate
shared library) used only to convert English text to IPA phonemes for Kokoro.
Fallbacks: system libespeak-ng, then the `espeak-ng` command line tool."""
import ctypes
import ctypes.util
import os
import re
import shutil
import subprocess
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_lock = threading.Lock()


class EspeakIPA:
    def __init__(self, lib_dir=None, voice='en-us'):
        self.voice = voice
        self.lib = None
        self.cli = None
        self.lib_dir = lib_dir
        self._init()

    def _init(self):
        cands = []
        if self.lib_dir:
            cands.append((os.path.join(self.lib_dir, 'libespeak-ng.so'), os.path.join(self.lib_dir, 'espeak-ng-data')))
        for name in ('espeak-ng', 'espeak'):
            p = ctypes.util.find_library(name)
            if p:
                cands.append((p, None))
        err = []
        for lib_path, data in cands:
            try:
                lib = ctypes.cdll.LoadLibrary(lib_path)
                lib.espeak_Initialize.restype = ctypes.c_int
                lib.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_int]
                r = lib.espeak_Initialize(0x02, 0, data.encode('utf-8') if data else None, 0)
                if r <= 0:
                    raise RuntimeError('espeak_Initialize failed')
                lib.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
                lib.espeak_SetVoiceByName.restype = ctypes.c_int
                if lib.espeak_SetVoiceByName(self.voice.encode()) != 0:
                    raise RuntimeError('voice %s not found' % self.voice)
                lib.espeak_TextToPhonemes.restype = ctypes.c_char_p
                lib.espeak_TextToPhonemes.argtypes = [ctypes.POINTER(ctypes.c_char_p), ctypes.c_int, ctypes.c_int]
                self.lib = lib
                return
            except Exception as e:  # try next
                err.append('%s: %s' % (lib_path, e))
        exe = shutil.which('espeak-ng') or shutil.which('espeak')
        if exe:
            self.cli = exe
            return
        raise RuntimeError('espeak-ng not available (needed for English): ' + '; '.join(err))

    def _raw(self, text, voice=None):
        voice = voice or self.voice
        if self.lib is not None:
            with _lock:
                if getattr(self, '_cur', self.voice) != voice:
                    if self.lib.espeak_SetVoiceByName(voice.encode()) != 0:
                        raise RuntimeError('voice %s not found' % voice)
                    self._cur = voice
                buf = ctypes.c_char_p(text.encode('utf-8'))
                ptr = ctypes.pointer(buf)
                out = []
                while ptr.contents.value is not None:
                    r = self.lib.espeak_TextToPhonemes(ptr, 1, 0x02)
                    if r:
                        out.append(r.decode('utf-8', 'ignore'))
                return ' '.join(out)
        r = subprocess.run([self.cli, '-q', '--ipa', '-v', voice, text], capture_output=True, text=True)
        return r.stdout

    def phonemize_chunk(self, text, voice=None):
        """IPA (with stress marks) of a punctuation-free chunk of text."""
        if not text.strip():
            return ''
        ph = self._raw(text, voice)
        ph = ph.replace('\n', ' ')
        ph = re.sub(r'\([a-z\-]+\)', '', ph)          # language switch flags like (fr)
        ph = re.sub(r'_+', '', ph)
        ph = re.sub(r'\s+', ' ', ph).strip()
        return ph
