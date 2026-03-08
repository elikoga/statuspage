import type { PageServerLoad } from './$types';
import { requireAuth } from '$lib/server/auth';
import { loadStatusData } from '$lib/server/api';

export const load: PageServerLoad = async ({ fetch }) => {
  await requireAuth(fetch);
  return loadStatusData(fetch, true);
};
