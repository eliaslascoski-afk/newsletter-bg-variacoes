import datetime
import time
import json
import urllib.request
import urllib.parse
import os
import sys
import traceback
import xml.etree.ElementTree as ET

# ============================================================
# CONFIGURACOES (via GitHub Secrets)
# ============================================================
NTFY_TOPICO = os.environ["NTFY_TOPICO"]
NTFY_URL = f"https://ntfy.sh/{NTFY_TOPICO}"
LUDOPEDIA_TOKEN = os.environ["LUDOPEDIA_TOKEN"]
LUDOPEDIA_API = "https://ludopedia.com.br/api/v1"

USER_AGENT = "newsletter_bg_variacoes/3.0 (RSS mode)"

TERMOS_FILTRO = [
    "solo",
    "automa",
    "house rule",
    "house rules",
    "variant",
    "single player",
    "singleplayer",
    "fan made",
    "homebrew",
    "tweak",
    "modo solo",
    "variante",
    "unofficial",
    "custom mode",
]

# Termos em portugues para filtrar somente topicos em PT
TERMOS_PORTUGUES = [
    "para", "com", "que", "nao", "uma", "dos", "das",
    "como", "mais", "mas", "tem", "por", "seu", "sua",
    "foi", "ser", "jogo", "jogos", "regra", "regras",
    "modo", "variante", "variacao", "casa", "solo",
    "partida", "carta", "cartas", "ficha", "dados",
    "jogador", "jogadores", "expansao", "campanha",
]

SUBREDDITS = [
    "boardgames",
    "soloboardgaming",
    "boardgamevariants",
]


def buscar_colecao_ludopedia():
    """Busca a colecao do usuario na API da Ludopedia e retorna lista de nomes."""
    jogos = []
    pagina = 1
    print("Buscando colecao da Ludopedia...")
    while True:
        url = f"{LUDOPEDIA_API}/colecao?pagina={pagina}&fl_tem=1"
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {LUDOPEDIA_TOKEN}",
                "User-Agent": USER_AGENT,
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                itens = data.get("colecao", [])
                if not itens:
                    break
                for item in itens:
                    nome = item.get("nm_jogo") or item.get("nm_jogo_original") or ""
                    if nome:
                        jogos.append(nome)
                pagina += 1
                time.sleep(1)
        except Exception as e:
            print(f"Erro ao buscar colecao Ludopedia (pagina {pagina}): {e}")
            traceback.print_exc()
            break
    print(f"Colecao carregada: {len(jogos)} jogos")
    return jogos


def buscar_rss(jogo, subreddit):
    """Busca via RSS publico do Reddit."""
    query = urllib.parse.quote(f"{jogo} solo OR automa OR variant OR homebrew OR house+rule")
    url = f"https://www.reddit.com/r/{subreddit}/search.rss?q={query}&sort=new&restrict_sr=1&t=week"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            tree = ET.parse(resp)
            root = tree.getroot()
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall("atom:entry", ns)
            posts = []
            for e in entries:
                titulo = e.find("atom:title", ns)
                link = e.find("atom:link", ns)
                autor = e.find("atom:author/atom:name", ns)
                updated = e.find("atom:updated", ns)
                content = e.find("atom:content", ns)
                posts.append({
                    "titulo": titulo.text if titulo is not None else "",
                    "url": link.get("href") if link is not None else "",
                    "autor": autor.text if autor is not None else "",
                    "criado": updated.text[:10] if updated is not None else "",
                    "corpo": content.text if content is not None else "",
                })
            return posts
    except Exception as e:
        print(f"  Erro RSS {jogo} / r/{subreddit}: {e}")
        return []


def e_em_portugues(post):
    """Verifica se o titulo ou corpo do post parece estar em portugues."""
    titulo = post["titulo"].lower()
    corpo = (post["corpo"] or "").lower()
    texto = titulo + " " + corpo
    # Conta quantos termos portugues aparecem
    encontrados = sum(1 for t in TERMOS_PORTUGUES if f" {t} " in f" {texto} ")
    return encontrados >= 2


def e_relevante(post, jogo):
    titulo = post["titulo"].lower()
    corpo = (post["corpo"] or "").lower()
    texto = titulo + " " + corpo
    tem_variacao = any(t in texto for t in TERMOS_FILTRO)
    palavras_jogo = [p.lower() for p in jogo.split() if len(p) > 3]
    tem_jogo = any(p in texto for p in palavras_jogo)
    return tem_variacao and tem_jogo


def formatar_data(iso):
    try:
        return datetime.datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return iso


def coletar_resultados(jogos):
    resultados = []
    for jogo in jogos:
        print(f"Buscando: {jogo}")
        for sub in SUBREDDITS:
            posts = buscar_rss(jogo, sub)
            time.sleep(4)
            for post in posts:
                if e_relevante(post, jogo) and e_em_portugues(post):
                    resultados.append({
                        "jogo": jogo,
                        "subreddit": sub,
                        "titulo": post["titulo"],
                        "url": post["url"],
                        "autor": post["autor"],
                        "criado": formatar_data(post["criado"]),
                    })
    vistos, unicos = set(), []
    for r in resultados:
        if r["url"] not in vistos:
            vistos.add(r["url"])
            unicos.append(r)
    return unicos


def enviar_notificacao(resultados):
    hoje = datetime.datetime.now().strftime("%d/%m/%Y")
    total = len(resultados)

    if total == 0:
        corpo = "Nenhuma novidade em portugues encontrada hoje. Ate amanha!"
    else:
        linhas = []
        por_jogo = {}
        for r in resultados:
            por_jogo.setdefault(r["jogo"], []).append(r)
        for jogo, posts in por_jogo.items():
            linhas.append(f"\n** {jogo} **")
            for p in posts:
                linhas.append(f"- {p['titulo']}")
                linhas.append(f"  {p['url']}")
                linhas.append(f"  r/{p['subreddit']} | u/{p['autor']} | {p['criado']}")
        corpo = "\n".join(linhas)

    titulo_notif = f"[BG] {total} novidade(s) em PT hoje - {hoje}"

    print(f"Enviando notificacao para ntfy.sh/{NTFY_TOPICO}...")
    try:
        dados = corpo.encode("utf-8")
        req = urllib.request.Request(
            NTFY_URL,
            data=dados,
            method="POST",
            headers={
                "Title": titulo_notif,
                "Priority": "default",
                "Tags": "game_die",
                "Content-Type": "text/plain; charset=utf-8",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"Notificacao enviada! Status: {resp.status}")
    except Exception as e:
        print(f"ERRO ao enviar notificacao: {e}")
        traceback.print_exc()
        sys.exit(1)


def main():
    print("=== Newsletter BG Variacoes (ntfy.sh + Ludopedia API) ===")
    print(f"Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    jogos = buscar_colecao_ludopedia()
    if not jogos:
        print("AVISO: colecao vazia ou erro na API. Encerrando.")
        sys.exit(1)
    print("Coletando posts em portugues via RSS do Reddit...")
    resultados = coletar_resultados(jogos)
    print(f"Total de posts relevantes em portugues: {len(resultados)}")
    enviar_notificacao(resultados)
    print("Concluido!")


if __name__ == "__main__":
    main()
