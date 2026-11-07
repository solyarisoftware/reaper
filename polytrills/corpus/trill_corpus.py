#!/usr/bin/env python3
"""Extract trill gestures from a take or a MIDI source and describe them.

This is the measuring instrument behind the corpus in this folder. It reads
*gestures*, not scores: any sequence of notes that alternates between two
pitches fast enough to be heard as an ornament, whether it was played by one
contributor, by a professional pianist in a MIDI performance, or sequenced.

Usage
-----
    python3 trill_corpus.py --take takes/c01-2026-11-07.csv
    python3 trill_corpus.py --midi /path/to/performances.zip
    python3 tests/trill_corpus.py --take ... --out /tmp/features.csv

Two input formats are understood:

  take CSV   `t,pitch,dur,vel[,chan]` — seconds, one row per note.
             This is what REAPER exports in the capture procedure.
  MIDI       `.mid`/`.midi` files, or a zip containing them (performance
             datasets usually ship as a zip). Sustain pedal (CC64) is read
             and reported, because a note held by the pedal keeps sounding
             after its key is released: the "overlap" between consecutive
             trill notes means something different with the pedal down.

Output: one row per trill episode, with the features the synthesis model
needs — rate, irregularity, onset, overlap, balance, accent, interval.

Definitions (all measured, none assumed):
  ioi        inter-onset interval, seconds between consecutive attacks
  rate       notes per second = 1 / median(ioi)
  ioi_cv     coefficient of variation of the ioIs: how uneven the trill is
  dur_med    median sounding duration of one note
  ov_med     median (note_end - next_attack): positive = the previous note
             still sounds when the next one starts (legato), negative = a gap
  onset_x    first ioi / median ioi of the body: how much slower it starts
  dur_ratio  median upper-note duration / median lower-note duration
  accent     mean upper velocity - mean lower velocity
  pedal      1 if sustain was down during the episode (MIDI input only)

The detector is deliberately conservative: it needs at least MIN_NOTES in a
row, alternation between exactly two pitches, and an interval no wider than
MAX_INTERVAL semitones. Chords are tolerated on the accompanying voices: an
onset is accepted if it contains the pitch the alternation expects.

No third-party dependency. Python 3.8+.
"""

import argparse
import csv
import statistics as st
import sys
import zipfile
from collections import Counter, defaultdict

MIN_IOI = 0.025        # a trill cannot be faster than 40 notes/s
MAX_IOI = 0.30         # slower than this is not an alternation, it is a run
CHORD_EPS = 0.012      # onsets closer than this are one chord
MIN_NOTES = 8          # at least four full alternations
MAX_INTERVAL = 4       # semitones


# ── MIDI reading ─────────────────────────────────────────────────────

def _varlen(d, i):
    v = 0
    while True:
        b = d[i]
        i += 1
        v = (v << 7) | (b & 0x7F)
        if not b & 0x80:
            return v, i


def parse_smf(data):
    """Return (division, tempos, notes, pedal).

    notes: [(start_tick, end_tick, pitch, velocity)]
    tempos: [(tick, usec_per_quarter)]
    pedal: [(tick, value)]  — CC64 only
    """
    if data[:4] != b'MThd':
        raise ValueError('not a MIDI file')
    hlen = int.from_bytes(data[4:8], 'big')
    division = int.from_bytes(data[12:14], 'big')
    if division & 0x8000:
        raise ValueError('SMPTE division not supported')
    i = 8 + hlen
    tempos, notes, pedal = [], [], []
    while i + 8 <= len(data) and data[i:i + 4] == b'MTrk':
        tlen = int.from_bytes(data[i + 4:i + 8], 'big')
        t = data[i + 8:i + 8 + tlen]
        i += 8 + tlen
        j = tick = 0
        status = None
        pending = defaultdict(list)
        while j < len(t):
            delta, j = _varlen(t, j)
            tick += delta
            if j >= len(t):
                break
            b = t[j]
            if b & 0x80:
                status = b
                j += 1
                if status in (0xF0, 0xF7):
                    ln, j = _varlen(t, j)
                    j += ln
                    continue
                if status == 0xFF:
                    meta = t[j]
                    j += 1
                    ln, j = _varlen(t, j)
                    if meta == 0x51 and ln == 3:
                        tempos.append((tick, int.from_bytes(t[j:j + 3], 'big')))
                    j += ln
                    continue
            if status is None or status >= 0xF0:
                j += 1
                continue
            hi = status & 0xF0
            n = 1 if hi in (0xC0, 0xD0) else 2
            if j + n > len(t):
                break
            p1 = t[j]
            p2 = t[j + 1] if n == 2 else 0
            j += n
            if hi == 0x90 and p2 > 0:
                pending[(status & 0x0F, p1)].append((tick, p2))
            elif hi == 0x80 or (hi == 0x90 and p2 == 0):
                k = (status & 0x0F, p1)
                if pending.get(k):
                    st_t, vel = pending[k].pop(0)
                    notes.append((st_t, tick, p1, vel))
            elif hi == 0xB0 and p1 == 64:
                pedal.append((tick, p2))
    notes.sort()
    return division, sorted(tempos), notes, sorted(pedal)


