# Site dralaratusset.com.br: blog + painel

Tudo que está aqui vira o site publicado no Netlify:

| Pasta | O que é |
|---|---|
| `site/` | Arquivos atuais do site (index.html, imagens, css). Vão para a raiz do domínio. |
| `conteudo/posts/` | Um arquivo `.md` por post. O painel grava aqui. |
| `conteudo/imagens/` | Fotos dos posts. Publicadas em `/blog/img/`. |
| `blog/` | Gerador do blog (`gerar.py`), layout, estilo e `config.json` (nome, CRM, endereço, link de agendamento). |
| `admin/` | Painel em `dralaratusset.com.br/admin`. |
| `netlify/functions/` | Funções do painel (login, salvar, imagens) e o build diário dos agendados. |

## Como funciona
1. A Lara entra em `/admin` com a senha e escreve, edita ou agenda um post.
2. O painel grava o post no GitHub.
3. O Netlify percebe a mudança, roda `blog/gerar.py` e publica em 1 a 2 minutos.
4. Todo dia às 6h um build automático coloca no ar os posts agendados para a data.

O gerador cria `/blog/`, uma página por post (com dados estruturados de artigo, perguntas frequentes e navegação), `sitemap.xml` e `robots.txt`. Se o site já tiver sitemap ou robots, ele mantém o conteúdo e acrescenta o blog.

## Configuração (uma vez só)
1. **Repositório:** criar no GitHub um repositório privado vazio (ex.: `site-dralaratusset`) com o conteúdo desta pasta na raiz.
2. **Site atual:** colocar os arquivos do site dentro de `site/` e um link "Blog" para `/blog/` no menu.
3. **Netlify → o site → Site configuration → Build & deploy → Link repository**: escolher o repositório. Comando e pasta de publicação já vêm do `netlify.toml`.
4. **GitHub → Settings → Developer settings → Fine-grained tokens**: criar um token só para esse repositório, com permissão *Contents: Read and write*.
5. **Netlify → Build & deploy → Build hooks**: criar um hook chamado "agendados" e copiar a URL.
6. **Netlify → Site configuration → Environment variables**:
   - `ADMIN_PASSWORD`: senha do painel
   - `GITHUB_TOKEN`: token do passo 4
   - `GITHUB_REPO`: `correaltd2-cell/site-dralaratusset`
   - `GITHUB_BRANCH`: `main`
   - `BUILD_HOOK_URL`: URL do passo 5
7. Fazer um novo deploy e abrir `dralaratusset.com.br/admin`.

Depois do primeiro deploy: cadastrar o site no Google Search Console e enviar `https://dralaratusset.com.br/sitemap.xml`.

## Testar localmente
```
pip install -r requirements.txt
python3 blog/gerar.py --tudo   # gera dist/ com todos os posts, inclusive agendados
```
