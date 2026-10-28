<script>
	import { enhance } from '$app/forms';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { ROLE_LABEL } from '$lib/roles.js';
    import Avatar from '$lib/components/Avatar.svelte';
    import Icon from '$lib/components/Icon.svelte';

	let { data, form } = $props();
    let saving = $state(false);
    let uploading = $state(false);
	const p = $derived(data.profile);

	// Nur Anzeige – Name, Benutzername und Rolle verwaltet die Schule
	const fields = $derived([
		{ label: 'First name', value: p.first_name },
		{ label: 'Last name', value: p.last_name },
		{ label: 'Username', value: p.username },
		{ label: 'Role', value: ROLE_LABEL[p.role] }
	]);
</script>

<svelte:head>
	<title>Profile · EduDevice</title>
</svelte:head>

<PageHeader title="My profile" subtitle="Your personal account information" />

<!-- Kopf-Karte: Bild/Initialen, Name, Rolle, Bild ändern -->
<section class="rounded-2xl border border-line bg-white p-6">
	<div class="flex flex-col gap-5 sm:flex-row sm:items-center">
		<Avatar user={p} class="size-20 text-2xl" />

		<div class="min-w-0 flex-1">
			<h2 class="truncate text-xl font-semibold">{p.first_name} {p.last_name}</h2>
			<p class="truncate text-sm text-subtle">@{p.username}</p>
			<span class="mt-2 inline-block rounded-full bg-accent-light px-3 py-1 text-xs font-semibold text-accent-dark">
				{ROLE_LABEL[p.role]}
			</span>
		</div>

		<div class="flex gap-2">
			<!-- Datei wählen -> Formular schickt sich sofort ab -->
			<form method="POST" action="?/uploadAvatar" enctype="multipart/form-data"
				use:enhance={() => {
					uploading = true;
					return async ({ update }) => {
						await update();
						uploading = false;
					};
				}}
			>
				<label class="flex cursor-pointer items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-medium text-white transition hover:bg-accent-dark">
					<Icon name="upload" />
					{uploading ? 'Uploading…' : p.profile_image ? 'Change picture' : 'Upload picture'}
					<input type="file" name="file" accept="image/jpeg,image/png,image/webp" class="hidden"
						disabled={uploading} onchange={(e) => e.currentTarget.form.requestSubmit()} />
				</label>
			</form>

			{#if p.profile_image}
				<form method="POST" action="?/removeAvatar" use:enhance>
					<button type="submit"
						class="flex cursor-pointer items-center gap-2 rounded-lg border border-ghost px-4 py-2.5 text-sm font-medium transition hover:border-error hover:text-error">
						<Icon name="trash" />
						Remove
					</button>
				</form>
			{/if}
		</div>
	</div>

	<p class="mt-4 text-xs text-subtle">JPG, PNG or WebP, max. 2 MB.</p>

	{#if form?.avatarError}
		<p class="mt-3 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.avatarError}</p>
	{:else if form?.avatarSuccess}
		<p class="mt-3 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success-dark">{form.avatarSuccess}</p>
	{/if}
</section>


<!-- Kontodaten -->
<section class="mt-6 rounded-2xl border border-line bg-white p-6">
	<h2 class="text-lg font-semibold">Account details</h2>
	<p class="text-sm text-subtle">Name, username and role are managed by your school.</p>

	<dl class="mt-5 divide-y divide-line">
		{#each fields as f (f.label)}
			<div class="grid gap-1 py-3 sm:grid-cols-3">
				<dt class="text-sm text-subtle">{f.label}</dt>
				<dd class="text-sm font-medium break-all sm:col-span-2">{f.value}</dd>
			</div>
		{/each}
	</dl>
</section>

<!-- E-Mail ändern -->
<section class="mt-6 rounded-2xl border border-line bg-white p-6">
	<h2 class="text-lg font-semibold">Email address</h2>
	<p class="text-sm text-subtle">Used for notifications from your school.</p>

	<form
		method="POST"
		action="?/updateEmail"
		class="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end"
		use:enhance={() => {
			saving = true;
			return async ({ update }) => {
				await update({ reset: false });
				saving = false;
			};
		}}
	>
		<div class="flex-1">
			<label for="email" class="label">Email</label>
			<input id="email" name="email" type="email" required maxlength="255"
				class="input" value={form?.email ?? p.email} />
		</div>
		<button type="submit" class="btn-primary sm:w-auto sm:px-6" disabled={saving}>
			{saving ? 'Saving…' : 'Save'}
		</button>
	</form>

	{#if form?.error}
		<p class="mt-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.error}</p>
	{:else if form?.success}
		<p class="mt-4 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success-dark">Your email has been updated.</p>
	{/if}
</section>