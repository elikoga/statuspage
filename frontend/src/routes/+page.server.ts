import type { PageServerLoad } from './$types';
import { loadStatusData } from '$lib/server/api';

export const load: PageServerLoad = async ({ fetch }) => {
  return loadStatusData(fetch);
};
