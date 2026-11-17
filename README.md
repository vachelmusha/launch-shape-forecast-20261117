# Launch Shape Forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/vachelmusha/launch-shape-forecast-20261117/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/vachelmusha/launch-shape-forecast-20261117/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

An offline, deterministic Python forecast for Twitch launch-day viewers. It reads the observed first hour and supplied historical launches, then forecasts hours 2–24 at quantile levels 5%, 25%, 50%, 75%, and 95%.

## Method

Each historical launch is a scenario, scaled to the observed first-hour audience. Similarity uses its preceding audience trajectory, viewers per broadcaster, launch platform, local versus global unlocks, and early access. A kernel weights similar scenarios while retaining a small population component. A continuous mixture adds uncertainty before weighted quantiles are computed in log space. Missing observations remain missing rather than becoming zeros. The GTA VI premiere series is excluded from launch scenarios because it is not a release day.

Bandwidth, metadata weighting, and mixture spread were selected by leave-one-launch-out validation on the 37 launches supplied as comparables in the practice input. The selected configuration had mean log pinball loss 0.5755 across those launches, versus 0.9296 for the house persistence formula. The console subset loss was 0.2146. These are local cross-validation results, not the contest's four-case practice score or an estimate of final placement.

No future practice answers, network calls, installed dependencies, or saved launch data are used by the entry. All scenarios come from the case it receives at run time.

## Run it

```sh
MAKEFUN_INPUT_DIR=/path/to/input MAKEFUN_OUTPUT_DIR=/path/to/output python3 main.py
```

With no environment variables it reads `/input/*.in` and writes `/output/*.out`. Python standard library only; tested locally under Python 3.12 and intended for the bounty's Python 3.13 runtime. The repository contains no data or credentials.

---

<sub>Entered on [make.fun](https://make.fun/?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
