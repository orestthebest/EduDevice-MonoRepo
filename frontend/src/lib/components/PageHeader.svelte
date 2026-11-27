<script>
	import Icon from '$lib/components/Icon.svelte';
	import { m } from '$lib/paraglide/messages.js';

	// title = Seitentitel, subtitle = kleiner Text darunter, children = optionale Buttons rechts
    // back = optionaler Link für den Zurück-Button (z.B. "/subjects")
	// lead = optionales Bild/Symbol links vom Titel (z.B. Fachbild)
	let { title, subtitle = '', back = '', lead, children } = $props();	
</script>

<div class="mb-4 flex items-start justify-between gap-4">
	<div class="flex items-start gap-3">
		{#if back}
			<a href={back} class="grid size-8 shrink-0 place-items-center rounded-lg border border-line bg-white transition hover:border-accent hover:text-accent-dark" aria-label={m.back()}>
				<Icon name="back" />
			</a>
		{/if}
		{@render lead?.()}
		<div>
			<h1 class="text-xl leading-8 font-bold">{title}</h1>
			{#if subtitle}<p class="text-sm text-subtle">{subtitle}</p>{/if}
		</div>
	</div>

	<div class="flex items-center gap-2">
		{@render children?.()}
		<form action="/logout?/logout" method="POST">
			<button
				type="submit"
				class="grid size-8 cursor-pointer place-items-center rounded-lg border border-line bg-white transition hover:border-accent hover:text-accent-dark"
				title={m.logout()} aria-label={m.logout()}
			>
				<Icon name="logout" />
			</button>
		</form>
	</div>
</div>