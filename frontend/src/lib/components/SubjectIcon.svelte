<script>
	import Icon from '$lib/components/Icon.svelte';

	// Fachbild oder Buch-Symbol als Ersatz (wie Avatar.svelte bei Profilbildern)
	// subject braucht id + image (Dateiname); class = Größe, z.B. "size-10"
	let { subject, class: cls = 'size-10' } = $props();
</script>

{#if subject.image}
	<!-- ?v= ändert sich bei jedem neuen Bild, daher sieht man ein neues Bild sofort -->
	<img src="/subjects/{subject.id}/image?v={encodeURIComponent(subject.image)}" alt=""
		class="{cls} shrink-0 rounded-lg object-cover" />
{:else}
	<span class="grid {cls} shrink-0 place-items-center rounded-lg bg-surface text-navy">
		<Icon name="book" />
	</span>
{/if}