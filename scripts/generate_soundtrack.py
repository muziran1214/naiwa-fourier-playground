from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, lfilter, fftconvolve

ROOT = Path(__file__).resolve().parents[1]
audio_dir = ROOT / 'output' / 'audio'
data_dir = ROOT / 'output' / 'data'
audio_dir.mkdir(parents=True, exist_ok=True)
data_dir.mkdir(parents=True, exist_ok=True)

SR = 44100
DURATION = 28.8  # 12 Bars at 100 BPM (2.4s per bar), 864 frames at 30 FPS
N_SAMPLES = int(SR * DURATION)
t = np.linspace(0, DURATION, N_SAMPLES, endpoint=False)

BEAT_DUR = 0.60
BAR_DUR = 2.40

def midi_to_freq(m):
    return 440.0 * (2.0 ** ((m - 69.0) / 12.0))

def soft_clip(x, drive=1.2):
    return np.tanh(x * drive) / np.tanh(drive)

def butter_lowpass(signal, cutoff_hz, order=3):
    nyq = 0.5 * SR
    norm_cutoff = np.clip(cutoff_hz / nyq, 0.001, 0.99)
    b, a = butter(order, norm_cutoff, btype='low')
    return lfilter(b, a, signal)

def butter_bandpass(signal, low_hz, high_hz, order=2):
    nyq = 0.5 * SR
    low = np.clip(low_hz / nyq, 0.001, 0.98)
    high = np.clip(high_hz / nyq, low + 0.005, 0.99)
    b, a = butter(order, [low, high], btype='band')
    return lfilter(b, a, signal)

def butter_highpass(signal, cutoff_hz, order=2):
    nyq = 0.5 * SR
    norm_cutoff = np.clip(cutoff_hz / nyq, 0.001, 0.99)
    b, a = butter(order, norm_cutoff, btype='high')
    return lfilter(b, a, signal)

def synth_lush_pad_note(freq, start_s, dur_s, amp=0.1, brightness=1800.0, attack=0.30, release=0.75):
    idx0 = max(0, int(start_s * SR))
    idx1 = min(N_SAMPLES, int((start_s + dur_s + release) * SR))
    if idx1 <= idx0:
        return np.zeros(0), np.zeros(0), idx0, idx0
    n = idx1 - idx0
    lt = np.arange(n) / SR

    env = np.ones(n)
    att_n = max(1, int(attack * SR))
    rel_n = max(1, int(release * SR))
    if att_n < n:
        env[:att_n] = 0.5 * (1.0 - np.cos(np.pi * np.arange(att_n) / att_n))
    if rel_n < n:
        env[-rel_n:] *= 0.5 * (1.0 + np.cos(np.pi * np.arange(rel_n) / rel_n))

    detunes_cents = [-19, -11, -4, 0, +4, +11, +19]
    pans = [0.15, 0.3, 0.45, 0.5, 0.55, 0.7, 0.85]
    sig_L = np.zeros(n)
    sig_R = np.zeros(n)
    vib = 0.0025 * np.sin(2 * np.pi * 4.8 * lt)

    for c, pan in zip(detunes_cents, pans):
        f_v = freq * (2.0 ** (c / 1200.0))
        phase = 2 * np.pi * f_v * (lt + vib / (2 * np.pi * 4.8)) + np.random.uniform(0, 2*np.pi)
        wave = np.zeros(n)
        for h_k in range(1, 11):
            if f_v * h_k < SR * 0.45:
                wave += ((-1)**(h_k+1)) * (np.sin(h_k * phase) / h_k) * np.exp(-0.08 * h_k)
        sig_L += wave * np.cos(pan * np.pi / 2)
        sig_R += wave * np.sin(pan * np.pi / 2)

    sig_L = butter_lowpass(sig_L, brightness, order=2) * env * amp * 0.35
    sig_R = butter_lowpass(sig_R, brightness, order=2) * env * amp * 0.35
    return sig_L, sig_R, idx0, idx1

