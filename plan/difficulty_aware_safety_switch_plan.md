# Difficulty-Aware Safety Switch: Detailed Action Plan

## 1. Purpose and Motivation

### 1.1 Problem
Current summarization pipelines often use a fixed factual-confidence threshold to decide whether to keep an abstractive summary or fallback to a safer extractive summary. A fixed threshold assumes all articles have equal difficulty, which is not true in real news data.

### 1.2 Proposed Novelty
Introduce a Difficulty-Aware Safety Switch that adapts the factual-confidence threshold per article. Harder articles require stricter factual confidence; easier articles allow normal abstractive output at a lower threshold.

### 1.3 Why this is a practical novelty
- Simple to explain and justify in viva.
- Easy to integrate into the existing 4-stage pipeline.
- Produces measurable and interpretable improvements in factual safety.
- Does not require retraining large language models.

## 2. High-Level Novelty Statement (for report and presentation)

This work proposes a lightweight, inference-time reliability mechanism that replaces a fixed fallback threshold with a dynamic threshold driven by article difficulty. The mechanism improves factual safety by requiring stronger confidence on difficult inputs while preserving fluency on easier inputs.

## 3. Scope and Boundaries

### 3.1 In scope
- Difficulty scoring from article-level signals.
- Dynamic threshold computation.
- Safety-switch decision update in reranker stage.
- Evaluation and ablation against fixed-threshold baseline.
- Dissertation documentation and presentation outputs.

### 3.2 Out of scope
- New foundation model training.
- Reinforcement learning or preference model training.
- Major architecture redesign outside current pipeline.

## 4. Research Questions

1. Does a dynamic threshold reduce factual risk compared to a fixed threshold?
2. What is the trade-off between factual safety and fallback rate?
3. Which difficulty signals contribute most to stable behavior?
4. Can a simple linear mapping provide sufficient gains for practical deployment?

## 5. Technical Design Overview

## 5.1 Inputs used by the switch
- Article text and sentence structure.
- Retrieval scores from evidence retriever.
- Candidate-level factual consistency score (FCS) from verifier.

## 5.2 Difficulty score design
Compute normalized difficulty score D in [0, 1] using weighted combination of:
- Length complexity signal.
- Entity density signal.
- Retrieval uncertainty signal.

Initial weighted form:
D = 0.4 x LengthNorm + 0.3 x EntityNorm + 0.3 x UncertaintyNorm

### 5.3 Dynamic threshold design
Use baseline threshold and difficulty-conditioned increase:
Threshold_dynamic = BaseThreshold + alpha x D

Initial defaults:
- BaseThreshold = 0.40
- alpha = 0.20

Expected threshold range:
- Easy article: near 0.40
- Hard article: up to around 0.60

### 5.4 Safety-switch decision
- If best candidate FCS >= Threshold_dynamic: accept abstractive summary.
- Else: trigger extractive fallback summary.

## 6. Implementation Action Plan (Phase-by-Phase)

## Phase 1: Baseline Lock and Reproducibility

### Objectives
- Freeze current fixed-threshold results as baseline.
- Ensure result reproducibility before introducing novelty.

### Actions
- Capture baseline metrics from current pipeline.
- Store baseline configuration snapshot.
- Record sample size, model versions, seed, and hardware details.

### Deliverables
- Baseline metrics table.
- Baseline run log and experiment note.

## Phase 2: Difficulty Signal Specification

### Objectives
- Finalize mathematical definitions of three difficulty signals.
- Define normalization strategy for each signal.

### Actions
- Define length normalization using robust min-max or percentile clipping.
- Define entity density as entities per sentence or per token.
- Define uncertainty using retrieval score margin or score entropy proxy.
- Validate ranges on a representative validation subset.

### Deliverables
- Signal definition sheet.
- Distribution plots/statistics for each signal.

## Phase 3: Difficulty Score Calibration

### Objectives
- Validate whether D meaningfully separates easy vs hard articles.

### Actions
- Compute D on validation set.
- Group samples into low/medium/high difficulty bins.
- Compare factuality and fallback behavior across bins.

### Deliverables
- Difficulty stratification table.
- Evidence that higher D corresponds to higher risk.

## Phase 4: Dynamic Threshold Integration

### Objectives
- Integrate dynamic threshold logic into reranking decision.
- Keep architecture unchanged except for decision rule.

### Actions
- Add per-sample threshold computation stage.
- Log dynamic threshold values per sample.
- Preserve backward compatibility with fixed-threshold mode.

### Deliverables
- Updated pipeline run capability for both fixed and dynamic modes.
- Per-sample decision trace fields in evaluation artifacts.

