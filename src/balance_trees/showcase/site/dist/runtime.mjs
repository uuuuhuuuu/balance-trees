// Keep API discovery separate so static hosting never depends on a server.
export async function detectEngine(baseURL, mode = 'auto', request = fetch) {
  if (mode === 'browser') return 'browser';
  try {
    const response = await request(new URL('./api/config', baseURL), {
      signal: AbortSignal.timeout(1500),
    });
    if (response.ok && (await response.json()).engine === 'python') return 'python';
  } catch { /* Ordinary static hosts have no Python API. */ }
  return 'browser';
}
