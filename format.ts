const money = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const qty = new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 });

export const formatMoney = (value: number) => money.format(value);
export const formatQty = (value: number) => qty.format(value);
export const formatPercent = (rate: number) => `${qty.format(rate * 100)}%`;

export const humanize = (key: string) => {
  const s = key.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
};

const UNIT_LABELS: Record<string, [string, string]> = {
  per_sheet: ["sheet", "sheets"],
  per_litre: ["litre", "litres"],
  per_roll: ["roll", "rolls"],
  per_sqm: ["sqm", "sqm"],
  per_point: ["point", "points"],
  per_panel: ["panel", "panels"],
  per_piece: ["piece", "pieces"],
};

export const unitLabel = (unit: string, quantity: number) => {
  const pair = UNIT_LABELS[unit];
  if (!pair) return unit.replace(/^per_/, "");
  return quantity === 1 ? pair[0] : pair[1];
};

export const formatDate = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
