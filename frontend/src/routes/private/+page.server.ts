import { redirect } from '@sveltejs/kit';
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, url }) => {
	const authRes = await fetch('/auth/me');
	if (!authRes.ok) {
		throw redirect(303, `/login?next=${encodeURIComponent(url.pathname)}`);
	}

	const [servicesRes, incidentsRes] = await Promise.all([
		fetch('/api/services?include_private=true'),
		fetch('/api/incidents')
	]);

	return {
		services: await servicesRes.json(),
		incidents: await incidentsRes.json()
	};
};
