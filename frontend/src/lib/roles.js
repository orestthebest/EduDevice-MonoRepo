// Rollen aus der DB (users.role) -> Anzeigename + Sidebar-Navigation
export const ROLE_LABEL = {
	schueler: 'Student',
	lehrkraft: 'Teacher',
	admin: 'Administrator'
};

export const NAV = {
	schueler: {
		section: 'My learning',
		items: [
			{ href: '/', label: 'Dashboard', icon: 'home' },
			{ href: '/subjects', label: 'Subjects & materials', icon: 'book' },
			{ href: '/excuses', label: 'Excuses', icon: 'clipboard' }
		]
	},
	lehrkraft: {
		section: 'Teaching',
		items: [
			{ href: '/', label: 'Dashboard', icon: 'home' },
			{ href: '/subjects', label: 'Subjects & materials', icon: 'folder' },
			{ href: '/excuses/review', label: 'Excuse review', icon: 'clipboard' }
		]
	},
	admin: {
		section: 'Administration',
		items: [
			{ href: '/', label: 'Dashboard', icon: 'home' },
			{ href: '/classes', label: 'Classes & students', icon: 'users' },
			{ href: '/subjects', label: 'All subjects', icon: 'grid' }
		]
	}
};

// Für alle Rollen gleich (wie im Wireframe unter "Shared")
export const SHARED_NAV = {
	section: 'Shared',
	items: [{ href: '/profile', label: 'Profile', icon: 'user' }]
};