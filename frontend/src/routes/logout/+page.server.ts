import { redirect } from '@sveltejs/kit';
import type { Actions } from './$types';

export const actions: Actions = {
	default: async ({ fetch, cookies }) => {
		await fetch('/auth/logout', { method: 'POST' });
		cookies.delete('session-token', { path: '/' });
		throw redirect(303, '/login');
	}
};
