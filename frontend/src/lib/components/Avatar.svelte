<script>
	// Profilbild oder Initialen als Ersatz
	// class = Größe + Schriftgröße, z.B. "size-20 text-2xl"
	let { user, class: cls = 'size-10 text-sm' } = $props();
	const initials = $derived((user.first_name[0] + user.last_name[0]).toUpperCase());
</script>

{#if user.profile_image}
	<img src="/avatar/{user.profile_image}" alt="{user.first_name} {user.last_name}"
		class="{cls} shrink-0 rounded-full object-cover" />
{:else}
	<span class="bg-brand-gradient grid {cls} shrink-0 place-items-center rounded-full font-semibold text-white">
		{initials}
	</span>
{/if}