def synth_celesta_pluck(freq, start_s, dur_s=1.2, amp=0.12, pan=0.5):
    idx0 = max(0, int(start_s * SR))
    idx1 = min(N_SAMPLES, int((start_s + dur_s) * SR))
    if idx1 <= idx0:
        return np.zeros(0), np.zeros(0), idx0, idx0
    n = idx1 - idx0
    lt = np.arange(n) / SR
    att_n = max(1, int(0.005 * SR))
    env = np.exp(-lt / (dur_s * 0.32)) * (1.0 - lt / dur_s)
    env[:att_n] *= np.linspace(0, 1, att_n)

    mod = 1.4 * np.exp(-lt * 12.0) * np.sin(2 * np.pi * (freq * 2.0) * lt)
    wave = (np.sin(2 * np.pi * freq * lt + mod)
            + 0.35 * np.sin(2 * np.pi * freq * 2.0 * lt) * np.exp(-lt * 5.0)
            + 0.15 * np.sin(2 * np.pi * freq * 3.0 * lt) * np.exp(-lt * 9.0))
    wave *= env * amp
    return wave * np.cos(pan * np.pi / 2), wave * np.sin(pan * np.pi / 2), idx0, idx1

def synth_expressive_lead(freq, start_s, dur_s, amp=0.14, pan=0.48):
    idx0 = max(0, int(start_s * SR))
    idx1 = min(N_SAMPLES, int((start_s + dur_s + 0.22) * SR))
    if idx1 <= idx0:
        return np.zeros(0), np.zeros(0), idx0, idx0
    n = idx1 - idx0
    lt = np.arange(n) / SR
    att_n = max(1, int(0.07 * SR))
    rel_n = max(1, int(0.22 * SR))
    env = np.ones(n)
    if att_n < n:
        env[:att_n] = 0.5 * (1.0 - np.cos(np.pi * np.arange(att_n) / att_n))
    if rel_n < n:
        env[-rel_n:] = 0.5 * (1.0 + np.cos(np.pi * np.arange(rel_n) / rel_n))

    vib_depth = 0.0045 * np.clip((lt - 0.10) / 0.25, 0.0, 1.0)
    phase = 2 * np.pi * freq * lt + vib_depth * freq * np.sin(2 * np.pi * 5.5 * lt)
    wave = np.zeros(n)
    for h_k, w_k in enumerate([1.0, 0.65, 0.42, 0.25, 0.18, 0.11, 0.06], start=1):
        if freq * h_k < SR * 0.45:
            wave += w_k * np.sin(h_k * phase)
    wave = butter_lowpass(wave, 2600.0, order=2) * env * amp
    return wave * np.cos(pan * np.pi / 2), wave * np.sin(pan * np.pi / 2), idx0, idx1

def synth_cinematic_hit(start_s, amp=0.28, is_climax=False):
    dur_s = 1.5 if is_climax else 0.70
    idx0 = max(0, int(start_s * SR))
    idx1 = min(N_SAMPLES, int((start_s + dur_s) * SR))
    if idx1 <= idx0:
        return np.zeros(0), np.zeros(0), idx0, idx0
    n = idx1 - idx0
    lt = np.arange(n) / SR
    f_inst = 46.0 + 90.0 * np.exp(-lt * 24.0)
    phase = 2 * np.pi * np.cumsum(f_inst) / SR
    body = np.sin(phase) * np.exp(-lt * (3.2 if is_climax else 6.5))
    thump = butter_lowpass(np.random.randn(n), 220.0, order=2) * np.exp(-lt * 18.0) * 0.4
    wave = (body + thump) * amp
    if is_climax:
        shimmer = butter_highpass(np.random.randn(n), 3500.0, order=2)
        shimmer = butter_lowpass(shimmer, 9500.0, order=2) * np.exp(-lt * 1.8) * 0.12 * amp
        return wave + shimmer * 0.9, wave - shimmer * 0.9, idx0, idx1
    return wave, wave, idx0, idx1

