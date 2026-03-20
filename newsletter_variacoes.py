import smtplib
import datetime
import json
import urllib.request
import urllib.parse
import os
import xml.etree.ElementTree as ET
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ============================================================
# CONFIGURACOES (via GitHub Secrets)
# ============================================================
EMAIL_REMETENTE    = os.environ["EMAIL_REMETENTE"]
SENHA_APP          = os.environ["SENHA_APP"]
EMAIL_DESTINATARIO = os.environ["EMAIL_DESTINATARIO"]

USER_AGENT = "newsletter_bg_variacoes/2.0 (RSS mode)"

# Jogos base da colecao Ludopedia all_type
JOGOS = [
    "Gwent Legendary Card Game",
    "Mini Rogue",
    "Skulls of Sedlec",
    "Bohnanza",
    "Doom Machine board game",
    "Scoundrel card game",
    "Cartographers Heroes",
    "Orchard 9 card solitaire",
    "One Card Dungeon",
    "Kingdomino",
    "Schotten Totten",
    "Flip 7 card game",
    "Onitama",
    "That's Pretty Clever",
    "Under Falling Skies",
    "Tawantinsuyu Inca Empire",
    "Regicide card game",
    "Ticket to Ride Paris",
    "Saboteur card game",
    "Tiny Epic Pirates",
    "Harmonies board game",
    "7 Wonders Duel",
    "Sprawlopolis",
    "Fantasy Realms",
    "Street Art board game",
    "The Crew Quest Planet Nine",
    "Moirai board game",
    "Pipoca card game",
    "Kelp Shark Octopus",
    "Splendor Duel",
    "Cryptid board game",
    "Bang Dice Game",
    "Palm Island board game",
    "Maskmen card game",
    "Scout Oink Games",
    "Deep Sea Adventure",
    "Sagrada board game",
    "Coup card game",
    "Azul Mini",
    "Hive Pocket",
    "Trio card game",
    "Solatro",
]

TERMOS_FILTRO = [
    "solo", "automa", "house rule", "house rules",
    "variant", "single player", "singleplayer",
    "fan made", "homebrew", "tweak", "modo solo",
    "variante", "unofficial", "custom mode",
]

SUBREDDITS = [
    "boardgames",
    "soloboardgaming",
    "boardgamevariants",
]


def buscar_rss(jogo, subreddit):
    """Busca via RSS publico do Reddit - sem autenticacao necessaria."""
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
                link   = e.find("atom:link", ns)
                autor  = e.find("atom:author/atom:name", ns)
                updated = e.find("atom:updated", ns)
                content = e.find("atom:content", ns)
                posts.append({
                    "titulo":  titulo.text  if titulo  is not None else "",
                    "url":     link.get("href") if link is not None else "",
                    "autor":   autor.text   if autor   is not None else "",
                    "criado":  updated.text[:10] if updated is not None else "",
                    "corpo":   content.text  if content is not None else "",
                })
            return posts
    except Exception as e:
        print(f"  Erro RSS {jogo} / r/{subreddit}: {e}")
        return []


def e_relevante(post, jogo):
    titulo = post["titulo"].lower()
    corpo  = (post["corpo"] or "").lower()
    texto  = titulo + " " + corpo
    # Deve conter termo de variacao
    tem_variacao = any(t in texto for t in TERMOS_FILTRO)
    # Deve mencionar ao menos parte do nome do jogo
    palavras_jogo = [p.lower() for p in jogo.split() if len(p) > 3]
    tem_jogo = any(p in texto for p in palavras_jogo)
    return tem_variacao and tem_jogo


def formatar_data(iso):
    try:
        return datetime.datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return iso


def coletar_resultados():
    resultados = []
    for jogo in JOGOS:
        print(f"Buscando: {jogo}")
        for sub in SUBREDDITS:
            posts = buscar_rss(jogo, sub)
            for post in posts:
                if e_relevante(post, jogo):
                    resultados.append({
                        "jogo":      jogo,
                        "subreddit": sub,
                        "titulo":    post["titulo"],
                        "url":       post["url"],
                        "autor":     post["autor"],
                        "criado":    formatar_data(post["criado"]),
                    })
    # Remove duplicatas por URL
    vistos, unicos = set(), []
    for r in resultados:
        if r["url"] not in vistos:
            vistos.add(r["url"])
            unicos.append(r)
    return unicos


