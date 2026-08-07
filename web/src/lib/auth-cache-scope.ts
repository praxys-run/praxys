export function tokenCacheScope(token: string | null): string {
  if (!token) return 'anonymous';

  let hash = 2166136261;
  for (let index = 0; index < token.length; index += 1) {
    hash ^= token.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `auth-${(hash >>> 0).toString(16)}`;
}
