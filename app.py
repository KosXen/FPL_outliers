import math
import numpy as np
import pandas as pd
import requests
import streamlit as st

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="FPL Scouting Engine", layout="wide", page_icon="⚽")

# --- CONSTANTS & THRESHOLDS ---
FPL_URL = "https://fantasy.premierleague.com/api/bootstrap-static/"
REGRESSION_WEIGHT = 1.5

SCOUTING_THRESHOLDS = {
    "FWD": {
        "buy_min_baseline": 42.0,
        "buy_min_xgi": 0.40,
        "buy_min_delta": 0.10,
        "over_max_baseline": 55.0,
        "over_max_xgi": 0.35,
        "over_min_gi": 0.45,
        "over_delta": -0.15,
    },
    "MID": {
        "buy_min_baseline": 30.0,
        "buy_min_xgi": 0.28,
        "buy_min_delta": 0.08,
        "over_max_baseline": 38.0,
        "over_max_xgi": 0.24,
        "over_min_gi": 0.35,
        "over_delta": -0.12,
    },
    "DEF": {
        "buy_min_baseline": 14.0,
        "buy_min_xgi": 0.10,
        "buy_min_delta": 0.04,
        "over_max_baseline": 18.0,
        "over_max_xgi": 0.08,
        "over_min_gi": 0.14,
        "over_delta": -0.06,
    },
}

# --- DATA RETRIEVAL & MAPPING ---
def get_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(FPL_URL, headers=headers)
    response.raise_for_status()
    return response.json()


def mapping(raw_data):
    teams_map = {t["id"]: t["name"] for t in raw_data["teams"]}
    positions_map = {p["id"]: p["singular_name_short"] for p in raw_data["element_types"]}

    df = pd.DataFrame(raw_data["elements"])
    df["team_name"] = df["team"].map(teams_map)
    df["position"] = df["element_type"].map(positions_map)
    df["price"] = df["now_cost"] / 10.0
    return df


def get_current_gameweek(raw_data):
    events = raw_data.get("events", [])
    for event in events:
        if event.get("is_current"):
            return event.get("id")
    for event in events:
        if event.get("is_next"):
            return max(1, event.get("id") - 1)
    return 1


# --- SCORING FUNCTIONS ---
def calculate_attacking_score(df):
    """
        Computes an objective Goal Threat Score (0 to 100).
        - 70% based on non-penalty expected goals
        - 30% based on Opta Threat index
    """
    NPXG_BENCHMARK = 0.60
    THREAT_BENCHMARK = 60.0

    # Calculate individual components
    npxg_component = (df["xG_per90"] / NPXG_BENCHMARK) * 70.0
    threat_component = (df["threat_per90"] / THREAT_BENCHMARK) * 30.0

    # Sum and clip between 0 and 100
    goal_score = (npxg_component + threat_component).clip(lower=0.0, upper=100.0)

    return goal_score


def calculate_creation_score(df):
    """
        Computes an objective Creation Score (0 to 100).
        - 70% based on expected assists
        - 30% based on Opta Creativity index
    """
    XA_BENCHMARK = 0.40
    CREATIVITY_BENCHMARK = 50.0

    # Calculate individual components
    xa_component = (df["xA_per90"] / XA_BENCHMARK) * 70.0
    creativity_component = (df["creativity_per90"] / CREATIVITY_BENCHMARK) * 30.0

    # Sum and clip between 0 and 100
    creation_score = (xa_component + creativity_component).clip(lower=0.0, upper=100.0)

    return creation_score


def calculate_baseline_score(df):
    """
        Computes a position-weighted Baseline Talent Score (0 to 100) using vectorization.
        - FWD: 80% Attacking / 20% Creation
        - MID: 55% Attacking / 45% Creation
        - DEF: 65% Primary Trait / 35% Secondary Trait
        - GKP: 0.0
    """
    # Calculate score for FWD
    fwd_score = (df["attacking_score"] * 0.80) + (df["creation_score"] * 0.20)

    # Calculate score for MID
    mid_score = (df["attacking_score"] * 0.60) + (df["creation_score"] * 0.40)

    # Calculate score for DEF
    def_primary = np.maximum(df["attacking_score"], df["creation_score"])
    def_sec = np.minimum(df["attacking_score"], df["creation_score"])
    def_score = (def_primary * 0.65) + (def_sec * 0.35)

    # Define conditions and choices, to apply the correct score based on the player's position
    conditions = [
        df["position"] == "FWD",
        df["position"] == "MID",
        df["position"] == "DEF",
    ]
    choices = [fwd_score, mid_score, def_score]

    # Assign score based on position
    baseline = np.select(conditions, choices, default=0.0)

    return pd.Series(baseline, index=df.index).round(1)


