# REAPER tools

My public REAPER tools, published as a **ReaPack repository** — install once, and REAPER keeps
them up to date.

## Install

In REAPER: *Extensions → ReaPack → Import a repository*, paste this URL, then synchronize:

```
https://github.com/solyarisoftware/reaper/raw/master/index.xml
```

Manual install, if you prefer: copy the `.jsfx` **and** its `.jsfx-inc` companions into the same
folder inside your REAPER resource directory (`Effects/<category>/` on Windows).

## Packages

| Package | ReaPack category | What it does |
|---|---|---|
| [CCScope](MIDI/ccscope/) | `MIDI/ccscope` | Oscilloscope for MIDI CC: scrolling graph and fader bars, per channel, with performance metrics |

Each package keeps its documentation next to its sources — README, changelog, roadmap, screenshot:

- [`MIDI/ccscope/`](MIDI/ccscope/) — [README](MIDI/ccscope/README.md) · [changelog](MIDI/ccscope/CHANGELOG.md) · [roadmap](MIDI/ccscope/TODO.md)

## How this repository is organised

This is a ReaPack repository, so **the folder tree is the package taxonomy**: a file in
`MIDI/ccscope/` is installed as `Effects/MIDI/ccscope/<file>` and appears under the
*MIDI/ccscope* category in ReaPack. The `index.xml` at the root is generated from the files'
metadata headers by [reapack-index](https://github.com/cfillion/reapack-index) running in GitHub
Actions — do not edit it by hand.

Each package lives in its own folder, with everything it needs: the sources, the includes it
imports (which resolve relative to it), and its own documentation.

## Related repositories

The scale collections are separate projects, each with its own documentation:

- [Claude-Debussy-Scales](https://github.com/solyarisoftware/Claude-Debussy-Scales)
- [Alexander-Scriabin-Scales](https://github.com/solyarisoftware/Alexander-Scriabin-Scales)
- [Olivier-Messiaen-Modes](https://github.com/solyarisoftware/Olivier-Messiaen-Modes)

## License

[MIT](LICENSE) — Copyright (c) 2025-2026 Giorgio Robino.
