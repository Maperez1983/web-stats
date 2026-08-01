import type { TaskEditorDocument } from '../domain/taskDocument';

export type TaskEditorVersion = {
  id: number;
  captured_at: string;
  reason: string;
  actor: string;
  kind: string;
  title: string;
  block: string;
  duration_minutes: number;
  objects_count: number;
  timeline_count: number;
};

export type TaskEditorSaveAsResponse = {
  ok: boolean;
  task: {
    id: number;
    title: string;
  };
  detail_url: string;
  editor_url: string;
};

export type TaskEditorRenameResponse = {
  ok: boolean;
  task: {
    id: number;
    title: string;
  };
  document?: TaskEditorDocument;
};

export type TaskEditorDeleteResponse = {
  ok: boolean;
  redirect_url: string;
};

export async function fetchTaskDocument(url: string): Promise<TaskEditorDocument> {
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
    },
  });
  if (!response.ok) {
    throw new Error(`No se pudo cargar el documento táctico (${response.status}).`);
  }
  const payload = await response.json();
  return payload.document as TaskEditorDocument;
}

function getCsrfToken(): string {
  const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

export async function saveGraphicCanvas(
  url: string,
  payload: {
    canvas_state: Record<string, unknown>;
    canvas_width: number;
    canvas_height: number;
    preview_data?: string;
  }
): Promise<void> {
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`No se pudo guardar la pizarra (${response.status}).`);
  }
}

export async function enqueueEditorJob(
  url: string,
  payload: Record<string, unknown>
): Promise<void> {
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`No se pudo lanzar el job (${response.status}).`);
  }
}

export async function saveTaskAs(
  url: string,
  payload: {
    title: string;
    canvas_state: Record<string, unknown>;
    canvas_width: number;
    canvas_height: number;
    preview_data?: string;
  }
): Promise<TaskEditorSaveAsResponse> {
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
  const data = (await response.json().catch(() => ({}))) as TaskEditorSaveAsResponse & { error?: string };
  if (!response.ok || !data.ok) {
    throw new Error(data.error || `No se pudo guardar como nueva tarea (${response.status}).`);
  }
  return data;
}

export async function renameTask(
  url: string,
  payload: {
    title: string;
  }
): Promise<TaskEditorRenameResponse> {
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
  const data = (await response.json().catch(() => ({}))) as TaskEditorRenameResponse & { error?: string };
  if (!response.ok || !data.ok) {
    throw new Error(data.error || `No se pudo renombrar la tarea (${response.status}).`);
  }
  return data;
}

export async function deleteTask(url: string): Promise<TaskEditorDeleteResponse> {
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify({}),
  });
  const data = (await response.json().catch(() => ({}))) as TaskEditorDeleteResponse & { error?: string };
  if (!response.ok || !data.ok) {
    throw new Error(data.error || `No se pudo eliminar la tarea (${response.status}).`);
  }
  return data;
}

export async function fetchTaskVersions(url: string): Promise<TaskEditorVersion[]> {
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
    },
  });
  if (!response.ok) {
    throw new Error(`No se pudo cargar el historial (${response.status}).`);
  }
  const data = (await response.json().catch(() => ({}))) as { versions?: TaskEditorVersion[] };
  return Array.isArray(data.versions) ? data.versions : [];
}

export async function restoreTaskVersion(
  url: string,
  payload: {
    backup_id: number;
  }
): Promise<void> {
  const response = await fetch(url, {
    method: 'POST',
    credentials: 'same-origin',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken(),
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const data = (await response.json().catch(() => ({}))) as { error?: string };
    throw new Error(data.error || `No se pudo restaurar la versión (${response.status}).`);
  }
}
