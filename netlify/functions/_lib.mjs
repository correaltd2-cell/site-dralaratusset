import { createHmac, timingSafeEqual } from "node:crypto";

const env = (k, padrao) => process.env[k] ?? padrao;
const SESSAO_HORAS = 12;

export const json = (dados, status = 200) =>
  new Response(JSON.stringify(dados), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });

function segredo() {
  const s = env("SESSION_SECRET") || env("ADMIN_PASSWORD");
  if (!s) throw new Error("ADMIN_PASSWORD não configurada no Netlify");
  return s;
}

function assinar(texto) {
  return createHmac("sha256", segredo()).update(texto).digest("base64url");
}

function iguais(a, b) {
  const x = Buffer.from(String(a));
  const y = Buffer.from(String(b));
  return x.length === y.length && timingSafeEqual(x, y);
}

export function senhaCorreta(senha) {
  const certa = env("ADMIN_PASSWORD");
  return Boolean(certa) && iguais(senha ?? "", certa);
}

export function criarToken() {
  const exp = String(Date.now() + SESSAO_HORAS * 3600e3);
  return `${exp}.${assinar(exp)}`;
}

export function tokenValido(req) {
  const t = (req.headers.get("authorization") || "").replace(/^Bearer\s+/i, "");
  const [exp, sig] = t.split(".");
  if (!exp || !sig || Number(exp) < Date.now()) return false;
  return iguais(sig, assinar(exp));
}

// ---- GitHub (conteúdo do site fica no repositório) ----
const API = env("GITHUB_API", "https://api.github.com");

async function gh(caminho, opcoes = {}) {
  const repo = env("GITHUB_REPO");
  const token = env("GITHUB_TOKEN");
  if (!repo || !token) throw new Error("GITHUB_REPO e GITHUB_TOKEN precisam estar configurados no Netlify");
  const r = await fetch(`${API}/repos/${repo}/contents/${caminho}`, {
    ...opcoes,
    headers: {
      authorization: `Bearer ${token}`,
      accept: opcoes.raw ? "application/vnd.github.raw+json" : "application/vnd.github+json",
      "x-github-api-version": "2022-11-28",
      "user-agent": "painel-blog",
      ...(opcoes.body ? { "content-type": "application/json" } : {}),
    },
  });
  if (r.status === 404) return null;
  if (!r.ok) {
    const msg = await r.text();
    const erro = new Error(`GitHub ${r.status}: ${msg.slice(0, 200)}`);
    erro.status = r.status;
    throw erro;
  }
  return opcoes.raw ? r.text() : r.json();
}

const ramo = () => env("GITHUB_BRANCH", "main");

export const listarPasta = (pasta) => gh(`${pasta}?ref=${ramo()}`);
export const lerArquivo = (caminho) => gh(`${caminho}?ref=${ramo()}`, { raw: true });

export function gravarArquivo(caminho, conteudoBase64, mensagem, sha) {
  return gh(caminho, {
    method: "PUT",
    body: JSON.stringify({ message: mensagem, content: conteudoBase64, branch: ramo(), ...(sha ? { sha } : {}) }),
  });
}

export function apagarArquivo(caminho, sha, mensagem) {
  return gh(caminho, { method: "DELETE", body: JSON.stringify({ message: mensagem, sha, branch: ramo() }) });
}
