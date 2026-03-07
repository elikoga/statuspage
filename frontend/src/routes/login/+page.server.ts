import { fail, redirect } from '@sveltejs/kit';
import type { Actions, PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch, url }) => {
	// Already logged in? Send them to their destination.
	const res = await fetch('/auth/me');
	if (res.ok) {
		const next = url.searchParams.get('next') ?? '/admin';
		throw redirect(303, next);
	}
	return { next: url.searchParams.get('next') ?? '/admin' };
};

export const actions: Actions = {
	default: async ({ fetch, request, cookies, url }) => {
		const data = await request.formData();
		const username = (data.get('username') as string) ?? '';
		const password = (data.get('password') as string) ?? '';

		const res = await fetch('/auth/login', {
			method: 'POST',
			headers: { 'Content-Type': 'application/json' },
			body: JSON.stringify({ username, password })
		});

		if (!res.ok) {
			return fail(401, { error: 'Invalid username or password.' });
		}

		const { token } = await res.json();
		cookies.set('session-token', token, {
			path: '/',
			httpOnly: true,
			sameSite: 'lax',
			maxAge: 60 * 60 * 24 * 7 // 7 days
		});

		const next = url.searchParams.get('next') ?? '/admin';
		throw redirect(303, next);
	}
};
