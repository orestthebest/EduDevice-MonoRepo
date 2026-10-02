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
			{ href: '/subjects', label: 'Subjects & materials', icon: 'book' }
		]
	},
	lehrkraft: {
		section: 'Teaching',
		items: [
			{ href: '/', label: 'Dashboard', icon: 'home' },
			{ href: '/subjects', label: 'Subjects & materials', icon: 'folder' }
		]
	},
	admin: {
		section: 'Administration',
		items: [
			{ href: '/', label: 'Dashboard', icon: 'home' },
			{ href: '/subjects', label: 'Classes & subjects', icon: 'grid' }
		]
	}
};