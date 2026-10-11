"""Assess bounded FIFO metadata; no raw PCM or device access."""
import re


def analyze(messages):
    fields = ('phase', 'port', 'tone_enabled', 'words', 'word_changes',
              'all_ones', 'peak', 'sign_crossings')
    pattern = (r'signal_phase=(\d+) port=(\d+) tone_enabled=(\d+) words=(\d+) '
               r'word_changes=(\d+) all_ones=(\d+) peak=(\d+) sign_crossings=(\d+)')
    rows = [dict(zip(fields, map(int, match.groups()))) for row in messages
            if (match := re.search(pattern, row))]
    indexed = {(r['phase'], r['port']): r for r in rows}
    valid = len(rows) == 6 and set(indexed) == {(p, a) for p in range(3) for a in range(2)}
    if valid:
        for phase in range(3):
            quiet, signal = indexed[phase, 0], indexed[phase, 1]
            valid &= quiet['peak'] == 0 and quiet['words'] > 5000
            valid &= signal['words'] > 5000 and signal['all_ones'] == 0
            valid &= signal['tone_enabled'] == (phase != 1)
            if phase == 1:
                # Up to one old FIFO remains after the STOP acknowledgment.
                valid &= signal['word_changes'] <= 64 and signal['sign_crossings'] <= 32
            else:
                valid &= signal['word_changes'] > signal['words'] * .9
                valid &= 1000 < signal['peak'] < 16000
                # Two mono16 samples/word: 1 kHz at 8 kHz crosses sign once
                # every two FIFO words. Permit a small startup FIFO tail.
                valid &= .45 < signal['sign_crossings'] / signal['words'] < .55
    return dict(signal_phases=rows, arm1_tone_signal_verified=bool(valid),
                received_gsm_speech_verified=False, sample_bytes_saved=False)
