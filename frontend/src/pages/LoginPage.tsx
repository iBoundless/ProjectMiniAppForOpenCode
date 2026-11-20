import { Button } from "../components/Button";
import type { AuthResult } from "../stores/auth";

interface Props {
  result: AuthResult | null;
  onRetry: () => void;
}

export function LoginPage({ result, onRetry }: Props) {
  if (result === null) {
    return (
      <div className="card empty" aria-busy="true">
        Вход…
      </div>
    );
  }
  if (result.state === "forbidden") {
    return (
      <div className="card">
        <h1 style={{ fontSize: 20 }}>Доступ запрещен</h1>
        <p className="hint">Этот аккаунт Telegram не входит в список разрешенных пользователей панели.</p>
      </div>
    );
  }
  if (result.state === "anonymous") {
    return (
      <div className="card">
        <h1 style={{ fontSize: 20 }}>Нужен вход</h1>
        {result.message && <p className="error-text">{result.message}</p>}
        <p className="hint">
          Откройте панель из Telegram через кнопку меню бота. Для Safari попросите в панели внутри Telegram
          одноразовую ссылку («Настройки» → «Открыть в Safari»): она действует 5 минут и только один раз.
        </p>
        <Button block onClick={onRetry}>
          Повторить
        </Button>
      </div>
    );
  }
  if (result.state === "error") {
    return (
      <div className="card">
        <h1 style={{ fontSize: 20 }}>Ошибка входа</h1>
        <p className="error-text">{result.message}</p>
        <Button block onClick={onRetry}>
          Повторить
        </Button>
      </div>
    );
  }
  return null;
}
