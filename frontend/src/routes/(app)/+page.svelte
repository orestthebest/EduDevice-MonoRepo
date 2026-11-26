<script>
	import Icon from '$lib/components/Icon.svelte';
	import { EXCUSE_STATUS, formatRange } from '$lib/excuses.js';
	import { periodLabel, subjectColor } from '$lib/timetable.js';
	import { m } from '$lib/paraglide/messages.js';
	import { getLocale } from '$lib/paraglide/runtime.js';

	// data.user kommt aus +layout.server.js
	let { data } = $props();

	// Begrüßung je nach Tageszeit
	const hour = new Date().getHours();
	const greeting = hour < 12 ? m.dash_good_morning : hour < 18 ? m.dash_good_afternoon : m.dash_good_evening;

	// Datum in der aktuellen Sprache, z.B. "Friday, 2 October" / "Freitag, 2. Oktober"
	const now = new Date();
	const today = now.toLocaleDateString(getLocale(), { weekday: 'long', day: 'numeric', month: 'long' });

	// Text unter der Begrüßung je nach Rolle
	const intro = {
		schueler: m.dash_intro_student,
		lehrkraft: m.dash_intro_teacher,
		admin: m.dash_intro_admin
	};

	// Jetzt als "HH:MM" -> Stunden im Stundenplan-Kärtchen als vorbei / jetzt / kommt markieren
	const nowTime = now.toTimeString().slice(0, 5);
	const lessonState = (l) => (l.cancelled ? 'cancelled' : nowTime >= l.end ? 'done' : nowTime >= l.start ? 'now' : 'next');

	// Materialien kommen in Schritt 3 aus der DB
	const recentMaterials = $derived(data.recentMaterials ?? []);
</script>

<svelte:head>
	<title>{m.nav_dashboard()} · EduDevice</title>
</svelte:head>

<!-- Kopfzeile: Titel + Logout -->
<div class="mb-6 flex items-start justify-between">
	<div>
		<h1 class="text-2xl font-bold">{m.nav_dashboard()}</h1>
		<p class="text-sm text-subtle">{m.dash_subtitle()}</p>
	</div>

	<form action="/logout?/logout" method="POST">
		<button
			type="submit"
			class="grid size-10 cursor-pointer place-items-center rounded-xl border border-line bg-white transition hover:border-accent hover:text-accent-dark"
			title={m.logout()} aria-label={m.logout()}
		>
			<Icon name="logout" />
		</button>
	</form>
</div>

<!-- Begrüßungs-Banner -->
<section class="bg-dash-gradient flex items-center justify-between gap-6 rounded-2xl border border-sidebar-border px-8 py-7">
	<div>
		<p class="text-sm font-semibold text-accent-dark">{today}</p>
		<h2 class="mt-1 text-3xl font-bold">{greeting({ name: data.user.first_name })}</h2>
		<p class="mt-2 text-subtle">{intro[data.user.role]()}</p>
	</div>
	<a href="/subjects"
		class="inline-flex shrink-0 items-center gap-2 rounded-lg bg-accent px-5 py-2.5 text-sm font-medium text-white transition hover:bg-accent-dark">
		{m.dash_open_subjects()} <Icon name="arrow" />
	</a>
</section>