def calculate_buy_score(df):
    """
        Applies the luck/regression multiplier to the baseline score.
        - Positive GI_delta: Boosts the player's rating (underperformer / buy target)
        - Negative GI_delta: Discounts the player's rating (overperformer / sell candidate)
    """

    # Calculate regression multiplier by adding 1 to GI_delta multiplied by regression weight.
    # This way if a player is underperforming, he will have his GI_delta boosted
    regression_multiplier = (1.0 + (df["GI_delta"] * REGRESSION_WEIGHT)).clip(lower=0.20)

    # Calculate final buy score, by fusing the regression multiplier (how much he is underperforming
    # with the "actual talent" (the baseline score we calculated earlier
    buy_score = (df["baseline_score"] * regression_multiplier).round(1)

    return buy_score


def calculate_advanced_metrics(df):
    # Calculate the 90s played by each player, so we can find per90 metrics
    df["ninetys"] = (df["minutes"] / 90.0).clip(lower=0.1)

    # Calculate xG and Goals per90
    df["xG_per90"] = (df["expected_goals"] / df["ninetys"]).round(2)
    df["goals_per90"] = (df["goals_scored"] / df["ninetys"]).round(2)

    # Calculate xA and Assists per90
    df["xA_per90"] = (df["expected_assists"] / df["ninetys"]).round(2)
    df["assists_per90"] = (df["assists"] / df["ninetys"]).round(2)

    # Calculate Opta Metrics: Creativity and Threat per90
    df["threat_per90"] = (df["threat"] / df["ninetys"]).round(1)
    df["creativity_per90"] = (df["creativity"] / df["ninetys"]).round(1)

    # Calculate Goal Involvements(GI) and xGI per90
    df["GI_per90"] = (df["goals_per90"] + df["assists_per90"]).round(2)
    df["xGI_per90"] = (df["xG_per90"] + df["xA_per90"]).round(2)

    # Calculate attacking, creation and baseline (actual talent) scores
    df["attacking_score"] = calculate_attacking_score(df)
    df["creation_score"] = calculate_creation_score(df)
    df["baseline_score"] = calculate_baseline_score(df)

    # Calculate Deltas for goals and assists (Expected - Actual) + Total Delta
    df["goal_delta"] = (df["xG_per90"] - df["goals_per90"]).round(2)
    df["assists_delta"] = (df["xA_per90"] - df["assists_per90"]).round(2)
    df["GI_delta"] = (df["xGI_per90"] - df["GI_per90"]).round(2)

    # Calculate the final buy score
    df["buy_score"] = calculate_buy_score(df)

    return df


