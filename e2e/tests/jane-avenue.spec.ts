import { expect, test } from '@playwright/test';

test.describe('Jane Avenue End-to-End Flows (mock mode)', () => {
  test('1. Golden path: parse preview 25 -> 28, run analysis, stream research steps, render all tabs, slider re-simulates, download report', async ({
    page,
    request,
  }) => {
    await page.goto('/');

    // 1. Type the golden query and check that the parse preview shows 25 -> 28
    const queryInput = page.locator('#policy-query-input');
    await expect(queryInput).toBeVisible();
    await queryInput.fill(
      'What would happen if the UK increased corporation tax from 25% to 28%?',
    );
    await queryInput.blur();

    await expect(page.locator('#spec-baseline-rate')).toHaveValue('25');
    await expect(page.locator('#spec-proposed-rate')).toHaveValue('28');
    await expect(page.locator('#spec-change-pp')).toContainText('+3pp');
    await expect(page.getByLabel('Scope status: Supported')).toBeVisible();

    // 2. Run the analysis
    await page.getByRole('button', { name: /Run analysis/i }).click();
    await expect(page).toHaveURL(/\/analyses\/[a-z0-9]+\/research/);

    const urlMatch = page.url().match(/\/analyses\/([a-z0-9]+)\//);
    expect(urlMatch).not.toBeNull();
    const analysisId = urlMatch![1];

    // 3. Check that research steps stream in and pipeline reaches completed state
    await expect(page.getByLabel('Pipeline stage progress')).toBeVisible();
    await expect(page.locator('main')).toContainText(/OBR|IFS|plan|search|Evidence|Sources/i);

    // Wait for analysis completion so all tabs are enabled
    const tabNav = page.getByRole('tablist', { name: 'Analysis views' });
    await expect(tabNav.getByRole('tab', { name: 'Report' })).toBeEnabled({
      timeout: 20_000,
    });

    // 4. Check that every tab renders with real M1+M2 data
    // Overview tab
    await tabNav.getByRole('tab', { name: 'Overview' }).click();
    await expect(page).toHaveURL(new RegExp(`/analyses/${analysisId}/overview`));
    await expect(page.locator('main')).toContainText(/Headline Projections/i);
    await expect(page.locator('main')).toContainText(/£7\.0bn/);
    await expect(page.locator('main')).toContainText(/£13\.3bn/);

    // Precedents tab
    await tabNav.getByRole('tab', { name: 'Precedents' }).click();
    await expect(page).toHaveURL(new RegExp(`/analyses/${analysisId}/precedents`));
    await expect(page.locator('main')).toContainText(/Precedents|CT-MAIN-2023|2023/i);
    await expect(page.locator('main')).toContainText(/Official costing|Observed outcome/i);

    // Scenarios tab (+ step 5: moving a slider updates custom series via POST /api/simulate)
    await tabNav.getByRole('tab', { name: 'Scenarios' }).click();
    await expect(page).toHaveURL(new RegExp(`/analyses/${analysisId}/scenarios`));
    await expect(page.locator('main')).toContainText(/Scenarios|central|revenue/i);
    await expect(page.locator('main')).toContainText(/assumption-driven ranges/i);

    const sliders = page.locator('input[type="range"]');
    expect(await sliders.count()).toBeGreaterThan(0);
    const firstSlider = sliders.first();
    const maxVal = (await firstSlider.getAttribute('max')) ?? '0.5';
    await firstSlider.fill(maxVal);
    await firstSlider.dispatchEvent('change');
    await expect(page.locator('main')).toContainText(/custom|recomputed/i, {
      timeout: 10_000,
    });

    // Assumptions tab
    await tabNav.getByRole('tab', { name: 'Assumptions' }).click();
    await expect(page).toHaveURL(new RegExp(`/analyses/${analysisId}/assumptions`));
    await expect(page.locator('main')).toContainText(
      /Assumptions|taxable_profit_elasticity/i,
    );

    // Verification tab
    await tabNav.getByRole('tab', { name: 'Verification' }).click();
    await expect(page).toHaveURL(new RegExp(`/analyses/${analysisId}/verification`));
    await expect(page.locator('main')).toContainText(/SCOPE-001/);
    await expect(page.locator('main')).toContainText(/CALC-001/);
    await expect(page.locator('main')).toContainText(/REPORT-001/);

    // Report tab (+ step 6: download the report)
    await tabNav.getByRole('tab', { name: 'Report' }).click();
    await expect(page).toHaveURL(new RegExp(`/analyses/${analysisId}/report`));
    await expect(page.locator('main')).toContainText(/Executive summary/i);
    await expect(page.locator('main')).toContainText(/Modelled impacts/i);

    // Verify markdown report download endpoint works and returns attachment
    const reportResp = await request.get(
      `http://localhost:8000/api/analyses/${analysisId}/report.md`,
    );
    expect(reportResp.ok()).toBeTruthy();
    expect(reportResp.headers()['content-type']).toContain('text/markdown');
    const reportMd = await reportResp.text();
    expect(reportMd).toContain('Executive summary');
    expect(reportMd.length).toBeGreaterThan(200);

    // Footer disclaimer must always be visible (Rule 14)
    await expect(page.locator('footer')).toContainText(
      'Prototype. Not official government analysis.',
    );
  });

  test('2. Out-of-scope path: "Raise corporation tax to 45%" withholds the forecast across overview, scenarios, and report', async ({
    page,
  }) => {
    await page.goto('/');

    const queryInput = page.locator('#policy-query-input');
    await queryInput.fill('Raise corporation tax to 45%');
    await queryInput.blur();

    await expect(page.getByLabel('Scope status: Unsupported')).toBeVisible();
    await expect(page.locator('main')).toContainText('Quantitative forecast withheld');

    await page.getByRole('button', { name: /Run analysis/i }).click();
    await expect(page).toHaveURL(/\/analyses\/[a-z0-9]+\/research/);

    const tabNav = page.getByRole('tablist', { name: 'Analysis views' });
    await expect(tabNav.getByRole('tab', { name: 'Report' })).toBeEnabled({
      timeout: 20_000,
    });

    // Overview shows withheld banner
    await tabNav.getByRole('tab', { name: 'Overview' }).click();
    await expect(
      page.getByRole('alert', { name: 'Quantitative forecast withheld' }),
    ).toBeVisible();

    // Scenarios shows withheld banner or withheld state
    await tabNav.getByRole('tab', { name: 'Scenarios' }).click();
    await expect(page.locator('main')).toContainText(
      /Quantitative forecast withheld|forecast_withheld|null/i,
    );

    // Report shows withheld state
    await tabNav.getByRole('tab', { name: 'Report' }).click();
    await expect(page.locator('main')).toContainText(
      /Quantitative model projections are withheld|Quantitative forecast withheld|forecast_withheld/i,
    );
  });

  test('3. Non-tax path: shows unsupported scope decision', async ({ page }) => {
    await page.goto('/');

    const queryInput = page.locator('#policy-query-input');
    await queryInput.fill('Build 50 new hospitals across England by 2030');
    await queryInput.blur();

    await expect(page.getByLabel('Scope status: Unsupported')).toBeVisible();
    await expect(page.locator('#spec-policy-type')).toHaveValue('unsupported');
    await expect(page.locator('main')).toContainText('Quantitative forecast withheld');
  });

  test('4. Evaluation page renders backtest table, ML honesty verdict, research gold set, and verifier fault suite', async ({
    page,
  }) => {
    await page.goto('/evaluation');
    await expect(page.locator('main')).toContainText(/Evaluation|Backtest/i);
    await expect(page.locator('main')).toContainText(/jane_behavioural|Behavioural/i);
    await expect(page.locator('main')).toContainText(/lightgbm|LightGBM/i);
    await expect(page.locator('main')).toContainText(/100\.0%|15\/15|18\/18/);
    await expect(page.locator('footer')).toContainText(
      'Prototype. Not official government analysis.',
    );
  });
});