## Phase 5: Hyperparameter Tuning and Stability

### Objectives
- Identify robust alpha and optional signal weights.

### Actions
- Run controlled sweeps for alpha (example: 0.10, 0.15, 0.20, 0.25).
- Optionally test weight variants around 0.4/0.3/0.3.
- Select setting based on factual safety gains with acceptable fallback rate.

### Deliverables
- Tuning summary table.
- Final selected configuration with rationale.

## Phase 6: Comparative Evaluation

### Objectives
- Demonstrate novelty impact against fixed-threshold baseline.

### Actions
- Run fixed-threshold and dynamic-threshold evaluations on same test subset.
- Compare core metrics: ROUGE, BERTScore, NLI-FCS, fallback rate, latency.
- Add risk-oriented comparison by difficulty bin.

### Deliverables
- Main comparison table (fixed vs dynamic).
- Difficulty-wise performance table.

## Phase 7: Ablation and Sensitivity Analysis

### Objectives
- Show that gains come from difficulty awareness, not random variation.

### Actions
- Remove one signal at a time (length-only, entity-only, uncertainty-only variants).
- Test constant D (sanity control).
- Evaluate sensitivity to alpha.

### Deliverables
- Ablation matrix.
- Sensitivity summary and interpretation.

## Phase 8: Error Analysis and Case Studies

### Objectives
- Provide qualitative evidence for viva and dissertation defense.

### Actions
- Curate examples where dynamic switch corrected risky abstractive output.
- Curate examples where dynamic switch may over-trigger fallback.
- Analyze failure patterns and edge cases.

### Deliverables
- 5 to 10 case studies with before/after decisions.
- Error taxonomy and mitigation notes.

## Phase 9: Dissertation Writing Integration

### Objectives
- Integrate novelty with clear academic framing.

### Actions
- Add method subsection on Difficulty-Aware Safety Switch.
- Add equation descriptions and calibration protocol.
- Add experiment and ablation results.
- Add limitations and future work section.

### Deliverables
- Updated methodology chapter text.
- Updated results and discussion chapter text.

## Phase 10: Viva and Presentation Readiness

### Objectives
- Prepare concise and defensible narrative.

### Actions
- Build one-slide novelty explanation.
- Build one-slide equation + decision flow.
- Build one-slide key results (fixed vs dynamic).
- Prepare short answers for expected examiner questions.

### Deliverables
- Final presentation slides for novelty section.
- Viva-ready speaking notes.

## 7. Evaluation Framework

## 7.1 Primary metrics
- NLI-FCS (or calibrated factual confidence metric).
- Hallucination proxy rate.
- Fallback rate.

## 7.2 Secondary metrics
- ROUGE-1/2/L.
- BERTScore F1.
- Mean latency.

## 7.3 Risk-utility reporting
- Factual safety gain vs fallback increase.
- Performance by difficulty bin (easy, medium, hard).

## 8. Success Criteria

The novelty is considered successful if:
- Dynamic mode improves factual safety metrics over fixed baseline.
- Increase in fallback rate remains within an acceptable practical range.
- Overall summary quality remains competitive.
- Results are stable across at least two random seeds or repeated runs.

## 9. Risks and Mitigation

### Risk 1: Over-conservative behavior
Dynamic threshold may trigger fallback too often.
- Mitigation: tune alpha and cap maximum threshold.

### Risk 2: Weak difficulty signals
Signals may not correlate with actual factual risk.
- Mitigation: run correlation checks and refine normalization.

### Risk 3: Metric reliability concerns
Single factual metric may overestimate confidence.
- Mitigation: include manual spot checks and qualitative case studies.

### Risk 4: Latency overhead
Additional signal computation may increase runtime.
- Mitigation: use lightweight features and cache intermediate statistics.

## 10. Documentation and Artifact Checklist

- Novelty method note (equation and design choices).
- Config snapshot for final runs.
- Fixed vs dynamic comparison tables.
- Ablation tables.
- Case-study appendix.
- Presentation-ready figures and flow diagram.

## 11. Suggested Timeline (4 Weeks)

Week 1:
- Baseline lock, signal definition, initial D computation.

Week 2:
- Dynamic threshold integration, logging, alpha tuning.

Week 3:
- Full evaluation, ablation, difficulty-bin analysis.

Week 4:
- Error analysis, dissertation writing updates, presentation prep.

## 12. Final Claim Positioning

This dissertation contribution is a practical reliability innovation at inference time: a difficulty-aware confidence gate for summarization that adapts fallback behavior to input complexity. The method is lightweight, explainable, and validated through controlled comparative experiments.
