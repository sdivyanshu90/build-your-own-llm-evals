# Statistical inference for evaluations

## Estimands before procedures

An estimand is the quantity the evaluation intends to learn: mean accuracy on a
defined population, median latency under a specified load, preference
probability for a rubric, or another operationally meaningful target. Select it
before selecting a confidence interval or test.

The package separates descriptive summaries from inferential procedures in
`packages/statistics/src/eval_platform_statistics`.
Every result records the method, confidence level or alternative, total and
effective sample sizes, seed where applicable, and typed warnings.

## Paired data

When baseline and candidate evaluate the same record, define
\(D_i = Y_{candidate,i} - Y_{baseline,i}\). The mean effect is

\[
\bar D = \frac{1}{n}\sum_{i=1}^{n} D_i,
\qquad
SE(\bar D) = \frac{s_D}{\sqrt n}.
\]

This uses within-record correlation. Independently resampling the baseline and
candidate destroys that correlation and usually gives the wrong uncertainty.
`align_pairs` in `packages/statistics/src/eval_platform_statistics/models.py`
matches stable record identities, rejects non-finite values, and reports every
excluded record. Dataset-version mismatches require explicit
intersection-only analysis.

Example: baseline scores `[0, 1, 0, 1]` and candidate scores `[1, 1, 1, 1]`
produce paired differences `[1, 0, 1, 0]`, mean improvement 0.5, and
probability of superiority `(2 + 0.5*2)/4 = 0.75`.

## Confidence intervals

### Student t interval

For a mean, the t interval is

\[
\bar X \pm t_{1-\alpha/2,n-1}\frac{s}{\sqrt n}.
\]

It assumes independent observations across sampling units and a sampling
distribution that is approximately normal. With very small, heavy-tailed
samples its coverage can be poor.

### Wilson and exact binomial intervals

The Wald interval \(\hat p \pm z\sqrt{\hat p(1-\hat p)/n}\) can leave `[0,1]`
and collapses at 0 or 1. The default proportion interval is Wilson:

\[
\frac{\hat p + z^2/(2n) \pm
z\sqrt{\hat p(1-\hat p)/n + z^2/(4n^2)}}{1+z^2/n}.
\]

For 5 successes in 10 trials, the 95% Wilson interval is approximately
`[0.2366, 0.7634]`. Exact Clopper-Pearson limits are available when conservative
coverage is preferred.

### Bootstrap

The percentile bootstrap resamples observed units and takes empirical
quantiles. The basic interval reflects quantiles around the observed estimate.
BCa additionally corrects median bias and jackknife-estimated acceleration.
These methods do not repair an unrepresentative dataset.

Paired bootstrap resamples shared record indices. Stratified bootstrap resamples
within each stratum while preserving stratum counts. Cluster bootstrap samples
whole groups, such as repeated conversations from the same user. Fewer than 20
clusters triggers a warning because cluster-level uncertainty is unstable.

Quantile bootstrap supports medians and latency percentiles. Tail quantiles need
far more observations than means.

## Hypothesis tests

- Paired t tests a zero mean difference.
- Wilcoxon signed-rank tests a symmetric difference distribution around zero;
  it is not merely a generic test of medians.
- The exact sign test uses only positive and negative differences.
- Exact McNemar uses only discordant paired binary outcomes.
- Paired permutation swaps the signs of record differences under exchangeability.
- The centered paired bootstrap test approximates a zero-mean null distribution.
- The pairwise binomial test excludes ties and states that denominator explicitly.

Tests return `p = 1` with an all-ties warning when no decisive information is
available. Zero differences and missing pairs are never silently discarded.

A p-value is the probability, under the test model, of data at least as
incompatible with the null as the observed data. It is not the probability the
null is true, the probability the candidate is better, or an effect size.

## Effect sizes and practical importance

Continuous paired output includes mean and median difference, relative
improvement, paired standardized mean difference \(d_z=\bar D/s_D\), and
probability of superiority. Binary output includes absolute risk difference,
relative risk, and the discordant-pair matched odds ratio. Relative improvement
is undefined when the baseline mean is zero.

A minimum practically important difference (MPID) classifies results as:

- statistically significant and practically meaningful;
- statistically significant but practically small;
- not statistically conclusive;
- evidence of a meaningful regression;
- compatible with the configured tolerance.

Compatibility with a tolerance interval is descriptive unless an equivalence
test was planned. Paired TOST performs two one-sided t tests against lower and
upper equivalence margins. Failing to reject a difference is not evidence of
equivalence.

## Multiple comparisons

Testing many metrics inflates the chance of at least one false positive. If
each of 20 independent null tests uses 5%, family-wise error is
\(1-0.95^{20}\), about 64%.

Bonferroni multiplies every p-value by the family size. Holm is uniformly at
least as powerful while controlling family-wise error. Benjamini-Hochberg
controls expected false-discovery rate under its dependence assumptions. The
comparison API stores raw values and applies Holm to the requested metric
family.

## Ranking models

Bradley-Terry models

\[
P(i \gt j)=\frac{\exp(\beta_i)}{\exp(\beta_i)+\exp(\beta_j)}
\]

with centered log abilities for identifiability. Explicit ties are excluded
with a warning. Davidson adds global tie strength
\(\nu\sqrt{\exp(\beta_i)\exp(\beta_j)}\) to the denominator.

Elo is provided only as a descriptive view. Sequential Elo depends on event
order, initial rating, and K factor. It is not a universal posterior ranking.

## Power and sample-size planning

Normal approximations estimate paired continuous and pairwise-preference sample
sizes. Inputs are alpha, target power, expected effect, and anticipated tie rate.
The continuous standardized effect uses the standard deviation of paired
differences, not a pooled independent-sample deviation. Inflate plans for
attrition, failed records, clustering, non-normal tails, and planned slices.

## Missingness, slices, and interpretation

Available-pair analysis assumes excluded observations do not create material
bias after conditioning on the study design. “Failures as zero” answers a
different estimand and must be configured explicitly. The report includes
failed and missing counts under either policy.

Slice estimates carry their own sample sizes and uncertainty. Exploratory
search across many slices creates multiple-comparison and selection bias.
Confirm apparent regressions on a prespecified or fresh dataset.

## Validation

Tests compare implementations to SciPy, hand calculations, deterministic
simulation, and properties such as ordered bounds and fixed-seed
reproducibility. Numerical tolerances reflect floating-point computation, not
permission for qualitative disagreement.
