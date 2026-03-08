import type { LayoutServerLoad } from './$types';
import { requireAuth } from '$lib/server/auth';

export const load: LayoutServerLoad = async ({ fetch }) => {
  const username = await requireAuth(fetch);
  return { username };
};
