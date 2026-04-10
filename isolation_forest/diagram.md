# autoDQM Isolation Forest — Architecture Diagram

```mermaid
flowchart TD

    %% ── Configuration ────────────────────────────────────────────────────────
    subgraph CFG["⚙️  env.sh  —  Central Path Configuration"]
        ENV["INSTALLATION_PATH · DATA_PATH
        GOOD_RUN_LIST · ALL_RUN_LIST
        MODELS_DIR · LOGS_DIR · REPORTS_DIR · PLOTS_DIR"]
    end

    %% ── Input ────────────────────────────────────────────────────────────────
    subgraph INPUT["📂  Input Data  (EOS /eos/user/t/tafoyava/autoDQM/data/)"]
        GOOD_LIST["good_run_list_EOS.txt
        glob patterns → training files"]
        ALL_LIST["all_run_list_EOS.txt
        glob patterns → validation files"]
        DIG["Digitizer_run*_subrun*.csv
        per-channel pulse data (long format)"]
        TRIG["TriggerBoard_run*.csv
        trigger rates per bit  ×13 + tot"]
        LVDS["TriggerBoardSlab_*_LVDSCounts.csv
        LVDS pin counts  ×50 + total"]
    end

    %% ── Feature Extraction ───────────────────────────────────────────────────
    subgraph FEAT["🔧  features.py  —  Feature Extraction"]
        direction TB
        FE["extract_features()
        groupby channel → mean · std · median"]
        F35["35 Digitizer features
        sideband · nPulses · pulseHeight/Area/Duration
        TDC · occupancy · frac_dead"]
        F15["＋15 TriggerBoard features
        triggerRate_bit1–13 · tot · counts
        (disabled with --no-trigger)"]
        F51["＋51 LVDS features
        LVDSpin0–49 · LVDStotal
        (disabled with --no-trigger-LVDS)"]
        FV["Feature vector per channel per file
        35 / 50 / 86 / 101 features
        depending on variant"]
        FE --> F35 --> FV
        FE --> F15 --> FV
        FE --> F51 --> FV
    end

    %% ── Training ─────────────────────────────────────────────────────────────
    subgraph TRAIN["🏋️  train.py  —  Model Training"]
        direction TB
        REF["ReferenceModel  (reference.py)
        Welford online statistics
        mean · std per  channel × feature
        O(channels × features) memory"]
        REFNPZ[("reference.npz")]
        SEEN[("seen_files.json")]
        IFT["IsolationForest  (sklearn)
        trained on z-scored vectors
        n_estimators=200 · contamination=0.05
        capped at 50 k vectors"]
        DETPKL[("detector.pkl")]
        REF --> REFNPZ
        REF --> SEEN
        REF --> IFT --> DETPKL
    end

    %% ── Detection ────────────────────────────────────────────────────────────
    subgraph DETECT["🔍  detector.py  —  Two-Layer Anomaly Detection"]
        direction LR
        L1["Layer 1 — Statistical
        z = |x − μ| / σ
        flag if  max(z) > 5σ"]
        L2["Layer 2 — Isolation Forest
        score new z-vectors
        flag if predict() = −1"]
        COMB["Per-channel result
        anomalous · method · max_z
        if_score · triggered_features
        ── methods ──
        statistical | isolation_forest
        statistical+IF | new_channel
        missing_channel"]
        L1 --> COMB
        L2 --> COMB
    end

    %% ── Application ──────────────────────────────────────────────────────────
    subgraph APPLY["📡  monitor.py  —  Application / Watch Mode"]
        direction TB
        WATCH["Watch directory  (poll 5 s)
        or batch via run list"]
        THRESH{"frac_anomalous
        channels ≥ 20%?"}
        OK["🟢 OK  — all nominal"]
        WARN["🟡 WARN  — below threshold"]
        ALT["🔴 ALERT  — above threshold
        → auto-plot if enabled"]
        WATCH --> THRESH
        THRESH -->|"= 0%"| OK
        THRESH -->|"> 0, < 20%"| WARN
        THRESH -->|"≥ 20%"| ALT
    end

    %% ── Log ──────────────────────────────────────────────────────────────────
    subgraph LOG["📝  Anomaly Log"]
        CSV[("anomalies.csv  (append-only)
        timestamp · filename · channel
        anomalous · method · max_z · if_score
        triggered_features")]
    end

    %% ── Reporting ────────────────────────────────────────────────────────────
    subgraph REPORT["📊  report.py  —  Run Quality Classification"]
        direction TB
        CL["classify_runs()
        per-subrun: good / bad
        per-run pattern analysis"]
        RG[("good_runs.txt")]
        RP[("partial_good_runs.txt")]
        RF[("persistent_fault_runs.txt")]
        RS[("run_summary.csv")]
        CL --> RG & RP & RF & RS
    end

    %% ── Run classifications (legend) ─────────────────────────────────────────
    subgraph RUNCLASS["Run Classification Logic"]
        direction TB
        CL_G["good  — all subruns nominal"]
        CL_P["partial  — clean good→bad transition"]
        CL_B["bad  — all subruns anomalous"]
        CL_M["mixed  — interleaved good/bad"]
        CL_F["persistent_fault  — one channel
        anomalous in every subrun"]
    end

    %% ── Plots ────────────────────────────────────────────────────────────────
    subgraph PLOTS["📈  plot.py  —  Visualization"]
        direction TB
        PR["Reference plots
        means heatmap · stds heatmap
        channel coverage bar chart"]
        PF["Per-file plots  (on ALERT)
        z-score heatmap · max_z per channel
        IF scores · detector geometry"]
        PL["Log summary plots
        anomaly rate over time
        channel frequency · feature frequency
        per-run good-fraction"]
    end

    %% ── Condor ───────────────────────────────────────────────────────────────
    subgraph CONDOR["☁️  HTCondor  —  submit.sub + run_pipeline.sh"]
        direction TB
        V1["trigger_lvds
        101 features  (full)"]
        V2["trigger_nolvds
        50 features"]
        V3["notrigger_lvds
        86 features"]
        V4["notrigger_nolvds
        35 features  (Digitizer only)"]
        PIPE["pipeline.py
        train → apply → report → plots
        4 CPUs · 4 GB · longlunch (2 h)"]
        V1 & V2 & V3 & V4 --> PIPE
    end

    %% ── Edges ────────────────────────────────────────────────────────────────
    CFG -->|"absolute paths sourced by"| TRAIN
    CFG -->|"absolute paths sourced by"| APPLY
    CFG -->|"absolute paths sourced by"| CONDOR

    GOOD_LIST -->|"resolve_run_list()"| FEAT
    ALL_LIST  -->|"resolve_run_list()"| FEAT
    DIG  --> FE
    TRIG --> FE
    LVDS --> FE

    FV -->|"training files"| TRAIN
    FV -->|"z-score vectors"| IFT

    REFNPZ & DETPKL -->|"loaded by"| DETECT

    WATCH -->|"new file"| FEAT
    FV -->|"new file vectors"| DETECT
    COMB --> THRESH
    COMB --> CSV

    CSV --> CL
    CL --> RUNCLASS

    REFNPZ --> PR
    CSV    --> PL
    ALT    -->|"per-file"| PF

    PIPE -->|"orchestrates"| TRAIN
    PIPE -->|"orchestrates"| APPLY
    PIPE -->|"orchestrates"| REPORT
    PIPE -->|"orchestrates"| PLOTS
```