def tick_to_sec(division, tempos, ticks):
    sec, prev, usec = 0.0, 0, 500000
    for tk, us in tempos:
        if tk > ticks:
            break
        sec += (tk - prev) * usec / 1e6 / division
        prev, usec = tk, us
    return sec + (ticks - prev) * usec / 1e6 / division


# ── trill detection ──────────────────────────────────────────────────

def find_trills(notes_sec):
    """Yield (run, pair) where run is [(t, end, pitch, vel)] alternating.

    notes_sec is [(t, end, pitch, vel)] in seconds, sorted by t.
    """
    groups = []
    for st_t, en, p, v in notes_sec:
        if groups and st_t - groups[-1][0] <= CHORD_EPS:
            groups[-1][1].append((st_t, en, p, v))
        else:
            groups.append((st_t, [(st_t, en, p, v)]))

    run, pair, last = [], None, None

    def close():
        if len(run) >= MIN_NOTES:
            return [m for _, m in run], pair
        return None

    for gi, (now, members) in enumerate(groups):
        out = None
        if run:
            dt = now - groups[run[-1][0]][0]
            if dt < MIN_IOI or dt > MAX_IOI:
                out = close()
                run, pair = [], None
            else:
                cands = [m for m in members if m[2] != last]
                if pair is None and cands:
                    near = min(cands, key=lambda m: abs(m[2] - last))
                    if abs(near[2] - last) <= MAX_INTERVAL:
                        pair = (min(last, near[2]), max(last, near[2]))
                        run.append((gi, near))
                        last = near[2]
                        if out:
                            yield out
                        continue
                elif pair is not None:
                    other = pair[1] if last == pair[0] else pair[0]
                    hit = [m for m in members if m[2] == other]
                    if hit:
                        run.append((gi, hit[0]))
                        last = other
                        if out:
                            yield out
                        continue
                out = close()
                run, pair = [], None
        if out:
            yield out
        top = max(members, key=lambda m: m[2])
        run, last, pair = [(gi, top)], top[2], None
    out = close()
    if out:
        yield out


