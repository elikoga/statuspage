<script lang="ts">
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const STATUS_LABEL: Record<string, string> = {
		operational: 'Operational',
		degraded: 'Degraded',
		outage: 'Outage',
		offline: 'Offline'
	};

	const STATUS_COLOR: Record<string, string> = {
		operational: 'bg-green-500',
		degraded: 'bg-yellow-500',
		outage: 'bg-red-500',
		offline: 'bg-gray-400'
	};

	const INCIDENT_STATUS_LABEL: Record<string, string> = {
		investigating: 'Investigating',
		identified: 'Identified',
		monitoring: 'Monitoring',
		resolved: 'Resolved'
	};

	const INCIDENT_STATUS_COLOR: Record<string, string> = {
		investigating: 'bg-red-100 text-red-800',
		identified: 'bg-orange-100 text-orange-800',
		monitoring: 'bg-blue-100 text-blue-800',
		resolved: 'bg-green-100 text-green-800'
	};

	function checkedAgo(ts: string | null): string | null {
		if (!ts) return null;
		const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
		if (diff < 120) return 'just now';
		if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
		return `${Math.floor(diff / 3600)}h ago`;
	}

	const openIncidents = $derived(
		data.incidents.filter((i: { status: string }) => i.status !== 'resolved')
	);

	const overallStatus = $derived(() => {
		const active = data.services.filter((s: { status: string }) => s.status !== 'offline');
		if (active.some((s: { status: string }) => s.status === 'outage')) return 'outage';
		if (active.some((s: { status: string }) => s.status === 'degraded')) return 'degraded';
		return 'operational';
	});

	// Group services preserving insertion order of group names.
	const serviceGroups = $derived(() => {
		const groups = new Map<string, typeof data.services>();
		for (const svc of data.services) {
			const g = (svc as { group?: string | null }).group ?? 'Other';
			if (!groups.has(g)) groups.set(g, []);
			groups.get(g)!.push(svc);
		}
		return groups;
	});
</script>

<svelte:head>
	<title>Status Page</title>
</svelte:head>

<div class="min-h-screen bg-gray-50">
	<header class="bg-white shadow-sm">
		<div class="mx-auto max-w-3xl px-4 py-6">
			<h1 class="text-2xl font-bold text-gray-900">System Status</h1>
		</div>
	</header>

	<main class="mx-auto max-w-3xl px-4 py-8 space-y-8">
		<!-- Overall banner -->
		<div
			class="rounded-lg p-4 text-white font-medium text-center
				{overallStatus() === 'operational'
				? 'bg-green-500'
				: overallStatus() === 'degraded'
					? 'bg-yellow-500'
					: 'bg-red-500'}"
		>
			{#if overallStatus() === 'operational'}
				All systems operational
			{:else if overallStatus() === 'degraded'}
				Some systems are experiencing degraded performance
			{:else}
				One or more systems are experiencing an outage
			{/if}
		</div>

		<!-- Active incidents -->
		{#if openIncidents.length > 0}
			<section>
				<h2 class="text-lg font-semibold text-gray-800 mb-3">Active Incidents</h2>
				<div class="space-y-3">
					{#each openIncidents as incident (incident.id)}
						<div class="bg-white rounded-lg border border-gray-200 p-4">
							<div class="flex items-center justify-between mb-1">
								<span class="font-medium text-gray-900">{incident.title}</span>
								<span
									class="text-xs font-medium px-2 py-0.5 rounded-full {INCIDENT_STATUS_COLOR[
										incident.status
									]}"
								>
									{INCIDENT_STATUS_LABEL[incident.status]}
								</span>
							</div>
							{#if incident.body}
								<p class="text-sm text-gray-600 mt-1 whitespace-pre-wrap">{incident.body}</p>
							{/if}
							<p class="text-xs text-gray-400 mt-2">
								{new Date(incident.created_at).toLocaleString()}
							</p>
						</div>
					{/each}
				</div>
			</section>
		{/if}

		<!-- Services grouped -->
		<section>
			<h2 class="text-lg font-semibold text-gray-800 mb-4">Services</h2>
			{#if data.services.length === 0}
				<p class="text-gray-500 text-sm">No services configured yet.</p>
			{:else}
				<div class="space-y-5">
					{#each [...serviceGroups()] as [groupName, groupServices]}
						<div>
							<h3
								class="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2 px-1"
							>
								{groupName}
							</h3>
							<div
								class="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100"
							>
								{#each groupServices as service (service.id)}
									<div class="flex items-center justify-between px-4 py-3">
										<div>
									{#if (service as {site_url?: string | null}).site_url || ((service as {url?: string | null}).url ?? '').startsWith('https://')}
										<a
											href={(service as {site_url?: string | null}).site_url ?? (service as {url?: string | null}).url}
											target="_blank"
											rel="noopener noreferrer"
											class="font-medium text-gray-900 hover:underline"
										>{service.name}</a>
									{:else}
										<span class="font-medium text-gray-900">{service.name}</span>
									{/if}
											{#if service.description}
												<p class="text-xs text-gray-500 mt-0.5">{service.description}</p>
											{/if}
											{#if checkedAgo((service as { last_checked_at?: string | null }).last_checked_at ?? null)}
												<p class="text-xs text-gray-400 mt-0.5">
													Checked {checkedAgo((service as { last_checked_at?: string | null }).last_checked_at ?? null)}
												</p>
											{/if}
										</div>
										<div class="flex items-center gap-2 shrink-0 ml-4">
											<span
												class="h-2.5 w-2.5 rounded-full {STATUS_COLOR[service.status]}"
											></span>
											<span class="text-sm text-gray-600"
												>{STATUS_LABEL[service.status]}</span
											>
										</div>
									</div>
								{/each}
							</div>
						</div>
					{/each}
				</div>
			{/if}
		</section>

		<!-- Past incidents (resolved) -->
		{#if data.incidents.length > openIncidents.length}
			<section>
				<h2 class="text-lg font-semibold text-gray-800 mb-3">Past Incidents</h2>
				<div class="space-y-3">
					{#each data.incidents.filter((i: { status: string }) => i.status === 'resolved') as incident (incident.id)}
						<div class="bg-white rounded-lg border border-gray-200 p-4 opacity-75">
							<div class="flex items-center justify-between mb-1">
								<span class="font-medium text-gray-700">{incident.title}</span>
								<span class="text-xs font-medium px-2 py-0.5 rounded-full bg-green-100 text-green-800"
									>Resolved</span
								>
							</div>
							{#if incident.body}
								<p class="text-sm text-gray-500 mt-1 whitespace-pre-wrap">{incident.body}</p>
							{/if}
							<p class="text-xs text-gray-400 mt-2">
								{new Date(incident.created_at).toLocaleString()}
							</p>
						</div>
					{/each}
				</div>
			</section>
		{/if}
	</main>

	<footer class="text-center text-xs text-gray-400 py-6">
		<a href="/admin" class="hover:underline">Admin</a>
	</footer>
</div>
