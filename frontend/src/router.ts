import { createRouter, createWebHistory } from "vue-router";
import { hasSession } from "./api";
import DashboardView from "./views/DashboardView.vue";
import LoginView from "./views/LoginView.vue";
import TerminalView from "./views/TerminalView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView },
    { path: "/", name: "dashboard", component: DashboardView, meta: { requiresAuth: true } },
    {
      path: "/devices/:deviceId/terminal",
      name: "terminal",
      component: TerminalView,
      meta: { requiresAuth: true },
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

router.beforeEach((to) => {
  if (to.meta.requiresAuth && !hasSession()) return { name: "login" };
  if (to.name === "login" && hasSession()) return { name: "dashboard" };
});

export default router;