def gerar_html(resultados):
    hoje = datetime.datetime.now().strftime("%d/%m/%Y")
    por_jogo = {}
    for r in resultados:
        por_jogo.setdefault(r["jogo"], []).append(r)

    if not resultados:
        blocos = "<p><em>Nenhuma novidade relevante encontrada hoje. Ate amanha!</em></p>"
    else:
        blocos = ""
        for jogo, posts in por_jogo.items():
            blocos += f"""
            <div style='margin-bottom:24px;border-left:4px solid #e67e22;padding-left:14px;'>
              <h3 style='margin:0 0 8px;color:#e67e22;'>&#127922; {jogo}</h3>
            """
            for p in posts:
                blocos += f"""
              <div style='margin-bottom:10px;background:#f9f9f9;padding:10px 12px;
                          border-radius:6px;border:1px solid #eee;'>
                <a href='{p["url"]}' style='font-weight:bold;color:#2c3e50;
                   text-decoration:none;' target='_blank'>{p["titulo"]}</a><br>
                <small style='color:#999;'>
                  r/{p["subreddit"]} &nbsp;|&nbsp;
                  u/{p["autor"]} &nbsp;|&nbsp;
                  &#128197; {p["criado"]}
                </small>
              </div>
                """
            blocos += "</div>"

    total = len(resultados)
    html = f"""
    <!DOCTYPE html><html lang='pt-BR'>
    <head><meta charset='UTF-8'>
    <style>
      body{{font-family:Arial,sans-serif;max-width:680px;margin:auto;
           background:#fff;color:#333;padding:20px;}}
      h1{{background:#2c3e50;color:#fff;padding:16px 20px;
          border-radius:8px;font-size:20px;margin-bottom:6px;}}
      .sub{{color:#666;font-size:13px;margin-bottom:24px;}}
      h2{{color:#2c3e50;border-bottom:2px solid #e67e22;
          padding-bottom:4px;font-size:16px;}}
      .rodape{{font-size:11px;color:#aaa;margin-top:30px;
               border-top:1px solid #eee;padding-top:10px;text-align:center;}}
    </style></head>
    <body>
      <h1>&#127922; Variacoes Diarias &mdash; Colecao all_type</h1>
      <p class='sub'><strong>Edicao de {hoje}</strong> &nbsp;|&nbsp;
        {total} resultado(s) &nbsp;|&nbsp;
        r/boardgames &bull; r/soloboardgaming &bull; r/boardgamevariants</p>
      <h2>&#128236; Novidades do Reddit</h2>
      {blocos}
      <div class='rodape'>
        Gerado automaticamente via GitHub Actions &bull; Todo dia as 08h (Brasilia)<br>
        Filtros: solo &bull; automa &bull; house rules &bull; variants &bull; homebrew<br>
        Repositorio: https://github.com/eliaslascoski-afk/newsletter-bg-variacoes
      </div>
    </body></html>
    """
    return html


def enviar_email(html):
    hoje = datetime.datetime.now().strftime("%d/%m/%Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[BG Newsletter] Variacoes & House Rules - {hoje}"
    msg["From"]    = EMAIL_REMETENTE
    msg["To"]      = EMAIL_DESTINATARIO
    msg.attach(MIMEText(html, "html", "utf-8"))
with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(EMAIL_REMETENTE, SENHA_APP)
        server.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIO, msg.as_string())
    print(f"E-mail enviado para {EMAIL_DESTINATARIO}")


def main():
    print("=== Newsletter BG Variacoes (RSS mode) ===")
    print(f"Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("Coletando posts via RSS publico do Reddit...")
    resultados = coletar_resultados()
    print(f"Total de posts relevantes: {len(resultados)}")
    html = gerar_html(resultados)
    print("Enviando e-mail...")
    enviar_email(html)
    print("Concluido!")


if __name__ == "__main__":
    main()
