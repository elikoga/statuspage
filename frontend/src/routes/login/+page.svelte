<script lang="ts">
	import { enhance } from '$app/forms';
	import type { ActionData, PageData } from './$types';

	let { data, form }: { data: PageData; form: ActionData } = $props();

	const oidcErrorMessages: Record<string, string> = {
		oidc_denied: 'Login was cancelled or denied by the provider.',
		oidc_invalid: 'Invalid or expired login request. Please try again.',
		oidc_failed: 'An error occurred while communicating with the identity provider.'
	};
</script>

<svelte:head>
	<title>Login — Status Page</title>
</svelte:head>

{#snippet passwordForm(buttonClass: string)}
	<form
		method="POST"
		use:enhance
		class="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-4"
	>
		<input type="hidden" name="next" value={data.next} />

		{#if form?.error}
			<p class="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">
				{form.error}
			</p>
		{/if}

		<div>
			<label for="username" class="block text-sm font-medium text-gray-700 mb-1"
				>Username</label
			>
			<input
				id="username"
				name="username"
				type="text"
				required
				autocomplete="username"
				class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
			/>
		</div>

		<div>
			<label for="password" class="block text-sm font-medium text-gray-700 mb-1"
				>Password</label
			>
			<input
				id="password"
				name="password"
				type="password"
				required
				autocomplete="current-password"
				class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
			/>
		</div>

		<button
			type="submit"
			class="w-full {buttonClass} text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
		>
			Sign in
		</button>
	</form>
{/snippet}

<div class="min-h-screen bg-gray-50 flex items-center justify-center px-4">
	<div class="w-full max-w-sm">
		<div class="text-center mb-8">
			<h1 class="text-2xl font-bold text-gray-900">Status Page</h1>
			<p class="text-sm text-gray-500 mt-1">Sign in to the admin panel</p>
		</div>

		{#if data.error && oidcErrorMessages[data.error]}
			<p class="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2 mb-4">
				{oidcErrorMessages[data.error]}
			</p>
		{/if}

		{#if data.oidcEnabled}
			<div class="bg-white rounded-xl border border-gray-200 shadow-sm p-6 mb-4">
				<a
					href="/auth/oidc/login?next={encodeURIComponent(data.next)}"
					class="flex items-center justify-center w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg px-4 py-2 text-sm font-medium transition-colors"
				>
					Sign in with {data.oidcProviderName}
				</a>
			</div>

			<details class="group">
				<summary
					class="cursor-pointer text-center text-xs text-gray-400 hover:text-gray-600 select-none mb-3"
				>
					Sign in with password instead
				</summary>

				{@render passwordForm('bg-gray-600 hover:bg-gray-700')}
			</details>
		{:else}
			{@render passwordForm('bg-blue-600 hover:bg-blue-700')}
		{/if}

		<p class="text-center mt-4 text-xs text-gray-400">
			<a href="/" class="hover:underline">Back to status page</a>
		</p>
	</div>
</div>
