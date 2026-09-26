// Inches <-> feet-and-inches display.
// Mirror of backend/app/util/units.py. Both are tested against fixtures/units/cases.json,
// so change them together.

const SIXTEENTHS_PER_INCH = 16;
const SIXTEENTHS_PER_FOOT = 12 * SIXTEENTHS_PER_INCH;

function toSixteenths(inches: number): number {
  if (!Number.isFinite(inches) || inches < 0) {
    throw new RangeError(`length must be a non-negative finite number, got ${inches}`);
  }
  return Math.floor(inches * SIXTEENTHS_PER_INCH + 0.5);
}

function gcd(a: number, b: number): number {
  return b === 0 ? a : gcd(b, a % b);
}

/** Whole inches plus a reduced fraction: 24 -> "1-1/2", 8 -> "1/2", 32 -> "2". */
function inchText(sixteenths: number): string {
  const whole = Math.floor(sixteenths / SIXTEENTHS_PER_INCH);
  const rem = sixteenths % SIXTEENTHS_PER_INCH;
  if (rem === 0) return String(whole);
  const divisor = gcd(rem, SIXTEENTHS_PER_INCH);
  const fraction = `${rem / divisor}/${SIXTEENTHS_PER_INCH / divisor}`;
  return whole === 0 ? fraction : `${whole}-${fraction}`;
}

/** Inches as a mixed number with no unit mark, for dimensions: 5.5 -> "5-1/2". */
export function formatFraction(inches: number): string {
  return inchText(toSixteenths(inches));
}

/** Inches as feet and inches: 64.5 -> `5' 4-1/2"`, 60 -> `5' 0"`, 4.5 -> `4-1/2"`. */
export function formatFtIn(inches: number): string {
  const total = toSixteenths(inches);
  const feet = Math.floor(total / SIXTEENTHS_PER_FOOT);
  const text = inchText(total % SIXTEENTHS_PER_FOOT);
  return feet === 0 ? `${text}"` : `${feet}' ${text}"`;
}

const NUMBER = String.raw`\d+(?:\.\d+)?`;
const INCHES = String.raw`(?:\d+[-\s]+\d+/\d+|\d+/\d+|${NUMBER})`;
const LENGTH_RE = new RegExp(
  String.raw`^\s*(?:(?<feet>${NUMBER})\s*')?\s*(?:(?<inches>${INCHES})\s*"?)?\s*$`,
);
const MIXED_RE = /^(?:(?<whole>\d+)[-\s]+)?(?<num>\d+)\/(?<den>\d+)$/;

function parseInches(token: string): number {
  const mixed = MIXED_RE.exec(token);
  if (mixed === null) return Number(token);
  const denominator = Number(mixed.groups!.den);
  if (denominator === 0) throw new RangeError(`zero denominator in "${token}"`);
  return Number(mixed.groups!.whole ?? 0) + Number(mixed.groups!.num) / denominator;
}

/**
 * Parse `5' 4-1/2"`, `5'`, `4 1/2"`, `1/2"`, `64.5` or `2.5'` into inches.
 * A bare number is inches. Throws RangeError on anything else (including negatives).
 */
export function parseLength(text: string): number {
  const normalized = text.replace(/″/g, '"').replace(/′/g, "'");
  const match = LENGTH_RE.exec(normalized);
  if (match === null || (match.groups!.feet === undefined && match.groups!.inches === undefined)) {
    throw new RangeError(`cannot parse length: "${text}"`);
  }
  const feet = match.groups!.feet !== undefined ? Number(match.groups!.feet) : 0;
  const inches = match.groups!.inches !== undefined ? parseInches(match.groups!.inches) : 0;
  return feet * 12 + inches;
}
