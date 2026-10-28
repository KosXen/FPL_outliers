# ⚽ FPL Data-Driven Scouting Engine

An automated Fantasy Premier League (FPL) scouting application built with Python and Streamlit. Rather than chasing past points, this engine evaluates underlying shot quality, chance creation volume, and regression variance to surface **underperforming buy targets** and **unsustainable overperformers**.

---

## 🚀 Key Features

* **Live Data Sync:** Direct ingestion from the official Fantasy Premier League API (`bootstrap-static`).
* **Position-Weighted Talent Index (`baseline_score`):**
  * **FWD:** 80% Finishing Threat / 20% Creative Output.
  * **MID:** Balanced 55% Finishing Threat / 45% Creative Output.
  * **DEF:** 65% Primary Trait / 35% Secondary Trait (dynamically caters to aerial set-piece center-backs and crossing fullbacks).
* **Regression Multiplier (`buy_score`):** Identifies players with high expected involvement whose actual goals and assists are lagging behind expected numbers due to conversion variance.
* **Overperformer / Trap Detector:** Flags players accumulating points on low underlying volume with negative delta values.
* **Dynamic Sample Size Gating:** Automatically filters players based on a gameweek-scaled minutes floor to prevent small-sample distortion.

---

## 📊 Metric Reference

| Metric | Description |
| :--- | :--- |
| **`baseline_score`** | Composite attacking quality (0–100) anchored against elite Premier League benchmarks. |
| **`xGI_per90`** | Expected Goal Involvements ($xG + xA$) standardized per 90 minutes. |
| **`GI_per90`** | Actual Goal Involvements ($\text{Goals} + \text{Assists}$) standardized per 90 minutes. |
| **`GI_delta`** | $xGI_{p90} - GI_{p90}$. Positive values indicate underperformance (buy targets); negative values indicate overperformance (traps). |
| **`buy_score`** | Position baseline scaled by the regression multiplier. |

> **Note on Defenders:** The model evaluates defenders strictly on attacking threat and delivery potential. Clean sheet likelihood and defensive fixtures should be evaluated separately.

---

## 🛠️ Local Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/](https://github.com/)<your-username>/fpl-scout.git
   cd fpl-scout