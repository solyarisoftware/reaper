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

- [`MIDI/ccscope/`](MIDI/ccscope/) — [README](MIDI/ccscope/README.md) · [changelog](MIDI/ccscope/CHANGELOG.md)

Issues and discussions are the roadmap for each package; no separate roadmap file is kept.

## How this repository is organised

This is a ReaPack repository, so **the folder tree is the package taxonomy**: a file in
`MIDI/ccscope/` is installed as `Effects/MIDI/ccscope/<file>` and appears under the
*MIDI/ccscope* category in ReaPack. The `index.xml` at the root is generated from the files'
metadata headers by [reapack-index](https://github.com/cfillion/reapack-index) running in GitHub
Actions — do not edit it by hand.

Each package lives in its own folder, with everything it needs: the sources, the includes it
imports (which resolve relative to it), and its own documentation.

## Feedback and contributions

- **Bug:** open an issue with reproduction steps and expected versus actual behaviour.
- **Idea or workflow need:** start a discussion in **Ideas**.
- **Defined feature or change request:** open an enhancement issue with completion criteria.

Start titles with the tool name, such as `CCScope - …`. Open topics are not promises of
implementation or delivery dates. Testing, documentation and code contributions are welcome.

Full guidelines: [CONTRIBUTING.md](CONTRIBUTING.md).

## Related repositories

The scale collections are separate projects, each with its own documentation:

- [Claude-Debussy-Scales](https://github.com/solyarisoftware/Claude-Debussy-Scales)
- [Alexander-Scriabin-Scales](https://github.com/solyarisoftware/Alexander-Scriabin-Scales)
- [Olivier-Messiaen-Modes](https://github.com/solyarisoftware/Olivier-Messiaen-Modes)

## Support

**IF YOU LIKE THE PROJECT, PLEASE ⭐️STAR THIS REPOSITORY TO SHOW YOUR SUPPORT!**

A star costs nothing, and it is the only signal GitHub shows to whoever is looking for a tool
like this one: the count is what makes a repository look alive.

If you want to go further, there is a donate button in the **Sponsor** menu of this repository:

- **[Donate with PayPal](https://www.paypal.com/donate/?hosted_button_id=AEV3EVJEUFM32)**

Donations are entirely voluntary and help cover investigation, development, testing and
documentation. You do not need to donate to report a bug, propose an improvement or join a
discussion. A donation does not guarantee implementation, priority, a delivery date or support.
It is not a purchase: nothing is unlocked and nothing changes in the license. The minimum is 5 EUR, for a practical reason — below that the
PayPal fee takes most of it. The same button funds the other open-source work of mine
(dxconvey, the scale collections), so one pointer covers all of it.

## License

[MIT](LICENSE) — Copyright (c) 2025-2026 Giorgio Robino.