---

## Feature Variants (4 Condor Jobs)

| Variant | Flags | Features |
|---|---|---|
| `trigger_lvds` | *(none)* | 35 + 15 + 51 = **101** |
| `trigger_nolvds` | `--no-trigger-LVDS` | 35 + 15 = **50** |
| `notrigger_lvds` | `--no-trigger` | 35 + 51 = **86** |
| `notrigger_nolvds` | `--no-trigger --no-trigger-LVDS` | **35** |

## Key Parameters

| Parameter | Default | Effect |
|---|---|---|
| `z_threshold` | 5.0 σ | Statistical layer sensitivity |
| `if_contamination` | 0.05 | Expected anomaly fraction in training data |
| `file_alert_threshold` | 0.20 | Fraction of bad channels to trigger `[ALERT]` |
| `n_estimators` | 200 | Isolation Forest size |
| `max_IF_samples` | 50 000 | Cap on training vectors (scalability) |
| `poll_interval` | 5 s | Watch-mode scan frequency |

## Output Artifacts

```
isolation_forest/
├── models/
│   ├── reference.npz       ← Welford statistics (mean, std per channel×feature)
│   ├── detector.pkl        ← Trained IsolationForest + thresholds
│   └── seen_files.json     ← Filenames already incorporated in reference
├── logs/
│   └── anomalies.csv       ← Append-only anomaly log (one row per channel per file)
├── reports/
│   ├── good_runs.txt
│   ├── partial_good_runs.txt
│   ├── persistent_fault_runs.txt
│   └── run_summary.csv
└── plots/
    ├── reference_means.png
    ├── reference_stds.png
    ├── reference_coverage.png
    ├── log_anomaly_rate.png
    ├── log_channel_frequency.png
    ├── log_feature_frequency.png
    └── <variant>/          ← per-alerted-file subdirectory
        ├── *_zscore_heatmap.png
        ├── *_max_zscore.png
        ├── *_if_scores.png
        └── *_geometry.png
```
