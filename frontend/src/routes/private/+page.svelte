<script lang="ts">
	import StatusPageView from '$lib/StatusPageView.svelte';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();
</script>

<svelte:head>
	<title>Private Status — Status Page</title>
</svelte:head>

<StatusPageView services={data.services} incidents={data.incidents} history={data.history} isPrivate />
