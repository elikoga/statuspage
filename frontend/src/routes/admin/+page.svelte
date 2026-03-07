<script lang="ts">
	import { enhance } from '$app/forms';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const SERVICE_STATUSES = ['operational', 'degraded', 'outage', 'offline'] as const;
	const INCIDENT_STATUSES = ['investigating', 'identified', 'monitoring', 'resolved'] as const;

	const STATUS_COLOR: Record<string, string> = {
		operational: 'text-green-600',
		degraded: 'text-yellow-600',
		outage: 'text-red-600',
		offline: 'text-gray-500'
	};

	let editingService: (typeof data.services)[number] | null = $state(null);
	let editingIncident: (typeof data.incidents)[number] | null = $state(null);
</script>

<svelte:head>
	<title>Admin — Status Page</title>
</svelte:head>

<main class="mx-auto max-w-4xl px-4 py-8 space-y-12">
		<!-- ── Services ────────────────────────────────────────────── -->
		<section>
			<h2 class="text-lg font-semibold text-gray-800 mb-4">Services</h2>

			<!-- Create service -->
			<form
				method="POST"
				action="?/createService"
				use:enhance
				class="bg-white rounded-lg border border-gray-200 p-4 mb-4 grid grid-cols-1 sm:grid-cols-4 gap-3"
			>
				<input
					name="name"
					required
					placeholder="Name"
					class="border border-gray-300 rounded px-3 py-2 text-sm col-span-1"
				/>
				<input
					name="description"
					placeholder="Description (optional)"
					class="border border-gray-300 rounded px-3 py-2 text-sm sm:col-span-2"
				/>
				<select
					name="status"
					class="border border-gray-300 rounded px-3 py-2 text-sm"
				>
					{#each SERVICE_STATUSES as s}
						<option value={s}>{s}</option>
					{/each}
				</select>
				<input
					name="url"
					placeholder="URL (optional)"
					class="border border-gray-300 rounded px-3 py-2 text-sm sm:col-span-2"
				/>
				<input
					name="group"
					placeholder="Group (e.g. Personal)"
					class="border border-gray-300 rounded px-3 py-2 text-sm"
				/>
				<div class="flex items-center gap-4 sm:col-span-4">
					<label class="flex items-center gap-2 text-sm text-gray-700">
						<input type="checkbox" name="is_public" value="true" checked class="rounded" />
						Public
					</label>
					<label class="flex items-center gap-2 text-sm text-gray-700">
						<input type="checkbox" name="check_enabled" value="true" checked class="rounded" />
						Health check
					</label>
				</div>
				<button
					type="submit"
					class="bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 text-sm font-medium"
				>
					Add service
				</button>
			</form>

			<!-- Service list -->
			{#if data.services.length === 0}
				<p class="text-gray-400 text-sm">No services yet.</p>
			{:else}
				<div class="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100">
					{#each data.services as service (service.id)}
						<div class="px-4 py-3">
							{#if editingService?.id === service.id}
								<form
									method="POST"
									action="?/updateService"
									use:enhance={() => () => { editingService = null; }}
									class="grid grid-cols-1 sm:grid-cols-4 gap-2"
								>
									<input type="hidden" name="id" value={service.id} />
									<input
										name="name"
										value={editingService.name}
										required
										class="border border-gray-300 rounded px-3 py-1.5 text-sm"
									/>
									<input
										name="description"
										value={editingService.description ?? ''}
										placeholder="Description"
										class="border border-gray-300 rounded px-3 py-1.5 text-sm sm:col-span-2"
									/>
									<select name="status" class="border border-gray-300 rounded px-3 py-1.5 text-sm">
										{#each SERVICE_STATUSES as s}
											<option value={s} selected={s === editingService.status}>{s}</option>
										{/each}
									</select>
								<input
									name="url"
									value={editingService.url ?? ''}
									placeholder="URL"
									class="border border-gray-300 rounded px-3 py-1.5 text-sm sm:col-span-2"
								/>
								<input
									name="group"
									value={(editingService as {group?: string | null}).group ?? ''}
									placeholder="Group"
									class="border border-gray-300 rounded px-3 py-1.5 text-sm sm:col-span-2"
								/>
								<div class="flex items-center gap-4 sm:col-span-4">
									<label class="flex items-center gap-2 text-sm text-gray-700">
										<input type="checkbox" name="is_public" value="true" checked={(editingService as {is_public?: boolean}).is_public !== false} class="rounded" />
										Public
									</label>
									<label class="flex items-center gap-2 text-sm text-gray-700">
										<input type="checkbox" name="check_enabled" value="true" checked={(editingService as {check_enabled?: boolean}).check_enabled !== false} class="rounded" />
										Health check
									</label>
								</div>
									<div class="flex gap-2">
										<button
											type="submit"
											class="bg-blue-600 hover:bg-blue-700 text-white rounded px-3 py-1.5 text-sm"
											>Save</button
										>
										<button
											type="button"
											onclick={() => (editingService = null)}
											class="border border-gray-300 rounded px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
											>Cancel</button
										>
									</div>
								</form>
							{:else}
								<div class="flex items-center justify-between">
								<div>
									<span class="font-medium text-gray-900">{service.name}</span>
									{#if service.description}
										<p class="text-xs text-gray-500">{service.description}</p>
									{/if}
									{#if (service as {group?: string | null}).group}
										<p class="text-xs text-gray-400 mt-0.5">Group: {(service as {group?: string | null}).group}</p>
									{/if}
									{#if (service as {last_checked_at?: string | null}).last_checked_at}
										<p class="text-xs text-gray-400">Last checked: {new Date((service as {last_checked_at?: string | null}).last_checked_at!).toLocaleTimeString()}</p>
									{/if}
								{#if !(service as {is_public?: boolean}).is_public}
									<span class="inline-block text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500 mt-0.5">Private</span>
								{/if}
								{#if !(service as {check_enabled?: boolean}).check_enabled}
									<span class="inline-block text-xs px-1.5 py-0.5 rounded bg-yellow-50 text-yellow-700 mt-0.5">Checks off</span>
								{/if}
								</div>
									<div class="flex items-center gap-3">
										<span class="text-sm {STATUS_COLOR[service.status]}">{service.status}</span>
										<button
											onclick={() => (editingService = { ...service })}
											class="text-xs text-blue-600 hover:underline">Edit</button
										>
										<form method="POST" action="?/deleteService" use:enhance>
											<input type="hidden" name="id" value={service.id} />
											<button
												type="submit"
												onclick={(e) => { if (!confirm('Delete this service?')) e.preventDefault(); }}
												class="text-xs text-red-500 hover:underline">Delete</button
											>
										</form>
									</div>
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
		</section>

		<!-- ── Incidents ───────────────────────────────────────────── -->
		<section>
			<h2 class="text-lg font-semibold text-gray-800 mb-4">Incidents</h2>

			<!-- Create incident -->
			<form
				method="POST"
				action="?/createIncident"
				use:enhance
				class="bg-white rounded-lg border border-gray-200 p-4 mb-4 grid grid-cols-1 sm:grid-cols-3 gap-3"
			>
				<input
					name="title"
					required
					placeholder="Title"
					class="border border-gray-300 rounded px-3 py-2 text-sm sm:col-span-2"
				/>
				<select name="status" class="border border-gray-300 rounded px-3 py-2 text-sm">
					{#each INCIDENT_STATUSES as s}
						<option value={s}>{s}</option>
					{/each}
				</select>
				<textarea
					name="body"
					placeholder="Details (optional)"
					rows="2"
					class="border border-gray-300 rounded px-3 py-2 text-sm sm:col-span-2 resize-none"
				></textarea>
				<button
					type="submit"
					class="bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 text-sm font-medium self-end"
				>
					Create incident
				</button>
			</form>

			<!-- Incident list -->
			{#if data.incidents.length === 0}
				<p class="text-gray-400 text-sm">No incidents yet.</p>
			{:else}
				<div class="bg-white rounded-lg border border-gray-200 divide-y divide-gray-100">
					{#each data.incidents as incident (incident.id)}
						<div class="px-4 py-3">
							{#if editingIncident?.id === incident.id}
								<form
									method="POST"
									action="?/updateIncident"
									use:enhance={() => () => { editingIncident = null; }}
									class="grid grid-cols-1 sm:grid-cols-3 gap-2"
								>
									<input type="hidden" name="id" value={incident.id} />
									<input
										name="title"
										value={editingIncident.title}
										required
										class="border border-gray-300 rounded px-3 py-1.5 text-sm sm:col-span-2"
									/>
									<select
										name="status"
										class="border border-gray-300 rounded px-3 py-1.5 text-sm"
									>
										{#each INCIDENT_STATUSES as s}
											<option value={s} selected={s === editingIncident.status}>{s}</option>
										{/each}
									</select>
									<textarea
										name="body"
										rows="2"
										class="border border-gray-300 rounded px-3 py-1.5 text-sm sm:col-span-3 resize-none"
										>{editingIncident.body}</textarea
									>
									<div class="flex gap-2 sm:col-span-3">
										<button
											type="submit"
											class="bg-blue-600 hover:bg-blue-700 text-white rounded px-3 py-1.5 text-sm"
											>Save</button
										>
										<button
											type="button"
											onclick={() => (editingIncident = null)}
											class="border border-gray-300 rounded px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
											>Cancel</button
										>
									</div>
								</form>
							{:else}
								<div class="flex items-start justify-between gap-4">
									<div>
										<span class="font-medium text-gray-900">{incident.title}</span>
										<span
											class="ml-2 text-xs font-medium px-1.5 py-0.5 rounded bg-gray-100 text-gray-600"
											>{incident.status}</span
										>
										{#if incident.body}
											<p class="text-sm text-gray-500 mt-1 whitespace-pre-wrap">{incident.body}</p>
										{/if}
										<p class="text-xs text-gray-400 mt-1">
											{new Date(incident.created_at).toLocaleString()}
										</p>
									</div>
									<div class="flex gap-3 shrink-0">
										<button
											onclick={() => (editingIncident = { ...incident })}
											class="text-xs text-blue-600 hover:underline">Edit</button
										>
										<form method="POST" action="?/deleteIncident" use:enhance>
											<input type="hidden" name="id" value={incident.id} />
											<button
												type="submit"
												onclick={(e) => { if (!confirm('Delete this incident?')) e.preventDefault(); }}
												class="text-xs text-red-500 hover:underline">Delete</button
											>
										</form>
									</div>
								</div>
							{/if}
						</div>
					{/each}
				</div>
			{/if}
	</section>
</main>
