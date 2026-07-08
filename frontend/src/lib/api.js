import axios from "axios";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

export async function fetchMe() {
  const r = await api.get("/auth/me");
  return r.data;
}

export async function logout() {
  await api.post("/auth/logout");
}

export async function createSessionFromId(session_id) {
  const r = await api.post("/auth/session", { session_id });
  return r.data;
}

export async function searchNace(q) {
  const r = await api.get(`/nace`, { params: { q, limit: 60 } });
  return r.data;
}

export async function createAudit(payload) {
  const r = await api.post("/audits", payload);
  return r.data;
}

export async function listAudits() {
  const r = await api.get("/audits");
  return r.data;
}

export async function getAudit(id) {
  const r = await api.get(`/audits/${id}`);
  return r.data;
}

export async function deleteAudit(id) {
  const r = await api.delete(`/audits/${id}`);
  return r.data;
}

export async function uploadFiles(id, files) {
  const fd = new FormData();
  files.forEach((f) => fd.append("files", f));
  const r = await api.post(`/audits/${id}/upload`, fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return r.data;
}

export function pdfUrl(id) {
  return `${API}/audits/${id}/pdf`;
}

export function boardBriefUrl(id) {
  return `${API}/audits/${id}/board-brief`;
}

export function streamUrl(id) {
  return `${API}/audits/${id}/stream`;
}
