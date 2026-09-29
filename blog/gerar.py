"""Monta o site final em dist/: site atual + /blog + /admin + sitemap + robots.

Roda no build do Netlify (ver netlify.toml). Localmente:
  pip install -r requirements.txt
  python3 blog/gerar.py            # posts com data até hoje
  python3 blog/gerar.py --tudo     # todos, inclusive agendados (revisão)
"""
import argparse
import html
import json
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import markdown

RAIZ = Path(__file__).resolve().parent.parent
BLOG = RAIZ / "blog"
DIST = RAIZ / "dist"
CFG = json.loads((BLOG / "config.json").read_text(encoding="utf-8"))
SITE = CFG["site"].rstrip("/")
MESES = ["", "janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def hoje_brasil():
    return (datetime.now(timezone.utc) - timedelta(hours=3)).date()


def data_extenso(d):
    return f"{d.day} de {MESES[d.month]} de {d.year}"


def valor(v):
    v = v.strip()
    if v.startswith(("\"", "[")):
        try:
            return json.loads(v)
        except json.JSONDecodeError:
            pass
    if v in ("true", "false"):
        return v == "true"
    return v.strip('"')


def texto_puro(md_text):
    t = re.sub(r"!\[[^\]]*\]\([^)]+\)", "", md_text)
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    return re.sub(r"[*_`#>]", "", t).strip()


def ler_post(path):
    raw = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", raw, re.S)
    if not m:
        raise ValueError(f"{path.name}: cabeçalho --- ausente")
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = valor(v)
    body = m.group(2).strip()
    body = re.sub(r"^# .*\n", "", body, count=1)
    body = re.split(r"\n---\n\*Dra\.", body)[0].strip()
    body = re.sub(r"\]\(/blog/([a-z0-9-]+)/?\)", r"](/blog/\1/)", body)

    faq = []
    sec = re.search(r"## Perguntas frequentes\n(.*?)(?=\n## |\Z)", body, re.S)
    if sec:
        for q, a in re.findall(r"### (.+?)\n+(.*?)(?=\n### |\Z)", sec.group(1), re.S):
            faq.append((q.strip(), texto_puro(a.strip())))

    meta.setdefault("categoria", "Dermatologia")
    meta.setdefault("palavras_secundarias", [])
    meta.setdefault("palavra_chave", "")
    if not meta.get("tempo_leitura"):
        meta["tempo_leitura"] = f"{max(1, round(len(body.split()) / 200))} min"
    meta["html"] = markdown.markdown(body, extensions=["extra", "sane_lists"])
    meta["data"] = datetime.strptime(meta["publicacao"], "%Y-%m-%d").date()
    meta["faq"] = faq
    meta["url"] = f"{SITE}/blog/{meta['slug']}/"
    return meta


def partes_do_site():
    """Pega CSS, menu e rodapé do index.html do site, para o blog ficar igual."""
    t = (RAIZ / "site" / "index.html").read_text(encoding="utf-8")
    css = re.search(r"<style>(.*?)</style>", t, re.S).group(1)
    nav = re.search(r'<nav class="nav".*?</nav>', t, re.S).group(0)
    rodape = re.search(r'<footer class="footer".*?</footer>', t, re.S).group(0)

    def ancoras(h):
        h = h.replace('href="#"', 'href="/"')
        return re.sub(r'href="#([\w-]+)"', r'href="/#\1"', h)
    nav = ancoras(nav).replace('<a href="/blog/">Blog</a>', '<a href="/blog/" aria-current="page">Blog</a>')
    return css, nav, ancoras(rodape)


CSS_SITE, NAV_SITE, RODAPE_SITE = partes_do_site()


def pagina(titulo, descricao, url, corpo, jsonld, imagem, og_tipo="website"):
    e = html.escape
    ld = "".join(f'<script type="application/ld+json">{json.dumps(j, ensure_ascii=False)}</script>'
                 for j in jsonld)
    head = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(titulo)}</title>