# Rhythmic Formant-Synthesized Comedic Belly-Laugh Syllable ("哈!" / "齁!")
# Locked to the exact mouth_open envelope in Act IV!
def synth_laugh_syllable(start_s, dur_s=0.17, pitch_hz=260.0, style="ha", amp=0.18, pan=0.5):
    idx0 = max(0, int(start_s * SR))
    idx1 = min(N_SAMPLES, int((start_s + dur_s) * SR))
    if idx1 <= idx0:
        return np.zeros(0), np.zeros(0), idx0, idx0
    n = idx1 - idx0
    lt = np.arange(n) / SR

    # Pitch arcs up quickly then drops playfully (classic comedic "Ha!" / "Hou!" inflection)
    f_contour = pitch_hz * (1.0 + 0.22 * np.sin(np.pi * (lt / dur_s) ** 0.65) - 0.15 * (lt / dur_s))
    phase = 2 * np.pi * np.cumsum(f_contour) / SR

    # Rich glottal harmonic pulse train
    glottal = np.zeros(n)
    for k in range(1, 18):
        if np.mean(f_contour) * k < SR * 0.44:
            glottal += np.sin(k * phase) / (k ** 0.65)

    # Add breathy aspiration burst at start ("H-a!")
    breath = butter_bandpass(np.random.randn(n), 800.0, 3200.0, order=2) * np.exp(-lt * 22.0) * 0.55

    raw_src = glottal + breath
    # Apply vowel formants: "ha" (F1=780, F2=1350, F3=2600) vs "hou" (F1=480, F2=920, F3=2350)
    if style == "ha":
        f1 = butter_bandpass(raw_src, 620.0, 960.0, order=2) * 1.0
        f2 = butter_bandpass(raw_src, 1150.0, 1600.0, order=2) * 0.75
        f3 = butter_bandpass(raw_src, 2300.0, 2900.0, order=2) * 0.35
    else:
        f1 = butter_bandpass(raw_src, 380.0, 620.0, order=2) * 1.1
        f2 = butter_bandpass(raw_src, 760.0, 1120.0, order=2) * 0.80
        f3 = butter_bandpass(raw_src, 2100.0, 2650.0, order=2) * 0.30

    # Also double with a playful staccato marimba/woodwind chuckle note so it blends musically!
    marimba = (np.sin(phase) + 0.4 * np.sin(2 * phase) * np.exp(-lt * 18.0)) * 0.65

    env = np.sin(np.pi * (lt / dur_s)) ** 1.3
    wave = (0.55 * (f1 + f2 + f3) + 0.45 * marimba) * env * amp
    return wave * np.cos(pan * np.pi / 2), wave * np.sin(pan * np.pi / 2), idx0, idx1

np.random.seed(42)
mix_L = np.zeros(N_SAMPLES)
mix_R = np.zeros(N_SAMPLES)

def add_to_mix(wL, wR, i0, i1):
    if i1 > i0:
        mix_L[i0:i1] += wL
        mix_R[i0:i1] += wR

