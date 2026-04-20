# Task Requirements Breakdown

## 1. Task objective

Build a clear, actionable user segmentation for a portfolio of five casual mobile games using 180 days of behavioral and transactional data. The output should help support personalized engagement, re-engagement, and monetization decisions.

## 2. Mandatory deliverables

- `Jupyter Notebook (.ipynb)` with all code, outputs, and inline commentary.
- Short summary document (`PDF` or `MD`), sized for roughly 1 to 3 pages, written for a non-technical stakeholder such as a Head of Product or CMO.
- `requirements.txt`.
- Final submission packaged as a single `.zip` archive.

## 3. What is core vs optional

### Core

The assignment explicitly states that **Part 2: User Segmentation** is the core of the task.

- Build a user-level feature set suitable for segmentation.
- Include and justify feature groups such as:
  - RFM features
  - engagement intensity and trajectory
  - progression velocity
  - monetization behavior
  - ad engagement trends
  - lifecycle stage
- Apply **at least two segmentation approaches** and compare them.
- Explain the final method choice and the selected number of segments.
- Profile each segment with:
  - descriptive name
  - size
  - key distinguishing metrics
  - radar chart or heatmap
  - short behavioral interpretation

### Optional

- Part 1: Exploratory Data Analysis
  - dataset profiling
  - KPI calculations and visualizations
  - at least 3 non-trivial patterns
- Part 3: Actionable recommendations
  - at least one concrete action per segment
  - simple impact vs implementation ease prioritization matrix
- Bonus items
  - segment stability analysis
  - predictive model from first 7 days to D30 segment
  - cross-game analysis
  - interactive visualization

## 4. Evaluation criteria and what they imply for solution design

### Analytical rigor (25%)

What is evaluated:
- Correct statistical methods
- Proper handling of distributions and outliers
- Sound validation such as silhouette, BIC, or stability checks

Implications:
- Use transformations and scaling deliberately, not mechanically.
- Compare segmentation methods with defensible criteria.
- Show why the chosen segmentation is stable enough and interpretable enough to use.

### Feature engineering creativity (20%)

What is evaluated:
- Thoughtful, non-obvious feature design
- Clear rationale
- Appropriate transformations

Implications:
- Go beyond raw counts and totals.
- Include behavioral trajectory, monetization mix, and lifecycle signals if supported by the data.
- Keep feature choices explainable and connected to business behavior.

### Visualization and communication (20%)

What is evaluated:
- Clear, publication-quality charts
- Effective visual encoding
- Concise explanations
- No chart junk

Implications:
- Use a small number of high-value visuals.
- Each chart should answer a specific question.
- Segment comparison visuals should be easy to scan and interpret quickly.

### Business sense (20%)

What is evaluated:
- Segments are actionable, not just mathematically separated
- Recommendations are realistic for mobile gaming

Implications:
- Prefer segments that can drive CRM, monetization, retention, or product decisions.
- Segment naming and descriptions should sound like something a product or marketing team could actually use.

### Code quality (15%)

What is evaluated:
- Clean, readable, reproducible code
- Modular structure
- Clear comments
- Functions/classes where appropriate

Implications:
- Keep notebook execution linear and reliable.
- Push repeated logic into small reusable helpers where useful.
- Avoid fragile notebook state and hidden dependencies between cells.

## 5. Definition of done

The submission is done when all of the following are true:

- The notebook runs end-to-end with `Run All` and no manual intervention.
- Random seeds are fixed for reproducibility.
- The notebook contains a complete segmentation workflow, not just exploratory analysis.
- At least two segmentation approaches are implemented and compared.
- The final segmentation choice and number of segments are justified.
- Every final segment has a descriptive profile and comparison visual.
- The summary document explains findings and recommendations for a non-technical stakeholder.
- `requirements.txt` is sufficient to reproduce the notebook environment.

## 6. Recommended scope for a strong submission

- Center the notebook on a clean end-to-end segmentation story rather than broad EDA.
- Include enough EDA to validate data quality, explain the feature design, and surface a few meaningful behavioral patterns.
- Build a user-level feature table that combines engagement, progression, monetization, ads, and lifecycle signals.
- Compare two strong segmentation baselines, then select the one that best balances validation quality, stability, and interpretability.
- Produce business-friendly segment profiles with sizes, revenue contribution, defining metrics, and concrete next actions.
- Keep the summary short and executive-ready: segmentation logic, key segment types, business implications, and prioritized actions.

## 7. What to deprioritize if time is limited

- Full optional KPI coverage if it does not materially improve the segmentation story.
- Bonus tasks such as predictive modeling, interactive dashboards, or cross-game deep dives.
- Excessive chart volume.
- Complex modeling that improves technical novelty but weakens interpretability or reproducibility.

If time becomes tight, preserve this order:

1. Reliable notebook execution and reproducibility.
2. Strong feature engineering.
3. Comparison of at least two segmentation approaches.
4. Clear segment profiling and justification.
5. Short, practical recommendations.
6. Extra EDA and bonus work.

## 8. Risks that could weaken the submission

- Treating segmentation as a pure clustering exercise without actionable interpretation.
- Using too many weak or redundant features without justification.
- Choosing the final model only on a metric and not on business usefulness or interpretability.
- Notebook cells that depend on hidden state or manual reruns.
- Unfixed seeds leading to unstable outputs.
- Spending too much time on optional sections and leaving the core segmentation underdeveloped.
- Overly long explanations or too many charts that obscure the main story.
- Recommendations that are generic and not tied to observed segment behavior.

## Implied expectations from the wording

These are not additional formal requirements, but they are strongly suggested by the brief:

- Prefer practical analysis over unnecessary complexity.
- Optimize for clarity of reasoning, not just model sophistication.
- Treat interpretability as part of model quality.
- Make outputs usable by both technical reviewers and business stakeholders.
- Ensure the final result looks polished enough for interview discussion, not just technically correct.
