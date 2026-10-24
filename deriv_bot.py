import os
import json
import logging
import asyncio
import websockets
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

# --- Configuration (lue depuis les variables d'environnement sur Railway) ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
DERIV_API_TOKEN = os.environ.get("DERIV_API_TOKEN")

# URL du WebSocket de Deriv pour le compte démo
DERIV_WS_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

# Symbole de l'or sur Deriv (XAU/USD)
SYMBOL = "frxXAUUSD"

async def deriv_connect():
    """Se connecte à Deriv et s'authentifie."""
    ws = await websockets.connect(DERIV_WS_URL)
    await ws.send(json.dumps({"authorize": DERIV_API_TOKEN}))
    response = await ws.recv()
    auth_data = json.loads(response)
    if "error" in auth_data:
        raise Exception(f"Erreur d'authentification Deriv : {auth_data['error']['message']}")
    logging.info("Connecté à Deriv avec succès.")
    return ws

async def get_balance(ws):
    """Récupère le solde du compte."""
    await ws.send(json.dumps({"balance": 1, "subscribe": 0}))
    response = await ws.recv()
    data = json.loads(response)
    return data.get("balance", {}).get("balance", 0), data.get("balance", {}).get("currency", "USD")

async def place_trade(ws, contract_type, stake=1):
    """Place un trade (CALL pour achat, PUT pour vente)."""
    proposal_req = {
        "proposal": 1,
        "amount": stake,
        "basis": "stake",
        "contract_type": contract_type,
        "currency": "USD",
        "duration": 5,
        "duration_unit": "m",
        "symbol": SYMBOL
    }
    await ws.send(json.dumps(proposal_req))
    proposal_resp = json.loads(await ws.recv())

    if "error" in proposal_resp:
        return f"Erreur de proposition : {proposal_resp['error']['message']}"

    proposal_id = proposal_resp["proposal"]["id"]
    ask_price = proposal_resp["proposal"]["ask_price"]

    buy_req = {
        "buy": proposal_id,
        "price": ask_price
    }
    await ws.send(json.dumps(buy_req))
    buy_resp = json.loads(await ws.recv())

    if "error" in buy_resp:
        return f"Erreur d'achat : {buy_resp['error']['message']}"

    return f"✅ Ordre {contract_type} placé pour {stake} USD sur {SYMBOL}. Contrat ID: {buy_resp['buy']['contract_id']}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 Bot Deriv (Démo) activé !\n"
        "Commandes :\n"
        "/status - Voir le solde\n"
        "/buy - Acheter (CALL) sur l'or\n"
        "/sell - Vendre (PUT) sur l'or\n"
        "/help - Aide"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        ws = await deriv_connect()
        balance, currency = await get_balance(ws)
        await ws.close()
        await update.message.reply_text(f"💰 Solde du compte démo : **{balance:.2f} {currency}**", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur : {e}")

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        ws = await deriv_connect()
        msg = await place_trade(ws, "CALL", stake=1)
        await ws.close()
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur lors de l'achat : {e}")

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        ws = await deriv_connect()
        msg = await place_trade(ws, "PUT", stake=1)
        await ws.close()
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"❌ Erreur lors de la vente : {e}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Commandes disponibles :\n"
        "/start - Démarrer le bot\n"
        "/status - Voir ton solde\n"
        "/buy - Placer un achat (CALL) sur l'or\n"
        "/sell - Placer une vente (PUT) sur l'or"
    )

def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("buy", buy))
    app.add_handler(CommandHandler("sell", sell))
    app.add_handler(CommandHandler("help", help_command))
    print("Bot démarré, en attente de messages...")
    app.run_polling()

if __name__ == "__main__":
    main()