# --- 1. CHORD PROGRESSION ACROSS ALL 4 ACTS (0.0s - 28.8s) ---
# Act I: 0.0s - 6.0s (Harmonic Awakening, M steps up every 1.0s)
# Act II: 6.0s - 16.8s (Slow-Reveal Precision Epicycle Trace, 10.8s full tour)
# Act III: 16.8s - 20.4s (Full 3D Portrait Bloom & Tap-to-Laugh Stitch Bridge)
# Act IV: 20.4s - 28.8s (Stitched 奶蛙捧腹大笑 Finale!)
chords = [
    # Act I (0.0s - 6.0s)
    (0.0,  2.4, [38, 50, 57, 61, 66, 69], 950.0,  0.14),  # Dmaj9
    (2.4,  2.4, [35, 47, 54, 57, 62, 66], 1500.0, 0.16),  # Bm9
    (4.8,  1.2, [33, 45, 52, 57, 62, 64], 2400.0, 0.19),  # A13sus4 riser

    # Act II (6.0s - 16.8s: Precision Epicycle Trace)
    (6.0,  2.4, [38, 50, 57, 62, 66, 74], 2800.0, 0.19),  # Dmaj9
    (8.4,  2.4, [42, 54, 57, 61, 66, 73], 3000.0, 0.19),  # F#m7
    (10.8, 2.4, [31, 43, 50, 55, 59, 69], 3200.0, 0.20),  # Gmaj9
    (13.2, 1.8, [28, 40, 47, 55, 59, 66], 3500.0, 0.21),  # Em9
    (15.0, 1.8, [33, 45, 52, 57, 61, 67], 4100.0, 0.23),  # A9sus4 -> A7

    # Act III (16.8s - 20.4s: Full 3D Portrait Bloom & Stitch Bridge)
    (16.8, 3.6, [26, 38, 50, 57, 62, 66, 69, 74], 4800.0, 0.24),  # Grand Dmaj9 Bloom!

    # Act IV (20.4s - 28.8s: Joyful Belly-Laugh Finale!)
    (20.4, 2.4, [38, 50, 57, 62, 66, 74], 4200.0, 0.20),  # D6/9 Bouncy Groove
    (22.8, 2.4, [31, 43, 50, 55, 59, 67], 4400.0, 0.20),  # G6/9
    (25.2, 1.8, [33, 45, 52, 57, 61, 69], 4500.0, 0.21),  # A13
    (27.0, 1.8, [26, 38, 50, 57, 62, 66, 74], 4800.0, 0.22), # Final Dmaj9 Resolution
]

for start_s, dur_s, notes, bright, amp in chords:
    for m_note in notes:
        wL, wR, i0, i1 = synth_lush_pad_note(
            midi_to_freq(m_note), start_s, dur_s,
            amp=amp / np.sqrt(len(notes)), brightness=bright,
            attack=0.22 if start_s > 0 else 0.35, release=0.8
        )
        add_to_mix(wL, wR, i0, i1)

# --- 2. ARPEGGIOS & MELODY FOR ACTS I-III ---
arp_patterns = [
    (0.0,  2.4, [62, 66, 69, 73, 74, 69, 66, 62]),
    (2.4,  2.4, [59, 62, 66, 69, 73, 69, 66, 62]),
    (4.8,  1.2, [57, 61, 64, 69]),
    (6.0,  2.4, [62, 66, 69, 74, 78, 74, 69, 66]),
    (8.4,  2.4, [61, 66, 69, 73, 76, 73, 69, 66]),
    (10.8, 2.4, [59, 62, 67, 71, 74, 71, 67, 62]),
    (13.2, 1.8, [59, 64, 67, 71, 74, 71]),
    (15.0, 1.8, [61, 64, 69, 73, 76, 81]),
    (16.8, 3.6, [62, 66, 69, 74, 78, 81, 86, 81, 78, 74, 69, 66]),
]
for start_s, dur_s, pattern in arp_patterns:
    step_s = dur_s / len(pattern)
    for idx, m_note in enumerate(pattern):
        t_note = start_s + idx * step_s
        pan = 0.25 + 0.5 * ((idx % 4) / 3.0)
        wL, wR, i0, i1 = synth_celesta_pluck(midi_to_freq(m_note), t_note, dur_s=1.0, amp=0.095, pan=pan)
        add_to_mix(wL, wR, i0, i1)

