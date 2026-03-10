import type { PageServerLoad, Actions } from './$types';
import { fail } from '@sveltejs/kit';
import type { Service, Incident } from '$lib/types';

export const load: PageServerLoad = async ({ fetch }) => {
	const [servicesRes, incidentsRes, notifSettingsRes, emailSubsRes, discordDestsRes] = await Promise.all([
		fetch('/api/services?include_private=true'),
		fetch('/api/incidents'),
		fetch('/api/notifications/settings'),
		fetch('/api/notifications/email-subscribers'),
		fetch('/api/notifications/discord/destinations')
	]);
	return {
		services: (await servicesRes.json()) as Service[],
		incidents: (await incidentsRes.json()) as Incident[],
		notifSettings: await notifSettingsRes.json(),
		emailSubscribers: await emailSubsRes.json(),
		discordDestinations: await discordDestsRes.json()
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
			muted: data.get('muted') === 'true',
			check_type: data.get('check_type') || 'http',
			check_command: data.get('check_command') || null,
			failure_threshold: Number(data.get('failure_threshold')) || 2
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
			muted: data.get('muted') === 'true',
			check_type: data.get('check_type') || undefined,
			check_command: data.get('check_command') || null,
			failure_threshold: Number(data.get('failure_threshold')) || undefined
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
	},

	saveTelegram: async ({ fetch, request }) => {
		const data = await request.formData();
		const bot_token = data.get('bot_token');
		const tokenVal = bot_token && bot_token.toString().trim() ? bot_token : null;
		return apiFetch(fetch, 'PUT', '/api/notifications/telegram', {
			bot_token: tokenVal,
			chat_id: data.get('chat_id') || null
		});
	},

	saveDiscord: async ({ fetch, request }) => {
		const data = await request.formData();
		const bot_token = data.get('bot_token');
		const tokenVal = bot_token && bot_token.toString().trim() ? bot_token : null;
		return apiFetch(fetch, 'PUT', '/api/notifications/discord', {
			bot_token: tokenVal
		});
	},

	addEmailSubscriber: async ({ fetch, request }) => {
		const data = await request.formData();
		return apiFetch(fetch, 'POST', '/api/notifications/email-subscribers', {
			email: data.get('email')
		});
	},

	deleteEmailSubscriber: async ({ fetch, request }) => {
		const data = await request.formData();
		const id = data.get('id') as string;
		return apiFetch(fetch, 'DELETE', `/api/notifications/email-subscribers/${id}`);
	},

	addDiscordDestination: async ({ fetch, request }) => {
		const data = await request.formData();
		return apiFetch(fetch, 'POST', '/api/notifications/discord/destinations', {
			destination_type: data.get('destination_type'),
			destination_id: data.get('destination_id'),
			label: data.get('label') || null
		});
	},

	deleteDiscordDestination: async ({ fetch, request }) => {
		const data = await request.formData();
		const id = data.get('id') as string;
		return apiFetch(fetch, 'DELETE', `/api/notifications/discord/destinations/${id}`);
	}
};