<meta name="description" content="{e(descricao)}">
<link rel="canonical" href="{url}">
<meta name="robots" content="index,follow,max-image-preview:large">
<meta property="og:type" content="{og_tipo}">
<meta property="og:locale" content="pt_BR">
<meta property="og:site_name" content="{e(CFG['nome'])}">
<meta property="og:title" content="{e(titulo)}">
<meta property="og:description" content="{e(descricao)}">
<meta property="og:url" content="{url}">
<meta property="og:image" content="{SITE}{imagem}">
<meta name="twitter:card" content="summary_large_image">
{ld}"""
    layout = (BLOG / "layout.html").read_text(encoding="utf-8")
    trocas = {
        "{{HEAD}}": head,
        "{{NAV}}": NAV_SITE,
        "{{RODAPE}}": RODAPE_SITE,
        "{{CONTEUDO}}": corpo,
        "{{NOME}}": e(CFG["nome"]),
        "{{PROFISSAO}}": e(CFG["profissao"]),
        "{{CRM}}": e(CFG["crm"]),
        "{{RQE}}": e(CFG["rqe"]),
        "{{ENDERECO}}": e(CFG["endereco"]["rua"] + " · " + CFG["endereco"]["bairro"] + " · "
                          + CFG["endereco"]["cidade"] + "/" + CFG["endereco"]["uf"]),
        "{{LINK_AGENDAR}}": e(CFG["link_agendar"]),
        "{{LINK_INSTAGRAM}}": e(CFG["link_instagram"]),
    }
    for k, v in trocas.items():
        layout = layout.replace(k, v)
    return layout


def card(p):
    e = html.escape
    img = (f'<img src="{e(p["imagem"])}" alt="" loading="lazy">' if p.get("imagem") else "")
    return (f'<a class="blog-card" href="/blog/{p["slug"]}/">{img}<span class="blog-card-meta">'
            f'{e(p["categoria"])} · {e(p["tempo_leitura"])}</span><h3>{e(p["titulo"])}</h3>'
            f'<p>{e(p.get("meta_descricao", ""))}</p></a>')


def gerar(posts, todos):
    e = html.escape
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(RAIZ / "site", DIST, ignore=shutil.ignore_patterns("LEIA-ME.md"))
    shutil.copytree(RAIZ / "admin", DIST / "admin", ignore=shutil.ignore_patterns("demo-posts.json"))
    (DIST / "css").mkdir(exist_ok=True)
    (DIST / "css" / "site.css").write_text(CSS_SITE, encoding="utf-8")
    shutil.copytree(RAIZ / "conteudo" / "imagens", DIST / "blog" / "img")
    shutil.copy(BLOG / "blog.css", DIST / "blog" / "blog.css")

    foto = "/blog/img/" + CFG["foto_autora"]
    publicados = {p["slug"] for p in posts}
    medico = {
        "@type": "Physician", "@id": f"{SITE}/#medica", "name": CFG["nome"], "url": SITE + "/",
        "image": SITE + foto, "medicalSpecialty": "Dermatology",
        "address": {"@type": "PostalAddress", "streetAddress": CFG["endereco"]["rua"],
                    "addressLocality": CFG["endereco"]["cidade"],
                    "addressRegion": CFG["endereco"]["uf"], "addressCountry": "BR"},
        "sameAs": [CFG["link_instagram"]],
    }
    autora = {"@type": "Person", "name": CFG["nome"], "jobTitle": "Médica dermatologista",
              "url": SITE + "/", "worksFor": {"@id": f"{SITE}/#medica"}}

    def sem_links_quebrados(h):
        return re.sub(r'<a href="/blog/([a-z0-9-]+)/">(.*?)</a>',
                      lambda m: m.group(0) if m.group(1) in publicados else m.group(2), h)

    for p in posts:
        rel = [q for q in posts if q is not p][:3]
        capa = (f'<img class="blog-capa" src="{e(p["imagem"])}" alt="{e(p["titulo"])}">'
                if p.get("imagem") else "")
        rel_html = ('<section class="blog-relacionados"><h2>Leia também</h2><div class="blog-grade">'
                    + "".join(card(q) for q in rel) + "</div></section>") if rel else ""
        corpo = f"""
<div class="blog-container">
  <nav class="blog-migalhas" aria-label="Você está em"><a href="/">Início</a> › <a href="/blog/">Blog</a> › {e(p['titulo'])}</nav>
  <header class="blog-cabeca">
    <p class="blog-tag">{e(p['categoria'])}</p>
    <h1>{e(p['titulo'])}</h1>
    <p class="blog-resumo">{e(p.get('meta_descricao', ''))}</p>
    <div class="blog-autor-linha"><img src="{foto}" alt="{e(CFG['nome'])}" width="44" height="44" loading="lazy">
      <span>Por <strong>{e(CFG['nome'])}</strong>, dermatologista · <time datetime="{p['publicacao']}">{data_extenso(p['data'])}</time> · {e(p['tempo_leitura'])} de leitura</span></div>
  </header>
  {capa}
  <article class="blog-texto">{sem_links_quebrados(p['html'])}</article>
  <aside class="blog-autora">
    <img src="{foto}" alt="{e(CFG['nome'])} no consultório" width="96" height="96" loading="lazy">
    <div>
      <h2>{e(CFG['nome'])}</h2>
      <p>{e(CFG['bio'])}</p>
      <a class="blog-btn" href="{e(CFG['link_agendar'])}">Agendar consulta</a>
    </div>
  </aside>
  <p class="blog-aviso">Este conteúdo é informativo e não substitui a consulta médica.</p>
  {rel_html}