melody_notes = [
    (1.0, 1.4, 66, 0.10), (2.4, 1.8, 69, 0.11), (4.2, 0.6, 66, 0.09), (4.8, 1.2, 73, 0.13),
    (6.0, 1.8, 74, 0.16), (7.8, 0.6, 73, 0.13),
    (8.4, 1.8, 69, 0.15), (10.2, 0.6, 66, 0.13),
    (10.8, 1.2, 71, 0.16), (12.0, 1.2, 74, 0.17),
    (13.2, 1.2, 76, 0.17), (14.4, 0.6, 74, 0.15),
    (15.0, 0.9, 73, 0.18), (15.9, 0.9, 76, 0.20),
    (16.8, 2.8, 78, 0.20), (17.4, 2.4, 86, 0.13),
]
for start_s, dur_s, m_note, amp_m in melody_notes:
    wL, wR, i0, i1 = synth_expressive_lead(midi_to_freq(m_note), start_s, dur_s, amp=amp_m, pan=0.46)
    add_to_mix(wL, wR, i0, i1)
    if start_s >= 6.0:
        wL2, wR2, i0, i1 = synth_expressive_lead(midi_to_freq(m_note - 12), start_s, dur_s, amp=amp_m * 0.65, pan=0.55)
        add_to_mix(wL2, wR2, i0, i1)

# --- 3. ACT I-III PERCUSSIVE PULSES & LANDMARK CHIMES ---
# Act I step-ups every 1.0s (6 steps in 6.0s)
for s_i in range(6):
    t_step = s_i * 1.0
    wL, wR, i0, i1 = synth_cinematic_hit(t_step, amp=0.24, is_climax=(s_i == 5))
    add_to_mix(wL, wR, i0, i1)
    cL, cR, ci0, ci1 = synth_celesta_pluck(midi_to_freq(74 + s_i * 2), t_step, dur_s=1.1, amp=0.14, pan=0.5)
    add_to_mix(cL, cR, ci0, ci1)

# Act II & III beats (6.0s to 20.4s)
for beat_idx in range(10, 34):
    t_beat = beat_idx * BEAT_DUR
    is_clim = (beat_idx == 10 or beat_idx == 28)  # 6.0s Trace Drop & 16.8s Full 3D Reveal Climax!
    amp_hit = 0.36 if is_clim else (0.21 if (beat_idx % 4 == 0) else 0.12)
    wL, wR, i0, i1 = synth_cinematic_hit(t_beat, amp=amp_hit, is_climax=is_clim)
    add_to_mix(wL, wR, i0, i1)

# Landmark chimes during Act II (6.0s + u * 10.8s)
landmark_u_notes = [
    (0.032, [86, 90, 93]),
    (0.090, [81, 86, 90]),
    (0.215, [85, 88, 93]),
    (0.469, [83, 86, 91]),
    (0.634, [83, 88, 91]),
    (0.749, [85, 88, 93]),
    (0.797, [86, 90, 95]),
    (0.925, [88, 93, 97]),
    (1.000, [74, 81, 86, 90, 98]),
]
for u_val, chord_notes in landmark_u_notes:
    t_lm = 6.00 + u_val * 10.80
    for idx, mn in enumerate(chord_notes):
        wL, wR, i0, i1 = synth_celesta_pluck(
            midi_to_freq(mn), t_lm + idx * 0.035, dur_s=1.4, amp=0.11, pan=0.3 + 0.4 * (idx / len(chord_notes))
        )
        add_to_mix(wL, wR, i0, i1)

# --- 4. ACT IV: STITCHED "奶蛙捧腹大笑" RHYTHMIC LAUGH CADENCE & BOUNCY FINALE (20.4s - 28.8s) ---
# At t = 19.6s - 20.3s, playful tap chime + inhale glissando!
for g_i, mn in enumerate([74, 78, 81, 86, 90, 93]):
    wL, wR, i0, i1 = synth_celesta_pluck(midi_to_freq(mn), 19.65 + g_i * 0.09, dur_s=0.6, amp=0.13, pan=0.5)
    add_to_mix(wL, wR, i0, i1)

