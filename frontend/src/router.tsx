import {
  createRouter,
  createRootRoute,
  createRoute,
  redirect,
} from '@tanstack/react-router';
import Layout from '@/components/Layout';
import LoginPage from '@/pages/LoginPage';
import ContactsPage from '@/pages/ContactsPage';
import ContactDetailPage from '@/pages/ContactDetailPage';
import PipelinePage from '@/pages/PipelinePage';
import CampaignsPage from '@/pages/CampaignsPage';
import ImportPage from '@/pages/ImportPage';

import { useEffect } from 'react';

// Placeholder pages for routes without dedicated pages yet
function PlaceholderPage({ title }: { title: string }) {
  useEffect(() => { document.title = `${title} — Sarson Funds CRM`; }, [title]);
  return (
    <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
      <p className="text-lg font-semibold">{title}</p>
      <p className="text-sm mt-1">Coming Soon</p>
    </div>
  );
}

// Root route
const rootRoute = createRootRoute();

// Login route (public)
const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: '/login',
  component: LoginPage,
});

// Auth guard
function requireAuth() {
  const token = localStorage.getItem('access_token');
  if (!token) {
    throw redirect({ to: '/login' });
  }
}

// Layout route (protected)
const layoutRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: 'layout',
  component: Layout,
  beforeLoad: requireAuth,
});

// Index → redirect to /contacts
const indexRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: '/',
  beforeLoad: () => {
    throw redirect({ to: '/contacts' });
  },
});

const contactsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: '/contacts',
  component: ContactsPage,
});

const contactDetailRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: '/contacts/$contactId',
  component: ContactDetailPage,
});

const companiesRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: '/companies',
  component: () => <PlaceholderPage title="Companies" />,
});

const pipelineRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: '/pipeline',
  component: PipelinePage,
});

const campaignsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: '/campaigns',
  component: CampaignsPage,
});

const segmentsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: '/segments',
  component: () => <PlaceholderPage title="Segments" />,
});

const importRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: '/import',
  component: ImportPage,
});

// Build route tree
const routeTree = rootRoute.addChildren([
  loginRoute,
  layoutRoute.addChildren([
    indexRoute,
    contactsRoute,
    contactDetailRoute,
    companiesRoute,
    pipelineRoute,
    campaignsRoute,
    segmentsRoute,
    importRoute,
  ]),
]);

export const router = createRouter({ routeTree });

// Type safety
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router;
  }
}
