<script>
	import Icon from '$lib/components/Icon.svelte';
	import { EXCUSE_STATUS, formatRange } from '$lib/excuses.js';

	// data.user kommt aus +layout.server.js
	let { data } = $props();

	// Begrüßung je nach Tageszeit
	const hour = new Date().getHours();
	const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';

	// Datum z.B. "Friday, 2 October"
	const now = new Date();
	const today = `${now.toLocaleDateString('en-GB', { weekday: 'long' })}, ${now.toLocaleDateString('en-GB', { day: 'numeric', month: 'long' })}`;

	// Text unter der Begrüßung je nach Rolle
	const intro = {
		schueler: 'Here are the latest materials from your subjects.',
		lehrkraft: 'Upload and manage materials for your subjects.',
		admin: 'Manage classes and subjects of the platform.'
	};

	// Materialien kommen in Schritt 3 aus der DB
	const recentMaterials = $derived(data.recentMaterials ?? []);
</script>

<svelte:head>
	<title>Dashboard · EduDevice</title>
</svelte:head>

<!-- Kopfzeile: Titel + Logout -->
<div class="mb-6 flex items-start justify-between">
	<div>
		<h1 class="text-2xl font-bold">Dashboard</h1>
		<p class="text-sm text-subtle">Your overview for today</p>
	</div>

	<form action="/logout?/logout" method="POST">
		<button
			type="submit"
			class="grid size-10 cursor-pointer place-items-center rounded-xl border border-line bg-white transition hover:border-accent hover:text-accent-dark"
			title="Log out" aria-label="Log out"
		>
			<Icon name="logout" />
		</button>
	</form>
</div>

<!-- Begrüßungs-Banner -->
<section class="bg-dash-gradient flex items-center justify-between gap-6 rounded-2xl border border-sidebar-border px-8 py-7">
	<div>
		<p class="text-sm font-semibold text-accent-dark">{today}</p>
		<h2 class="mt-1 text-3xl font-bold">{greeting}, {data.user.first_name}</h2>
		<p class="mt-2 text-subtle">{intro[data.user.role]}</p>
	</div>
	<a href="/subjects"
		class="inline-flex shrink-0 items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white transition hover:bg-accent-dark">
		Open subjects <Icon name="arrow" />
	</a>
</section>
<!-- Entschuldigungen: Schüler sehen offene Fehlstunden, Klassenvorstände offene Anträge -->
{#if data.excuses}
	{@const ex = data.excuses}
	<section class="mt-6 rounded-2xl border border-line bg-white p-6">
		<div class="mb-4 flex items-center justify-between">
			<h2 class="text-lg font-semibold">{data.user.role === 'schueler' ? 'Excuses' : 'Pending excuses'}</h2>
			<a href={data.user.role === 'schueler' ? '/excuses' : '/excuses/review'}
				class="rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
				{data.user.role === 'schueler' ? 'Open excuses' : 'View all'}
			</a>
		</div>

		{#if data.user.role === 'schueler'}
			<div class="grid gap-3 sm:grid-cols-3">
				<div class="rounded-xl bg-surface p-4">
					<p class="text-2xl font-bold {ex.unexcused > 0 ? 'text-[#b4730f]' : ''}">{ex.unexcused}</p>
					<p class="text-xs text-subtle">Unexcused {ex.unexcused === 1 ? 'lesson' : 'lessons'}</p>
				</div>
				<div class="rounded-xl bg-surface p-4">
					<p class="text-2xl font-bold">{ex.pending}</p>
					<p class="text-xs text-subtle">Waiting for review</p>
				</div>
				<div class="rounded-xl bg-surface p-4">
					{#if ex.latest}
						<span class="rounded-full px-2.5 py-0.5 text-xs font-semibold {EXCUSE_STATUS[ex.latest.status].class}">
							{EXCUSE_STATUS[ex.latest.status].label}
						</span>
						<p class="mt-2 text-xs text-subtle">Latest: {formatRange(ex.latest.date_from, ex.latest.date_to)}</p>
					{:else}
						<p class="text-sm font-medium">–</p>
						<p class="text-xs text-subtle">No excuses yet</p>
					{/if}
				</div>
			</div>
		{:else if ex.pending === 0}
			<p class="rounded-xl bg-surface px-4 py-6 text-center text-sm text-subtle">No excuses waiting for review.</p>
		{:else}
			<p class="mb-2 text-sm text-subtle">{ex.pending} waiting</p>
			<ul class="divide-y divide-divider">
				{#each ex.latest as e (e.id)}
					<li class="flex items-center justify-between gap-3 py-2.5 text-sm">
						<span class="font-medium">{e.student_name} <span class="font-normal text-subtle">· {e.class_name}</span></span>
						<span class="text-xs text-subtle">{formatRange(e.date_from, e.date_to)}</span>
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}

<!-- Zuletzt hochgeladene Materialien -->
<section class="mt-6 rounded-2xl border border-line bg-white p-6">
	<div class="mb-4 flex items-center justify-between">
		<h2 class="text-lg font-semibold">Recent materials</h2>
		<a href="/subjects"
			class="rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
			Browse subjects
		</a>
	</div>

	{#if recentMaterials.length === 0}
		<p class="rounded-xl bg-surface px-4 py-8 text-center text-sm text-subtle">No materials uploaded yet.</p>
	{:else}
		<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
			{#each recentMaterials as m (m.id)}
				<a href="/materials/{m.id}" class="flex items-center gap-3 rounded-xl bg-surface p-3 transition hover:bg-accent-light">
					<span class="grid size-10 shrink-0 place-items-center rounded-lg bg-white text-subtle">
						<Icon name="file" />
					</span>
					<div class="min-w-0">
						<p class="truncate text-sm font-semibold">{m.title}</p>
						<p class="truncate text-xs text-subtle">{m.subject_name} · {m.ext.toUpperCase()}</p>
					</div>
				</a>
			{/each}
		</div>
	{/if}
</section>