# Define exact laugh burst schedule (t_laugh_start, pitch_midi, style, intensity)
# We also save this exact laugh schedule so the video renderer locks mouth_open & belly_jiggle 100% to every syllable!
laugh_syllables = [
    # Burst 1 (20.4s - 22.6s): "哈-哈-哈-哈! 齁-齁-齁-齁!"
    (20.40, 69, "ha",  0.90), (20.60, 71, "ha",  0.95), (20.80, 74, "ha",  1.00), (21.00, 76, "ha",  1.00),
    (21.20, 74, "ha",  0.90), (21.40, 71, "ha",  0.85),
    (21.65, 66, "hou", 0.95), (21.85, 69, "hou", 1.00), (22.05, 71, "hou", 1.00), (22.25, 74, "hou", 0.95),
    # Burst 2 (22.8s - 25.0s): Higher pitched hysterical belly laugh! "哈哈哈哈哈哈哈!"
    (22.80, 71, "ha",  0.95), (22.98, 74, "ha",  1.00), (23.16, 76, "ha",  1.00), (23.34, 78, "ha",  1.00),
    (23.52, 79, "ha",  1.00), (23.70, 78, "ha",  0.95), (23.88, 76, "ha",  0.90), (24.06, 74, "ha",  0.85),
    (24.30, 67, "hou", 0.95), (24.50, 71, "hou", 1.00), (24.70, 74, "hou", 0.95),
    # Burst 3 (25.2s - 27.4s): Peak head-back roar + playful chuckle resolution!
    (25.20, 74, "ha",  1.00), (25.38, 78, "ha",  1.00), (25.56, 81, "ha",  1.00), (25.74, 83, "ha",  1.00),
    (25.92, 81, "ha",  0.95), (26.10, 78, "ha",  0.90), (26.30, 74, "hou", 0.85),
    (26.60, 71, "ha",  0.75), (26.85, 69, "ha",  0.65), (27.10, 66, "hou", 0.55),
]

for t_syl, m_pitch, l_style, l_int in laugh_syllables:
    wL, wR, i0, i1 = synth_laugh_syllable(
        t_syl, dur_s=0.165, pitch_hz=midi_to_freq(m_pitch), style=l_style, amp=0.22 * l_int, pan=0.48
    )
    add_to_mix(wL, wR, i0, i1)
    # Accompanying bouncy pizzicato / celesta sparkle on each laugh syllable
    cL, cR, ci0, ci1 = synth_celesta_pluck(
        midi_to_freq(m_pitch + 12), t_syl, dur_s=0.35, amp=0.09 * l_int, pan=0.35 + 0.3 * (m_pitch % 3) / 2.0
    )
    add_to_mix(cL, cR, ci0, ci1)

# Bouncy percussion on every beat in Act IV (20.4s - 27.6s)
for beat_idx in range(34, 47):
    t_beat = beat_idx * BEAT_DUR
    wL, wR, i0, i1 = synth_cinematic_hit(t_beat, amp=0.24 if (beat_idx % 2 == 0) else 0.15, is_climax=(beat_idx == 34))
    add_to_mix(wL, wR, i0, i1)

# --- 5. STEREO HALL REVERB & MASTERING ---
ir_dur = 2.0
ir_n = int(SR * ir_dur)
ir_t = np.arange(ir_n) / SR
ir_env = np.exp(-ir_t * 2.8) * (1.0 - np.exp(-ir_t * 35.0))
ir_L = butter_lowpass(np.random.randn(ir_n) * ir_env, 3800.0, order=2)
ir_R = butter_lowpass(np.random.randn(ir_n) * ir_env, 3800.0, order=2)
ir_L /= np.sqrt(np.sum(ir_L**2))
ir_R /= np.sqrt(np.sum(ir_R**2))

rev_L = fftconvolve(mix_L, ir_L, mode='full')[:N_SAMPLES]
rev_R = fftconvolve(mix_R, ir_R, mode='full')[:N_SAMPLES]

