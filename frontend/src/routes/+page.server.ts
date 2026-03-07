import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
	const [servicesRes, incidentsRes, historyRes] = await Promise.all([
		fetch('/api/services'),
		fetch('/api/incidents'),
		fetch('/api/history?days=90')
	]);

	const services = await servicesRes.json();
	const incidents = await incidentsRes.json();
	const history = await historyRes.json();

	return { services, incidents, history };
};
