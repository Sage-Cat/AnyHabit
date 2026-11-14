/** Number with a fixed count of decimals, in the Ukrainian format (1 234,5). */
export const formatNumber = (value, digits = 1) =>
  (Number.isFinite(Number(value)) ? Number(value) : 0).toLocaleString('uk-UA', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits
  });
