export const dollars = (cents: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(
    cents / 100,
  );
export function cents(value: string): number {
  if (!/^-?\d+(\.\d{1,2})?$/.test(value.trim()))
    throw new Error("Enter dollars with up to two decimal places.");
  const [whole, fraction = ""] = value.trim().replace("-", "").split(".");
  const n = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
  if (!Number.isSafeInteger(n) || n > 1000000000)
    throw new Error("Amount is too large.");
  return value.trim().startsWith("-") ? -n : n;
}
