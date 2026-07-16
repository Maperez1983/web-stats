import type { TaskEditorDocument } from '../domain/taskDocument';

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
