<script>
	import { page } from '$app/state';
	import { afterNavigate } from '$app/navigation';
	import Icon from '$lib/components/Icon.svelte';
	import { NAV, ROLE_LABEL } from '$lib/roles.js';

	let { data, children } = $props();

	// Mobile: Sidebar ein-/ausklappen, nach Navigation automatisch schließen
	let menuOpen = $state(false);
	afterNavigate(() => (menuOpen = false));

	const nav = $derived(NAV[data.user.role]);
	const initials = $derived((data.user.first_name[0] + data.user.last_name[0]).toUpperCase());

	// "/" nur exakt aktiv, andere auch für Unterseiten (z.B. /subjects/3)
	const isActive = (href) =>
		href === '/' ? page.url.pathname === '/' : page.url.pathname.startsWith(href);
</script>

<div class="min-h-screen bg-surface lg:pl-64">
	<!-- Mobile Topbar -->
	<header class="sticky top-0 z-30 flex items-center justify-between border-b border-line bg-white px-4 py-3 lg:hidden">
		<img src="/EduDeviceFlow.png" alt="EduDevice" class="h-8 w-auto" />
		<button class="rounded-lg p-2 hover:bg-surface" onclick={() => (menuOpen = true)} aria-label="Open menu">
			<Icon name="menu" class="size-5" />
		</button>
	</header>

	{#if menuOpen}
		<button class="fixed inset-0 z-40 bg-navy/30 lg:hidden" onclick={() => (menuOpen = false)} aria-label="Close menu"></button>
	{/if}

	<!-- Sidebar -->
	<aside
		class="bg-dash-gradient-vertical fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-sidebar-border px-4 py-6 transition-transform
		{menuOpen ? 'translate-x-0' : '-translate-x-full'} lg:translate-x-0"
	>
		<div class="flex items-center justify-between px-2">
			<a href="/"><img src="/EduDeviceFlow.png" alt="EduDevice" class="h-15 w-auto" /></a>
			<button class="rounded-lg p-1.5 lg:hidden" onclick={() => (menuOpen = false)} aria-label="Close menu">
				<Icon name="x" class="size-5" />
			</button>
		</div>

		<nav class="mt-10 flex-1">
			<p class="mb-2 px-3 text-[11px] font-semibold tracking-wider text-subtle uppercase">{nav.section}</p>
			<ul class="space-y-1">
				{#each nav.items as item (item.href)}
					<li>
						<a
							href={item.href}
							class="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition
							{isActive(item.href)
								? 'bg-white text-accent-dark shadow-[0_2px_8px_rgb(67_56_150/0.12)]'
								: 'text-navy hover:bg-white/55'}"
						>
							<Icon name={item.icon} />
							{item.label}
						</a>
					</li>
				{/each}
			</ul>
		</nav>

		<!-- User-Karte unten -->
				<div class="flex items-center gap-3 rounded-xl border border-white/60 bg-white/55 p-3">
			<span class="bg-brand-gradient grid size-10 shrink-0 place-items-center rounded-full text-sm font-semibold text-white">
				{initials}
			</span>
			<div class="min-w-0">
				<p class="truncate text-sm font-semibold">{data.user.first_name} {data.user.last_name}</p>
				<p class="truncate text-xs text-subtle">{ROLE_LABEL[data.user.role]}</p>
			</div>
		</div>
	</aside>

	<!-- Seiteninhalt -->
	<main class="mx-auto max-w-6xl px-4 py-6 sm:px-8 sm:py-8">
		{@render children()}
	</main>
</div>