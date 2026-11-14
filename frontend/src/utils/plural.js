const RULES = new Intl.PluralRules('uk-UA');

/** Ukrainian plural form: plural(n, ['день', 'дні', 'днів']) -> one / few / many. */
export const plural = (count, forms) => {
  const category = RULES.select(Math.abs(Number(count) || 0));
  if (category === 'one') return forms[0];
  if (category === 'few') return forms[1];
  return forms[2];
};

/** "3 дні", "1 запис" — the number together with the right form. */
export const pluralCount = (count, forms) => `${count} ${plural(count, forms)}`;