# --- CACHED PIPELINE (Auto-refreshes every 1 hour) ---
@st.cache_data(ttl=3600)
def load_and_process_data():
    raw_data = get_data()
    df = mapping(raw_data)

    numeric_cols = [
        "minutes", "goals_scored", "assists", "expected_goals",
        "expected_assists", "creativity", "threat", "penalties_missed", "penalties_saved"
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    cur_gw = get_current_gameweek(raw_data)
    min_minutes = max(90, (cur_gw - math.ceil(cur_gw / 6)) * 90)

    df_qualified = df[df["minutes"] >= min_minutes].copy()
    df_processed = calculate_advanced_metrics(df_qualified)
    return df_processed, cur_gw, min_minutes


# --- STREAMLIT UI ---
st.title("⚽ FPL Data-Driven Scouting Engine")
st.caption("Identify underperforming buy targets and unsustainable overperformers based on underlying xGI and Opta threat.")

with st.spinner("Fetching latest Premier League data..."):
    df, cur_gw, min_mins = load_and_process_data()

# Stat Metrics Banner
col1, col2, col3 = st.columns(3)
col1.metric("Active Gameweek", f"GW {cur_gw}")
col2.metric("Minutes Required (Sample Size)", f"{min_mins} mins")
col3.metric("Eligible Starting Assets", f"{len(df)} players")

st.divider()


# --- HOW IT WORKS / METRICS GUIDE ---
with st.expander("ℹ️ How It Works & How to Read These Metrics", expanded=False):
    st.markdown("""
    ### 🧠 Methodology & Metric Definitions

    This scouting tool ignores raw historical points and instead analyzes **underlying chance quality** to find players who are statistically due for positive returns (buy targets) or due for a dry spell (traps).

    ---

    #### 1. What is the Baseline Score (0 – 100)?
    A player's true offensive talent per 90 minutes, normalized against elite Premier League benchmarks:
    * **Attacking Threat:** 70% Expected Goals ($xG$) + 30% Opta Threat (penalty-box presence).
    * **Creative Output:** 70% Expected Assists ($xA$) + 30% Opta Creativity (delivery volume).
    * **Positional Fusion:**
      * **FWD:** Weighted 80% Attacking / 20% Creative.
      * **MID:** Balanced 55% Attacking / 45% Creative.
      * **DEF:** 65% Primary Trait / 35% Secondary Trait (rewards both aerial center-backs and crossing full-backs).

    ---

    #### 2. What is GI and GI Delta?
    * **`GI` (Goal Involvements):** Actual real-world returns ($\text{Goals} + \text{Assists}$).
    * **`xGI` (Expected Goal Involvements):** The returns a player *should* have had based on chance quality ($\text{xG} + \text{xA}$).
    * **`GI_delta` ($xGI - GI$):** 
      * **Positive ($> 0$):** Underperforming. The player is getting into great positions or setting up teammates, but experiencing bad finishing luck. **Prime Buy Candidate.**
      * **Negative ($< 0$):** Overperforming. The player is scoring low-percentage screamers or fluke deflections at an unsustainable rate. **Regression / Sell Risk.**

    ---

    #### ⚠️ Important Note on Defenders (DEF)
    * This engine scouts defenders **purely for their attacking ceiling** (set-piece headers, open-play crosses, key passes).
    * **It does NOT factor in Clean Sheet likelihood or team defensive strength.** Always cross-reference a defender's attacking score with their team's fixture difficulty and clean sheet record before transferring.
    """)


# Position Selector
selected_pos = st.selectbox("Select Position to Scout:", options=["FWD", "MID", "DEF"], index=0)
cfg = SCOUTING_THRESHOLDS[selected_pos]
subset = df[df["position"] == selected_pos].copy()

display_cols = [
    "web_name", "team_name", "price", "minutes",
    "baseline_score", "buy_score", "GI_delta",
    "xGI_per90", "GI_per90", "goals_scored", "assists"
]

# Tabs for easy phone/desktop navigation
tab_buy, tab_talismans, tab_over = st.tabs([
    "🎯 Top Buy Targets (Underperformers)",
    "⭐ Core Talismans (League Best)",
    "⚠️ Overperformers (Sell / Traps)"
])

with tab_buy:
    st.subheader(f"Top {selected_pos} Buy Targets")
    st.write("Players with high underlying threat/creation whose actual goals and assists are lagging behind.")
    buy_targets = subset[
        (
            (subset["baseline_score"] >= cfg["buy_min_baseline"]) |
            (subset["xGI_per90"] >= cfg["buy_min_xgi"])
        ) &
        (subset["GI_delta"] >= cfg["buy_min_delta"])
    ].sort_values(by="buy_score", ascending=False).head(15)

    if not buy_targets.empty:
        st.dataframe(buy_targets[display_cols], use_container_width=True)
    else:
        st.info("No players currently meet the underperforming criteria.")

with tab_talismans:
    st.subheader(f"Core {selected_pos} Talismans")
    st.write("Highest baseline volume threats regardless of luck.")
    talismans = subset.sort_values(by="baseline_score", ascending=False).head(15)
    st.dataframe(talismans[display_cols], use_container_width=True)

with tab_over:
    st.subheader(f"{selected_pos} Overperformers / Regression Risks")
    st.write("Players scoring points despite low underlying volume (Low Baseline OR Low xGI).")
    overperformers = subset[
        (
            (subset["baseline_score"] < cfg["over_max_baseline"]) |
            (subset["xGI_per90"] < cfg["over_max_xgi"])
        ) &
        (subset["GI_per90"] >= cfg["over_min_gi"]) &
        (subset["GI_delta"] <= cfg["over_delta"])
    ].sort_values(by=["GI_delta", "baseline_score"], ascending=[True, True]).head(15)

    if not overperformers.empty:
        st.dataframe(overperformers[display_cols], use_container_width=True)
    else:
        st.success("No significant overperformers found.")