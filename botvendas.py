import discord
from discord.ext import commands
from discord.ui import View, Button
import json
import os
from datetime import datetime

TOKEN = "MTQyNDU5MDU0Nzg0MjEwNTQ1NQ.GH9wS0.LJFpNxmEwp0Rq7YhWcSXCVK2AnyVaJayuBHPmM"

def carregar_json(caminho):
    if not os.path.exists(caminho):
        with open(caminho, "w", encoding="utf-8") as f:
            f.write("{}")
        return {}
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
            if not conteudo:
                with open(caminho, "w", encoding="utf-8") as fw:
                    fw.write("{}")
                return {}
            return json.loads(conteudo)
    except json.JSONDecodeError:
        with open(caminho, "w", encoding="utf-8") as fw:
            fw.write("{}")
        return {}

def get_paths(guild):
    server_name = "".join(c for c in guild.name if c.isalnum() or c in (" ", "-", "_")).rstrip()
    folder_path = os.path.join("servers", server_name)
    os.makedirs(folder_path, exist_ok=True)
    produtos_path = os.path.join(folder_path, "produtos.json")
    vendas_path = os.path.join(folder_path, "vendas.json")
    for path in [produtos_path, vendas_path]:
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("{}")
    return produtos_path, vendas_path

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

ID_CANAL_LOGS = 123456789012345678

@bot.event
async def on_guild_join(guild):
    produtos_path, vendas_path = get_paths(guild)
    print(f"Pasta criada para o servidor '{guild.name}' com arquivos iniciais.")

@bot.command()
async def loja(ctx):
    produtos_path, _ = get_paths(ctx.guild)
    produtos = carregar_json(produtos_path)
    if not produtos:
        await ctx.send("Nenhum produto disponível no momento.")
        return
    embed = discord.Embed(
        title="Loja Oficial",
        description="Escolha o produto que deseja comprar clicando em um dos botões abaixo:",
        color=discord.Color.green()
    )
    view = View()
    for nome_produto, info in produtos.items():
        valor = info.get("valor", 0)
        estoque = info.get("estoque", 0)
        label = f"{nome_produto} - R${valor:.2f} ({estoque} un.)"
        view.add_item(Button(label=label, style=discord.ButtonStyle.primary, custom_id=f"{ctx.guild.id}|{nome_produto}"))
    await ctx.send(embed=embed, view=view)

@bot.command()
async def addproduto(ctx, nome: str, valor: float, estoque: int = 1):
    if not any(role.name.lower() == "adm" for role in ctx.author.roles):
        await ctx.send("Você não tem permissão para adicionar produtos.")
        return
    produtos_path, _ = get_paths(ctx.guild)
    produtos = carregar_json(produtos_path)
    produtos[nome] = {"valor": valor, "estoque": estoque}
    with open(produtos_path, "w", encoding="utf-8") as f:
        json.dump(produtos, f, indent=4, ensure_ascii=False)
    await ctx.send(f"Produto {nome} adicionado com sucesso!\nValor: R${valor:.2f} | Estoque: {estoque}")