</div>"""
        img = p.get("imagem") or foto
        ld = [
            {"@context": "https://schema.org", "@type": "BlogPosting",
             "headline": p["titulo"], "description": p.get("meta_descricao", ""),
             "datePublished": p["publicacao"], "dateModified": p.get("atualizado", p["publicacao"]),
             "inLanguage": "pt-BR", "mainEntityOfPage": p["url"], "image": SITE + img,
             "keywords": [k for k in [p["palavra_chave"]] + p["palavras_secundarias"] if k],
             "author": autora, "publisher": medico},
            {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Início", "item": SITE + "/"},
                {"@type": "ListItem", "position": 2, "name": "Blog", "item": SITE + "/blog/"},
                {"@type": "ListItem", "position": 3, "name": p["titulo"], "item": p["url"]}]},
        ]
        if p["faq"]:
            ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
                {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}}
                for q, a in p["faq"]]})
        d = DIST / "blog" / p["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            pagina(f"{p['titulo']} | {CFG['nome']}", p.get("meta_descricao", ""), p["url"],
                   corpo, ld, img, "article"), encoding="utf-8")

    lista = "".join(card(p) for p in posts) or '<p>Os primeiros textos chegam em breve.</p>'
    corpo = f"""
<div class="blog-container">
  <header class="blog-capa-lista">
    <p class="blog-tag">Blog</p>
    <h1>{CFG['blog_titulo']}</h1>
    <p>{e(CFG['blog_descricao'])}</p>
  </header>
  <div class="blog-grade">{lista}</div>
</div>"""
    ld = [medico | {"@context": "https://schema.org"},
          {"@context": "https://schema.org", "@type": "Blog", "name": f"Blog da {CFG['nome']}",
           "url": SITE + "/blog/", "inLanguage": "pt-BR", "publisher": {"@id": f"{SITE}/#medica"},
           "blogPost": [{"@type": "BlogPosting", "headline": p["titulo"], "url": p["url"],
                         "datePublished": p["publicacao"]} for p in posts]}]
    (DIST / "blog" / "index.html").write_text(
        pagina(f"Blog | {CFG['nome']}, {CFG['profissao']}", CFG["blog_descricao"],
               SITE + "/blog/", corpo, ld, foto), encoding="utf-8")

    # últimos posts na página inicial
    idx = DIST / "index.html"
    marca = "<!-- BLOG-RECENTES -->"
    h = idx.read_text(encoding="utf-8")
    if marca in h:
        secao = ""
        if posts:
            cards = "".join(card(p) for p in posts[:3])
            secao = (BLOG / "secao-home.html").read_text(encoding="utf-8").replace("{{CARDS}}", cards)
        idx.write_text(h.replace(marca, secao), encoding="utf-8")

    # feed RSS
    itens_rss = "".join(
        f"<item><title>{e(p['titulo'])}</title><link>{p['url']}</link><guid>{p['url']}</guid>"
        f"<pubDate>{datetime.combine(p['data'], datetime.min.time()).strftime('%a, %d %b %Y 09:00:00 -0300')}</pubDate>"
        f"<description>{e(p.get('meta_descricao', ''))}</description></item>" for p in posts)
    (DIST / "blog" / "feed.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
        f"<title>Blog da {e(CFG['nome'])}</title><link>{SITE}/blog/</link>"
        f"<description>{e(CFG['blog_descricao'])}</description><language>pt-BR</language>{itens_rss}</channel></rss>\n",
        encoding="utf-8")

    # sitemap: mantém as URLs que o site já tinha e acrescenta o blog
    locs = {}
    antigo = RAIZ / "site" / "sitemap.xml"
    if antigo.exists():
        for loc in re.findall(r"<loc>\s*(.*?)\s*</loc>", antigo.read_text(encoding="utf-8")):
            if "/blog/" not in loc:
                locs[loc] = None
    locs.setdefault(SITE + "/", None)
    locs[SITE + "/blog/"] = posts[0]["publicacao"] if posts else None
    for p in posts:
        locs[p["url"]] = p.get("atualizado", p["publicacao"])
    itens = "".join(f"<url><loc>{html.escape(u)}</loc>" + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>"
                    for u, d in locs.items())
    (DIST / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{itens}</urlset>\n', encoding="utf-8")

    robots = RAIZ / "site" / "robots.txt"
    txt = robots.read_text(encoding="utf-8") if robots.exists() else "User-agent: *\nAllow: /\n"
    if "Disallow: /admin" not in txt:
        txt = txt.replace("User-agent: *\n", "User-agent: *\nDisallow: /admin/\n", 1)
    if "Sitemap:" not in txt:
        txt = txt.rstrip() + f"\n\nSitemap: {SITE}/sitemap.xml\n"
    (DIST / "robots.txt").write_text(txt, encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tudo", action="store_true")
    a = ap.parse_args()
    hoje = hoje_brasil()
    todos = [ler_post(f) for f in sorted((RAIZ / "conteudo" / "posts").glob("*.md"))]
    posts = sorted((p for p in todos if not p.get("rascunho") and (a.tudo or p["data"] <= hoje)),
                   key=lambda p: p["data"], reverse=True)
    gerar(posts, todos)
    print(f"dist/: {len(posts)} de {len(todos)} posts no ar (hoje: {hoje})")
    for p in posts:
        print(f"  {p['publicacao']}  /blog/{p['slug']}/")