final_L = mix_L * 0.74 + (rev_L * 0.26 + rev_R * 0.07)
final_R = mix_R * 0.74 + (rev_R * 0.26 + rev_L * 0.07)

fade_in = int(0.15 * SR)
fade_out = int(1.3 * SR)
final_L[:fade_in] *= np.linspace(0, 1, fade_in)
final_R[:fade_in] *= np.linspace(0, 1, fade_in)
final_L[-fade_out:] *= 0.5 * (1.0 + np.cos(np.pi * np.arange(fade_out) / fade_out))
final_R[-fade_out:] *= 0.5 * (1.0 + np.cos(np.pi * np.arange(fade_out) / fade_out))

peak = max(np.max(np.abs(final_L)), np.max(np.abs(final_R)), 1e-6)
final_L = soft_clip(final_L / peak * 0.92, drive=1.15)
final_R = soft_clip(final_R / peak * 0.92, drive=1.15)

stereo_int16 = np.column_stack([
    (final_L * 32000).astype(np.int16),
    (final_R * 32000).astype(np.int16)
])
wav_path = audio_dir / 'naiwa_soundtrack.wav'
wavfile.write(wav_path, SR, stereo_int16)

# Extract per-frame RMS, 32-band spectrum, AND exact per-frame laugh animation curves at 30 FPS (864 frames)!
FPS = 30
N_FRAMES = int(round(DURATION * FPS))
mono = 0.5 * (final_L + final_R)
frame_rms = np.zeros(N_FRAMES)
frame_spec = np.zeros((N_FRAMES, 32))
win_size = int(SR / FPS)
band_edges = np.geomspace(45.0, 6000.0, 33)

for f_i in range(N_FRAMES):
    s0 = f_i * win_size
    s1 = min(N_SAMPLES, s0 + win_size * 2)
    chunk = mono[s0:s1]
    if len(chunk) > 0:
        frame_rms[f_i] = np.sqrt(np.mean(chunk**2))
        spec = np.abs(np.fft.rfft(chunk * np.hanning(len(chunk))))
        freqs_fft = np.fft.rfftfreq(len(chunk), 1.0 / SR)
        for b_i in range(32):
            mask = (freqs_fft >= band_edges[b_i]) & (freqs_fft < band_edges[b_i+1])
            if np.any(mask):
                frame_spec[f_i, b_i] = np.mean(spec[mask])

frame_rms /= (np.max(frame_rms) + 1e-8)
frame_spec = np.log1p(frame_spec * 8.0)
frame_spec /= (np.max(frame_spec) + 1e-8)
for b_i in range(32):
    frame_spec[:, b_i] = np.convolve(frame_spec[:, b_i], [0.2, 0.5, 0.3], mode='same')

# Precompute smooth, physics-coupled per-frame laugh rig parameters for all 864 frames!
laugh_mouth = np.zeros(N_FRAMES)
laugh_squint = np.zeros(N_FRAMES)
laugh_lean = np.zeros(N_FRAMES)
laugh_head = np.zeros(N_FRAMES)
laugh_belly_inf = np.zeros(N_FRAMES)
laugh_belly_dy = np.zeros(N_FRAMES)
laugh_hand = np.zeros(N_FRAMES)
laugh_bounce = np.zeros(N_FRAMES)

