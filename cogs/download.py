import discord
from utils.default import CustomContext
from discord.ext import commands
from utils.data import DiscordBot
from utils import http


class Download_Commands(commands.Cog):
    def __init__(self, bot):
        self.bot: DiscordBot = bot

    @commands.group(invoke_without_command=True)
    async def AD(self, ctx: CustomContext):
        """ AllDebrid API commands """
        await ctx.send("Use `!AB status` to check AllDebrid API authentication status")

    @AD.command()
    async def status(self, ctx: CustomContext):
        """ Check AllDebrid API authentication status """
        # Get API key from bot config
        api_key = self.bot.config.alldebrid_api_key
        
        if not api_key:
            await ctx.send("❌ **Error:** ALLDEBRID_API_KEY not found in .env file")
            return

        async with ctx.channel.typing():
            try:
                # Make authenticated request to AllDebrid API
                headers = {'Authorization': f'Bearer {api_key}'}
                response = await http.get('https://api.alldebrid.com/v4/user', headers=headers, res_method="json")
                
                if response.status == 200:
                    data = response.response
                    if data.get('status') == 'success':
                        user_data = data.get('data', {}).get('user', {})
                        username = user_data.get('username', 'Unknown')
                        is_premium = user_data.get('isPremium', False)
                        premium_status = "✅ Premium" if is_premium else "❌ Free"
                        
                        embed = discord.Embed(
                            title="🔗 AllDebrid API Status",
                            description="✅ **Authentication successful!**",
                            color=discord.Color.green()
                        )
                        embed.add_field(name="Username", value=username, inline=True)
                        embed.add_field(name="Account Type", value=premium_status, inline=True)
                        embed.add_field(name="API Status", value="🟢 Connected", inline=True)
                        
                        await ctx.send(embed=embed)
                    else:
                        error_msg = data.get('error', {}).get('message', 'Unknown error')
                        await ctx.send(f"❌ **API Error:** {error_msg}")
                elif response.status == 401:
                    await ctx.send("❌ **Authentication Failed:** Invalid API key")
                elif response.status == 429:
                    await ctx.send("⚠️ **Rate Limited:** Too many requests to AllDebrid API")
                else:
                    await ctx.send(f"❌ **HTTP Error:** Status code {response.status}")
                    
            except Exception as e:
                # More detailed error information
                error_type = type(e).__name__
                await ctx.send(f"❌ **Connection Error:** {error_type} - {str(e)}")
                # For debugging, you can uncomment the next line to see full traceback
                # await ctx.send(f"Debug: {repr(e)}")


async def setup(bot):
    await bot.add_cog(Download_Commands(bot))
