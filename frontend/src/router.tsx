import {
  createRouter,
  createRootRoute,
  createRoute,
  redirect,
} from "@tanstack/react-router";
import Layout from "@/components/Layout";
import LoginPage from "@/pages/LoginPage";
import ContactsPage from "@/pages/ContactsPage";
import ContactDetailPage from "@/pages/ContactDetailPage";
import CampaignsPage from "@/pages/CampaignsPage";
import SalesCampaignsPage from "@/pages/SalesCampaignsPage";
import ImportPage from "@/pages/ImportPage";
import TagsPage from "@/pages/TagsPage";
import ImportHistoryPage from "@/pages/ImportHistoryPage";
import UsersPage from "@/pages/UsersPage";
import CampaignStatsPage from "@/pages/CampaignStatsPage";
import InvitesPage from "@/pages/InvitesPage";
import RegisterPage from "@/pages/RegisterPage";
import AuthCallbackPage from "@/pages/AuthCallbackPage";
import CompaniesPage from "@/pages/CompaniesPage";
import ListsPage from "@/pages/ListsPage";
import ApiControlsPage from "@/pages/ApiControlsPage";
import GoogleAdsPage from "@/pages/GoogleAdsPage";
import ActivityPage from "@/pages/ActivityPage";
import SheetsPage from "@/pages/SheetsPage";
import DocsPage from "@/pages/DocsPage";
import ChangelogPage from "@/pages/ChangelogPage";

import { useEffect } from "react";

function PlaceholderPage({ title }: { title: string }) {
  useEffect(() => {
    document.title = `${title} — Sarson Funds CRM`;
  }, [title]);
  return (
    <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
      <p className="text-lg font-semibold">{title}</p>
      <p className="text-sm mt-1">Coming Soon</p>
    </div>
  );
}

function UnauthorizedPage() {
  useEffect(() => {
    document.title = "Unauthorized — Sarson Funds CRM";
  }, []);
  return (
    <div className="flex flex-col items-center justify-center py-24 text-muted-foreground">
      <p className="text-lg font-semibold">Access Denied</p>
      <p className="text-sm mt-1">You don&apos;t have permission to view this page.</p>
    </div>
  );
}

const rootRoute = createRootRoute();

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: LoginPage,
  validateSearch: (search: Record<string, unknown>) => ({
    error: (search.error as string) || undefined,
  }),
  beforeLoad: () => {
    const token = localStorage.getItem("access_token");
    if (token) throw redirect({ to: "/" });
  },
});

const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/register",
  component: RegisterPage,
  beforeLoad: () => {
    const token = localStorage.getItem("access_token");
    if (token) throw redirect({ to: "/" });
  },
});

const authCallbackRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/auth/callback",
  component: AuthCallbackPage,
  validateSearch: (search: Record<string, unknown>) => ({
    token: (search.token as string) || undefined,
  }),
});

function requireAuth() {
  const token = localStorage.getItem("access_token");
  if (!token) {
    throw redirect({ to: "/login" });
  }
}

const layoutRoute = createRoute({
  getParentRoute: () => rootRoute,
  id: "layout",
  component: Layout,
  beforeLoad: requireAuth,
});

const indexRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({ to: "/contacts" });
  },
});

const contactsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/contacts",
  component: ContactsPage,
  validateSearch: (search: Record<string, unknown>) => ({
    page: Number(search.page) || undefined,
    sort: (search.sort as string) || undefined,
    order: (search.order as string) || undefined,
    status: (search.status as string) || undefined,
    search: (search.search as string) || undefined,
    rep: (search.rep as string) || undefined,
  }),
});

const contactDetailRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/contacts/$contactId",
  component: ContactDetailPage,
});

const companiesRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/companies",
  component: CompaniesPage,
  validateSearch: (search: Record<string, unknown>) => ({
    q: (search.q as string) || undefined,
    openId: (search.openId as string) || undefined,
  }),
});

const googleAdsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/google-ads",
  component: GoogleAdsPage,
});

const campaignsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/campaigns",
  component: CampaignsPage,
});

const salesCampaignsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/sales-campaigns",
  component: SalesCampaignsPage,
});

const listsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/lists",
  component: ListsPage,
});

const importRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/import",
  component: ImportPage,
});

const tagsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/tags",
  component: TagsPage,
});

const importHistoryRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/imports",
  component: ImportHistoryPage,
});

const campaignStatsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/campaign-stats",
  component: CampaignStatsPage,
});

const usersRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/admin/users",
  component: UsersPage,
});

const invitesRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/admin/invites",
  component: InvitesPage,
});

const apiControlsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/api-controls",
  component: ApiControlsPage,
});

const activityRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/activity",
  component: ActivityPage,
});

const sheetsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/sheets",
  component: SheetsPage,
});

const docsRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/admin/docs",
  component: DocsPage,
});

const changelogRoute = createRoute({
  getParentRoute: () => layoutRoute,
  path: "/admin/changelog",
  component: ChangelogPage,
});

const routeTree = rootRoute.addChildren([
  loginRoute,
  registerRoute,
  authCallbackRoute,
  layoutRoute.addChildren([
    indexRoute,
    contactsRoute,
    contactDetailRoute,
    companiesRoute,
    googleAdsRoute,
    campaignsRoute,
    salesCampaignsRoute,
    listsRoute,
    importRoute,
    tagsRoute,
    importHistoryRoute,
    campaignStatsRoute,
    usersRoute,
    invitesRoute,
    apiControlsRoute,
    activityRoute,
    sheetsRoute,
    docsRoute,
    changelogRoute,
  ]),
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
