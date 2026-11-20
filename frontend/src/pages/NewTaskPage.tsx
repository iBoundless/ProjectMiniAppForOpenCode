import { useEffect, useState, type FormEvent } from "react";
import { errorMessage } from "../api/client";
import { catalog, sessions } from "../api/endpoints";
import { navigate } from "../app/router";
import { Button } from "../components/Button";
import { Header } from "../components/Header";
import { Skeleton } from "../components/Skeleton";
import { useToast } from "../components/toast-context";
import { useAsync } from "../stores/useAsync";

export function NewTaskPage() {
  const toast = useToast();
  const projects = useAsync(() => catalog.projects(), []);
  const [directory, setDirectory] = useState("");
  const [model, setModel] = useState("");
  const [agent, setAgent] = useState("");
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!directory && projects.data?.items.length) setDirectory(projects.data.items[0].canonical);
  }, [projects.data, directory]);

  const models = useAsync(() => catalog.models(directory || undefined), [directory]);
  const agents = useAsync(() => catalog.agents(directory || undefined), [directory]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!directory || !prompt.trim()) return;
    setSubmitting(true);
    setError(null);
    const [provider, ...rest] = model ? model.split("/") : [];
    try {
      const session = await sessions.create({
        directory,
        prompt,
        model: model ? { provider, id: rest.join("/") } : null,
        agent: agent || null,
      });
      toast.show("Задача запущена");
      navigate({ name: "session", id: session.id });
    } catch (exc) {
      setError(errorMessage(exc));
    } finally {
      setSubmitting(false);
    }
  }

  if (projects.loading && !projects.data) {
    return (
      <>
        <Header title="Новая задача" back="#/" />
        <Skeleton lines={5} />
      </>
    );
  }

  return (
    <>
      <Header title="Новая задача" back="#/" />
      <form className="card" onSubmit={submit}>
        <label className="field">
          <span>Проект</span>
          <select value={directory} onChange={(event) => setDirectory(event.target.value)} required>
            {(projects.data?.items ?? []).map((project) => (
              <option key={project.id} value={project.canonical}>
                {project.title}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Модель</span>
          <select value={model} onChange={(event) => setModel(event.target.value)}>
            <option value="">По умолчанию</option>
            {(models.data?.items ?? []).map((item) => (
              <option key={`${item.provider}/${item.model}`} value={`${item.provider}/${item.model}`}>
                {item.label} ({item.provider})
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Агент</span>
          <select value={agent} onChange={(event) => setAgent(event.target.value)}>
            <option value="">По умолчанию</option>
            {(agents.data?.items ?? []).map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Задача</span>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Что нужно сделать?"
            maxLength={20000}
            required
          />
        </label>
        {projects.error != null && <p className="error-text">{errorMessage(projects.error)}</p>}
        {error && <p className="error-text">{error}</p>}
        <Button type="submit" block loading={submitting} disabled={!directory || !prompt.trim()}>
          Запустить
        </Button>
      </form>
    </>
  );
}
