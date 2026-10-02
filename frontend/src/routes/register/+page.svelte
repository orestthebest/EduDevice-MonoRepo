<script>
    import AuthLayout from '$lib/components/AuthLayout.svelte';

    // form enthält eine evtl. Fehlermeldung vom register-Action.
    let { form } = $props();

    	// Ausgewählte Rolle (Student ist Standard)
	let role = $state('student');

	const roles = [
		{ value: 'student', label: 'Student' },
		{ value: 'teacher', label: 'Teacher' }
	];
</script>

<svelte:head>
    <title>Register · EduDevice</title>
</svelte:head>

<AuthLayout>
    <h1 class="text-4xl font-bold">Register</h1>
    <p class="mt-2 text-subtle">Create your student account.</p>

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
            <legend class="label">Sign up as</legend>
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
                <label for="firstName" class="label">First name</label>
                <input type="text" id="firstName" name="firstName" required autocomplete="given-name"
                    value={form?.values?.firstName ?? ''} class="input" />
            </div>
            <div>
                <label for="lastName" class="label">Last name</label>
                <input type="text" id="lastName" name="lastName" required autocomplete="family-name"
                    value={form?.values?.lastName ?? ''} class="input" />
            </div>
        </div>

        <div>
            <label for="username" class="label">Username</label>
            <input type="text" id="username" name="username" required
                placeholder="e.g. elira.krasniqi" autocomplete="username"
                value={form?.values?.username ?? ''} class="input" />
        </div>

        <div>
            <label for="email" class="label">E-mail</label>
            <input type="email" id="email" name="email" required autocomplete="email"
                placeholder="you@school.example"
                value={form?.values?.email ?? ''} class="input" />
        </div>

        <div>
            <label for="password" class="label">Password</label>
            <input type="password" id="password" name="password" required minlength="8"
                placeholder="At least 8 characters" autocomplete="new-password" class="input" />
        </div>

        <button type="submit" class="btn-primary">Create Account</button>

        <!-- Link zum Login für User, die schon einen Account haben -->
        <p class="text-center text-sm text-subtle">
            Already have an account? <a href="/login" class="font-medium text-accent hover:text-accent-darker">Login here</a>
        </p>
    </form>
</AuthLayout>