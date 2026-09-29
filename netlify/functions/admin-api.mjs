import {
  json, senhaCorreta, criarToken, tokenValido,
  listarPasta, lerArquivo, gravarArquivo, apagarArquivo,
} from "./_lib.mjs";

const PASTA_POSTS = "conteudo/posts";
const PASTA_IMAGENS = "conteudo/imagens";
const ARQUIVO_OK = /^[a-z0-9-]+\.md$/;
const SLUG_OK = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const DATA_OK = /^\d{4}-\d{2}-\d{2}$/;
const ORDEM = ["titulo", "slug", "publicacao", "categoria", "palavra_chave", "palavras_secundarias",
  "meta_descricao", "imagem", "rascunho", "atualizado"];

const b64 = (texto) => Buffer.from(texto, "utf-8").toString("base64");
const espera = (ms) => new Promise((r) => setTimeout(r, ms));

export function lerPost(texto) {
  const m = texto.replace(/\r\n/g, "\n").match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!m) return { meta: {}, corpo: texto };
  const meta = {};
  for (const linha of m[1].split("\n")) {
    const i = linha.indexOf(":");
    if (i < 0) continue;
    const k = linha.slice(0, i).trim();
    let v = linha.slice(i + 1).trim();
    try { v = JSON.parse(v); } catch { v = v.replace(/^"|"$/g, ""); }
    meta[k] = v;
  }
  let corpo = m[2].trim().replace(/^# .*\n+/, "");
  corpo = corpo.split(/\n---\n\*Dra\./)[0].trim();
  return { meta, corpo };
}

export function montarPost(meta, corpo) {
  const linhas = ORDEM.filter((k) => meta[k] !== undefined && meta[k] !== "" && meta[k] !== false)
    .map((k) => `${k}: ${JSON.stringify(meta[k])}`);
  return `---\n${linhas.join("\n")}\n---\n\n# ${meta.titulo}\n\n${corpo.trim()}\n`;
}

function validar(meta) {
  if (!meta.titulo || meta.titulo.length < 5) return "Preencha o título.";
  if (!SLUG_OK.test(meta.slug || "")) return "O endereço (slug) só pode ter letras minúsculas, números e hífens.";
  if (!DATA_OK.test(meta.publicacao || "")) return "Escolha a data de publicação.";
  if (meta.imagem && !/^\/blog\/img\/[a-z0-9._-]+$/.test(meta.imagem)) return "Imagem de capa inválida.";
  return null;
}

async function listar() {
  const itens = (await listarPasta(PASTA_POSTS)) || [];
  const arquivos = itens.filter((i) => i.type === "file" && ARQUIVO_OK.test(i.name));
  const posts = await Promise.all(arquivos.map(async (a) => {
    const { meta } = lerPost(await lerArquivo(a.path));
    return { arquivo: a.name, sha: a.sha, titulo: meta.titulo || a.name, slug: meta.slug,
      publicacao: meta.publicacao, categoria: meta.categoria, rascunho: Boolean(meta.rascunho) };
  }));
  return posts.sort((x, y) => String(y.publicacao).localeCompare(String(x.publicacao)));
}

async function salvar(dados) {
  const meta = { ...dados.meta };
  const corpo = String(dados.corpo || "");
  meta.titulo = String(meta.titulo || "").trim();
  meta.slug = String(meta.slug || "").trim();
  if (typeof meta.palavras_secundarias === "string") {
    meta.palavras_secundarias = meta.palavras_secundarias.split(",").map((s) => s.trim()).filter(Boolean);
  }
  meta.rascunho = Boolean(meta.rascunho);
  const erro = validar(meta);
  if (erro) return json({ erro }, 400);

  const novo = `${meta.slug}.md`;
  const antigo = dados.arquivo && ARQUIVO_OK.test(dados.arquivo) ? dados.arquivo : null;
  if (antigo) meta.atualizado = new Date(Date.now() - 3 * 3600e3).toISOString().slice(0, 10);

  if (novo !== antigo) {
    const existente = (await listarPasta(PASTA_POSTS) || []).find((i) => i.name === novo);
    if (existente) return json({ erro: "Já existe um post com esse endereço. Mude o slug." }, 409);
  }
  const texto = montarPost(meta, corpo);
  const r = await gravarArquivo(`${PASTA_POSTS}/${novo}`, b64(texto),
    `Blog: ${antigo ? "atualiza" : "novo post"} "${meta.titulo}"`, novo === antigo ? dados.sha : undefined);
  if (antigo && novo !== antigo && dados.sha) {
    await apagarArquivo(`${PASTA_POSTS}/${antigo}`, dados.sha, `Blog: renomeia ${antigo} para ${novo}`);
  }
  return json({ ok: true, arquivo: novo, sha: r.content.sha });
}

async function enviarImagem(dados) {
  const m = String(dados.dados || "").match(/^data:image\/(jpeg|png|webp);base64,(.+)$/);
  if (!m) return json({ erro: "Envie uma imagem JPG, PNG ou WebP." }, 400);
  if (m[2].length > 5_500_000) return json({ erro: "Imagem muito grande (máx. 4 MB)." }, 413);
  const base = String(dados.nome || "imagem").toLowerCase().normalize("NFD")
    .replace(/[̀-ͯ]/g, "").replace(/\.[a-z0-9]+$/, "").replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "").slice(0, 40) || "imagem";
  const nome = `${Date.now().toString(36)}-${base}.${m[1] === "jpeg" ? "jpg" : m[1]}`;
  await gravarArquivo(`${PASTA_IMAGENS}/${nome}`, m[2], `Blog: imagem ${nome}`);
  return json({ ok: true, url: `/blog/img/${nome}` });
}

export default async (req) => {
  const url = new URL(req.url);
  const rota = url.pathname.replace(/^\/api\/admin\/?/, "").replace(/\/$/, "");
  try {
    if (rota === "login" && req.method === "POST") {
      const { senha } = await req.json().catch(() => ({}));
      if (!senhaCorreta(senha)) { await espera(800); return json({ erro: "Senha incorreta." }, 401); }
      return json({ token: criarToken() });
    }
    if (!tokenValido(req)) return json({ erro: "Sessão expirada. Entre de novo." }, 401);

    if (rota === "posts" && req.method === "GET") return json({ posts: await listar() });
    if (rota === "posts" && req.method === "PUT") return await salvar(await req.json());

    const m = rota.match(/^posts\/([a-z0-9-]+\.md)$/);
    if (m && req.method === "GET") {
      const itens = (await listarPasta(PASTA_POSTS)) || [];
      const item = itens.find((i) => i.name === m[1]);
      if (!item) return json({ erro: "Post não encontrado." }, 404);
      const { meta, corpo } = lerPost(await lerArquivo(item.path));
      return json({ arquivo: item.name, sha: item.sha, meta, corpo });
    }
    if (m && req.method === "DELETE") {
      const sha = url.searchParams.get("sha");
      if (!sha) return json({ erro: "Faltou a versão do arquivo." }, 400);
      await apagarArquivo(`${PASTA_POSTS}/${m[1]}`, sha, `Blog: remove ${m[1]}`);
      return json({ ok: true });
    }
    if (rota === "imagens" && req.method === "POST") return await enviarImagem(await req.json());
    return json({ erro: "Rota não encontrada." }, 404);
  } catch (e) {
    const conflito = e.status === 409 || e.status === 422;
    return json({ erro: conflito
      ? "Este post foi alterado em outra janela. Recarregue a lista e tente de novo."
      : `Não foi possível concluir: ${e.message}` }, conflito ? 409 : 500);
  }
};

export const config = { path: "/api/admin/*" };