def features(run, pedal_down=0):
    """Describe one trill episode."""
    n = len(run)
    t = [r[0] for r in run]
    ioi = [t[k + 1] - t[k] for k in range(n - 1)]
    dur = [r[1] - r[0] for r in run]
    ov = [run[k][1] - t[k + 1] for k in range(n - 1)]
    vel = [r[3] for r in run]
    lo, hi = min(run, key=lambda r: r[2])[2], max(run, key=lambda r: r[2])[2]
    dl = [d for d, r in zip(dur, run) if r[2] == lo]
    dh = [d for d, r in zip(dur, run) if r[2] == hi]
    vl = [v for v, r in zip(vel, run) if r[2] == lo]
    vh = [v for v, r in zip(vel, run) if r[2] == hi]
    body = sorted(ioi[len(ioi) // 4:] or ioi)
    med_body = body[len(body) // 2]
    mean = sum(ioi) / len(ioi)
    sd = (sum((x - mean) ** 2 for x in ioi) / len(ioi)) ** 0.5
    med_ioi = sorted(ioi)[len(ioi) // 2]
    return dict(
        n=n, span=t[-1] - t[0], ioi_med=med_ioi, rate=1.0 / med_ioi,
        ioi_cv=sd / mean if mean else 0.0,
        dur_med=sorted(dur)[len(dur) // 2],
        ov_med=sorted(ov)[len(ov) // 2],
        onset_x=ioi[0] / med_body if med_body else 0.0,
        dur_ratio=sorted(dh)[len(dh) // 2] / sorted(dl)[len(dl) // 2] if dl and dh else 0.0,
        accent=(sum(vh) / len(vh) - sum(vl) / len(vl)) if vl and vh else 0.0,
        interval=hi - lo, pedal=pedal_down,
    )


# ── sources ──────────────────────────────────────────────────────────

def notes_from_take(path):
    out = []
    with open(path, newline='') as f:
        for r in csv.DictReader(f):
            t = float(r['t'])
            out.append((t, t + float(r['dur']), int(r['pitch']), int(r.get('vel') or 0)))
    out.sort()
    return out


def takes_from_midi(source):
    """Yield (name, notes_sec, pedal_spans_sec) from a directory or a zip."""
    if source.endswith('.zip'):
        z = zipfile.ZipFile(source)
        names = sorted(n for n in z.namelist() if n.lower().endswith(('.mid', '.midi')))
        for name in names:
            yield name, z.read(name)
    else:
        import pathlib
        for p in sorted(pathlib.Path(source).rglob('*')):
            if p.suffix.lower() in ('.mid', '.midi'):
                yield str(p), p.read_bytes()


# ── report ───────────────────────────────────────────────────────────

def q(v, p):
    v = sorted(v)
    if not v:
        return 0.0
    i = (len(v) - 1) * p
    lo = int(i)
    return v[lo] + (v[min(lo + 1, len(v) - 1)] - v[lo]) * (i - lo)


def summarise(rows, label):
    if not rows:
        print(f'{label}: nessun trillo trovato')
        return
    g = lambda k: [r[k] for r in rows]
    print(f'\n{label}: {len(rows)} episodi, {sum(r["n"] for r in rows)} note')
    print(f'  rate        {q(g("rate"), .1):5.1f} / {st.median(g("rate")):5.1f} / {q(g("rate"), .9):5.1f}  note/s (p10/med/p90)')
    print(f'  irregolarità{q(g("ioi_cv"), .1):5.2f} / {st.median(g("ioi_cv")):5.2f} / {q(g("ioi_cv"), .9):5.2f}  CV degli IOI')
    print(f'  onset       {q(g("onset_x"), .1):5.2f} / {st.median(g("onset_x")):5.2f} / {q(g("onset_x"), .9):5.2f}  primo IOI / corpo')
    print(f'  legato      {q(g("ov_med"), .1)*1000:5.0f} / {st.median(g("ov_med"))*1000:5.0f} / {q(g("ov_med"), .9)*1000:5.0f}  ms (>0 = sovrapposti)')
    print(f'  balance     {q([x for x in g("dur_ratio") if x], .1):5.2f} / {st.median([x for x in g("dur_ratio") if x]):5.2f} / {q([x for x in g("dur_ratio") if x], .9):5.2f}  upper/base')
    print(f'  accento     {q(g("accent"), .1):5.1f} / {st.median(g("accent")):5.1f} / {q(g("accent"), .9):5.1f}  vel upper-base')
    print(f'  durata      {q(g("n"), .1):5.0f} / {st.median(g("n")):5.0f} / {q(g("n"), .9):5.0f}  note per episodio')
    print(f'  intervalli  {dict(sorted(Counter(r["interval"] for r in rows).items()))} (semitoni)')
    if any('pedal' in r for r in rows):
        print(f'  pedale giù  {sum(r["pedal"] for r in rows)}/{len(rows)} episodi')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--take', action='append', default=[], help='take CSV (t,pitch,dur,vel[,chan])')
    ap.add_argument('--midi', action='append', default=[], help='MIDI file, directory or zip')
    ap.add_argument('--out', help='write one row per episode to this CSV')
    args = ap.parse_args()
    if not args.take and not args.midi:
        ap.print_help()
        return 1

    out = open(args.out, 'w', newline='') if args.out else None
    writer = None
    if out:
        writer = csv.writer(out)
        writer.writerow(['source', 'n', 'span', 'ioi_med', 'rate', 'ioi_cv', 'dur_med',
                         'ov_med', 'onset_x', 'dur_ratio', 'accent', 'interval', 'pedal'])

    for path in args.take:
        rows = []
        for run, pair in find_trills(notes_from_take(path)):
            if pair and pair[1] - pair[0] <= MAX_INTERVAL:
                rows.append(features(run))
        summarise(rows, f'take {path}')
        if writer:
            for r in rows:
                writer.writerow([path] + [round(r[k], 6) for k in
                                ('n', 'span', 'ioi_med', 'rate', 'ioi_cv', 'dur_med',
                                 'ov_med', 'onset_x', 'dur_ratio', 'accent', 'interval', 'pedal')])

    for source in args.midi:
        rows = []
        used = 0
        for name, blob in takes_from_midi(source):
            try:
                div, tempos, notes, pedal = parse_smf(blob)
            except Exception:
                continue
            if not notes or div <= 0:
                continue
            used += 1
            ns = [(tick_to_sec(div, tempos, a), tick_to_sec(div, tempos, b), p, v)
                  for a, b, p, v in notes]
            for run, pair in find_trills(ns):
                if not pair or pair[1] - pair[0] > MAX_INTERVAL:
                    continue
                t0, t1 = run[0][0], run[-1][0]
                down = 0
                state = 0
                for tk, val in pedal:
                    ts = tick_to_sec(div, tempos, tk)
                    if ts <= t0:
                        state = val
                    elif ts <= t1 and val >= 64:
                        down = 1
                if state >= 64:
                    down = 1
                rows.append(features(run, down))
        if writer:
            for r in rows:
                writer.writerow([source] + [round(r[k], 6) for k in
                                ('n', 'span', 'ioi_med', 'rate', 'ioi_cv', 'dur_med',
                                 'ov_med', 'onset_x', 'dur_ratio', 'accent', 'interval', 'pedal')])
        summarise(rows, f'MIDI {source} ({used} file letti)')
        if rows:
            no_pedal = [r for r in rows if not r['pedal']]
            summarise(no_pedal, f'MIDI {source} — solo pedale ALZATO')

    if out:
        out.close()
        print(f'\nfeature scritte in {args.out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
