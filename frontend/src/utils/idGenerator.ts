export function generateId(prefix = 'id'): string {
  return `${prefix}_${crypto.randomUUID().slice(0, 8)}`;
}
