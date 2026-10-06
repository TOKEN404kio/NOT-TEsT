import discord
from discord import app_commands
import json
import os
from flask import Flask
from threading import Thread

# --- Flask Web Server Setup (Required for Render) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run_web_server():
    # Render provides a PORT environment variable automatically
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# --- Discord Bot Setup ---
class BackupBot(discord.Client):
    def __init__(self):
        # Requests all intents so the bot can read channels, categories, and roles
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        # Syncs the slash commands with Discord
        await self.tree.sync()
        print(f'Logged in as {self.user} and commands synced.')

client = BackupBot()

# 1. Command to save the server structure
@client.tree.command(name="backup", description="Saves the current server layout.")
@app_commands.checks.has_permissions(administrator=True)
async def backup(interaction: discord.Interaction):
    guild = interaction.guild
    backup_data = {
        "server_name": guild.name,
        "categories": [],
        "roles": []
    }

    # Save roles (excluding @everyone and bot-managed roles)
    for role in guild.roles:
        if not role.is_default() and not role.managed:
            backup_data["roles"].append({
                "name": role.name,
                "color": role.color.value,
                "permissions": role.permissions.value
            })

    # Save categories and their underlying channels
    for category in guild.categories:
        cat_data = {"name": category.name, "channels": []}
        for channel in category.channels:
            cat_data["channels"].append({
                "name": channel.name,
                "type": str(channel.type)
            })
        backup_data["categories"].append(cat_data)

    # Save data to a local JSON file named after the server ID
    with open(f"backup_{guild.id}.json", "w") as f:
        json.dump(backup_data, f, indent=4)

    await interaction.response.send_message("✅ Server layout successfully backed up!")

# 2. Command to restore the server structure
@client.tree.command(name="restore", description="Restores the saved server layout.")
@app_commands.checks.has_permissions(administrator=True)
async def restore(interaction: discord.Interaction):
    guild = interaction.guild
    file_path = f"backup_{guild.id}.json"

    if not os.path.exists(file_path):
        await interaction.response.send_message("❌ No backup file found for this server.", ephemeral=True)
        return

    await interaction.response.send_message("🔄 Restoring server structure... This may take a moment.")

    with open(file_path, "r") as f:
        data = json.load(f)

    # Restore original server name
    await guild.edit(name=data["server_name"])

    # Recreate the roles
    created_roles = {}
    for r_data in data["roles"]:
        role = await guild.create_role(
            name=r_data["name"],
            color=discord.Color(r_data["color"]),
            permissions=discord.Permissions(r_data["permissions"])
        )
        created_roles[r_data["name"]] = role

    # Recreate categories, text channels, and voice channels
    for cat_data in data["categories"]:
        category = await guild.create_category(name=cat_data["name"])
        for ch_data in cat_data["channels"]:
            if ch_data["type"] == "text":
                await guild.create_text_channel(name=ch_data["name"], category=category)
            elif ch_data["type"] == "voice":
                await guild.create_voice_channel(name=ch_data["name"], category=category)

    await interaction.channel.send("✨ Server structure restoration complete!")

# --- Execution ---
if __name__ == "__main__":
    keep_alive()  # Starts the background web server for Render
    
    # Securely gets the token from Render's Environment Variables
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        client.run(token)
    else:
        print("Error: No DISCORD_TOKEN found in your environment variables.")