for f_i in range(N_FRAMES):
    ts = f_i / FPS
    if ts < 19.60:
        continue
    elif ts < 20.40:
        # Pre-laugh tap & deep inhale anticipation (19.60s - 20.40s)
        p = (ts - 19.60) / 0.80
        inhale = np.sin(np.pi * (p ** 0.8))
        laugh_mouth[f_i] = 0.22 * (p ** 1.5)
        laugh_squint[f_i] = 0.45 * (p ** 1.2)
        laugh_lean[f_i] = -3.0 * inhale
        laugh_head[f_i] = -4.0 * inhale
        laugh_belly_inf[f_i] = 0.95 * inhale
        laugh_belly_dy[f_i] = -9.0 * inhale
        laugh_hand[f_i] = -0.8 * inhale
        laugh_bounce[f_i] = -6.0 * inhale
    else:
        # Active Belly-Laughing Finale (20.40s - 28.80s)
        # Sum contributions from each laugh syllable pulse + continuous carrier wave
        m_val = 0.18
        b_osc = 0.0
        for t_syl, m_pitch, l_style, l_int in laugh_syllables:
            dt = ts - t_syl
            if -0.03 <= dt <= 0.20:
                pulse = np.sin(np.pi * np.clip((dt + 0.03) / 0.21, 0.0, 1.0)) ** 1.1
                m_val = max(m_val, (0.65 + 0.35 * l_int) * pulse)
            if -0.05 <= dt <= 0.28:
                b_osc += l_int * np.sin(2 * np.pi * 5.2 * dt) * np.exp(-abs(dt - 0.08) * 9.0)

        # Envelope across Act IV (rises quickly at 20.4s, peaks at 23-26.5s, settles gently 27.3-28.8s)
        act4_env = np.clip((ts - 20.35) / 0.25, 0.0, 1.0) * np.clip((28.65 - ts) / 1.35, 0.0, 1.0)
        # Extra head-back surge during Burst 2 & Burst 3
        burst_surge = (
            0.65 * np.exp(-((ts - 21.3) / 0.9) ** 2)
            + 0.90 * np.exp(-((ts - 23.6) / 1.1) ** 2)
            + 1.15 * np.exp(-((ts - 25.8) / 1.0) ** 2)
        )

        laugh_mouth[f_i] = np.clip(m_val * act4_env, 0.0, 1.0)
        laugh_squint[f_i] = np.clip((0.78 + 0.22 * np.sin(ts * 6.0) ** 2) * act4_env, 0.0, 1.0)
        laugh_lean[f_i] = (4.5 + 8.5 * burst_surge + 3.0 * b_osc) * act4_env
        laugh_head[f_i] = (5.0 + 9.0 * burst_surge + 5.5 * b_osc) * act4_env
        # Belly jiggle has slight phase lag behind mouth/head for rubbery secondary physics!
        jiggle_wave = np.sin(2 * np.pi * 5.2 * (ts - 20.40) - 0.55)
        laugh_belly_inf[f_i] = (0.35 * burst_surge + 0.85 * jiggle_wave) * act4_env
        laugh_belly_dy[f_i] = (14.5 * jiggle_wave) * act4_env
        laugh_hand[f_i] = (1.25 * np.sin(2 * np.pi * 5.2 * (ts - 20.40) - 0.25)) * act4_env
        laugh_bounce[f_i] = (9.5 * np.sin(2 * np.pi * 5.2 * (ts - 20.40))) * act4_env

# Temporal smoothing on rig channels so motion is 100% fluid at 30 FPS
ker3 = np.array([0.22, 0.56, 0.22])
for arr in [laugh_mouth, laugh_squint, laugh_lean, laugh_head, laugh_belly_inf, laugh_belly_dy, laugh_hand, laugh_bounce]:
    arr[:] = np.convolve(arr, ker3, mode='same')

np.savez(data_dir / 'audio_sync_features.npz',
         frame_rms=frame_rms, frame_spec=frame_spec, fps=FPS, n_frames=N_FRAMES,
         laugh_mouth=laugh_mouth, laugh_squint=laugh_squint,
         laugh_lean=laugh_lean, laugh_head=laugh_head,
         laugh_belly_inf=laugh_belly_inf, laugh_belly_dy=laugh_belly_dy,
         laugh_hand=laugh_hand, laugh_bounce=laugh_bounce)
print(f"Synthesized {DURATION}s 4-Act soundtrack & {N_FRAMES}-frame laugh rig curves successfully!")
