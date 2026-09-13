/** Turn an HttpErrorResponse into something a person can read.
 *
 * `error.detail` is not always a string. FastAPI answers a validation failure with a
 * LIST of objects, and interpolating that into a template produced "[object Object]" --
 * a message that tells the reader nothing and hides a real 422 behind what looks like a
 * rendering bug. Anything that is not a string is described rather than stringified.
 */
export function errorText(e: unknown, fallback: string): string {
  const err = (e as { error?: unknown; status?: number })?.error;
  const status = (e as { status?: number })?.status;

  // The browser reports a blocked or failed request as status 0, with no body. That is
  // the genuinely-unreachable case, and it is worth saying so plainly.
  if (status === 0) return fallback;

  const detail = (err as { detail?: unknown })?.detail;

  if (typeof detail === 'string' && detail.trim()) return detail;

  if (Array.isArray(detail)) {
    // Pydantic: [{loc: [...], msg: '...', type: '...'}]
    const parts = detail
      .map((d) => {
        const loc = Array.isArray(d?.loc) ? d.loc.filter((x: unknown) => x !== 'body').join('.') : '';
        const msg = typeof d?.msg === 'string' ? d.msg : JSON.stringify(d);
        return loc ? `${loc}: ${msg}` : msg;
      })
      .filter(Boolean);
    if (parts.length) return `${status ?? ''} ${parts.join('; ')}`.trim();
  }

  if (detail && typeof detail === 'object') return JSON.stringify(detail);

  if (typeof err === 'string' && err.trim()) return err;

  const title = (err as { title?: unknown })?.title;
  if (typeof title === 'string' && title.trim()) {
    return status ? `${status} ${title}` : title;
  }

  return status ? `${fallback} (HTTP ${status})` : fallback;
}
