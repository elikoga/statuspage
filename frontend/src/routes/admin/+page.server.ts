import type { PageServerLoad, Actions } from './$types';
import { fail } from '@sveltejs/kit';
import type { Service, Incident } from '$lib/types';

export const load: PageServerLoad = async ({ fetch }) => {
	const [servicesRes, incidentsRes] = await Promise.all([
		fetch('/api/services?include_private=true'),
		fetch('/api/incidents')
	]);
	return {
		services: (await servicesRes.json()) as Service[],
		incidents: (await incidentsRes.json()) as Incident[]
	};
};

async function apiFetch(
	fetch: typeof globalThis.fetch,
	method: string,
	url: string,
	body?: object
) {
	const res = await fetch(url, {
		method,
		...(body !== undefined && {
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify(body)
		})
	});
	if (!res.ok) return fail(res.status, { error: await res.text() });
}

export const actions: Actions = {
	createService: async ({ fetch, request }) => {
		const data = await request.formData();
		return apiFetch(fetch, 'POST', '/api/services', {
			name: data.get('name'),
			description: data.get('description') || null,
			url: data.get('url') || null,
			site_url: data.get('site_url') || null,
			group: data.get('group') || null,
			status: data.get('status') || 'operational',
			is_public: data.get('is_public') === 'true',
			check_enabled: data.get('check_enabled') === 'true',
			on_demand: data.get('on_demand') === 'true',
			check_type: data.get('check_type') || 'http',
			check_command: data.get('check_command') || null
		});
	},

	updateService: async ({ fetch, request }) => {
		const data = await request.formData();
		const id = data.get('id') as string;
		return apiFetch(fetch, 'PATCH', `/api/services/${id}`, {
			name: data.get('name') || undefined,
			description: data.get('description') || undefined,
			url: data.get('url') || undefined,
			site_url: data.get('site_url') || null,
			group: data.get('group') || null,
			status: data.get('status') || undefined,
			is_public: data.get('is_public') === 'true',
			check_enabled: data.get('check_enabled') === 'true',
			on_demand: data.get('on_demand') === 'true',
			check_type: data.get('check_type') || undefined,
			check_command: data.get('check_command') || null
		});
	},

	deleteService: async ({ fetch, request }) => {
		const data = await request.formData();
		const id = data.get('id') as string;
		return apiFetch(fetch, 'DELETE', `/api/services/${id}`);
	},

	createIncident: async ({ fetch, request }) => {
		const data = await request.formData();
		return apiFetch(fetch, 'POST', '/api/incidents', {
			title: data.get('title'),
			body: data.get('body') || '',
			status: data.get('status') || 'investigating'
		});
	},

	updateIncident: async ({ fetch, request }) => {
		const data = await request.formData();
		const id = data.get('id') as string;
		return apiFetch(fetch, 'PATCH', `/api/incidents/${id}`, {
			title: data.get('title') || undefined,
			body: data.get('body') || undefined,
			status: data.get('status') || undefined
		});
	},

	deleteIncident: async ({ fetch, request }) => {
		const data = await request.formData();
		const id = data.get('id') as string;
		return apiFetch(fetch, 'DELETE', `/api/incidents/${id}`);
	}
};
