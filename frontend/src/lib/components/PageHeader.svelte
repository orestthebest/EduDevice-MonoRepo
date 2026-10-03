<script>
	import Icon from '$lib/components/Icon.svelte';

	// title = Seitentitel, subtitle = kleiner Text darunter, children = optionale Buttons rechts
	let { title, subtitle = '', children } = $props();
</script>

<div class="mb-6 flex items-start justify-between gap-4">
	<div>
		<h1 class="text-2xl font-bold">{title}</h1>
		{#if subtitle}<p class="text-sm text-subtle">{subtitle}</p>{/if}
	</div>

	<div class="flex items-center gap-2">
		{@render children?.()}
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
</div>