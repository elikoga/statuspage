import { redirect } from '@sveltejs/kit';

export async function requireAuth(fetch: typeof globalThis.fetch): Promise<string> {
  const res = await fetch('/auth/me');
  if (!res.ok) throw redirect(303, '/login');
  const data = await res.json();
  return data.username as string;
}
