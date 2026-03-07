import { redirect } from '@sveltejs/kit';
import type { LayoutServerLoad } from './$types';

export const load: LayoutServerLoad = async ({ fetch, url }) => {
	const res = await fetch('/auth/me');
	if (!res.ok) {
		throw redirect(303, `/login?next=${encodeURIComponent(url.pathname)}`);
	}
	const { username } = await res.json();
	return { username };
};
