import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	const [servicesRes, incidentsRes] = await Promise.all([
		fetch('/api/services'),
		fetch('/api/incidents')
	]);

	const services = await servicesRes.json();
	const incidents = await incidentsRes.json();

	return { services, incidents };
};
