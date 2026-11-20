<script>
	// children = das Formular (Login oder Register)
	let { children } = $props();

	import { m } from '$lib/paraglide/messages.js';
	import { locales, getLocale, setLocale } from '$lib/paraglide/runtime.js';
</script>

<div class="grid min-h-screen lg:grid-cols-[42%_1fr]">

	<!-- Linke Seite: Marken-Verlauf mit Slogan (nur auf großen Bildschirmen) -->
	<aside class="bg-brand-gradient hidden flex-col justify-center px-16 py-12 text-white lg:flex">
		<h2 class="max-w-md text-5xl leading-[1.1] font-bold tracking-tight">
			{m.auth_slogan()}
		</h2>
		<p class="mt-6 max-w-sm text-white/85">
			{m.auth_subslogan()}
		</p>
	</aside>

	<!-- Rechte Seite: Logo oben rechts, Formular in der Mitte -->
	<main class="flex min-h-screen flex-col bg-white px-6 py-6 sm:px-10 sm:py-8">
		<div class="flex items-center justify-between">
			<!-- Sprachauswahl: setLocale speichert die Sprache im Cookie und lädt die Seite neu -->
			<div class="flex gap-1 rounded-lg border border-ghost p-1" role="group" aria-label={m.language()}>
				{#each locales as locale (locale)}
					<button
						type="button"
						onclick={() => setLocale(locale)}
						class="rounded-md px-2.5 py-1 text-xs font-semibold uppercase transition
						{getLocale() === locale
							? 'bg-accent-xlight text-accent-dark'
							: 'text-subtle hover:text-navy'}"
					>
						{locale}
					</button>
				{/each}
			</div>
			<img src="/EduDeviceFlow.png" alt="EduDevice" class="h-12 w-auto sm:h-16" />
		</div>
			<div class="flex flex-1 items-center justify-center py-10">
			<div class="w-full max-w-md">
				{@render children()}
			</div>
		</div>
	</main>
</div>