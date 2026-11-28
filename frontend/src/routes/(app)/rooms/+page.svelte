<script>
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { m } from '$lib/paraglide/messages.js';

	let { data, form } = $props();

	let editingId = $state(null); // Raum, der gerade bearbeitet wird
	let busy = $state(false);

	// Für alle Formulare: während des Speicherns sperren, danach Bearbeiten beenden
	function submit() {
		busy = true;
		return async ({ result, update }) => {
			await update();
			busy = false;
			if (result.type === 'success') editingId = null;
		};
	}
</script>

<svelte:head>
	<title>{m.nav_rooms()} · EduDevice</title>
</svelte:head>

<PageHeader title={m.nav_rooms()} subtitle={m.rooms_subtitle()} />

{#if data.missing}
	<p class="mb-3 rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm">{m.rooms_missing()}</p>
{/if}

<!-- Neuer Raum: Name + Plätze in einer Zeile -->
<section class="rounded-xl border border-line bg-white p-4 sm:p-5">
	<h2 class="text-base font-semibold">{m.rooms_add()}</h2>
	<form method="POST" action="?/create" use:enhance={submit} class="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
		<div class="flex-1">
			<label for="room-name" class="label">{m.rooms_name()}</label>
			<input id="room-name" name="name" maxlength="50" required class="input" placeholder={m.tt_room_placeholder()} />
		</div>
		<div class="sm:w-40">
			<label for="room-capacity" class="label">{m.rooms_capacity()} <span class="font-normal text-subtle">{m.optional()}</span></label>
			<input id="room-capacity" name="capacity" type="number" min="1" max="500" class="input" />
		</div>
		<button type="submit" class="btn-primary inline-flex items-center justify-center gap-1.5 sm:w-auto sm:px-5" disabled={busy || data.missing}>
			<Icon name="plus" /> {m.rooms_add()}
		</button>
	</form>
	{#if form?.error}
		<p class="mt-3 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.error}</p>
	{/if}
</section>

<!-- Alle Räume -->
<section class="mt-4 rounded-xl border border-line bg-white p-4 sm:p-5">
	<h2 class="text-base font-semibold">{m.rooms_all({ n: data.rooms.length })}</h2>

	{#if form?.listError}
		<p class="mt-3 rounded-lg border border-error/30 bg-error/10 px-3 py-2 text-sm text-error">{form.listError}</p>
	{/if}

	{#if data.rooms.length === 0}
		<p class="mt-3 rounded-lg bg-surface px-3 py-4 text-center text-sm text-subtle">{m.rooms_none()}</p>
	{:else}
		<ul class="mt-1 divide-y divide-divider">
			{#each data.rooms as r (r.id)}
				<li class="py-2">
					{#if editingId === r.id}
						<!-- Bearbeiten direkt in der Zeile -->
						<form method="POST" action="?/update" use:enhance={submit} class="flex flex-wrap items-center gap-2">
							<input type="hidden" name="id" value={r.id} />
							<input name="name" value={r.name} maxlength="50" required aria-label={m.rooms_name()} class="input min-w-32 flex-1" />
							<input name="capacity" type="number" min="1" max="500" value={r.capacity ?? ''}
								aria-label={m.rooms_capacity()} placeholder={m.rooms_capacity()} class="input w-28" />
							<button type="submit" disabled={busy}
								class="cursor-pointer rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white transition hover:bg-accent-dark disabled:opacity-40">
								{m.save()}
							</button>
							<button type="button" onclick={() => (editingId = null)}
								class="cursor-pointer rounded-lg border border-ghost px-3 py-2 text-sm font-medium transition hover:border-accent">
								{m.cancel()}
							</button>
						</form>
					{:else}
						<div class="flex items-center gap-3">
							<span class="grid size-8 shrink-0 place-items-center rounded-lg bg-surface text-navy">
								<Icon name="door" />
							</span>
							<span class="min-w-0 flex-1 truncate text-sm font-medium">{r.name}</span>
							{#if r.capacity}
								<span class="text-xs text-subtle">{m.rooms_seats({ n: r.capacity })}</span>
							{/if}
							<button type="button" onclick={() => (editingId = r.id)} aria-label={m.rooms_edit({ name: r.name })} title={m.rooms_edit({ name: r.name })}
								class="grid size-7 cursor-pointer place-items-center rounded-md border border-ghost text-subtle transition hover:border-accent hover:text-accent-dark">
								<Icon name="pencil" class="size-3.5" />
							</button>
							<form method="POST" action="?/delete" use:enhance={submit}>
								<input type="hidden" name="id" value={r.id} />
								<button type="submit" disabled={busy} aria-label={m.rooms_delete({ name: r.name })} title={m.rooms_delete({ name: r.name })}
									class="grid size-7 cursor-pointer place-items-center rounded-md border border-ghost text-subtle transition hover:border-error hover:text-error">
									<Icon name="trash" class="size-3.5" />
								</button>
							</form>
						</div>
					{/if}
				</li>
			{/each}
		</ul>
	{/if}
</section>