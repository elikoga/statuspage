import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, url }) => {
	const authRes = await fetch('/auth/me');
	if (!authRes.ok) {
		throw redirect(303, `/login?next=${encodeURIComponent(url.pathname)}`);
	}

	const [servicesRes, incidentsRes, historyRes] = await Promise.all([
		fetch('/api/services?include_private=true'),
		fetch('/api/incidents'),
		fetch('/api/history?days=90&include_private=true')
	]);

	return {
		services: await servicesRes.json(),
		incidents: await incidentsRes.json(),
		history: await historyRes.json()
	};
};
