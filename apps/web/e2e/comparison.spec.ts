import { expect, test } from "@playwright/test";

const projectId = "01900000-0000-7000-8000-000000000002";
const comparisonId = "01900000-0000-7000-8000-000000000003";
const runA = "01900000-0000-7000-8000-000000000004";
const runB = "01900000-0000-7000-8000-000000000005";
const dataset = "01900000-0000-7000-8000-000000000006";

test("comparison exposes interval, sample size, missingness, and limitations", async ({
  page,
}) => {
  await page.route("**/api/v1/projects/*/comparisons/*", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        id: comparisonId,
        project_id: projectId,
        baseline_run_id: runA,
        candidate_run_id: runB,
        baseline_dataset_version_id: dataset,
        candidate_dataset_version_id: dataset,
        dataset_compatible: true,
        intersection_only: false,
        configuration: {},
        metrics: [
          {
            metric_identifier: "exact_match",
            metric_version: "1.0.0",
            baseline_mean: 0.7,
            candidate_mean: 0.75,
            mean_difference: 0.05,
            median_difference: 0,
            relative_improvement: 0.0714,
            probability_of_superiority: 0.55,
            standardized_mean_difference: 0.12,
            confidence_interval: {
              lower: 0.01,
              upper: 0.09,
              confidence: 0.95,
              method: "paired_bca_bootstrap",
            },
            p_value: 0.03,
            adjusted_p_value: 0.04,
            test_method: "paired_permutation",
            total_union_count: 105,
            paired_count: 100,
            missing_baseline_count: 2,
            missing_candidate_count: 3,
            failed_baseline_count: 1,
            failed_candidate_count: 2,
            practical_interpretation:
              "statistically_significant_and_practically_meaningful",
            warnings: [],
            largest_improvements: [],
            largest_regressions: [],
          },
        ],
        limitations: ["Synthetic browser fixture."],
      }),
    });
  });
  await page.goto(`/projects/${projectId}/comparisons/${comparisonId}`);
  await expect(
    page.getByRole("heading", { name: "Experiment comparison" }),
  ).toBeVisible();
  await expect(
    page.getByRole("img", { name: /confidence interval 0.0100 to 0.0900/ }),
  ).toBeVisible();
  await expect(page.getByText(/n=100/)).toBeVisible();
  await expect(
    page.getByText(/Missing: 2 baseline and 3 candidate/),
  ).toBeVisible();
  await expect(page.getByText("Synthetic browser fixture.")).toBeVisible();
});
