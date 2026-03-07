<script lang="ts">
	import type { LayoutData } from './$types';
	import { enhance } from '$app/forms';

	let { data, children }: { data: LayoutData; children: import('svelte').Snippet } = $props();
</script>

<div class="min-h-screen bg-gray-50">
	<header class="bg-white shadow-sm">
		<div class="mx-auto max-w-4xl px-4 py-5 flex items-center justify-between">
			<h1 class="text-xl font-bold text-gray-900">Admin</h1>
			<div class="flex items-center gap-4">
				<span class="text-sm text-gray-500">{data.username}</span>
				<a href="/" class="text-sm text-blue-600 hover:underline">Public page</a>
				<a href="/private" class="text-sm text-blue-600 hover:underline">Private page</a>
				<form method="POST" action="/logout" use:enhance>
					<button type="submit" class="text-sm text-gray-500 hover:text-gray-800">Sign out</button>
				</form>
			</div>
		</div>
	</header>

	{@render children()}
</div>