@bot.command()
async def meuspedidos(ctx):
    _, vendas_path = get_paths(ctx.guild)
    vendas = carregar_json(vendas_path)
    user_id = str(ctx.author.id)
    if user_id not in vendas or not vendas[user_id]:
        await ctx.send("Você ainda não fez nenhuma compra.")
        return
    embed = discord.Embed(
        title=f"Histórico de compras de {ctx.author.name}",
        color=discord.Color.blue()
    )
    for pedido in vendas[user_id]:
        embed.add_field(
            name=f"{pedido['produto']}",
            value=f"Valor: R${pedido['valor']:.2f}\nData: {pedido['data']}",
            inline=False
        )
    await ctx.send(embed=embed)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.data or interaction.data.get("custom_id") is None:
        return
    try:
        guild_id_str, produto = interaction.data["custom_id"].split("|")
        guild = bot.get_guild(int(guild_id_str))
        if guild is None:
            await interaction.response.send_message("Não consegui identificar o servidor da compra.", ephemeral=True)
            return
    except Exception:
        return
    produtos_path, vendas_path = get_paths(guild)
    produtos = carregar_json(produtos_path)
    vendas = carregar_json(vendas_path)
    if produto not in produtos:
        return
    info = produtos[produto]
    if info.get("estoque", 0) <= 0:
        await interaction.response.send_message("Este produto está sem estoque.", ephemeral=True)
        return
    valor = info.get("valor", 0)
    await interaction.response.send_message(
        f"{interaction.user.mention}, verifique seu privado para continuar a compra!",
        ephemeral=True
    )
    try:
        user = interaction.user
        view = View()
        botao_pix = Button(label="Pagar com PIX", style=discord.ButtonStyle.success)

        async def pagar_pix(inter: discord.Interaction):
            await inter.response.send_message(
                f"Chave PIX: pix@exemplo.com\nValor: R${valor:.2f}\nEnvie o comprovante da compra (imagem) para confirmar.",
                ephemeral=True
            )
            def check(msg):
                return msg.author == user and msg.attachments and msg.channel == inter.channel
            try:
                msg = await bot.wait_for("message", check=check, timeout=300)
            except:
                await user.send("Tempo limite para envio do comprovante expirou. Tente novamente mais tarde.")
                return
            data = datetime.now().strftime("%d/%m/%Y %H:%M")
            user_id = str(user.id)
            if user_id not in vendas:
                vendas[user_id] = []
            vendas[user_id].append({"produto": produto, "valor": valor, "data": data})
            with open(vendas_path, "w", encoding="utf-8") as f:
                json.dump(vendas, f, indent=4, ensure_ascii=False)
            produtos[produto]["estoque"] -= 1
            with open(produtos_path, "w", encoding="utf-8") as f:
                json.dump(produtos, f, indent=4, ensure_ascii=False)
            await msg.add_reaction("✅")
            await user.send(f"Compra recebida! Comprovante enviado para análise.\nProduto: {produto}\nValor: R${valor:.2f}")
            anexo_url = msg.attachments[0].url if msg.attachments else "Nenhum anexo enviado"
            dono = None
            try:
                dono = guild.owner or await guild.fetch_member(guild.owner_id)
            except:
                pass
            if dono:
                try:
                    await dono.send(
                        f"Nova venda no servidor {guild.name}!\n"
                        f"Comprador: {user.name} ({user.id})\n"
                        f"Produto: {produto}\n"
                        f"Valor: R${valor:.2f}\n"
                        f"Data: {data}\n"
                        f"Comprovante: {anexo_url}"
                    )
                except discord.Forbidden:
                    dono = None
            if not dono:
                canal_vendas = discord.utils.get(guild.text_channels, name="vendas")
                if canal_vendas:
                    await canal_vendas.send(
                        f"Nova venda no servidor!\n"
                        f"Comprador: {user.name} ({user.id})\n"
                        f"Produto: {produto}\n"
                        f"Valor: R${valor:.2f}\n"
                        f"Data: {data}\n"
                        f"Comprovante: {anexo_url}"
                    )
            canal_logs = bot.get_channel(ID_CANAL_LOGS)
            if canal_logs:
                await canal_logs.send(
                    f"Nova compra realizada!\n{user.mention}\nProduto: {produto}\nValor: R${valor:.2f}\n{data}"
                )

        botao_pix.callback = pagar_pix
        view.add_item(botao_pix)
        embed = discord.Embed(
            title=f"Compra de {produto}",
            description=f"Olá {user.name}, o valor do produto {produto} é R${valor:.2f}.\nEscolha abaixo o método de pagamento:",
            color=discord.Color.blurple()
        )
        await user.send(embed=embed, view=view)
    except discord.Forbidden:
        await interaction.followup.send(
            "Não consegui te mandar mensagem no privado! Verifique se seu PV está aberto.",
            ephemeral=True
        )

@bot.command()
async def vendas(ctx):
    if not any(role.name.lower() == "adm" for role in ctx.author.roles):
        await ctx.send("Você não tem permissão para ver todas as vendas.")
        return
    _, vendas_path = get_paths(ctx.guild)
    vendas = carregar_json(vendas_path)
    if not vendas:
        await ctx.send("Nenhuma venda registrada neste servidor.")
        return
    embed = discord.Embed(
        title=f"Todas as vendas do servidor {ctx.guild.name}",
        color=discord.Color.gold()
    )
    for user_id, pedidos in vendas.items():
        usuario = ctx.guild.get_member(int(user_id))
        nome_usuario = usuario.name if usuario else f"ID {user_id}"
        pedidos_texto = "\n".join([f"{p['produto']} - R${p['valor']:.2f} | {p['data']}" for p in pedidos])
        embed.add_field(name=nome_usuario, value=pedidos_texto, inline=False)
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")

bot.run(TOKEN)
