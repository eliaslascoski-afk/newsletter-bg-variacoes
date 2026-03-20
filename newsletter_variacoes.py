import smtplib
import datetime
import json
import urllib.request
import urllib.parse
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ============================================================
# CONFIGURACOES (via GitHub Secrets)
# ============================================================
EMAIL_REMETENTE    = os.environ["EMAIL_REMETENTE"]
SENHA_APP          = os.environ["SENHA_APP"]
EMAIL_DESTINATARIO = os.environ["EMAIL_DESTINATARIO"]

REDDIT_CLIENT_ID     = os.environ["REDDIT_CLIENT_ID"]
REDDIT_CLIENT_SECRET = os.environ["REDDIT_CLIENT_SECRET"]
REDDIT_USER_AGENT    = "newsletter_bg_variacoes/1.0 (by eliaslascoski)"

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
    "Fishing card game",
]

TERMOS_FILTRO = [
    "solo", "automa", "house rule", "house rules",
    "variant", "single player", "singleplayer",
    "fan made", "homebrew", "mod", "tweak",
    "modo solo", "variante", "regra caseira",
    "expansion", "unofficial", "custom",
]

SUBREDDITS = [
    "boardgames",
    "soloboardgaming",
    "boardgamevariants",
    "tabletopgamedesign",
]


def get_reddit_token():
    data = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    credentials = f"{REDDIT_CLIENT_ID}:{REDDIT_CLIENT_SECRET}"
    import base64
    encoded = base64.b64encode(credentials.encode()).decode()
    req = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=data,
        headers={
            "Authorization": f"Basic {encoded}",
            "User-Agent": REDDIT_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())["access_token"]


def buscar_posts(token, jogo, subreddit, limite=15):
    query = urllib.parse.quote(
        f'{jogo} (solo OR automa OR "house rule" OR variant OR homebrew)'
    )
    url = (f"https://oauth.reddit.com/r/{subreddit}/search"
           f"?q={query}&sort=new&limit={limite}&t=week&restrict_sr=1")
    req = urllib.request.Request(url, headers={
        "Authorization": f"bearer {token}",
        "User-Agent": REDDIT_USER_AGENT,
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()).get("data", {}).get("children", [])
    except Exception as e:
        print(f"  Erro buscando {jogo} em r/{subreddit}: {e}")
        return []


def e_relevante(post):
    titulo = post["data"].get("title", "").lower()
    corpo  = post["data"].get("selftext", "").lower()
    texto  = titulo + " " + corpo
    return any(t in texto for t in TERMOS_FILTRO)


def coletar_resultados(token):
    resultados = []
    for jogo in JOGOS:
        print(f"Buscando: {jogo}")
        for sub in SUBREDDITS:
            posts = buscar_posts(token, jogo, sub)
            for post in posts:
                if e_relevante(post):
                    resultados.append({
                        "jogo": jogo,
                        "subreddit": sub,
                        "titulo": post["data"]["title"],
                        "url": "https://reddit.com" + post["data"]["permalink"],
                        "score": post["data"]["score"],
                        "comentarios": post["data"]["num_comments"],
                        "criado": datetime.datetime.fromtimestamp(
                            post["data"]["created_utc"]
                        ).strftime("%d/%m/%Y"),
                    })
    # Remove duplicatas
    vistos, unicos = set(), []
    for r in resultados:
        if r["url"] not in vistos:
            vistos.add(r["url"])
            unicos.append(r)
    unicos.sort(key=lambda x: x["score"], reverse=True)
    return unicos


def gerar_html(resultados):
    hoje = datetime.datetime.now().strftime("%d/%m/%Y")
    por_jogo = {}
    for r in resultados:
        por_jogo.setdefault(r["jogo"], []).append(r)

    blocos = ""
    if not resultados:
        blocos = "<p><em>Nenhuma novidade relevante encontrada hoje. Ate amanha!</em></p>"
    else:
        for jogo, posts in por_jogo.items():
            blocos += f"""
            <div style='margin-bottom:24px;border-left:4px solid #e67e22;padding-left:14px;'>
              <h3 style='margin:0 0 8px;color:#e67e22;'>&#127922; {jogo}</h3>
            """
            for p in posts:
                blocos += f"""
              <div style='margin-bottom:10px;background:#f9f9f9;padding:10px 12px;
                          border-radius:6px;border:1px solid #eee;'>
                <a href='{p["url"]}' style='font-weight:bold;color:#2c3e50;text-decoration:none;'
                   target='_blank'>{p["titulo"]}</a><br>
                <small style='color:#999;'>
                  r/{p["subreddit"]} &nbsp;|&nbsp;
                  &#8679; {p["score"]} &nbsp;|&nbsp;
                  &#128172; {p["comentarios"]} comentarios &nbsp;|&nbsp;
                  &#128197; {p["criado"]}
                </small>
              </div>
                """
            blocos += "</div>"

    total = len(resultados)
    html = f"""
    <!DOCTYPE html>
    <html lang='pt-BR'>
    <head><meta charset='UTF-8'>
    <style>
      body{{font-family:Arial,sans-serif;max-width:680px;margin:auto;
           background:#fff;color:#333;padding:20px;}}
      h1{{background:#2c3e50;color:#fff;padding:16px 20px;border-radius:8px;
          font-size:20px;margin-bottom:6px;}}
      .subtitulo{{color:#666;font-size:13px;margin-bottom:24px;}}
      h2{{color:#2c3e50;border-bottom:2px solid #e67e22;padding-bottom:4px;font-size:16px;}}
      a{{color:#e67e22;}}
      .rodape{{font-size:11px;color:#aaa;margin-top:30px;border-top:1px solid #eee;
               padding-top:10px;text-align:center;}}
    </style>
    </head>
    <body>
      <h1>&#127922; Variacoes Diarias &mdash; Colecao all_type</h1>
      <p class='subtitulo'>
        <strong>Edicao de {hoje}</strong> &nbsp;|&nbsp;
        {total} resultado(s) filtrado(s) &nbsp;|&nbsp;
        Fontes: r/boardgames, r/soloboardgaming, r/boardgamevariants
      </p>
      <h2>&#128236; Novidades do Reddit</h2>
      {blocos}
      <div class='rodape'>
        Gerado automaticamente via GitHub Actions &bull;
        Filtros: solo &bull; automa &bull; house rules &bull; variants &bull; homebrew<br>
        Para cancelar ou alterar, acesse:
        https://github.com/eliaslascoski-afk/newsletter-bg-variacoes
      </div>
    </body>
    </html>
    """
    return html


def enviar_email(html):
    hoje = datetime.datetime.now().strftime("%d/%m/%Y")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[BG Newsletter] Variacoes & House Rules — {hoje}"
    msg["From"]    = EMAIL_REMETENTE
    msg["To"]      = EMAIL_DESTINATARIO
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_REMETENTE, SENHA_APP)
        server.sendmail(EMAIL_REMETENTE, EMAIL_DESTINATARIO, msg.as_string())
    print(f"E-mail enviado para {EMAIL_DESTINATARIO}")


def main():
    print("=== Newsletter BG Variacoes ===")
    print(f"Data: {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}")
    print("Obtendo token Reddit...")
    token = get_reddit_token()
    print("Coletando posts...")
    resultados = coletar_resultados(token)
    print(f"Total de posts relevantes encontrados: {len(resultados)}")
    html = gerar_html(resultados)
    print("Enviando e-mail...")
    enviar_email(html)
    print("Concluido!")


if __name__ == "__main__":
    main()
