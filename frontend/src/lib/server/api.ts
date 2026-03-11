import type { Service, ServicePublic, Incident, DayStatus } from '$lib/types';

export async function loadStatusData(
  fetch: typeof globalThis.fetch,
  includePrivate: true
): Promise<{ services: Service[]; incidents: Incident[]; history: Record<string, DayStatus[]> }>;
export async function loadStatusData(
  fetch: typeof globalThis.fetch,
  includePrivate?: false
): Promise<{ services: ServicePublic[]; incidents: Incident[]; history: Record<string, DayStatus[]> }>;
export async function loadStatusData(
  fetch: typeof globalThis.fetch,
  includePrivate = false
): Promise<{ services: Service[] | ServicePublic[]; incidents: Incident[]; history: Record<string, DayStatus[]> }> {
  const priv = includePrivate ? '?include_private=true' : '';
  const hist = includePrivate ? '?days=90&include_private=true' : '?days=90';
  const [sr, ir, hr] = await Promise.all([
    fetch(`/api/services${priv}`),
    fetch('/api/incidents'),
    fetch(`/api/history${hist}`)
  ]);
  return {
    services: await sr.json() as Service[] | ServicePublic[],
    incidents: await ir.json() as Incident[],
    history: await hr.json() as Record<string, DayStatus[]>
  };
}
