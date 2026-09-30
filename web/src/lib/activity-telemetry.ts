const ACTIVITY_URL = /(\/api\/history\/|\/history\/)([\s\S]+)/i

export function redactActivityUrl(value: string): string {
  const candidate = value.replace(/(?:%[0-9a-f]{2})+/gi, encoded => {
    try {
      return decodeURIComponent(encoded)
    } catch {
      return encoded
    }
  })
  if (!ACTIVITY_URL.test(candidate)) return value
  return candidate.replace(ACTIVITY_URL, (_match, prefix, remainder) => {
    const canonicalPrefix = prefix.toLowerCase()
    const detail = canonicalPrefix === '/api/history/' && /\/detail(?:[/?#\s]|$)/i.test(remainder)
    return `${canonicalPrefix}{activity_id}${detail ? '/detail' : ''}`
  }).replace(/[?#].*$/, '')
}
