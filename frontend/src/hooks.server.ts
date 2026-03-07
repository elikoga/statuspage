import type { HandleFetch } from '@sveltejs/kit';
import { env } from '$env/dynamic/private';

const DEFAULT_BASE_URL = 'http://127.0.0.1:8000';
let privateBaseUrl = new URL(env.PRIVATE_BASE_URL ?? DEFAULT_BASE_URL);

const validHosts = ['localhost', '127.0.0.1', '::1'];
if (
	!(
		privateBaseUrl.protocol === 'http:' &&
		validHosts.some((h) => privateBaseUrl.host.startsWith(h))
	)
) {
	console.warn(
		`Private base URL host "${privateBaseUrl.host}" is not localhost. Falling back to default.`
	);
	privateBaseUrl = new URL(DEFAULT_BASE_URL);
}

export const handleFetch: HandleFetch = async ({ request, fetch, event }) => {
	const parsed = new URL(request.url);
	if (
		event.url.host === parsed.host &&
		parsed.pathname.startsWith('/api')
	) {
		const rewritten = new URL(request.url);
		rewritten.host = privateBaseUrl.host;
		rewritten.protocol = privateBaseUrl.protocol;
		request = new Request(rewritten, request);
	}
	return fetch(request);
};
