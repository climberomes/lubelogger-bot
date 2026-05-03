import discord
from discord import app_commands
from discord.ext import commands
import aiohttp
import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
LUBELOGGER_URL = os.getenv("LUBELOGGER_URL")        # e.g. http://192.168.1.50:8080
LUBELOGGER_API_KEY = os.getenv("LUBELOGGER_API_KEY") # API key from LubeLogger settings
ALLOWED_CHANNEL = os.getenv("ALLOWED_CHANNEL_ID")   # Optional: restrict to a channel ID

# ── Bot setup ──────────────────────────────────────────────────────────────────
intents = discord.Intents.default()

class LubeBot(commands.Bot):
    async def setup_hook(self):
        try:
            synced = await self.tree.sync()
            print(f"✅  Synced {len(synced)} commands: {[c.name for c in synced]}")
        except Exception as e:
            print(f"❌  Sync failed: {e}")

bot = LubeBot(command_prefix="!", intents=intents)

# ── Helpers ────────────────────────────────────────────────────────────────────
def lubelogger_headers() -> dict:
    """Build request headers with API key and locale-invariant formatting."""
    headers = {
        "Content-Type": "application/json",
        "culture-invariant": "",   # Return numbers as numbers, not locale strings
    }
    if LUBELOGGER_API_KEY:
        headers["x-api-key"] = LUBELOGGER_API_KEY
    return headers

async def get_vehicles() -> list[dict]:
    """Fetch all vehicles from LubeLogger."""
    async with aiohttp.ClientSession(headers=lubelogger_headers()) as session:
        async with session.get(f"{LUBELOGGER_URL}/api/vehicles") as resp:
            resp.raise_for_status()
            return await resp.json()

