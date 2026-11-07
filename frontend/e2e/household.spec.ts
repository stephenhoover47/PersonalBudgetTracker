import { test, expect } from "@playwright/test";

for (const viewport of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "iphone", width: 390, height: 844 },
]) {
  test(`${viewport.name}: household workflow`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/");
    await page.getByLabel("Email", { exact: true }).fill("one@example.com");
    await page
      .getByLabel("Password", { exact: true })
      .fill("sample test password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "A clear view, Stephen." }),
    ).toBeVisible();
    await page.getByLabel("Budget month", { exact: true }).fill("2026-11");
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await page.getByLabel("Account name").fill("Joint card " + viewport.name);
    await page
      .getByRole("combobox", { name: "Type", exact: true })
      .selectOption("credit");
    await page
      .getByRole("button", { name: "Add account", exact: true })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: "Shared account added." }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Import", exact: true }).click();
    await page
      .getByRole("combobox", { name: "Shared account", exact: true })
      .selectOption({ label: "Joint card " + viewport.name });
    await page.getByLabel("CSV file").setInputFiles({
      name: "sample.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        "date,merchant,amount,external_id\n2026-11-01,Test Market,100.01,one\n2026-11-02,Card Payment,-100.01,two\n",
      ),
    });
    await page
      .getByRole("button", { name: "Preview import", exact: true })
      .click();
    await expect(
      page.getByRole("heading", { name: "Review before importing" }),
    ).toBeVisible();
    await page
      .getByLabel("Enter the net total from your export ($)")
      .fill("0.00");
    await page
      .getByRole("button", { name: "Confirm import", exact: true })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: "Imported 2 transactions" }),
    ).toBeVisible();
    await page
      .getByRole("button", { name: "Transactions", exact: true })
      .click();
    await page
      .getByRole("textbox", { name: "Search merchants" })
      .fill("Test Market");
    await expect(
      page.getByRole("row").filter({ hasText: "Test Market" }),
    ).toHaveCount(viewport.name === "desktop" ? 1 : 2);
    const row = page
      .getByRole("row")
      .filter({ hasText: "Test Market" })
      .first();
    await row.getByRole("button", { name: "Edit", exact: true }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await dialog.getByLabel("Transaction type").selectOption("expense");
    await dialog.getByLabel("Split 1 dollars").fill("60.01");
    await dialog
      .getByRole("button", { name: "Add split", exact: true })
      .click();
    await dialog
      .getByLabel("Split 2 category")
      .selectOption({ label: "Dining" });
    await dialog.getByLabel("Split 2 dollars").fill("40.00");
    await dialog
      .getByRole("button", { name: "Save transaction", exact: true })
      .click();
    await expect(dialog).not.toBeVisible();
    await page.getByRole("button", { name: "Plan", exact: true }).click();
    await page.getByLabel("Groceries budget", { exact: true }).fill("500.00");
    await page
      .locator(".budget-row")
      .filter({ hasText: "Groceries" })
      .getByRole("button", { name: "Save", exact: true })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: "Monthly budget saved." }),
    ).toBeVisible();
    await page.getByLabel("Goal name", { exact: true }).fill("Travel");
    await page
      .getByLabel("Monthly allocation ($)", { exact: true })
      .fill("250");
    await page.getByRole("button", { name: "Save allocation" }).click();
    await expect(
      page.getByRole("status").filter({ hasText: "Allocation saved." }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Overview", exact: true }).click();
    await expect(page.getByText("Travel", { exact: true })).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBeTruthy();
    await page.screenshot({
      path: `test-results/${viewport.name}-overview.png`,
      fullPage: true,
    });
    expect(errors).toEqual([]);
    await page
      .getByRole("button", { name: "Sign out", exact: true })
      .filter({ visible: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Sign in", exact: true }),
    ).toBeVisible();
  });
}
