import type { PageServerLoad, Actions } from './$types';
import { fail } from '@sveltejs/kit';

export const load: PageServerLoad = async ({ fetch }) => {
	const [servicesRes, incidentsRes] = await Promise.all([
		fetch('/api/services?include_private=true'),
		fetch('/api/incidents')
	]);
	return {
		services: await servicesRes.json(),
		incidents: await incidentsRes.json()
	};
};

export const actions: Actions = {
	createService: async ({ fetch, request }) => {
		const data = await request.formData();
		const res = await fetch('/api/services', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				name: data.get('name'),
				description: data.get('description') || null,
				url: data.get('url') || null,
				group: data.get('group') || null,
				status: data.get('status') || 'operational',
				is_public: data.get('is_public') === 'true',
				check_enabled: data.get('check_enabled') === 'true'
			})
		});
		if (!res.ok) return fail(res.status, { error: await res.text() });
	},

	updateService: async ({ fetch, request }) => {
		const data = await request.formData();
		const id = data.get('id') as string;
		const res = await fetch(`/api/services/${id}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				name: data.get('name') || undefined,
				description: data.get('description') || undefined,
				url: data.get('url') || undefined,
				group: data.get('group') || null,
				status: data.get('status') || undefined,
				is_public: data.get('is_public') === 'true',
				check_enabled: data.get('check_enabled') === 'true'
			})
		});
		if (!res.ok) return fail(res.status, { error: await res.text() });
	},

	deleteService: async ({ fetch, request }) => {
		const data = await request.formData();
		const id = data.get('id') as string;
		const res = await fetch(`/api/services/${id}`, { method: 'DELETE' });
		if (!res.ok) return fail(res.status, { error: await res.text() });
	},

	createIncident: async ({ fetch, request }) => {
		const data = await request.formData();
		const res = await fetch('/api/incidents', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				title: data.get('title'),
				body: data.get('body') || '',
				status: data.get('status') || 'investigating'
			})
		});
		if (!res.ok) return fail(res.status, { error: await res.text() });
	},

	updateIncident: async ({ fetch, request }) => {
		const data = await request.formData();
		const id = data.get('id') as string;
		const res = await fetch(`/api/incidents/${id}`, {
			method: 'PATCH',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({
				title: data.get('title') || undefined,
				body: data.get('body') || undefined,
				status: data.get('status') || undefined
			})
		});
		if (!res.ok) return fail(res.status, { error: await res.text() });
	},

	deleteIncident: async ({ fetch, request }) => {
		const data = await request.formData();
		const id = data.get('id') as string;
		const res = await fetch(`/api/incidents/${id}`, { method: 'DELETE' });
		if (!res.ok) return fail(res.status, { error: await res.text() });
	}
};
