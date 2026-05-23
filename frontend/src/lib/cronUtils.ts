/** Normalize whitespace in a cron expression. */
export function normalizeCron(value: string): string {
  return value.trim().replace(/\s+/g, ' ');
}

/** Standard 5-field cron (minute hour dom month dow). */
export function isValidCron(value: string): boolean {
  const expr = normalizeCron(value);
  if (!expr) return false;
  const parts = expr.split(' ');
  return parts.length === 5;
}

export function cronValidationError(value: string): string | null {
  const expr = normalizeCron(value);
  if (!expr) return null;
  const parts = expr.split(' ');
  if (parts.length === 5) return null;
  if (!expr.includes(' ') && expr.includes('*')) {
    return 'Add spaces between fields, e.g. */2 * * * * (not */2****)';
  }
  return `Cron needs exactly 5 fields (minute hour day month weekday). Got ${parts.length}. Example: */2 * * * *`;
}