<!-- Stundenplan heute (Schüler) -->
{#if data.timetable}
	{@const t = data.timetable}
	<section class="mt-6 rounded-2xl border border-line bg-white p-6">
		<div class="mb-4 flex items-center justify-between">
			<h2 class="text-lg font-semibold">{m.dash_today_timetable()}</h2>
			<a href="/timetable"
				class="rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
				{m.dash_full_timetable()}
			</a>
		</div>

		{#if t.dayOff}
			<p class="rounded-xl bg-surface px-4 py-6 text-center text-sm text-subtle">{m.dash_no_lessons()}{t.dayOff.note ? ` · ${t.dayOff.note}` : ''}.</p>
		{:else if t.lessons.length === 0}
			<p class="rounded-xl bg-surface px-4 py-6 text-center text-sm text-subtle">{m.dash_no_lessons()}.</p>
		{:else}
			<ul class="divide-y divide-divider">
				{#each t.lessons as l (`${l.from}-${l.subject}`)}
					{@const state = lessonState(l)}
					<li class="flex items-center gap-3 py-2.5 text-sm {state === 'done' || state === 'cancelled' ? 'opacity-50' : ''}">
						<span class="w-24 shrink-0 text-subtle tabular-nums">{l.start}–{l.end}</span>
						<span class="h-8 w-1 shrink-0 rounded-full" style="background: {subjectColor(l.subject)}"></span>
						<span class="min-w-0 flex-1">
							<span class="block truncate font-medium {l.cancelled ? 'line-through' : ''}">{l.subject}</span>
							<span class="block truncate text-xs text-subtle">
								{m.period()} {l.from}{l.to > l.from ? `–${l.to}` : ''}{l.room ? ` · ${l.room}` : ''}{l.teacher ? ` · ${l.teacher}` : ''}
							</span>
						</span>
						{#if state === 'now'}
							<span class="rounded-full bg-accent-light px-2.5 py-0.5 text-xs font-semibold text-accent-dark">{m.lesson_now()}</span>
						{:else if state === 'cancelled'}
							<span class="rounded-full bg-error/12 px-2.5 py-0.5 text-xs font-semibold text-error">{m.lesson_cancelled()}</span>
						{/if}
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}

<!-- Anwesenheit: heutige Stunden der Lehrkraft laut Stundenplan -->
{#if data.attendance}
	{@const open = data.attendance.lessons.filter((l) => !l.recorded).length}
	<section class="mt-6 rounded-2xl border border-line bg-white p-6">
		<div class="mb-4 flex items-center justify-between">
			<h2 class="text-lg font-semibold">{m.dash_today_attendance()}</h2>
			<a href="/attendance"
				class="rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
				{m.dash_take_attendance()}
			</a>
		</div>

		{#if data.attendance.lessons.length === 0}
			<p class="rounded-xl bg-surface px-4 py-6 text-center text-sm text-subtle">{m.dash_no_lessons()}.</p>
		{:else}
			<p class="mb-2 text-sm text-subtle">{open === 0 ? m.dash_all_recorded() : m.dash_not_recorded({ count: open })}</p>
			<ul class="divide-y divide-divider">
				{#each data.attendance.lessons as l (`${l.subjectId}-${l.start}`)}
					<li>
						<a href="/attendance?subject={l.subjectId}&date={data.attendance.date}&time={l.start}"
							class="flex items-center gap-3 py-2.5 text-sm transition hover:text-accent-dark">
							<span class="w-24 shrink-0 text-subtle">{periodLabel(l.start)}</span>
							<span class="flex-1 font-medium">
								{l.subject}
								<span class="font-normal text-subtle">· {l.className}{l.room ? ` · ${l.room}` : ''}</span>
							</span>
							<span class="rounded-full px-2.5 py-0.5 text-xs font-semibold
								{l.recorded ? 'bg-success/12 text-success-dark' : 'bg-warning/15 text-[#b4730f]'}">
								{l.recorded ? m.attendance_recorded() : m.attendance_open()}
							</span>
						</a>
					</li>
				{/each}
			</ul>
		{/if}
	</section>
{/if}
<!-- Entschuldigungen: Schüler sehen offene Fehlstunden, Klassenvorstände offene Anträge -->
{#if data.excuses}
	{@const ex = data.excuses}
	<section class="mt-6 rounded-2xl border border-line bg-white p-6">
		<div class="mb-4 flex items-center justify-between">
			<h2 class="text-lg font-semibold">{data.user.role === 'schueler' ? m.nav_excuses() : m.dash_pending_excuses()}</h2>
			<a href={data.user.role === 'schueler' ? '/excuses' : '/excuses/review'}
				class="rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
				{data.user.role === 'schueler' ? m.dash_open_excuses() : m.dash_view_all()}
			</a>
		</div>

		{#if data.user.role === 'schueler'}
			<div class="grid gap-3 sm:grid-cols-3">
				<div class="rounded-xl bg-surface p-4">
					<p class="text-2xl font-bold {ex.unexcused > 0 ? 'text-[#b4730f]' : ''}">{ex.unexcused}</p>
					<p class="text-xs text-subtle">{ex.unexcused === 1 ? m.dash_unexcused_lesson() : m.dash_unexcused_lessons()}</p>
				</div>
				<div class="rounded-xl bg-surface p-4">
					<p class="text-2xl font-bold">{ex.pending}</p>
					<p class="text-xs text-subtle">{m.dash_waiting_review()}</p>
				</div>
				<div class="rounded-xl bg-surface p-4">
					{#if ex.latest}
						<span class="rounded-full px-2.5 py-0.5 text-xs font-semibold {EXCUSE_STATUS[ex.latest.status].class}">
							{EXCUSE_STATUS[ex.latest.status].label}
						</span>
						<p class="mt-2 text-xs text-subtle">{m.dash_latest({ range: formatRange(ex.latest.date_from, ex.latest.date_to) })}</p>
					{:else}
						<p class="text-sm font-medium">–</p>
						<p class="text-xs text-subtle">{m.dash_no_excuses()}</p>
					{/if}
				</div>
			</div>
		{:else if ex.pending === 0}
			<p class="rounded-xl bg-surface px-4 py-6 text-center text-sm text-subtle">{m.dash_no_pending()}</p>
		{:else}
			<p class="mb-2 text-sm text-subtle">{m.dash_waiting({ count: ex.pending })}</p>
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
		<h2 class="text-lg font-semibold">{m.dash_recent_materials()}</h2>
		<a href="/subjects"
			class="rounded-lg border border-ghost px-3 py-1.5 text-sm font-medium transition hover:border-accent hover:text-accent-dark">
			{m.dash_browse_subjects()}
		</a>
	</div>

	{#if recentMaterials.length === 0}
		<p class="rounded-xl bg-surface px-4 py-8 text-center text-sm text-subtle">{m.dash_no_materials()}</p>
	{:else}
		<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
			{#each recentMaterials as mat (mat.id)}
				<a href="/materials/{mat.id}" class="flex items-center gap-3 rounded-xl bg-surface p-3 transition hover:bg-accent-light">
					<span class="grid size-10 shrink-0 place-items-center rounded-lg bg-white text-subtle">
						<Icon name="file" />
					</span>
					<div class="min-w-0">
						<p class="truncate text-sm font-semibold">{mat.title}</p>
						<p class="truncate text-xs text-subtle">{mat.subject_name} · {mat.ext.toUpperCase()}</p>
					</div>
				</a>
			{/each}
		</div>
	{/if}
</section>