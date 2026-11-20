<script>
    import AuthLayout from '$lib/components/AuthLayout.svelte';
    import { m } from '$lib/paraglide/messages.js';

    // form enthält eine evtl. Fehlermeldung vom register-Action.
    let { form } = $props();

    	// Ausgewählte Rolle (Student ist Standard)
	let role = $state('student');

	const roles = [
		{ value: 'student', label: m.role_student() },
		{ value: 'teacher', label: m.role_teacher() }
	];
</script>

<svelte:head>
    <title>{m.register_title()} · EduDevice</title>
</svelte:head>

<AuthLayout>
    <h1 class="text-4xl font-bold">{m.register_title()}</h1>
    <p class="mt-2 text-subtle">{m.register_subtitle()}</p>

    <!-- Fehlermeldung anzeigen, falls die Registrierung fehlgeschlagen ist -->
    {#if form?.error}
        <p class="mt-6 rounded-lg border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
            {form.error}
        </p>
    {/if}

    <!-- Registrierungs-Formular: schickt die Daten an den register-Action -->
    <form action="?/register" method="POST" class="mt-8 flex flex-col gap-5">

        <!-- Rollen-Auswahl: versteckte Radio-Buttons, gestylt als zwei Buttons -->
        <fieldset>
            <legend class="label">{m.register_sign_up_as()}</legend>
            <div class="grid grid-cols-2 gap-3">
                {#each roles as r (r.value)}
                    <label
                        class="cursor-pointer rounded-lg border py-2.5 text-center text-sm font-medium transition
                        {role === r.value
                            ? 'border-accent bg-accent-xlight text-accent-dark'
                            : 'border-ghost bg-white text-navy hover:border-accent/50'}"
                    >
                        <input type="radio" name="role" value={r.value} bind:group={role} class="sr-only" />
                        {r.label}
                    </label>
                {/each}
            </div>
        </fieldset>

        <!-- Vor- und Nachname nebeneinander -->
        <div class="grid gap-5 sm:grid-cols-2">
            <div>
                <label for="firstName" class="label">{m.first_name()}</label>
                <input type="text" id="firstName" name="firstName" required autocomplete="given-name"
                    value={form?.values?.firstName ?? ''} class="input" />
            </div>
            <div>
                <label for="lastName" class="label">{m.last_name()}</label>
                <input type="text" id="lastName" name="lastName" required autocomplete="family-name"
                    value={form?.values?.lastName ?? ''} class="input" />
            </div>
        </div>

        <div>
            <label for="username" class="label">{m.username()}</label>
            <input type="text" id="username" name="username" required
                placeholder={m.username_placeholder()} autocomplete="username"
                value={form?.values?.username ?? ''} class="input" />
        </div>

        <div>
            <label for="email" class="label">{m.email()}</label>
            <input type="email" id="email" name="email" required autocomplete="email"
                placeholder="you@school.example"
                value={form?.values?.email ?? ''} class="input" />
        </div>

        <div>
            <label for="password" class="label">{m.password()}</label>
            <input type="password" id="password" name="password" required minlength="8"
                placeholder={m.password_placeholder()} autocomplete="new-password" class="input" />
        </div>

        <button type="submit" class="btn-primary">{m.register_button()}</button>

        <!-- Link zum Login für User, die schon einen Account haben -->
        <p class="text-center text-sm text-subtle">
            {m.register_have_account()} <a href="/login" class="font-medium text-accent hover:text-accent-darker">{m.register_login_link()}</a>
        </p>
    </form>
</AuthLayout>