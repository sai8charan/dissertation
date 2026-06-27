"""
evaluation/check_targets.py
---------------------------
Compare saved experiment metrics against EXPECTED_TARGETS from config.py.

Usage:
    python evaluation/check_targets.py
    python evaluation/check_targets.py --results results/full_comparison_table.csv
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

sys.path.append(str(Path(__file__).parent.parent))
from config import EXPECTED_TARGETS, RESULTS_DIR

# Names used in experiments/run_pipeline.py (override via CLI if needed)
PIPELINE_NAMES = [
    "Pipeline (hybrid+verify+rerank)",
    "pipeline",
    "Pipeline",
]
BASELINE_BART_NAMES = [
    "BART-fine-tuned",
    "BART-fine-tuned ",
    "bart_finetuned",
]


def _load_metrics(results_path: Optional[Path] = None) -> pd.DataFrame:
    if results_path and results_path.exists():
        df = pd.read_csv(results_path)
        if "system" in df.columns:
            return df.set_index("system")
        return df

    rows: List[Dict] = []
    for f in sorted(RESULTS_DIR.glob("eval_*.json")):
        with open(f, encoding="utf-8") as fp:
            rows.append(json.load(fp))
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).set_index("system")


def _find_row(df: pd.DataFrame, candidates: List[str]) -> Optional[pd.Series]:
    for name in candidates:
        if name in df.index:
            return df.loc[name]
    for name in candidates:
        for idx in df.index:
            if name.lower() in str(idx).lower():
                return df.loc[idx]
    return None


def _status(passed: Optional[bool]) -> str:
    if passed is None:
        return "PENDING"
    return "PASS" if passed else "FAIL"


def check_targets(df: pd.DataFrame) -> Tuple[List[Dict], bool]:
    """
    Returns list of check dicts and whether all available checks passed.
    """
    targets = EXPECTED_TARGETS
    checks: List[Dict] = []
    all_passed = True

    pipe = _find_row(df, PIPELINE_NAMES)
    bart = _find_row(df, BASELINE_BART_NAMES)

    def add(name: str, target: str, value, passed: Optional[bool]):
        nonlocal all_passed
        if passed is False:
            all_passed = False
        checks.append({
            "objective": name,
            "target": target,
            "value": value,
            "status": _status(passed),
        })

    if pipe is not None:
        rouge2 = pipe.get("rouge2")
        if rouge2 is not None and rouge2 == rouge2:
            add(
                "Pipeline ROUGE-2",
                f">= {targets['pipeline_rouge2_min']}",
                rouge2,
                float(rouge2) >= targets["pipeline_rouge2_min"],
            )
        else:
            add("Pipeline ROUGE-2", f">= {targets['pipeline_rouge2_min']}", "TBD", None)

        nli = pipe.get("nli_fcs")
        if nli is not None and nli == nli:
            add(
                "Pipeline NLI-FCS",
                f">= {targets['pipeline_nli_fcs_min']}",
                round(float(nli), 4),
                float(nli) >= targets["pipeline_nli_fcs_min"],
            )
        else:
            add(
                "Pipeline NLI-FCS",
                f">= {targets['pipeline_nli_fcs_min']}",
                "TBD",
                None,
            )

        fb = pipe.get("fallback_rate")
        if fb is not None and fb == fb:
            add(
                "Extractive fallback rate",
                f"< {targets['fallback_rate_max_pct']}%",
                f"{fb}%",
                float(fb) < targets["fallback_rate_max_pct"],
            )
        else:
            add(
                "Extractive fallback rate",
                f"< {targets['fallback_rate_max_pct']}%",
                "TBD",
                None,
            )
    else:
        add("Pipeline ROUGE-2", f">= {targets['pipeline_rouge2_min']}", "no results", None)
        add("Pipeline NLI-FCS", f">= {targets['pipeline_nli_fcs_min']}", "no results", None)
        add(
            "Extractive fallback rate",
            f"< {targets['fallback_rate_max_pct']}%",
            "no results",
            None,
        )

    if pipe is not None and bart is not None:
        p_fcs = pipe.get("nli_fcs")
        b_fcs = bart.get("nli_fcs")
        if (
            p_fcs is not None and p_fcs == p_fcs
            and b_fcs is not None and b_fcs == b_fcs
        ):
            delta_ok = float(p_fcs) >= targets["pipeline_nli_fcs_min"] and float(
                b_fcs
            ) <= targets["baseline_nli_fcs_max"]
            add(
                "Pipeline vs BART NLI-FCS gap",
                f"pipeline >= {targets['pipeline_nli_fcs_min']}, "
                f"BART <= {targets['baseline_nli_fcs_max']}",
                f"pipeline={round(float(p_fcs), 4)}, BART={round(float(b_fcs), 4)}",
                delta_ok,
            )
        else:
            add(
                "Pipeline vs BART NLI-FCS gap",
                f"pipeline >= {targets['pipeline_nli_fcs_min']}, "
                f"BART <= {targets['baseline_nli_fcs_max']}",
                "TBD",
                None,
            )
    else:
        add(
            "Pipeline vs BART NLI-FCS gap",
            f"pipeline >= {targets['pipeline_nli_fcs_min']}, "
            f"BART <= {targets['baseline_nli_fcs_max']}",
            "missing pipeline or BART-fine-tuned row",
            None,
        )

    return checks, all_passed


def print_report(checks: List[Dict]) -> None:
    print("\n-- Dissertation Objective Targets " + "-" * 40)
    print(f"{'Objective':<32} {'Target':<28} {'Value':<22} {'Status'}")
    print("-" * 90)
    for c in checks:
        print(
            f"{c['objective']:<32} {str(c['target']):<28} "
            f"{str(c['value']):<22} {c['status']}"
        )
    print("-" * 90)
    pending = sum(1 for c in checks if c["status"] == "PENDING")
    failed = sum(1 for c in checks if c["status"] == "FAIL")
    passed = sum(1 for c in checks if c["status"] == "PASS")
    print(f"PASS: {passed}  FAIL: {failed}  PENDING: {pending}\n")


def save_report(checks: List[Dict], all_passed: bool) -> Path:
    out = RESULTS_DIR / "target_check_report.json"
    payload = {
        "checks": checks,
        "all_passed": all_passed,
        "note": "Human evaluation targets checked separately via human_eval.py",
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return out


def main(results_path: Optional[Path] = None) -> int:
    df = _load_metrics(results_path)
    if df.empty:
        print("No evaluation results found. Run experiments/run_pipeline.py first.")
        checks, _ = check_targets(df)
        print_report(checks)
        save_report(checks, False)
        return 1

    checks, all_passed = check_targets(df)
    print_report(checks)
    out = save_report(checks, all_passed)
    print(f"Report saved to {out}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--results",
        type=Path,
        default=RESULTS_DIR / "full_comparison_table.csv",
        help="CSV from run_pipeline.py (default: results/full_comparison_table.csv)",
    )
    args = parser.parse_args()
    path = args.results if args.results.exists() else None
    sys.exit(main(path))
