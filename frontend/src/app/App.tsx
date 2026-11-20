import { useCallback, useEffect, useState } from "react";
import { setUnauthorizedHandler } from "../api/client";
import { permissions } from "../api/endpoints";
import { events } from "../api/events";
import { Nav } from "../components/Nav";
import { ToastProvider } from "../components/Toasts";
import { HomePage } from "../pages/HomePage";
import { LoginPage } from "../pages/LoginPage";
import { NewTaskPage } from "../pages/NewTaskPage";
import { PermissionsPage } from "../pages/PermissionsPage";
import { ServicePage } from "../pages/ServicePage";
import { SessionPage } from "../pages/SessionPage";
import { SettingsPage } from "../pages/SettingsPage";
import { signIn, type AuthResult } from "../stores/auth";
import { useRoute } from "./router";

export function App() {
  const route = useRoute();
  const [authResult, setAuthResult] = useState<AuthResult | null>(null);
  const [pendingPermissions, setPendingPermissions] = useState(0);

  const login = useCallback(async () => {
    setAuthResult(null);
    setAuthResult(await signIn());
  }, []);

  useEffect(() => {
    void login();
  }, [login]);

  useEffect(() => {
    setUnauthorizedHandler(() => setAuthResult({ state: "anonymous", message: "Сессия входа истекла" }));
    return () => setUnauthorizedHandler(null);
  }, []);

  const signedIn = authResult?.state === "ok";

  useEffect(() => {
    if (!signedIn) return;
    events.start();
    const refresh = () =>
      permissions.list().then(
        (result) => setPendingPermissions(result.items.length),
        () => undefined,
      );
    void refresh();
    const unsubscribe = events.subscribe((event) => {
      if (event.type === "permission.asked" || event.type === "permission.replied") void refresh();
    });
    return () => {
      unsubscribe();
      events.stop();
    };
  }, [signedIn]);

  if (authResult?.state !== "ok") {
    return (
      <ToastProvider>
        <div className="app">
          <LoginPage result={authResult} onRetry={() => void login()} />
        </div>
      </ToastProvider>
    );
  }

  let page;
  switch (route.name) {
    case "new":
      page = <NewTaskPage />;
      break;
    case "session":
      page = <SessionPage key={route.id} id={route.id} />;
      break;
    case "permissions":
      page = <PermissionsPage onChange={setPendingPermissions} />;
      break;
    case "service":
      page = <ServicePage />;
      break;
    case "settings":
      page = (
        <SettingsPage
          user={authResult.user}
          onLogout={() => setAuthResult({ state: "anonymous", message: "Вы вышли" })}
        />
      );
      break;
    default:
      page = <HomePage />;
  }

  return (
    <ToastProvider>
      <div className="app">{page}</div>
      <Nav current={route.name} pendingPermissions={pendingPermissions} />
    </ToastProvider>
  );
}
