<script lang="ts">
	import { enhance } from '$app/forms';
	import type { PageData } from './$types';
	import type { Service } from '$lib/types';

	let { data }: { data: PageData } = $props();

	const SERVICE_STATUSES = ['operational', 'degraded', 'outage', 'offline'] as const;
	const INCIDENT_STATUSES = ['investigating', 'identified', 'monitoring', 'resolved'] as const;

	const STATUS_COLOR: Record<string, string> = {
		operational: 'text-green-600',
		degraded: 'text-yellow-600',
		outage: 'text-red-600',
		offline: 'text-gray-500'
	};

	let editingService: Service | null = $state(null);
	let editingIncident: (typeof data.incidents)[number] | null = $state(null);
	let newCheckType: string = $state('http');
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
					name="site_url"
					placeholder="Site URL (optional, shown as link)"
					class="border border-gray-300 rounded px-3 py-2 text-sm sm:col-span-2"
				/>
				<input
					name="group"
					placeholder="Group (e.g. Personal)"
					class="border border-gray-300 rounded px-3 py-2 text-sm sm:col-span-2"
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
					<label class="flex items-center gap-2 text-sm text-gray-700">
						<input type="checkbox" name="muted" value="true" class="rounded" />
						Muted
					</label>
					<label class="flex items-center gap-2 text-sm text-gray-700">
						<input type="checkbox" name="voice_call" value="true" class="rounded" />
						Call on outage
					</label>
				<label class="flex items-center gap-2 text-sm text-gray-700 sm:col-span-2">
					Failure threshold
					<input
						type="number"
						name="failure_threshold"
						value="2"
						min="1"
						class="border border-gray-300 rounded px-3 py-2 text-sm w-20"
					/>
				</label>
				</div>
				<div class="sm:col-span-4 space-y-2">
					<select
						name="check_type"
						bind:value={newCheckType}
						class="border border-gray-300 rounded px-3 py-2 text-sm"
					>
						<option value="http">HTTP</option>
						<option value="command">Command</option>
					</select>
					{#if newCheckType === 'command'}
						<textarea
							name="check_command"
							placeholder="Shell command (exit 0 = up)"
							rows="3"
							class="w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono resize-y"
						></textarea>
					{/if}
				</div>
				<div class="sm:col-span-4 flex justify-end">
					<button
						type="submit"
						class="bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 text-sm font-medium"
					>
						Add service
					</button>
				</div>
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
								name="site_url"
								value={editingService.site_url ?? ''}
								placeholder="Site URL"
								class="border border-gray-300 rounded px-3 py-1.5 text-sm sm:col-span-2"
							/>
								<input
									name="group"
									value={editingService.group ?? ''}
									placeholder="Group"
									class="border border-gray-300 rounded px-3 py-1.5 text-sm sm:col-span-2"
								/>
								<div class="flex items-center gap-4 sm:col-span-4">
									<label class="flex items-center gap-2 text-sm text-gray-700">
										<input type="checkbox" name="is_public" value="true" checked={editingService.is_public !== false} class="rounded" />
										Public
									</label>
									<label class="flex items-center gap-2 text-sm text-gray-700">
										<input type="checkbox" name="check_enabled" value="true" checked={editingService.check_enabled !== false} class="rounded" />
										Health check
									</label>
									<label class="flex items-center gap-2 text-sm text-gray-700">
									<input type="checkbox" name="muted" value="true" checked={editingService.muted === true} class="rounded" />
									Muted
									</label>
									<label class="flex items-center gap-2 text-sm text-gray-700">
									<input type="checkbox" name="voice_call" value="true" checked={editingService.voice_call === true} class="rounded" />
									Call on outage
									</label>
						<label class="flex items-center gap-2 text-sm text-gray-700 sm:col-span-2">
							Failure threshold
							<input
								type="number"
								name="failure_threshold"
								value={editingService.failure_threshold ?? 2}
								min="1"
								class="border border-gray-300 rounded px-3 py-1.5 text-sm w-20"
							/>
						</label>
								</div>
								<div class="sm:col-span-4 space-y-2">
									<select
										name="check_type"
										bind:value={editingService.check_type}
										class="border border-gray-300 rounded px-3 py-1.5 text-sm"
									>
										<option value="http">HTTP</option>
										<option value="command">Command</option>
									</select>
									{#if editingService.check_type === 'command'}
										<textarea
											name="check_command"
											rows="3"
											class="w-full border border-gray-300 rounded px-3 py-1.5 text-sm font-mono resize-y"
										>{editingService.check_command ?? ''}</textarea>
									{/if}
								</div>
								<div class="flex gap-2 sm:col-span-4">
									<button
										type="submit"
										class="bg-blue-600 hover:bg-blue-700 text-white rounded px-3 py-1.5 text-sm"
										>Save</button>
									<button
										type="button"
										onclick={() => (editingService = null)}
										class="border border-gray-300 rounded px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-50"
										>Cancel</button>
								</div>
								</form>
							{:else}
								<div class="flex items-start justify-between gap-4">
									<div class="min-w-0 flex-1">
										{#if service.site_url || (service.url ?? '').startsWith('https://')}
											<a
												href={service.site_url ?? service.url}
												target="_blank"
												rel="noopener noreferrer"
												class="font-medium text-gray-900 hover:underline"
											>{service.name}</a>
										{:else}
											<span class="font-medium text-gray-900">{service.name}</span>
										{/if}
										{#if service.description}
											<p class="text-xs text-gray-500">{service.description}</p>
										{/if}
										{#if service.group}
											<p class="text-xs text-gray-400 mt-0.5">Group: {service.group}</p>
										{/if}
										{#if service.url}
											<p class="text-xs text-gray-400 mt-0.5 font-mono truncate">{service.url}</p>
										{/if}
										{#if service.last_checked_at}
											<p class="text-xs text-gray-400 mt-0.5">Last checked: {new Date(service.last_checked_at).toLocaleTimeString()}</p>
										{/if}
										<div class="flex flex-wrap gap-1 mt-1">
											{#if !service.is_public}
												<span class="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">Private</span>
											{/if}
											{#if !service.check_enabled}
												<span class="text-xs px-1.5 py-0.5 rounded bg-yellow-50 text-yellow-700">Checks off</span>
											{/if}
									{#if service.muted}
										<span class="text-xs px-1.5 py-0.5 rounded bg-blue-50 text-blue-600">Muted</span>
											{/if}
											{#if service.check_type === 'command'}
												<span class="text-xs px-1.5 py-0.5 rounded bg-purple-50 text-purple-700">Command check</span>
											{/if}
											{#if service.voice_call}
												<span class="text-xs px-1.5 py-0.5 rounded bg-orange-50 text-orange-700">Phone alert</span>
											{/if}
										</div>
									</div>
									<div class="flex items-center gap-3 shrink-0">
										<span class="text-sm {STATUS_COLOR[service.status]}">{service.status}</span>
										<button
											onclick={() => (editingService = { ...service })}
											class="text-xs text-blue-600 hover:underline">Edit</button>
										<form method="POST" action="?/deleteService" use:enhance>
											<input type="hidden" name="id" value={service.id} />
											<button
												type="submit"
												onclick={(e) => { if (!confirm('Delete this service?')) e.preventDefault(); }}
												class="text-xs text-red-500 hover:underline">Delete</button>
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

		<!-- ── Notifications ────────────────────────────────────────── -->
		<section>
			<h2 class="text-lg font-semibold text-gray-800 mb-4">Notifications</h2>
			<div class="space-y-8">

				<!-- Email Subscribers -->
				<div class="bg-white rounded-lg border border-gray-200 p-4">
					<h3 class="text-base font-medium text-gray-700 mb-3">Email Subscribers</h3>
					<form method="POST" action="?/addEmailSubscriber" use:enhance class="flex gap-2 mb-4">
						<input name="email" type="email" required placeholder="email@example.com" class="border border-gray-300 rounded px-3 py-2 text-sm flex-1" />
						<button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 text-sm font-medium">Add</button>
					</form>
					{#if data.emailSubscribers.length === 0}
						<p class="text-gray-400 text-sm">None configured.</p>
					{:else}
						<ul class="divide-y divide-gray-100">
							{#each data.emailSubscribers as sub (sub.id)}
								<li class="flex items-center justify-between py-2">
									<span class="text-sm text-gray-800">{sub.email}</span>
									<form method="POST" action="?/deleteEmailSubscriber" use:enhance>
										<input type="hidden" name="id" value={sub.id} />
										<button type="submit" class="text-xs text-red-500 hover:underline">Delete</button>
									</form>
								</li>
							{/each}
						</ul>
					{/if}
				</div>

				<!-- Telegram -->
				<div class="bg-white rounded-lg border border-gray-200 p-4">
					<h3 class="text-base font-medium text-gray-700 mb-3">Telegram</h3>
					<form method="POST" action="?/saveTelegram" use:enhance class="flex flex-col gap-3">
						<div class="flex items-center gap-2">
							<input type="password" name="bot_token" placeholder="Bot token (leave blank to keep)" class="border border-gray-300 rounded px-3 py-2 text-sm flex-1" />
							{#if data.notifSettings.telegram.bot_token_set}
								<span class="text-xs text-gray-500">(configured)</span>
							{/if}
						</div>
						<input name="chat_id" placeholder="Chat ID" value={data.notifSettings.telegram.chat_id ?? ''} class="border border-gray-300 rounded px-3 py-2 text-sm" />
						<div class="flex justify-end">
							<button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 text-sm font-medium">Save</button>
						</div>
					</form>
				</div>

				<!-- Voice calls -->
				<div class="bg-white rounded-lg border border-gray-200 p-4">
					<h3 class="text-base font-medium text-gray-700 mb-3">Phone call (SIP + TTS)</h3>
					<form method="POST" action="?/saveVoice" use:enhance class="flex flex-col gap-3">
						<label class="flex items-center gap-2 text-sm text-gray-700">
							<input type="checkbox" name="enabled" value="true" checked={data.notifSettings.voice.enabled} class="rounded" />
							Call my mobile when a service stays down
						</label>
						<div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
							<label class="text-sm text-gray-600">Mobile number (E.164)
								<input name="destination" value={data.notifSettings.voice.destination ?? ''} placeholder="+491701234567" class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm" />
							</label>
							<label class="text-sm text-gray-600">Escalation schedule (e.g. 5m,30m,2h,6h,24h)
								<input name="escalation_schedule" value={data.notifSettings.voice.escalation_schedule ?? '5m,30m,2h,6h,24h'} placeholder="5m,30m,2h,6h,24h" class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm" />
							</label>
							<label class="text-sm text-gray-600">SIP number (caller ID)
								<input name="sip_number" value={data.notifSettings.voice.sip_number ?? ''} placeholder="+4952517090538" class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm" />
							</label>
							<label class="text-sm text-gray-600">SIP auth username
								<input name="sip_auth_username" value={data.notifSettings.voice.sip_auth_username ?? ''} placeholder="IMPI_4952517090538" class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm" />
							</label>
							<label class="text-sm text-gray-600">SIP password
								<input type="password" name="sip_password" placeholder={data.notifSettings.voice.sip_password_set ? '(configured — leave blank to keep)' : 'password'} class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm" />
							</label>
							<label class="text-sm text-gray-600">SIP registrar
								<input name="sip_registrar" value={data.notifSettings.voice.sip_registrar ?? ''} placeholder="fixed.vodafone.de" class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm" />
							</label>
							<label class="text-sm text-gray-600">SIP proxy / outbound (optional)
								<input name="sip_proxy" value={data.notifSettings.voice.sip_proxy ?? ''} placeholder="egf12.fixed.vodafone.de" class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm" />
							</label>
							<label class="text-sm text-gray-600">DNS server (optional)
								<input name="dns_server" value={data.notifSettings.voice.dns_server ?? ''} placeholder="1.1.1.1" class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm" />
							</label>
							<label class="text-sm text-gray-600">TTS engine
								<select name="tts_engine" class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm">
									<option value="piper" selected={(data.notifSettings.voice.tts_engine ?? 'piper') === 'piper'}>Piper (neural)</option>
									<option value="espeak-ng" selected={data.notifSettings.voice.tts_engine === 'espeak-ng'}>espeak-ng (fallback)</option>
								</select>
							</label>
							<label class="text-sm text-gray-600">Piper model path (optional)
								<input name="tts_model" value={data.notifSettings.voice.tts_model ?? ''} placeholder="defaults to STATUSPAGE_PIPER_MODEL" class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm" />
							</label>
							<label class="text-sm text-gray-600">TTS language (espeak fallback)
								<input name="tts_language" value={data.notifSettings.voice.tts_language ?? 'de'} placeholder="de" class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm" />
							</label>
							<label class="text-sm text-gray-600">Minimum repeats (then loops until you hang up)
								<input type="number" name="repeat_count" min="1" max="10" value={data.notifSettings.voice.repeat_count ?? 3} class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm" />
							</label>
							<label class="text-sm text-gray-600">Pause between repeats (seconds)
								<input type="number" name="repeat_pause_seconds" min="0" max="10" step="0.1" value={data.notifSettings.voice.repeat_pause_seconds ?? 0.8} class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm" />
							</label>
							<label class="text-sm text-gray-600">Stop after (minutes)
								<input type="number" name="max_call_minutes" min="1" max="60" value={Math.round((data.notifSettings.voice.max_call_seconds ?? 600) / 60)} class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm" />
							</label>
						</div>
						<label class="text-sm text-gray-600">Message template (optional)
							<textarea name="message_template" rows="2" placeholder={'Achtung. Statusseite {instance}. {services} seit {minutes} Minuten nicht erreichbar.'} class="mt-1 w-full border border-gray-300 rounded px-3 py-2 text-sm font-mono">{data.notifSettings.voice.message_template ?? ''}</textarea>
						</label>
						<p class="text-xs text-gray-400">Placeholders: {'{services}'}, {'{instance}'}, {'{minutes}'}. {'{services}'} includes the URL and last check error. One call at each schedule step; each call repeats until you hang up (or the stop-after limit).</p>
						<div class="flex justify-end">
							<button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 text-sm font-medium">Save</button>
						</div>
					</form>
					<form method="POST" action="?/testVoiceCall" use:enhance class="flex justify-end mt-2">
						<button type="submit" class="border border-gray-300 rounded px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">Call me now (test)</button>
					</form>
				</div>

				<!-- Discord -->
				<div class="bg-white rounded-lg border border-gray-200 p-4">
					<h3 class="text-base font-medium text-gray-700 mb-3">Discord</h3>
					<form method="POST" action="?/saveDiscord" use:enhance class="flex flex-col gap-3 mb-6">
						<div class="flex items-center gap-2">
							<input type="password" name="bot_token" placeholder="Bot token (leave blank to keep)" class="border border-gray-300 rounded px-3 py-2 text-sm flex-1" />
							{#if data.notifSettings.discord.bot_token_set}
								<span class="text-xs text-gray-500">(configured)</span>
							{/if}
						</div>
						<div class="flex justify-end">
							<button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 text-sm font-medium">Save</button>
						</div>
					</form>
					{#if data.notifSettings.discord.app_id}
						<a
							href="https://discord.com/oauth2/authorize?client_id={data.notifSettings.discord.app_id}&scope=bot&permissions=0"
							target="_blank"
							rel="noopener noreferrer"
							class="inline-flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-800 underline mb-4 block"
						>Invite bot to server</a>
					{/if}
					<h4 class="text-sm font-medium text-gray-700 mb-2">Destinations</h4>
					<form method="POST" action="?/addDiscordDestination" use:enhance class="flex flex-wrap gap-2 mb-4">
						<select name="destination_type" class="border border-gray-300 rounded px-3 py-2 text-sm">
							<option value="channel">channel</option>
							<option value="user">user</option>
						</select>
						<input name="destination_id" required placeholder="Channel or User ID" class="border border-gray-300 rounded px-3 py-2 text-sm flex-1" />
						<input name="label" placeholder="Label (optional)" class="border border-gray-300 rounded px-3 py-2 text-sm" />
						<button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white rounded px-4 py-2 text-sm font-medium">Add</button>
					</form>
					{#if data.discordDestinations.length === 0}
						<p class="text-gray-400 text-sm">None configured.</p>
					{:else}
						<ul class="divide-y divide-gray-100">
							{#each data.discordDestinations as dest (dest.id)}
								<li class="flex items-center justify-between py-2">
									<div class="flex items-center gap-2">
										<span class="text-sm text-gray-800">{dest.label ?? dest.destination_id}</span>
										<span class="text-xs px-1.5 py-0.5 rounded bg-gray-100 text-gray-500">{dest.destination_type}</span>
									</div>
									<form method="POST" action="?/deleteDiscordDestination" use:enhance>
										<input type="hidden" name="id" value={dest.id} />
										<button type="submit" class="text-xs text-red-500 hover:underline">Delete</button>
									</form>
								</li>
							{/each}
						</ul>
					{/if}
				</div>

			</div>
		</section>
</main>
