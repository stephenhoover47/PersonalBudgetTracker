import { test, expect } from "@playwright/test";

for (const viewport of [
  { name: "desktop", width: 1440, height: 1000 },
  { name: "iphone", width: 390, height: 844 },
]) {
  test(`${viewport.name}: household workflow`, async ({ page }) => {
    const travelGoal = `Travel ${viewport.name}`, holidayGoal = `Holiday ${viewport.name}`;
    await page.setViewportSize(viewport);
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/");
    await expect(page).toHaveTitle("PocketWatcher · Household budget");
    await expect(page.getByRole("img", {name: "PocketWatcher", exact: true})).toBeVisible();
    expect((await page.request.get("/brand/pocketwatcher-logo.png")).ok()).toBeTruthy();
    await page.getByLabel("Email", { exact: true }).fill("one@example.com");
    await page
      .getByLabel("Password", { exact: true })
      .fill("sample test password");
    await page.getByRole("button", { name: "Sign in", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "A clear view, Stephen." }),
    ).toBeVisible();
    await expect(page.getByRole("link", {name: "PocketWatcher home"})).toBeVisible();
    const mark = page.locator(".brand-mark");
    expect(await mark.evaluate((img: HTMLImageElement) => img.complete && img.naturalWidth > 0)).toBeTruthy();
    await page.getByLabel("Budget month", { exact: true }).fill("2026-11");
    await page.getByRole("button", { name: "Settings", exact: true }).click();
    await expect(page.getByRole("heading", {name: "Connect your banks"})).toBeVisible();
    await expect(page.getByRole("button", {name: "Connect a bank", exact: true})).toBeDisabled();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
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
    const accountSettings = page.getByRole("group", {name: `Account: Joint card ${viewport.name}`, exact: true});
    await accountSettings.getByRole("button", {name: "Edit", exact: true}).click();
    await accountSettings.getByLabel(`Edit Joint card ${viewport.name} name`).fill(`Shared card ${viewport.name}`);
    await accountSettings.getByRole("button", {name: "Save changes", exact: true}).click();
    const renamedAccount = page.getByRole("group", {name: `Account: Shared card ${viewport.name}`, exact: true});
    await expect(renamedAccount).toBeVisible();
    page.once("dialog", d => d.accept());
    await renamedAccount.getByRole("button", {name: "Archive", exact: true}).click();
    await expect(renamedAccount).toHaveCount(0);
    await page.getByText(`Archived: Shared card ${viewport.name}`, {exact: true}).click();
    await page.getByRole("button", {name: `Restore Shared card ${viewport.name}`, exact: true}).click();
    await renamedAccount.getByRole("button", {name: "Edit", exact: true}).click();
    await renamedAccount.getByLabel(`Edit Shared card ${viewport.name} name`).fill(`Joint card ${viewport.name}`);
    await renamedAccount.getByRole("button", {name: "Save changes", exact: true}).click();
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
      (viewport.name === "iphone" ? page.getByRole("article") : page.getByRole("row")).filter({ hasText: "Test Market" }),
    ).toHaveCount(viewport.name === "desktop" ? 1 : 2);
    const visibleActivity = viewport.name === "iphone" ? page.locator(".transaction-cards") : page.locator(".transaction-table");
    await expect(visibleActivity).toContainText("Nov 1, 2026");
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.screenshot({path: `test-results/${viewport.name}-transactions.png`, fullPage: true});
    if (viewport.name === "iphone") {
      for (const width of [320, 375, 430, 768]) {
        await page.setViewportSize({width, height: 844});
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
        const controlsFit = await page.locator(".month-control").evaluate(el => {
          const bounds = el.getBoundingClientRect();
          return bounds.left >= 0 && bounds.right <= window.innerWidth;
        });
        expect(controlsFit).toBeTruthy();
      }
      await page.setViewportSize(viewport);
    }

    const row = viewport.name === "iphone"
      ? page.getByRole("article").filter({hasText: "Test Market"}).first()
      : page.getByRole("row").filter({hasText: "Test Market"}).first();
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
    await expect(page.getByLabel("Groceries budget", {exact: true})).toHaveCount(0);
    await expect(page.getByRole("button", {name: "Save changes", exact: true})).toHaveCount(0);
    await page.getByRole("button", {name: "Edit plan", exact: true}).click();
    await page.getByLabel("Groceries budget", {exact: true}).fill("500.00");
    await page.getByRole("button", {name: "Add savings goal", exact: true}).click();
    const newGoal = page.getByRole("group").filter({has: page.getByRole("textbox", {name: /Goal \d+ name/})}).last();
    await newGoal.getByRole("textbox", {name: /name/}).fill(travelGoal);
    await newGoal.getByRole("textbox", {name: /allocation/}).fill("250");
    await page.getByRole("button", {name: "Save changes", exact: true}).click();
    await expect(page.getByRole("status").filter({hasText: "Plan saved"})).toBeVisible();
    await expect(page.getByText(travelGoal, {exact: true})).toBeVisible();
    await expect(page.getByLabel("Groceries budget", {exact: true})).toHaveCount(0);
    await page.getByRole("button", {name: "Edit plan", exact: true}).click();
    await page.getByLabel("Groceries budget", {exact: true}).fill("900");
    await page.getByRole("button", {name: "Cancel", exact: true}).click();
    await page.getByRole("button", {name: "Edit plan", exact: true}).click();
    await expect(page.getByLabel("Groceries budget", {exact: true})).toHaveValue("500.00");
    await page.getByRole("button", {name: "Cancel", exact: true}).click();
    await page.getByLabel("Budget month", {exact: true}).fill("2026-12");
    await expect(page.getByText(travelGoal, {exact: true})).toBeVisible();
    await page.getByRole("button", {name: "Edit plan", exact: true}).click();
    const goal = page.getByRole("group", {name: /^Savings goal/}).filter({has: page.getByRole("textbox", {name: /Goal \d+ name/}).filter({visible: true})}).filter({has: page.locator(`input[value="${travelGoal}"]`)});
    await goal.getByRole("textbox", {name: /allocation/}).fill("50");
    await page.getByRole("button", {name: "Save changes", exact: true}).click();
    await expect(page.getByRole("button", {name: "Edit plan", exact: true})).toBeVisible();
    await page.getByRole("button", {name: "Next month", exact: true}).click();
    await expect(page.getByLabel("Budget month", {exact: true})).toHaveValue("2027-01");
    await expect(page.locator(".goal").filter({hasText: travelGoal})).toContainText("$50.00");
    await page.getByRole("button", {name: "Previous month", exact: true}).click();
    await expect(page.getByLabel("Budget month", {exact: true})).toHaveValue("2026-12");
    await page.getByRole("button", {name: "Edit plan", exact: true}).click();
    await page.getByLabel("Groceries budget", {exact: true}).fill("700");
    page.once("dialog", d => d.dismiss());
    await page.getByRole("button", {name: "Next month", exact: true}).click();
    await expect(page.getByLabel("Budget month", {exact: true})).toHaveValue("2026-12");
    await expect(page.getByLabel("Groceries budget", {exact: true})).toHaveValue("700");
    await page.getByRole("button", {name: "Cancel", exact: true}).click();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
    await page.screenshot({path: `test-results/${viewport.name}-plan.png`, fullPage: true});
    await page.getByRole("button", { name: "Overview", exact: true }).click();
    await expect(page.getByText("Monthly savings target", {exact: true})).toBeVisible();
    await page.screenshot({
      path: `test-results/${viewport.name}-overview.png`,
      fullPage: true,
    });
    const manifestResponse = await page.request.get("/manifest.webmanifest");
    expect(manifestResponse.ok()).toBeTruthy();
    const manifest = await manifestResponse.json();
    expect(manifest.display).toBe("standalone");
    expect(manifest.name).toBe("PocketWatcher");
    expect(manifest.short_name).toBe("PocketWatcher");
    expect(manifest.start_url).toBe("/");
    for (const icon of manifest.icons) {
      expect((await page.request.get(icon.src)).ok()).toBeTruthy();
    }
    await page.evaluate(async () => {
      await navigator.serviceWorker.ready;
    });
    expect((await page.request.get("/api/me")).headers()["cache-control"]).toBe(
      "no-store",
    );
    expect(await page.evaluate(async () => await caches.keys())).toEqual([]);
    expect(errors).toEqual([]);
    await page
      .getByRole("button", { name: "Sign out", exact: true })
      .filter({ visible: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Sign in", exact: true }),
    ).toBeVisible();
    await page.context().setOffline(true);
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Let’s reconnect." }),
    ).toBeVisible();
    expect(await page.evaluate(async () => await caches.keys())).toEqual([]);
    await page.context().setOffline(false);
    await page.getByRole("link", { name: "Try again" }).click();
    await expect(
      page.getByRole("button", { name: "Sign in", exact: true }),
    ).toBeVisible();
  });
}
