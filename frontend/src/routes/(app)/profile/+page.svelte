<script>
	import { enhance } from '$app/forms';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { ROLE_LABEL } from '$lib/roles.js';
    import Avatar from '$lib/components/Avatar.svelte';
    import Icon from '$lib/components/Icon.svelte';

	let { data, form } = $props();
    let saving = $state(false);
    let savingUsername = $state(false);
	let savingPassword = $state(false);
    let uploading = $state(false);
	const p = $derived(data.profile);

	// Nur Anzeige – Name und Rolle verwaltet die Schule
	const fields = $derived([
		{ label: 'First name', value: p.first_name },
		{ label: 'Last name', value: p.last_name },
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
	<p class="text-sm text-subtle">Name and role are managed by your school.</p>

	<dl class="mt-5 divide-y divide-line">
		{#each fields as f (f.label)}
			<div class="grid gap-1 py-3 sm:grid-cols-3">
				<dt class="text-sm text-subtle">{f.label}</dt>
				<dd class="text-sm font-medium break-all sm:col-span-2">{f.value}</dd>
			</div>
		{/each}
	</dl>
</section>

<!-- Username ändern -->
<section class="mt-6 rounded-2xl border border-line bg-white p-6">
	<h2 class="text-lg font-semibold">Username</h2>
	<p class="text-sm text-subtle">You use it to log in. 3–50 characters.</p>

	<form
		method="POST"
		action="?/updateUsername"
		class="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end"
		use:enhance={() => {
			savingUsername = true;
			return async ({ update }) => {
				await update({ reset: false });
				savingUsername = false;
			};
		}}
	>
		<div class="flex-1">
			<label for="username" class="label">Username</label>
			<input id="username" name="username" type="text" required minlength="3" maxlength="50"
				autocomplete="username" class="input" value={form?.username ?? p.username} />
		</div>
		<button type="submit" class="btn-primary sm:w-auto sm:px-6" disabled={savingUsername}>
			{savingUsername ? 'Saving…' : 'Save'}
		</button>
	</form>

	{#if form?.usernameError}
		<p class="mt-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.usernameError}</p>
	{:else if form?.usernameSuccess}
		<p class="mt-4 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success-dark">Your username has been updated. Use it next time you log in.</p>
	{/if}
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

<!-- Passwort ändern -->
<section class="mt-6 rounded-2xl border border-line bg-white p-6">
	<h2 class="text-lg font-semibold">Password</h2>
	<p class="text-sm text-subtle">At least 8 characters.</p>

	<form
		method="POST"
		action="?/updatePassword"
		class="mt-5 grid gap-4 sm:grid-cols-3"
		use:enhance={() => {
			savingPassword = true;
			return async ({ update }) => {
				await update(); // leert die Felder nach Erfolg
				savingPassword = false;
			};
		}}
	>
		<div>
			<label for="current_password" class="label">Current password</label>
			<input id="current_password" name="current_password" type="password" required
				autocomplete="current-password" class="input" />
		</div>
		<div>
			<label for="new_password" class="label">New password</label>
			<input id="new_password" name="new_password" type="password" required minlength="8" maxlength="72"
				autocomplete="new-password" class="input" />
		</div>
		<div>
			<label for="confirm_password" class="label">Repeat new password</label>
			<input id="confirm_password" name="confirm_password" type="password" required minlength="8" maxlength="72"
				autocomplete="new-password" class="input" />
		</div>
		<div class="sm:col-span-3 sm:flex sm:justify-end">
			<button type="submit" class="btn-primary sm:w-auto sm:px-6" disabled={savingPassword}>
				{savingPassword ? 'Saving…' : 'Change password'}
			</button>
		</div>
	</form>

	{#if form?.passwordError}
		<p class="mt-4 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">{form.passwordError}</p>
	{:else if form?.passwordSuccess}
		<p class="mt-4 rounded-lg border border-success/30 bg-success/10 px-4 py-3 text-sm text-success-dark">Your password has been changed.</p>
	{/if}
</section>