async def add_gas_record(vehicle_id: int, mileage: int, gallons: float,
                         cost: float, location: str) -> dict:
    """POST a new fuel-up record to LubeLogger."""
    payload = {
        "date": date.today().isoformat(),   # YYYY-MM-DD
        "odometer": mileage,
        "fuelConsumed": gallons,
        "cost": cost,
        "notes": "",
        "tags": location,                   # location → tag field
        "isFillToFull": True,
        "missedFuelUp": False,
        "extraFields": [],
    }
    async with aiohttp.ClientSession(headers=lubelogger_headers()) as session:
        async with session.post(
            f"{LUBELOGGER_URL}/api/vehicle/gasrecords/add?vehicleId={vehicle_id}",
            json=payload,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

def build_vehicle_choices_cache(vehicles: list[dict]) -> list[app_commands.Choice]:
    """Turn vehicle list into slash-command choices (max 25)."""
    return [
        app_commands.Choice(name=f"[{v['id']}] {v['name']}", value=str(v["id"]))
        for v in vehicles[:25]
    ]

async def add_service_record(vehicle_id: int, odometer: int, description: str,
                             cost: float, notes: str) -> dict:
    """POST a new service record to LubeLogger."""
    payload = {
        "date": date.today().isoformat(),
        "odometer": odometer,
        "description": description,
        "cost": cost,
        "notes": notes,
        "tags": "",
        "extraFields": [],
    }
    async with aiohttp.ClientSession(headers=lubelogger_headers()) as session:
        async with session.post(
            f"{LUBELOGGER_URL}/api/vehicle/servicerecords/add?vehicleId={vehicle_id}",
            json=payload,
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

# ── Events ─────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅  Logged in as {bot.user}")

# ── /fuel command ──────────────────────────────────────────────────────────────
@bot.tree.command(name="fuel", description="Log a fuel-up to LubeLogger")
@app_commands.describe(
    car_id    = "Vehicle ID from LubeLogger (use /cars to list)",
    mileage   = "Current odometer reading (miles or km)",
    gallons   = "Gallons (or litres) pumped",
    total_cost= "Total cost of the fill-up (dollars)",
    location  = "Station name / location — saved as a tag",
)
async def fuel(
    interaction: discord.Interaction,
    car_id    : int,
    mileage   : int,
    gallons   : float,
    total_cost: float,
    location  : str,
):
    # Optional channel guard
    if ALLOWED_CHANNEL and str(interaction.channel_id) != ALLOWED_CHANNEL:
        await interaction.response.send_message(
            "⛔  This command is only allowed in the designated channel.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=False)

    try:
        result = await add_gas_record(car_id, mileage, gallons, total_cost, location)
    except aiohttp.ClientResponseError as e:
        await interaction.followup.send(
            f"❌  LubeLogger returned **HTTP {e.status}**: {e.message}"
        )
        return
    except Exception as e:
        await interaction.followup.send(f"❌  Unexpected error: `{e}`")
        return

    ppg = total_cost / gallons if gallons else 0

    embed = discord.Embed(
        title="⛽  Fuel-up Logged!",
        color=discord.Color.green(),
    )
    embed.add_field(name="🚗 Vehicle ID",  value=f"`{car_id}`",              inline=True)
    embed.add_field(name="📍 Location",    value=location,                   inline=True)
    embed.add_field(name="🔢 Odometer",    value=f"{mileage:,}",             inline=True)
    embed.add_field(name="🪣 Gallons",     value=f"{gallons:.3f}",           inline=True)
    embed.add_field(name="💵 Total Cost",  value=f"${total_cost:.2f}",       inline=True)
    embed.add_field(name="📊 Price/Gal",   value=f"${ppg:.3f}",              inline=True)
    embed.set_footer(text=f"Date: {date.today().isoformat()}")

    await interaction.followup.send(embed=embed)


# ── /service command ──────────────────────────────────────────────────────────
@bot.tree.command(name="service", description="Log a service record to LubeLogger")
@app_commands.describe(
    car_id      = "Vehicle ID from LubeLogger (use /cars to list)",
    odometer    = "Current odometer reading",
    description = "What was done (e.g. Oil Change) — can be left blank",
    cost        = "Total cost of the service",
    notes       = "Any additional notes — can be left blank",
)
async def service(
    interaction: discord.Interaction,
    car_id     : int,
    odometer   : int,
    cost       : float,
    description: str = "",
    notes      : str = "",
):
    if ALLOWED_CHANNEL and str(interaction.channel_id) != ALLOWED_CHANNEL:
        await interaction.response.send_message(
            "⛔  This command is only allowed in the designated channel.", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=False)

    try:
        result = await add_service_record(car_id, odometer, description, cost, notes)
    except aiohttp.ClientResponseError as e:
        await interaction.followup.send(
            f"❌  LubeLogger returned **HTTP {e.status}**: {e.message}"
        )
        return
    except Exception as e:
        await interaction.followup.send(f"❌  Unexpected error: `{e}`")
        return

    embed = discord.Embed(
        title="🔧  Service Record Logged!",
        color=discord.Color.blue(),
    )
    embed.add_field(name="🚗 Vehicle ID",   value=f"`{car_id}`",          inline=True)
    embed.add_field(name="🔢 Odometer",     value=f"{odometer:,}",        inline=True)
    embed.add_field(name="💵 Cost",         value=f"${cost:.2f}",         inline=True)
    if description:
        embed.add_field(name="📋 Description", value=description,         inline=False)
    if notes:
        embed.add_field(name="📝 Notes",       value=notes,               inline=False)
    embed.set_footer(text=f"Date: {date.today().isoformat()}")

    await interaction.followup.send(embed=embed)


# ── /cars command ──────────────────────────────────────────────────────────────
@bot.tree.command(name="cars", description="List all vehicles in LubeLogger")
async def cars(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    try:
        vehicles = await get_vehicles()
    except Exception as e:
        await interaction.followup.send(f"❌  Could not fetch vehicles: `{e}`")
        return

    if not vehicles:
        await interaction.followup.send("No vehicles found in LubeLogger.")
        return

    embed = discord.Embed(title="🚗  Vehicles in LubeLogger", color=discord.Color.blurple())
    for v in vehicles:
        label = f"{v.get('year', '')} {v.get('make', '')} {v.get('model', '')}".strip()
        embed.add_field(
            name=f"[{v['id']}] {label}",
            value=f"Plate: {v.get('licensePlate', '—')}",
            inline=False,
        )
    await interaction.followup.send(embed=embed)


# ── Run ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN is not set in .env")
    if not LUBELOGGER_URL:
        raise RuntimeError("LUBELOGGER_URL is not set in .env")
    if not LUBELOGGER_API_KEY:
        print("⚠️  Warning: LUBELOGGER_API_KEY is not set — requests will be unauthenticated")
    bot.run(DISCORD_TOKEN)
