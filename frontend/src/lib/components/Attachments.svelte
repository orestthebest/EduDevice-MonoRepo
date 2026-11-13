<script>
	import { enhance } from '$app/forms';
	import Icon from '$lib/components/Icon.svelte';
	import { formatSize } from '$lib/format.js';

	// Anhänge einer Entschuldigung: Name öffnet im neuen Tab, Pfeil lädt herunter, ✕ entfernt (nur Schüler, nur pending)
	let { excuseId, attachments = [], canRemove = false } = $props();
	let removingId = $state(null);
</script>

{#if attachments.length > 0}
	<ul class="mt-2 flex flex-wrap gap-2">
		{#each attachments as att (att.id)}
			{@const href = `/excuses/${excuseId}/attachments/${att.id}`}
			<li class="flex max-w-full items-center gap-1 rounded-lg border border-line bg-surface py-1 pr-1 pl-3 text-sm">
				<Icon name="file" class="size-4 shrink-0 text-subtle" />
				<a href="{href}?view" target="_blank" rel="noopener"
					class="min-w-0 truncate font-medium hover:text-accent-dark hover:underline">{att.original_name}</a>
				<span class="shrink-0 pl-1 text-xs text-subtle">{formatSize(att.size_bytes)}</span>
				<a {href} download aria-label="Download {att.original_name}"
					class="rounded-md p-1 text-subtle transition hover:bg-white hover:text-accent-dark">
					<Icon name="download" class="size-4" />
				</a>
				{#if canRemove}
					<form method="POST" action="?/removeAttachment"
						use:enhance={() => {
							removingId = att.id;
							return async ({ update }) => {
								await update();
								removingId = null;
							};
						}}>
						<input type="hidden" name="excuse_id" value={excuseId} />
						<input type="hidden" name="attachment_id" value={att.id} />
						<button type="submit" disabled={removingId === att.id} aria-label="Remove {att.original_name}"
							class="cursor-pointer rounded-md p-1 text-subtle transition hover:bg-white hover:text-error disabled:opacity-50">
							<Icon name="x" class="size-4" />
						</button>
					</form>
				{/if}
			</li>
		{/each}
	</ul>
{/if}