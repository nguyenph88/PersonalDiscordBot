import discord
from utils.default import CustomContext
from discord.ext import commands
from utils.data import DiscordBot
from utils import http


class Download_Commands(commands.Cog):
    def __init__(self, bot):
        self.bot: DiscordBot = bot

    def _get_api_key(self):
        """Get AllDebrid API key from config"""
        return self.bot.config.alldebrid_api_key

    def _clean_service_name(self, service_name: str) -> str:
        """Clean service name by removing URL prefixes and extensions"""
        cleaned_name = service_name.strip().lower()
        
        # Remove common URL prefixes
        prefixes_to_remove = ['www.', 'http://', 'https://', 'ftp://']
        for prefix in prefixes_to_remove:
            if cleaned_name.startswith(prefix):
                cleaned_name = cleaned_name[len(prefix):]
        
        # Remove common domain extensions
        extensions_to_remove = [
            '.com', '.net', '.org', '.co', '.io', '.tv', '.me', '.info', '.biz',
            '.us', '.uk', '.de', '.fr', '.it', '.es', '.nl', '.ru', '.cn', '.jp',
            '.kr', '.in', '.br', '.au', '.ca', '.mx', '.ar', '.cl', '.pe',
            '.co.uk', '.com.au', '.co.jp', '.co.kr', '.co.in', '.co.za', '.co.nz',
            '.co.il', '.co.ke', '.co.ug', '.co.tz', '.co.zw', '.co.bw', '.co.na'
        ]
        for ext in extensions_to_remove:
            if cleaned_name.endswith(ext):
                cleaned_name = cleaned_name[:-len(ext)]
        
        # Remove trailing slashes and dots
        return cleaned_name.rstrip('/.').strip()

    async def _make_api_request(self, url: str, headers: dict = None, res_method: str = "json"):
        """Make API request with error handling"""
        try:
            response = await http.get(url, headers=headers, res_method=res_method)
            return response
        except Exception as e:
            raise Exception(f"Connection Error: {type(e).__name__} - {str(e)}")

    def _create_error_embed(self, title: str, description: str, error_type: str = None):
        """Create a standardized error embed"""
        embed = discord.Embed(title=title, description=description, color=discord.Color.red())
        if error_type:
            embed.add_field(name="Error Type", value=error_type, inline=True)
        return embed

    def _create_success_embed(self, title: str, description: str, color: discord.Color = discord.Color.green()):
        """Create a standardized success embed"""
        return discord.Embed(title=title, description=description, color=color)

    async def _check_api_authentication(self):
        """Check if API key is available"""
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("ALLDEBRID_API_KEY not found in .env file")
        return api_key

    async def _get_hosts_data(self):
        """Get hosts data from AllDebrid API"""
        response = await self._make_api_request('https://api.alldebrid.com/v4/hosts')
        
        if response.status != 200:
            raise Exception(f"HTTP Error: Status code {response.status}")
        
        data = response.response
        if data.get('status') != 'success':
            error_msg = data.get('error', {}).get('message', 'Unknown error')
            raise Exception(f"API Error: {error_msg}")
        
        hosts_data = data.get('data', {})
        if not hosts_data:
            raise Exception("No hosts data available")
        
        return hosts_data

    def _extract_service_lists(self, hosts_data: dict):
        """Extract hosts, streams, and redirectors from API data"""
        hosts_list = []
        streams_list = []
        redirectors_list = []
        
        if isinstance(hosts_data, dict):
            # Extract hosts
            if 'hosts' in hosts_data:
                hosts_item = hosts_data['hosts']
                if isinstance(hosts_item, list):
                    hosts_list = hosts_item
                elif isinstance(hosts_item, dict):
                    hosts_list = list(hosts_item.keys())
            
            # Extract streams
            if 'streams' in hosts_data:
                streams_item = hosts_data['streams']
                if isinstance(streams_item, list):
                    streams_list = streams_item
                elif isinstance(streams_item, dict):
                    streams_list = list(streams_item.keys())
            
            # Extract redirectors
            if 'redirectors' in hosts_data:
                redirectors_item = hosts_data['redirectors']
                if isinstance(redirectors_item, list):
                    redirectors_list = redirectors_item
                elif isinstance(redirectors_item, dict):
                    redirectors_list = list(redirectors_item.keys())
        
        return hosts_list, streams_list, redirectors_list

    @commands.group(invoke_without_command=True)
    async def AD(self, ctx: CustomContext):
        """ AllDebrid API commands """
        await ctx.send("Available commands:\n`!AD status` - Check API authentication\n`!AD supported_host <name>` - Check if a service is supported\n`!AD supported_hosts` - List all supported services\n`!AD history <number>` - Get recent download history")

    @AD.command()
    async def status(self, ctx: CustomContext):
        """ Check AllDebrid API authentication status """
        async with ctx.channel.typing():
            try:
                api_key = await self._check_api_authentication()
                headers = {'Authorization': f'Bearer {api_key}'}
                response = await self._make_api_request('https://api.alldebrid.com/v4/user', headers=headers)
                
                data = response.response
                user_data = data.get('data', {}).get('user', {})
                username = user_data.get('username', 'Unknown')
                is_premium = user_data.get('isPremium', False)
                premium_status = "✅ Premium" if is_premium else "❌ Free"
                
                embed = self._create_success_embed(
                    "🔗 AllDebrid API Status",
                    "✅ **Authentication successful!**"
                )
                embed.add_field(name="Username", value=username, inline=True)
                embed.add_field(name="Account Type", value=premium_status, inline=True)
                embed.add_field(name="API Status", value="🟢 Connected", inline=True)
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                error_embed = self._create_error_embed("❌ Authentication Failed", str(e))
                await ctx.send(embed=error_embed)

    @AD.command()
    async def supported_host(self, ctx: CustomContext, *, service_name: str):
        """ Check if a specific host/stream/redirector is supported by AllDebrid """
        if not service_name:
            await ctx.send("❌ **Error:** Please provide a service name to check")
            return
        
        cleaned_name = self._clean_service_name(service_name)
        if not cleaned_name:
            await ctx.send("❌ **Error:** Please provide a valid service name")
            return
        
        async with ctx.channel.typing():
            try:
                hosts_data = await self._get_hosts_data()
                hosts_list, streams_list, redirectors_list = self._extract_service_lists(hosts_data)
                
                # Check if the cleaned service name is supported
                if cleaned_name in [host.lower() for host in hosts_list]:
                    embed = self._create_success_embed(
                        "✅ Service Supported!",
                        f"**{service_name}** is supported as a **Host** on AllDebrid"
                    )
                    embed.add_field(name="Category", value="📁 File Hosting", inline=True)
                    embed.add_field(name="Status", value="🟢 Active", inline=True)
                    embed.add_field(name="Cleaned Name", value=f"`{cleaned_name}`", inline=True)
                    await ctx.send(embed=embed)
                    return
                
                if cleaned_name in [stream.lower() for stream in streams_list]:
                    embed = self._create_success_embed(
                        "✅ Service Supported!",
                        f"**{service_name}** is supported as a **Stream** on AllDebrid"
                    )
                    embed.add_field(name="Category", value="🎬 Streaming", inline=True)
                    embed.add_field(name="Status", value="🟢 Active", inline=True)
                    embed.add_field(name="Cleaned Name", value=f"`{cleaned_name}`", inline=True)
                    await ctx.send(embed=embed)
                    return
                
                if cleaned_name in [redirector.lower() for redirector in redirectors_list]:
                    embed = self._create_success_embed(
                        "✅ Service Supported!",
                        f"**{service_name}** is supported as a **Redirector** on AllDebrid"
                    )
                    embed.add_field(name="Category", value="🔗 Link Redirector", inline=True)
                    embed.add_field(name="Status", value="🟢 Active", inline=True)
                    embed.add_field(name="Cleaned Name", value=f"`{cleaned_name}`", inline=True)
                    await ctx.send(embed=embed)
                    return
                
                # Service not found
                embed = self._create_error_embed(
                    "❌ Service Not Supported",
                    f"**{service_name}** is not currently supported by AllDebrid"
                )
                embed.add_field(name="Cleaned Name", value=f"`{cleaned_name}`", inline=True)
                embed.add_field(name="Total Supported Services", value=f"Hosts: {len(hosts_list)} | Streams: {len(streams_list)} | Redirectors: {len(redirectors_list)}", inline=False)
                embed.set_footer(text="Use !AD supported_hosts to see all supported services")
                await ctx.send(embed=embed)
                
            except Exception as e:
                error_embed = self._create_error_embed("❌ Error", str(e))
                await ctx.send(embed=error_embed)

    @AD.command()
    async def supported_hosts(self, ctx: CustomContext):
        """ List all supported hosts on AllDebrid """
        async with ctx.channel.typing():
            try:
                hosts_data = await self._get_hosts_data()
                hosts_list, streams_list, redirectors_list = self._extract_service_lists(hosts_data)
                
                embed = discord.Embed(
                    title="🌐 AllDebrid Supported Services",
                    description=f"**Hosts:** {len(hosts_list)} | **Streams:** {len(streams_list)} | **Redirectors:** {len(redirectors_list)}",
                    color=discord.Color.purple()
                )
                
                # Add hosts field
                if hosts_list:
                    hosts_display = ", ".join(hosts_list[:15])
                    if len(hosts_list) > 15:
                        hosts_display += f"\n... and {len(hosts_list) - 15} more"
                    embed.add_field(
                        name=f"📁 Hosts ({len(hosts_list)})",
                        value=hosts_display,
                        inline=False
                    )
                
                # Add streams field
                if streams_list:
                    streams_display = ", ".join(streams_list[:15])
                    if len(streams_list) > 15:
                        streams_display += f"\n... and {len(streams_list) - 15} more"
                    embed.add_field(
                        name=f"🎬 Streams ({len(streams_list)})",
                        value=streams_display,
                        inline=False
                    )
                
                # Add redirectors field
                if redirectors_list:
                    redirectors_display = ", ".join(redirectors_list[:15])
                    if len(redirectors_list) > 15:
                        redirectors_display += f"\n... and {len(redirectors_list) - 15} more"
                    embed.add_field(
                        name=f"🔗 Redirectors ({len(redirectors_list)})",
                        value=redirectors_display,
                        inline=False
                    )
                
                embed.set_footer(text="Note: These are the supported services on AllDebrid")
                await ctx.send(embed=embed)
                
            except Exception as e:
                error_embed = self._create_error_embed("❌ Error", str(e))
                await ctx.send(embed=error_embed)

    @AD.command()
    async def history(self, ctx: CustomContext, limit: int = 10):
        """ Get recent download history from AllDebrid """
        # Validate limit
        if limit < 1 or limit > 50:
            await ctx.send("❌ **Error:** Please specify a number between 1 and 50")
            return
        
        async with ctx.channel.typing():
            try:
                api_key = await self._check_api_authentication()
                headers = {'Authorization': f'Bearer {api_key}'}
                response = await self._make_api_request('https://api.alldebrid.com/v4/user/links', headers=headers)
                
                data = response.response
                links_data = data.get('data', {}).get('links', [])
                
                if not links_data:
                    await ctx.send("📭 **No Links Found:** No download links available")
                    return
                
                # Limit the links to the requested number
                limited_links = links_data[:limit]
                
                embed = discord.Embed(
                    title=f"📋 AllDebrid Download Links (Last {len(limited_links)} items)",
                    color=discord.Color.blue()
                )
                
                for i, item in enumerate(limited_links, 1):
                    # Extract relevant information from links item
                    link = item.get('link', 'Unknown')
                    host = item.get('host', 'Unknown')
                    filename = item.get('filename', 'Unknown')
                    size = item.get('size', 'Unknown')
                    date = item.get('date', 'Unknown')
                    status = item.get('status', 'Unknown')
                    
                    # Truncate long values for display
                    display_link = link[:50] + "..." if len(link) > 50 else link
                    display_filename = filename[:30] + "..." if len(filename) > 30 else filename
                    
                    # Status emoji
                    status_emoji = "✅" if status == "downloaded" else "⏳" if status == "downloading" else "❌"
                    
                    field_value = f"**Host:** {host}\n**File:** {display_filename}\n**Size:** {size}\n**Status:** {status_emoji} {status}\n**Date:** {date}\n**Link:** {display_link}"
                    
                    embed.add_field(
                        name=f"#{i}",
                        value=field_value,
                        inline=False
                    )
                
                await ctx.send(embed=embed)
                
            except Exception as e:
                error_embed = self._create_error_embed("❌ Error", str(e))
                await ctx.send(embed=error_embed)


async def setup(bot):
    await bot.add_cog(Download_Commands(bot))
