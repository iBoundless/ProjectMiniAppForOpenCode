import { useState } from "react";
import { errorMessage } from "../api/client";
import { auth, settings } from "../api/endpoints";
import { isTelegram, telegram } from "../auth/telegram";
import { Button } from "../components/Button";
import { Header } from "../components/Header";
import { Skeleton } from "../components/Skeleton";
import { useToast } from "../components/toast-context";
import type { User } from "../types/api";
import { useAsync } from "../stores/useAsync";

export function SettingsPage({ user, onLogout }: { user: User; onLogout: () => void }) {
  const toast = useToast();
  const notifications = useAsync(() => settings.notifications(), []);
  const [saving, setSaving] = useState(false);
  const [link, setLink] = useState<string | null>(null);

  async function toggle(value: boolean) {
    setSaving(true);
    try {
      notifications.setData(await settings.setNotifyAll(value));
    } catch (exc) {
      toast.error(errorMessage(exc));
    } finally {
      setSaving(false);
    }
  }

  async function openInBrowser() {
    try {
      const { url } = await auth.loginToken();
      const absolute = new URL(url, window.location.origin).toString();
      const app = telegram();
      if (isTelegram() && app?.openLink) {
        app.openLink(absolute);
      } else {
        setLink(absolute);
      }
    } catch (exc) {
      toast.error(errorMessage(exc));
    }
  }

  async function logout() {
    try {
      await auth.logout();
    } finally {
      onLogout();
    }
  }

  return (
    <>
      <Header title="Настройки" />
      <div className="card">
        <div className="title">{[user.first_name, user.last_name].filter(Boolean).join(" ") || user.username}</div>
        <div className="hint">ID {user.id}</div>
      </div>

      <div className="section-title">Уведомления</div>
      {notifications.loading && !notifications.data && <Skeleton lines={2} />}
      {notifications.data && (
        <div className="card">
          <label className="toggle">
            <input
              type="checkbox"
              checked={notifications.data.notify_all}
              disabled={saving}
              onChange={(event) => void toggle(event.target.checked)}
            />
            <span>Все сессии (как «notify all» в боте)</span>
          </label>
          <p className="hint">Подписок на отдельные сессии: {notifications.data.subscribed_sessions.length}</p>
        </div>
      )}
      {notifications.error != null && <div className="card error-text">{errorMessage(notifications.error)}</div>}

      <div className="section-title">Safari и домашний экран</div>
      <div className="card">
        <p className="hint">
          Одноразовая ссылка входа действует 5 минут. Откройте ее в Safari и добавьте панель на домашний экран.
        </p>
        <Button block variant="secondary" onClick={() => void openInBrowser()}>
          Открыть в Safari
        </Button>
        {link && (
          <p className="mono pre" style={{ marginTop: 8 }}>
            <a href={link}>{link}</a>
          </p>
        )}
      </div>

      <Button block variant="danger" onClick={() => void logout()} style={{ marginTop: 12 }}>
        Выйти
      </Button>
    </>
  );
}
