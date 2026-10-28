# ⚽ FPL Data-Driven Scouting Engine

A Streamlit app that scouts Fantasy Premier League players using **underlying chance quality** (xG, xA, Opta Threat and Creativity) instead of raw points. It highlights players who are likely to bounce back, players who are genuine talents, and players who are likely to regress.

**🔗 Live app:** `https://fpl-outliers.streamlit.app/`

---

## Features

| Tab | What it shows |
|---|---|
| 🎯 **Top Buy Targets** | Players with strong underlying numbers whose goals and assists are lagging behind (positive `GI_delta`). |
| ⭐ **Core Talismans** | The highest-rated players by baseline score, regardless of luck. |
| ⚠️ **Overperformers** | Players returning more than their underlying numbers justify (negative `GI_delta`). Regression and sell risks. |

- Covers **FWD, MID and DEF** (goalkeepers are excluded).
- Pulls live data from the official FPL API and refreshes automatically every hour.
- Applies a dynamic minutes filter that grows with the season, so small samples don't skew results.

---

## How It Works

All metrics are calculated **per 90 minutes**.

**1. Attacking Score (0–100)**
70% non-penalty xG + 30% Opta Threat, normalised against elite benchmarks.

**2. Creation Score (0–100)**
70% xA + 30% Opta Creativity, normalised against elite benchmarks.

**3. Baseline Score (0–100)**: a position-weighted blend of the two:

| Position | Weighting |
|---|---|
| FWD | 80% Attacking / 20% Creation |
| MID | 60% Attacking / 40% Creation |
| DEF | 65% best trait / 35% second-best trait |

**4. GI Delta**
`GI_delta = xGI per 90 − GI per 90`
- **Positive**: underperforming, so more returns are likely (buy).
- **Negative**: overperforming, so a dry spell is likely (sell).

**5. Buy Score**
`Buy Score = Baseline Score × (1 + GI_delta × 1.5)`
The multiplier is floored at 0.20 so extreme overperformers are heavily discounted but never reach zero.

Each position has its own thresholds for the buy and overperformer tabs. They live in `SCOUTING_THRESHOLDS` at the top of `app.py` and are easy to tune.

**Minutes filter:** `max(90, (current_GW − ceil(current_GW / 6)) × 90)`

> ⚠️ **Defenders:** they are scored on attacking output only (set pieces, crosses, key passes). Clean sheet probability and team defensive strength are **not** considered, so check fixtures and clean sheet records before transferring.

---

## Run Locally

**Requirements:** Python 3.9+

```bash
# 1. Clone the repo
git clone https://github.com/KosXen/FPL_outliers.git
cd FPL_outliers

# 2. Install dependencies
pip install streamlit pandas numpy requests

# 3. Run the app
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Project Structure

```
├── app.py              # Data pipeline, scoring logic and Streamlit UI
├── requirements.txt    # Python dependencies
└── README.md
```

---

## Data Source

Data comes from the public [FPL API](https://fantasy.premierleague.com/api/bootstrap-static/). This project is unofficial and not affiliated with the Premier League.

## Disclaimer

Expected-stats models show probabilities, not guarantees. Use this tool as one input in your transfer decisions, alongside fixtures, injuries, rotation risk and personal judgement.
