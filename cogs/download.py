import discord
from utils.default import CustomContext
from discord.ext import commands
from utils.data import DiscordBot
from utils import http
import requests
from bs4 import BeautifulSoup
import re
import asyncio
import datetime
import pytz
import threading
import time


class Download_Commands(commands.Cog):
    def __init__(self, bot):
        self.bot: DiscordBot = bot
    
    # Global wait time for API calls (in seconds)
    API_WAIT_TIME = 5

    # global loop time to run the magnet_get_status command
    MAGNET_GET_STATUS_LOOP_TIME = 3
    
    # Global wait time for user reactions (in seconds)
    REACTION_WAIT_TIME = 15

    # Global wait time between each message delete while purging channel
    MESSAGE_DELETE_WAIT_TIME = 1

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

    async def _make_api_request(self, url: str, headers: dict = None, res_method: str = "json", method: str = "GET", data: dict = None):
        """Make API request with error handling"""
        try:
            if method.upper() == "POST":
                response = await http.post(url, headers=headers, data=data, res_method=res_method)
            else:
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

    async def _check_delayed_link_status(self, delayed_id: str, api_key: str):
        """Check the status of a delayed link until it's ready"""
        headers = {'Authorization': f'Bearer {api_key}'}
        max_attempts = 30  # Maximum 30 attempts (5 minutes with 10-second intervals)
        attempt = 0
        
        while attempt < max_attempts:
            try:
                # Check delayed link status
                response = await self._make_api_request(
                    f'https://api.alldebrid.com/v4/link/delayed',
                    headers=headers,
                    method="GET"
                )
                
                data = response.response
                if data.get('status') == 'success':
                    delayed_data = data.get('data', {})
                    
                    # Check if our delayed_id is in the list
                    for item in delayed_data.get('links', []):
                        if item.get('id') == delayed_id:
                            status = item.get('status', 'unknown')
                            
                            if status == 'ready':
                                # Link is ready, return the unlock data
                                return item
                            elif status == 'error':
                                raise Exception(f"Link processing failed: {item.get('message', 'Unknown error')}")
                            elif status in ['pending', 'downloading']:
                                # Still processing, wait and try again
                                await asyncio.sleep(10)  # Wait 10 seconds
                                attempt += 1
                                continue
                            else:
                                # Unknown status
                                await asyncio.sleep(10)
                                attempt += 1
                                continue
                    
                    # If delayed_id not found, it might be ready or failed
                    await asyncio.sleep(10)
                    attempt += 1
                    
                else:
                    error_msg = data.get('error', {}).get('message', 'Unknown error')
                    raise Exception(f"API Error checking delayed status: {error_msg}")
                    
            except Exception as e:
                if attempt >= max_attempts - 1:
                    raise e
                await asyncio.sleep(10)
                attempt += 1
        
        # If we reach here, the link took too long
        raise Exception("Link processing timed out after 5 minutes")

    def _extract_file_type(self, filename: str) -> str:
        """Extract file type from filename"""
        if not filename or filename == 'Unknown':
            return 'Unknown'
        
        if '.' in filename:
            return filename.split('.')[-1].upper()
        return 'No Extension'

    def _format_file_size(self, size):
        """Format file size for display"""
        if not size or size == 'Unknown':
            return 'Unknown'
        
        try:
            size_bytes = int(size)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.1f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.1f} PB"
        except (ValueError, TypeError):
            return str(size)

    def _truncate_text(self, text: str, max_length: int = 50) -> str:
        """Truncate text with ellipsis if too long"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."

    @commands.group(invoke_without_command=True)
    async def AD(self, ctx: CustomContext):
        """ AllDebrid API commands """
        await ctx.send("Available commands:\n`!AD status` - Check API authentication\n`!AD download <link>` - Unlock/download a link\n`!AD magnet_upload <magnet_uri>` - Upload magnet link to AllDebrid and get Magnet ID\n`!AD magnet_get_status <magnet_id>` - Check magnet status and information\n`!AD magnet_get_files <magnet_id>` - Get all download files and links\n`!AD magnet_search <url>` - Search for magnet URIs on a given URL\n`!AD supported_host <name>` - Check if a service is supported\n`!AD supported_hosts` - List all supported services\n`!AD history <number>` - Get recent download history")

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
                    size = self._format_file_size(item.get('size', 'Unknown'))
                    date = item.get('date', 'Unknown')
                    status = item.get('status', 'Unknown')
                    
                    # Truncate long values for display
                    display_link = self._truncate_text(link, 50)
                    display_filename = self._truncate_text(filename, 30)
                    
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

    @AD.command()
    async def download(self, ctx: CustomContext, *, link: str):
        """ Download/unlock a link using AllDebrid """
        if not link:
            await ctx.send("❌ **Error:** Please provide a link to download")
            return
        
        # Clean the link
        link = link.strip()
        if not link.startswith(('http://', 'https://')):
            await ctx.send("❌ **Error:** Please provide a valid URL starting with http:// or https://")
            return
        
        async with ctx.channel.typing():
            try:
                api_key = await self._check_api_authentication()
                headers = {'Authorization': f'Bearer {api_key}'}
                
                # Make POST request to unlock the link
                data = {'link': link}
                response = await self._make_api_request(
                    'https://api.alldebrid.com/v4/link/unlock',
                    headers=headers,
                    method="POST",
                    data=data
                )
                
                data = response.response
                if data.get('status') == 'success':
                    unlock_data = data.get('data', {})
                    
                    # Check if this is a delayed response
                    delayed_id = unlock_data.get('delayed')
                    if delayed_id:
                        # Send initial message about delayed processing
                        processing_embed = discord.Embed(
                            title="⏳ Link Processing...",
                            description="Your link is being processed by AllDebrid. This may take a few minutes.",
                            color=discord.Color.orange()
                        )
                        processing_embed.add_field(name="🔗 Original Link", value=f"```{link}```", inline=False)
                        processing_embed.set_footer(text="Please wait while we check the status...")
                        processing_msg = await ctx.send(embed=processing_embed)
                        
                        try:
                            # Poll for completion
                            final_data = await self._check_delayed_link_status(delayed_id, api_key)
                            
                            # Update the message with final results
                            await self._send_link_info_embed(ctx, final_data, link, processing_msg)
                            
                        except Exception as e:
                            # Update with error
                            error_embed = self._create_error_embed("❌ Link Processing Failed", str(e))
                            error_embed.add_field(name="🔗 Original Link", value=f"```{link}```", inline=False)
                            await processing_msg.edit(embed=error_embed)
                            
                    else:
                        # Immediate response, send results directly
                        await self._send_link_info_embed(ctx, unlock_data, link)
                    
                else:
                    error_msg = data.get('error', {}).get('message', 'Unknown error')
                    embed = self._create_error_embed(
                        "❌ Link Unlock Failed",
                        f"**Error:** {error_msg}"
                    )
                    embed.add_field(name="🔗 Original Link", value=f"```{link}```", inline=False)
                    await ctx.send(embed=embed)
                    
            except Exception as e:
                error_embed = self._create_error_embed("❌ Error", str(e))
                error_embed.add_field(name="🔗 Original Link", value=f"```{link}```", inline=False)
                await ctx.send(embed=error_embed)

    @AD.command()
    async def magnet_upload(self, ctx: CustomContext, *, magnet_uri: str):
        """ Upload a magnet link to AllDebrid and get Magnet ID """
        if not magnet_uri:
            await ctx.send("❌ **Error:** Please provide a magnet URI to upload")
            return
        
        # Clean and validate the magnet URI
        magnet_uri = magnet_uri.strip()
        if not magnet_uri.startswith('magnet:?'):
            await ctx.send("❌ **Error:** Please provide a valid magnet URI starting with `magnet:?`")
            return
        
        async with ctx.channel.typing():
            try:
                api_key = await self._check_api_authentication()
                headers = {'Authorization': f'Bearer {api_key}'}
                
                # Make POST request to upload the magnet
                data = {'magnets[]': magnet_uri}
                response = await self._make_api_request(
                    'https://api.alldebrid.com/v4/magnet/upload',
                    headers=headers,
                    method="POST",
                    data=data
                )
                
                data = response.response
                if data.get('status') == 'success':
                    magnet_data = data.get('data', {})
                    magnets = magnet_data.get('magnets', [])
                    
                    if magnets:
                        # The magnets data is actually a dictionary, not a list
                        magnet_info = magnets[0]  # Get the magnet data directly
                        
                        magnet_id = magnet_info.get('id')
                        magnet_name = magnet_info.get('name', 'Unknown')  # Use 'filename' instead of 'name'
                        
                        # Get size from the correct field
                        size_value = magnet_info.get('size')
                        magnet_size = self._format_file_size(size_value) if size_value else 'Unknown'
                        
                        if magnet_id:
                            # Wait for API to process the magnet
                            await ctx.send(f"⏳ **Processing magnet...** Please wait {self.API_WAIT_TIME} seconds for the API to return updated information.")
                            await asyncio.sleep(self.API_WAIT_TIME)
                            
                            # Make a second API call to get updated information
                            try:
                                magnet_id_int = int(magnet_id)
                                status_data = {'id': magnet_id_int}
                                status_response = await self._make_api_request(
                                    'https://api.alldebrid.com/v4.1/magnet/status',
                                    headers=headers,
                                    method="POST",
                                    data=status_data
                                )
                                
                                status_result = status_response.response
                                if status_result.get('status') == 'success':
                                    updated_magnet_data = status_result.get('data', {}).get('magnets', {})
                                    if updated_magnet_data:
                                        # Use updated information
                                        magnet_name = updated_magnet_data.get('name', magnet_name)
                                        size_value = updated_magnet_data.get('size', size_value)
                                        magnet_size = self._format_file_size(size_value) if size_value else 'Unknown'
                            except Exception as e:
                                # If second API call fails, continue with original data
                                print(f"Warning: Could not get updated magnet info: {e}")
                            
                            # Now display the information (either updated or original)
                            embed = self._create_success_embed(
                                "🧲 Magnet Uploaded Successfully!",
                                f"**Magnet uploaded to AllDebrid**"
                            )
                            embed.add_field(name="🔗 Magnet ID", value=f"`{magnet_id}`", inline=True)
                            embed.add_field(name="📁 Name", value=magnet_name, inline=True)
                            embed.add_field(name="📏 Size", value=magnet_size, inline=True)
                            
                            embed.set_footer(text="Use this Magnet ID for further operations")
                            await ctx.send(embed=embed)
                            
                            # Send combined next steps and status check message
                            combined_embed = discord.Embed(
                                title="📋 Next Steps & Quick Status Check",
                                description="To check the status of your uploaded magnet, use the following commands:",
                                color=discord.Color.blue()
                            )
                            combined_embed.add_field(
                                name="🔍 Check Magnet Status",
                                value=f"`!AD magnet_get_status {magnet_id}`",
                                inline=False
                            )
                            combined_embed.add_field(
                                name="📁 Get Files to Download (when ready)",
                                value=f"`!AD magnet_get_files {magnet_id}`",
                                inline=False
                            )
                            combined_embed.add_field(
                                name="🔗 Request Direct File Download (when ready)",
                                value=f"`!AD download <file_link>`",
                                inline=False
                            )
                            combined_embed.add_field(
                                name="🤔 Quick Status Check",
                                value="Do you want me to check the status of the magnet for you?\n*(The file can only be downloaded when the status is Ready)*",
                                inline=False
                            )
                            combined_embed.add_field(
                                name=f"👍 React with thumbs up (within {self.REACTION_WAIT_TIME} seconds)",
                                value="I'll automatically check the magnet status for you",
                                inline=False
                            )
                            combined_embed.add_field(
                                name="⏰ Or wait and check manually",
                                value=f"Use `!AD magnet_get_status {magnet_id}` when you're ready",
                                inline=False
                            )
                            combined_embed.set_footer(text="The magnet may take some time to process")
                            
                            status_msg = await ctx.send(embed=combined_embed)
                            await status_msg.add_reaction("👍")
                            
                            # Wait for reaction
                            def check(reaction, user):
                                return user == ctx.author and str(reaction.emoji) == "👍" and reaction.message.id == status_msg.id
                            
                            try:
                                await self.bot.wait_for('reaction_add', timeout=self.REACTION_WAIT_TIME, check=check)
                                
                                # User reacted with thumbs up, automatically check status
                                await ctx.send(f"👍 **Checking magnet status automatically...**")
                                
                                # Call the magnet_get_status function
                                await self.magnet_get_status(ctx, str(magnet_id))
                                
                            except asyncio.TimeoutError:
                                # No reaction within timeout period
                                timeout_embed = discord.Embed(
                                    title="⏰ Time's up!",
                                    description="You can check the magnet status manually anytime using:",
                                    color=discord.Color.orange()
                                )
                                timeout_embed.add_field(
                                    name="🔍 Manual Status Check",
                                    value=f"`!AD magnet_get_status {magnet_id}`",
                                    inline=False
                                )
                                await ctx.send(embed=timeout_embed)
                        else:
                            embed = self._create_error_embed(
                                "❌ Magnet Upload Failed",
                                "No magnet ID returned from AllDebrid"
                            )
                            embed.add_field(name="🔗 Original Magnet", value=f"```{magnet_uri}```", inline=False)
                            await ctx.send(embed=embed)
                    else:
                        embed = self._create_error_embed(
                            "❌ Magnet Upload Failed",
                            "No magnet data returned from AllDebrid"
                        )
                        embed.add_field(name="🔗 Original Magnet", value=f"```{magnet_uri}```", inline=False)
                        await ctx.send(embed=embed)
                    
                else:
                    error_msg = data.get('error', {}).get('message', 'Unknown error')
                    embed = self._create_error_embed(
                        "❌ Magnet Upload Failed",
                        f"**Error:** {error_msg}"
                    )
                    embed.add_field(name="🔗 Original Magnet", value=f"```{magnet_uri}```", inline=False)
                    await ctx.send(embed=embed)
                    
            except Exception as e:
                error_embed = self._create_error_embed("❌ Error", str(e))
                error_embed.add_field(name="🔗 Original Magnet", value=f"```{magnet_uri}```", inline=False)
                await ctx.send(embed=error_embed)

    @AD.command()
    async def magnet_get_status(self, ctx: CustomContext, magnet_id: str):
        """ Check magnet status and information using Magnet ID """
        if not magnet_id:
            await ctx.send("❌ **Error:** Please provide a magnet ID to check")
            return
        
        # Clean the magnet ID
        magnet_id = magnet_id.strip()
        if not magnet_id:
            await ctx.send("❌ **Error:** Please provide a valid magnet ID")
            return
        
        async with ctx.channel.typing():
            try:
                api_key = await self._check_api_authentication()
                headers = {'Authorization': f'Bearer {api_key}'}
                
                # Convert magnet_id to integer array as required by API
                try:
                    magnet_id_int = int(magnet_id)
                    headerdata = {'id': magnet_id_int}
                except ValueError:
                    await ctx.send("❌ **Error:** Magnet ID must be a valid number")
                    return
                
                # Loop to check magnet status multiple times
                magnet_status = None
                magnet_data = None
                
                for loop_count in range(self.MAGNET_GET_STATUS_LOOP_TIME + 1):
                    # Make POST request to check magnet status
                    response = await self._make_api_request(
                        'https://api.alldebrid.com/v4.1/magnet/status',
                        headers=headers,
                        method="POST",
                        data=headerdata
                    )
                    
                    data = response.response
                    
                    if data.get('status') == 'success':
                        magnet_data = data.get('data', {}).get('magnets', {})
                        
                        if magnet_data:
                            magnet_status = magnet_data.get('status', 'Unknown')
                            status_lower = magnet_status.lower()
                            
                            # If magnet is ready, break out of the loop
                            if status_lower == "ready":
                                break
                            
                            # If not ready and not the last loop, wait before next attempt
                            if loop_count < self.MAGNET_GET_STATUS_LOOP_TIME - 1:
                                await ctx.send(f"⏳ **Attempt {loop_count + 1}/{self.MAGNET_GET_STATUS_LOOP_TIME}:** Magnet not ready yet. Waiting {self.API_WAIT_TIME} seconds before next check...")
                                await asyncio.sleep(self.API_WAIT_TIME)

                            # if last loop, send error message
                            if loop_count == self.MAGNET_GET_STATUS_LOOP_TIME:
                                await ctx.send(f"⏳ **Attempt {loop_count}/{self.MAGNET_GET_STATUS_LOOP_TIME}:** Magnet not ready yet. Printing the magnet data...")
                        else:
                            # Magnet not found, break out of loop
                            break
                    else:
                        # API error, break out of loop
                        break
                
                # Process the final result
                if data.get('status') == 'success' and magnet_data:
                    # Extract magnet information from the correct structure
                    magnet_progress = "Ready" if magnet_status == 'Ready' else "Not Ready (maybe not enough seeders??!!)"
                    
                    # Get size from the correct field
                    size_value = magnet_data.get('size')
                    magnet_size = self._format_file_size(size_value) if size_value else 'Unknown'
                    
                    # Get files from the correct structure
                    files = magnet_data.get('files', [])
                    magnet_links = []
                    if files:
                        for file_group in files:
                            if 'e' in file_group:  # 'e' contains the actual files
                                magnet_links.extend(file_group['e'])
                
                    # Create embed with magnet information
                    embed = discord.Embed(
                        title="🧲 Magnet Status Check",
                        description=f"**Magnet ID:** `{magnet_id}`",
                        color=discord.Color.blue()
                    )
                    
                    embed.add_field(name="📏 Size", value=magnet_size, inline=True)
                    embed.add_field(name="📊 Progress", value=f"{magnet_progress}", inline=True)
                    
                    # Status with emoji (case-insensitive comparison)
                    status_lower = magnet_status.lower()
                    status_emoji = "✅" if status_lower == "ready" else "⏳" if status_lower == "downloading" else "❌"
                    embed.add_field(name="🔄 Status: (waiting for seeders)", value=f"{status_emoji} {magnet_status.title()}", inline=True)
                    
                    # Add links if available
                    if magnet_links:
                        embed.add_field(name="🔗 Links", value=f"{len(magnet_links)} files available", inline=True)
                        
                        # Show first few links
                        if len(magnet_links) <= 5:
                            links_display = "\n".join([f"• {link.get('n', 'Unknown')} ({self._format_file_size(link.get('s', 'Unknown'))})" for link in magnet_links])
                        else:
                            links_display = "\n".join([f"• {link.get('n', 'Unknown')} ({self._format_file_size(link.get('s', 'Unknown'))})" for link in magnet_links[:5]])
                            links_display += f"\n... and {len(magnet_links) - 5} more files"
                        
                        embed.add_field(name="📋 Files", value=links_display, inline=False)
                    else:
                        embed.add_field(name="📋 Files", value="No files available yet", inline=False)
                    
                    # add magnet_get_status command to the embed
                    if status_lower != "ready":
                        embed.add_field(name="🔍 Check Magnet Status (again later)", value=f"- Use `!AD magnet_get_status {magnet_id}`\n- Don't complain, use a magnet with many seeders to get a good download :)", inline=False)
                    # Set footer based on magnet status
                    embed.set_footer(text=f"Magnet ID: {magnet_id}")
                    await ctx.send(embed=embed)
                    
                    # If magnet is ready, send additional message about next steps
                    if status_lower == "ready":
                        next_steps_embed = discord.Embed(
                            title="🎉 Magnet Ready for Download!",
                            description="Your magnet is ready! Here's how to download your files:",
                            color=discord.Color.green()
                        )
                        next_steps_embed.add_field(
                            name="📁 Step 1: Get Download Links",
                            value=f"`!AD magnet_get_files {magnet_id}`",
                            inline=False
                        )
                        next_steps_embed.add_field(
                            name="🔗 Step 2: Download Files",
                            value="`!AD download <file_link>`\n*(Use the links from magnet_get_files)*",
                            inline=False
                        )
                        next_steps_embed.add_field(
                            name="💡 Tip",
                            value="There may be some trash files in the magnet, so check the files before downloading.",
                            inline=False
                        )
                        next_steps_embed.add_field(
                            name="🤔 Quick File List",
                            value="Do you want me to get the file list for you?\n*(I'll automatically run the magnet_get_files command)*",
                            inline=False
                        )
                        next_steps_embed.add_field(
                            name=f"👍 React with thumbs up (within {self.REACTION_WAIT_TIME} seconds)",
                            value="I'll automatically get the file list for you",
                            inline=False
                        )
                        next_steps_embed.add_field(
                            name="⏰ Or get files manually",
                            value=f"Use `!AD magnet_get_files {magnet_id}` when you're ready",
                            inline=False
                        )
                        next_steps_embed.set_footer(text="Links will expire in 48 hours")
                        
                        files_msg = await ctx.send(embed=next_steps_embed)
                        await files_msg.add_reaction("👍")
                        
                        # Wait for reaction
                        def check(reaction, user):
                            return user == ctx.author and str(reaction.emoji) == "👍" and reaction.message.id == files_msg.id
                        
                        try:
                            await self.bot.wait_for('reaction_add', timeout=self.REACTION_WAIT_TIME, check=check)
                            
                            # User reacted with thumbs up, automatically get files
                            await ctx.send(f"👍 **Getting file list automatically...**")
                            
                            # Call the magnet_get_files function
                            await self.magnet_get_files(ctx, str(magnet_id))
                            
                        except asyncio.TimeoutError:
                            # No reaction within timeout period
                            timeout_embed = discord.Embed(
                                title="⏰ Time's up!",
                                description="You can get the file list manually anytime using:",
                                color=discord.Color.orange()
                            )
                            timeout_embed.add_field(
                                name="📁 Manual File List",
                                value=f"`!AD magnet_get_files {magnet_id}`",
                                inline=False
                            )
                            await ctx.send(embed=timeout_embed)
                else:
                    error_msg = data.get('error', {}).get('message', 'Unknown error')
                    embed = self._create_error_embed(
                        "❌ Magnet Status Check Failed",
                        f"**Error:** {error_msg}"
                    )
                    embed.add_field(name="🔗 Magnet ID", value=f"`{magnet_id}`", inline=False)
                    await ctx.send(embed=embed)
                    
            except Exception as e:
                error_embed = self._create_error_embed("❌ Error", str(e))
                error_embed.add_field(name="🔗 Magnet ID", value=f"`{magnet_id}`", inline=False)
                await ctx.send(embed=error_embed)

    @AD.command()
    async def magnet_get_files(self, ctx: CustomContext, magnet_id: str):
        """ Get all download files and links for a magnet ID """
        if not magnet_id:
            await ctx.send("❌ **Error:** Please provide a magnet ID to get files")
            return
        
        # Clean the magnet ID
        magnet_id = magnet_id.strip()
        if not magnet_id:
            await ctx.send("❌ **Error:** Please provide a valid magnet ID")
            return
        
        async with ctx.channel.typing():
            try:
                api_key = await self._check_api_authentication()
                headers = {'Authorization': f'Bearer {api_key}'}
                
                # Make POST request to get magnet files
                # Convert magnet_id to integer array as required by API
                try:
                    magnet_id_int = int(magnet_id)
                    data = {'id[]': [magnet_id_int]}
                except ValueError:
                    await ctx.send("❌ **Error:** Magnet ID must be a valid number")
                    return
                
                response = await self._make_api_request(
                    'https://api.alldebrid.com/v4/magnet/files',
                    headers=headers,
                    method="POST",
                    data=data
                )
                
                data = response.response
                
                if data.get('status') == 'success':
                    magnets_data = data.get('data', {}).get('magnets', [])
                    
                    if magnets_data and len(magnets_data) > 0:
                        # Get the first magnet (since we're querying by specific ID)
                        magnet_data = magnets_data[0]
                        magnet_id_from_response = magnet_data.get('id', 'Unknown')
                        
                        # Get files from the correct structure
                        files = magnet_data.get('files', [])
                        magnet_links = []
                        
                        if files:
                            for file_group in files:
                                if 'e' in file_group:  # 'e' contains the actual files
                                    magnet_links.extend(file_group['e'])
                        
                        if magnet_links:
                            # Send summary embed first
                            summary_embed = discord.Embed(
                                title="📁 Magnet Files Available",
                                description=f"**Magnet ID:** `{magnet_id}`",
                                color=discord.Color.green()
                            )
                            
                            summary_embed.add_field(name="📋 Total Files", value=f"{len(magnet_links)} files", inline=True)
                            summary_embed.add_field(name="📤 Sending Files", value="One file per message below", inline=True)
                            
                            summary_embed.set_footer(text=f"Magnet ID: {magnet_id}")
                            await ctx.send(embed=summary_embed)
                            
                            # Send one file per embed
                            for i, link in enumerate(magnet_links, 1):
                                file_name = link.get('n', 'Unknown')
                                file_size = self._format_file_size(link.get('s', 'Unknown'))
                                download_link = link.get('l', 'No link available')
                                file_type = self._extract_file_type(file_name)
                                
                                # Create individual file embed
                                file_embed = discord.Embed(
                                    title=f"📁 File {i}/{len(magnet_links)}",
                                    description=f"**{file_name}**",
                                    color=discord.Color.blue()
                                )
                                
                                file_embed.add_field(name="📏 Size", value=file_size, inline=True)
                                file_embed.add_field(name="📋 Type", value=file_type, inline=True)
                                file_embed.add_field(name="🔗 Download Link", value=download_link, inline=False)
                                file_embed.add_field(name="💻 Download Command", value=f"`!AD download {download_link}`", inline=False)
                                
                                file_embed.set_footer(text=f"File {i} of {len(magnet_links)} | Magnet ID: {magnet_id}")
                                await ctx.send(embed=file_embed)
                                
                                # Wait 0.5 seconds before sending the next message
                                if i < len(magnet_links):  # Don't wait after the last file
                                    await asyncio.sleep(0.5)
                            
                            # Send final instructions embed
                            instructions_embed = discord.Embed(
                                title="🔗 Download Instructions",
                                description="To download any file, use the command shown above each file:",
                                color=discord.Color.purple()
                            )
                            
                            instructions_embed.add_field(
                                name="💡 How to Download",
                                value="1. Copy the download command from any file above\n2. Paste it in the chat and press Enter\n3. The bot will provide you with a direct download link",
                                inline=False
                            )
                            
                            instructions_embed.add_field(
                                name="⚠️ Important Notes",
                                value="• Links will expire in 48 hours\n• You can download files one at a time\n• Some files in the magnet are trash or virus files - use your own judgement\n• Commands are in code blocks for easy copying",
                                inline=False
                            )
                            
                            instructions_embed.set_footer(text=f"Magnet ID: {magnet_id} | Total Files: {len(magnet_links)}")
                            await ctx.send(embed=instructions_embed)
                        else:
                            embed = self._create_error_embed(
                                "❌ No Files Available",
                                f"No files found for magnet ID: `{magnet_id}`"
                            )
                            await ctx.send(embed=embed)
                    else:
                        embed = self._create_error_embed(
                            "❌ Magnet Not Found",
                            f"No magnet found with ID: `{magnet_id}`"
                        )
                        await ctx.send(embed=embed)
                    
                else:
                    error_msg = data.get('error', {}).get('message', 'Unknown error')
                    embed = self._create_error_embed(
                        "❌ Magnet Files Check Failed",
                        f"**Error:** {error_msg}"
                    )
                    embed.add_field(name="🔗 Magnet ID", value=f"`{magnet_id}`", inline=False)
                    await ctx.send(embed=embed)
                    
            except Exception as e:
                error_embed = self._create_error_embed("❌ Error", str(e))
                error_embed.add_field(name="🔗 Magnet ID", value=f"`{magnet_id}`", inline=False)
                await ctx.send(embed=error_embed)



    async def _send_link_info_embed(self, ctx: CustomContext, unlock_data: dict, original_link: str, message_to_edit: discord.Message = None):
        """Send or edit a message with link information"""
        # Extract information from the response
        host = unlock_data.get('host', 'Unknown')
        filename = unlock_data.get('filename', 'Unknown')
        size = self._format_file_size(unlock_data.get('filesize', 'Unknown'))
        download_link = unlock_data.get('link', 'No direct link available')
        file_type = self._extract_file_type(filename)
        
        # Create embed with link information
        embed = discord.Embed(
            title="🔗 Link Unlocked Successfully!",
            description=f"**Link processed by AllDebrid**",
            color=discord.Color.green()
        )
        
        embed.add_field(name="🌐 Host", value=host, inline=True)
        embed.add_field(name="📁 Filename", value=filename, inline=True)
        embed.add_field(name="📏 Size", value=size, inline=True)
        embed.add_field(name="📋 Type", value=file_type, inline=True)
        
        # Add download link if available
        if download_link and download_link != 'No direct link available':
            # Add full link as hidden field for copying
            embed.add_field(name="🔗 Full Download Link", value=f"{download_link}", inline=False)
        else:
            embed.add_field(name="⚠️ Note", value="No direct download link available for this file type", inline=False)
        
        # Add original link
        embed.add_field(name="🔗 Original Link", value=f"```{original_link}```", inline=False)
        
        embed.set_footer(text="Link will expire in 48 hours")
        
        if message_to_edit:
            await message_to_edit.edit(embed=embed)
        else:
            await ctx.send(embed=embed)

    @AD.command()
    async def magnet_search(self, ctx: CustomContext, *, url: str):
        """Search for magnet URIs on a given URL"""
        if not url:
            await ctx.send("❌ **Error:** Please provide a URL to search")
            return
        
        # Clean the URL
        url = url.strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        async with ctx.channel.typing():
            try:
                # Send initial message
                search_msg = await ctx.send("🔍 **Searching for magnet links...**")
                
                # Make HTTP request to the URL
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                
                response = requests.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                
                # Parse HTML content
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find all text content and links
                text_content = soup.get_text()
                links = soup.find_all('a', href=True)
                
                # Check for bot protection (minimal content, no magnets)
                content_length = len(response.content)
                text_length = len(text_content)
                
                # If we get very little content, it's likely bot protection
                if content_length < 10000 or text_length < 1000:
                    # Check if this looks like a bot-blocked page
                    bot_indicators = [
                        'blocked' in text_content.lower(),
                        'captcha' in text_content.lower(),
                        'robot' in text_content.lower(),
                        'access denied' in text_content.lower(),
                        'forbidden' in text_content.lower(),
                        len(links) < 10,  # Very few links
                        all('redirect' in link.get('href', '').lower() for link in links[:5])  # All redirect links
                    ]
                    
                    if any(bot_indicators) or (content_length < 5000 and text_length < 500):
                        # This is likely bot protection
                        embed = discord.Embed(
                            title="🚫 Bot Protection Detected",
                            description="This website appears to block automated requests and bots",
                            color=discord.Color.orange()
                        )
                        
                        embed.add_field(
                            name="🔗 URL Searched",
                            value=f"```{url}```",
                            inline=False
                        )
                        
                        embed.add_field(
                            name="⚠️ What Happened",
                            value="• The website detected this as an automated request\n• Only minimal content was returned\n• Magnet links are hidden from bots",
                            inline=False
                        )
                        
                        embed.add_field(
                            name="💡 Solutions",
                            value="• Try accessing the URL manually in a browser\n• Use a different torrent site\n• Consider using torrent search APIs instead\n• Some sites require JavaScript or cookies",
                            inline=False
                        )
                        
                        embed.add_field(
                            name="📊 Technical Details",
                            value=f"• Content size: {content_length} bytes\n• Text length: {text_length} characters\n• Links found: {len(links)}",
                            inline=False
                        )
                        
                        embed.set_footer(text="Bot protection detected | Magnet search failed")
                        
                        await search_msg.edit(content="❌ **Bot protection detected**", embed=embed)
                        return
                
                # Extract magnet URIs using regex pattern
                magnet_pattern = r'magnet:\?[^\s<>"\']+'
                found_magnets = re.findall(magnet_pattern, text_content)
                
                # Also check href attributes for magnet links
                for link in links:
                    href = link.get('href', '')
                    if href.startswith('magnet:?'):
                        found_magnets.append(href)
                
                # Remove duplicates while preserving order
                unique_magnets = []
                seen = set()
                for magnet in found_magnets:
                    if magnet not in seen:
                        unique_magnets.append(magnet)
                        seen.add(magnet)
                
                # Update search message with results
                if unique_magnets:
                    # Create success embed
                    embed = discord.Embed(
                        title="🧲 Magnet Search Results",
                        description=f"Found **{len(unique_magnets)}** magnet link(s) on the page",
                        color=discord.Color.green()
                    )
                    
                    embed.add_field(
                        name="🔗 URL Searched",
                        value=f"```{url}```",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="📊 Results",
                        value=f"**Total found:** {len(found_magnets)}\n**Unique magnets:** {len(unique_magnets)}",
                        inline=True
                    )
                    
                    # Show first few magnets (truncated if too long)
                    if len(unique_magnets) <= 3:
                        magnets_display = "\n".join([f"• `{magnet[:100]}...`" if len(magnet) > 100 else f"• `{magnet}`" for magnet in unique_magnets])
                    else:
                        magnets_display = "\n".join([f"• `{magnet[:100]}...`" if len(magnet) > 100 else f"• `{magnet}`" for magnet in unique_magnets[:3]])
                        magnets_display += f"\n... and {len(unique_magnets) - 3} more magnets"
                    
                    embed.add_field(
                        name="🧲 Magnets Found",
                        value=magnets_display,
                        inline=False
                    )
                    
                    embed.add_field(
                        name="💡 Next Steps",
                        value="Use `!AD magnet_upload <magnet_uri>` to upload any magnet and continue the workflow",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="⚠️ Note",
                        value="• Copy the full magnet URI from the results above\n• Some magnets may be duplicates or invalid\n• Use magnets with many seeders for better download success",
                        inline=False
                    )
                    
                    embed.set_footer(text=f"Search completed | {len(unique_magnets)} unique magnets found")
                    
                    await search_msg.edit(content="✅ **Search completed!**", embed=embed)
                    
                else:
                    # No magnets found
                    embed = discord.Embed(
                        title="🔍 No Magnets Found",
                        description="No magnet links were found on the specified URL",
                        color=discord.Color.orange()
                    )
                    
                    embed.add_field(
                        name="🔗 URL Searched",
                        value=f"```{url}```",
                        inline=False
                    )
                    
                    embed.add_field(
                        name="💡 Suggestions",
                        value="• Make sure the URL contains magnet links\n• Check if the page requires authentication\n• Try different pages on the same website\n• Verify the magnets are in the correct format (magnet:?...)",
                        inline=False
                    )
                    
                    embed.set_footer(text="Search completed | No magnets found")
                    
                    await search_msg.edit(content="❌ **No magnets found**", embed=embed)
                    
            except requests.exceptions.RequestException as e:
                error_embed = self._create_error_embed(
                    "❌ Connection Error",
                    f"Unable to connect to the URL: {str(e)}"
                )
                error_embed.add_field(name="🔗 URL", value=f"```{url}```", inline=False)
                await search_msg.edit(content="❌ **Search failed**", embed=error_embed)
                
            except Exception as e:
                error_embed = self._create_error_embed(
                    "❌ Search Error",
                    f"An error occurred while searching: {str(e)}"
                )
                error_embed.add_field(name="🔗 URL", value=f"```{url}```", inline=False)
                await search_msg.edit(content="❌ **Search failed**", embed=error_embed)

    @AD.command()
    async def purge(self, ctx: CustomContext):
        """Show channel purge information and allow manual purging"""
        try:
            # Check if channel purging is configured
            if not self.bot.config.request_channel_name or self.bot.config.request_channel_purge_hours is None:
                embed = self._create_error_embed(
                    "❌ Channel Purging Not Configured",
                    "Channel purging is not configured. Please set `REQUEST_CHANNEL_NAME` and `REQUEST_CHANNEL_PURGE_HOURS` in your `.env` file.",
                    "Configuration Missing"
                )
                await ctx.send(embed=embed)
                return

            # Validate purge hours
            valid_hours = [0, 1, 2, 3, 4, 6, 12]
            if self.bot.config.request_channel_purge_hours not in valid_hours:
                embed = self._create_error_embed(
                    "❌ Invalid Purge Configuration",
                    f"`REQUEST_CHANNEL_PURGE_HOURS` must be one of {valid_hours}. Current value: {self.bot.config.request_channel_purge_hours}",
                    "Configuration Error"
                )
                await ctx.send(embed=embed)
                return

            # Find the channel in the current guild
            channel = discord.utils.get(ctx.guild.text_channels, name=self.bot.config.request_channel_name)

            if not channel:
                embed = self._create_error_embed(
                    "❌ Channel Not Found",
                    f"Channel `#{self.bot.config.request_channel_name}` not found in this server.",
                    "Channel Missing"
                )
                await ctx.send(embed=embed)
                return

            # Check if auto-purge is disabled
            if self.bot.config.request_channel_purge_hours == 0:
                # Create information embed for disabled auto-purge
                embed = discord.Embed(
                    title="🧹 Channel Purge Information",
                    description=f"Information about channel purging for `#{self.bot.config.request_channel_name}`",
                    color=discord.Color.orange()
                )

                embed.add_field(
                    name="📺 Channel",
                    value=f"`#{self.bot.config.request_channel_name}`",
                    inline=True
                )

                embed.add_field(
                    name="⏰ Auto-Purge Status",
                    value="**Disabled** (The value is set to 0 in the .env file)",
                    inline=True
                )

                embed.add_field(
                    name="💡 Manual Purge",
                    value="React with 👍 to purge the channel immediately",
                    inline=True
                )

                embed.set_footer(text="Auto-purge is disabled. Use this command to manually purge the channel.")
            else:
                # Calculate next purge time for enabled auto-purge
                pdt_tz = pytz.timezone('US/Pacific')
                now = datetime.datetime.now(pdt_tz)
                
                # Calculate next purge time (midnight + purge interval)
                next_purge = now.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # If we're past midnight today, move to next interval
                while next_purge <= now:
                    next_purge += datetime.timedelta(hours=self.bot.config.request_channel_purge_hours)
                
                # Calculate time until next purge
                time_until_purge = next_purge - now
                hours_until_purge = time_until_purge.total_seconds() / 3600

                # Create information embed for enabled auto-purge
                embed = discord.Embed(
                    title="🧹 Channel Purge Information",
                    description=f"Information about automatic channel purging for `#{self.bot.config.request_channel_name}`",
                    color=discord.Color.blue()
                )

                embed.add_field(
                    name="📺 Channel",
                    value=f"`#{self.bot.config.request_channel_name}`",
                    inline=True
                )

                embed.add_field(
                    name="⏰ Purge Interval",
                    value=f"Every **{self.bot.config.request_channel_purge_hours}** hours",
                    inline=True
                )

                embed.add_field(
                    name="🕐 Next Scheduled Purge",
                    value=f"<t:{int(next_purge.timestamp())}:F>\n(<t:{int(next_purge.timestamp())}:R>)",
                    inline=False
                )

                embed.add_field(
                    name="⏳ Time Remaining",
                    value=f"**{hours_until_purge:.1f}** hours until next purge",
                    inline=True
                )

                embed.add_field(
                    name="💡 Manual Purge",
                    value="React with 👍 to purge the channel immediately",
                    inline=True
                )

                embed.set_footer(text="Channel purging starts at midnight PDT and follows the configured interval")

            # Send the embed and add reaction
            message = await ctx.send(embed=embed)
            await message.add_reaction("👍")

            # Wait for user reaction
            try:
                def check(reaction, user):
                    return (
                        user == ctx.author and
                        reaction.message.id == message.id and
                        str(reaction.emoji) == "👍"
                    )

                await self.bot.wait_for('reaction_add', timeout=self.REACTION_WAIT_TIME, check=check)

                # User confirmed, proceed with purge
                await self._purge_channel(target_guild=ctx.guild)

                # Send confirmation to the user
                confirm_embed = discord.Embed(
                    title="✅ Channel Purged",
                    description=f"Successfully purged `#{self.bot.config.request_channel_name}` in this server as requested.",
                    color=discord.Color.green()
                )
                
                if self.bot.config.request_channel_purge_hours == 0:
                    confirm_embed.add_field(
                        name="⏰ Auto-Purge Status",
                        value="**Disabled** - No scheduled purges",
                        inline=True
                    )
                else:
                    confirm_embed.add_field(
                        name="⏰ Next Scheduled Purge",
                        value=f"<t:{int(next_purge.timestamp())}:R>",
                        inline=True
                    )
                
                await ctx.send(embed=confirm_embed)

            except asyncio.TimeoutError:
                # User didn't react in time
                if self.bot.config.request_channel_purge_hours == 0:
                    timeout_embed = discord.Embed(
                        title="⏰ Timeout",
                        description="No response received. Channel was not purged.",
                        color=discord.Color.orange()
                    )
                else:
                    timeout_embed = discord.Embed(
                        title="⏰ Timeout",
                        description="No response received. Channel will be purged automatically at the scheduled time.",
                        color=discord.Color.orange()
                    )
                await message.edit(embed=timeout_embed)

        except Exception as e:
            embed = self._create_error_embed(
                "❌ Error",
                f"An error occurred while getting purge information: {str(e)}",
                type(e).__name__
            )
            await ctx.send(embed=embed)

    async def _start_channel_purge_scheduler(self):
        """Start the channel purge scheduler in a separate thread"""
        if not self.bot.config.request_channel_name or self.bot.config.request_channel_purge_hours is None:
            return
        
        # Check if auto-purge is disabled (0 hours)
        if self.bot.config.request_channel_purge_hours == 0:
            print(f"ℹ️ Auto-purge disabled for channel '{self.bot.config.request_channel_name}' (REQUEST_CHANNEL_PURGE_HOURS = 0)")
            return
        
        # Validate purge hours
        valid_hours = [0, 1, 2, 3, 4, 6, 12]
        if self.bot.config.request_channel_purge_hours not in valid_hours:
            print(f"Warning: REQUEST_CHANNEL_PURGE_HOURS must be one of {valid_hours}. Current value: {self.bot.config.request_channel_purge_hours}")
            return
        
        # Start scheduler in a separate thread
        thread = threading.Thread(target=self._channel_purge_scheduler, daemon=True)
        thread.start()
        print(f"✅ Channel purge scheduler started for channel '{self.bot.config.request_channel_name}' every {self.bot.config.request_channel_purge_hours} hours")

    def _channel_purge_scheduler(self):
        """Background thread for channel purging"""
        pdt_tz = pytz.timezone('US/Pacific')
        
        while True:
            try:
                # Get current time in PDT
                now = datetime.datetime.now(pdt_tz)
                
                # Calculate next purge time (midnight + purge interval)
                next_purge = now.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # If we're past midnight today, move to next interval
                while next_purge <= now:
                    next_purge += datetime.timedelta(hours=self.bot.config.request_channel_purge_hours)
                
                # Calculate time until next purge
                time_until_purge = (next_purge - now).total_seconds()
                
                print(f"🕐 Next channel purge scheduled for {next_purge.strftime('%Y-%m-%d %H:%M:%S')} PDT (in {time_until_purge/3600:.1f} hours)")
                
                # Sleep until next purge time
                time.sleep(time_until_purge)
                
                # Execute purge for all guilds
                asyncio.run_coroutine_threadsafe(self._purge_channel_all_guilds(), self.bot.loop)
                
            except Exception as e:
                print(f"❌ Error in channel purge scheduler: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

    async def _purge_channel(self, target_guild=None):
        """Purge all messages from the request channel"""
        try:
            channel_name = self.bot.config.request_channel_name
            if not channel_name:
                return
            
            # Find the channel
            channel = None
            if target_guild:
                # Purge specific guild's channel
                channel = discord.utils.get(target_guild.text_channels, name=channel_name)
            else:
                # Purge all guilds' channels (for automatic purging)
                for guild in self.bot.guilds:
                    channel = discord.utils.get(guild.text_channels, name=channel_name)
                    if channel:
                        break
            
            if not channel:
                print(f"❌ Channel '{channel_name}' not found")
                return
            
            # Check if bot has permission to manage messages
            if not channel.permissions_for(channel.guild.me).manage_messages:
                print(f"❌ Bot doesn't have permission to manage messages in channel '{channel_name}'")
                return
            
            # Delete all messages
            deleted_count = 0
            async for message in channel.history(limit=None):
                try:
                    await message.delete()
                    deleted_count += 1
                    await asyncio.sleep(self.MESSAGE_DELETE_WAIT_TIME)  # Rate limiting
                except Exception as e:
                    print(f"❌ Failed to delete message {message.id}: {e}")
            
            # Send purge confirmation
            embed = discord.Embed(
                title="🧹 Channel Purged",
                description=f"Successfully deleted **{deleted_count}** messages from the channel",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="⏰ Next Purge",
                value=f"<t:{int((datetime.datetime.now(pytz.timezone('US/Pacific')) + datetime.timedelta(hours=self.bot.config.request_channel_purge_hours)).timestamp())}:R>",
                inline=True
            )
            embed.set_footer(text=f"Auto-purge every {self.bot.config.request_channel_purge_hours} hours")
            
            await channel.send(embed=embed)
            print(f"✅ Purged {deleted_count} messages from channel '{channel_name}'")
            
        except Exception as e:
            print(f"❌ Error purging channel: {e}")

    async def _purge_channel_all_guilds(self):
        """Purge all messages from the request channel in all guilds"""
        try:
            channel_name = self.bot.config.request_channel_name
            if not channel_name:
                return
            
            # Find all guilds that have the channel
            guilds_with_channel = []
            for guild in self.bot.guilds:
                channel = discord.utils.get(guild.text_channels, name=channel_name)
                if channel:
                    guilds_with_channel.append((guild, channel))
            
            if not guilds_with_channel:
                print(f"❌ Channel '{channel_name}' not found in any guild")
                return
            
            total_deleted = 0
            
            # Purge each guild's channel
            for guild, channel in guilds_with_channel:
                try:
                    # Check if bot has permission to manage messages
                    if not channel.permissions_for(channel.guild.me).manage_messages:
                        print(f"❌ Bot doesn't have permission to manage messages in guild '{guild.name}' channel '{channel_name}'")
                        continue
                    
                    # Delete all messages
                    deleted_count = 0
                    async for message in channel.history(limit=None):
                        try:
                            await message.delete()
                            deleted_count += 1
                            await asyncio.sleep(self.MESSAGE_DELETE_WAIT_TIME)  # Rate limiting
                        except Exception as e:
                            print(f"❌ Failed to delete message {message.id} in guild '{guild.name}': {e}")
                    
                    total_deleted += deleted_count
                    print(f"✅ Purged {deleted_count} messages from guild '{guild.name}' channel '{channel_name}'")
                    
                    # Send purge confirmation to this guild's channel
                    embed = discord.Embed(
                        title="🧹 Channel Purged",
                        description=f"Successfully deleted **{deleted_count}** messages from the channel",
                        color=discord.Color.blue()
                    )
                    embed.add_field(
                        name="⏰ Next Purge",
                        value=f"<t:{int((datetime.datetime.now(pytz.timezone('US/Pacific')) + datetime.timedelta(hours=self.bot.config.request_channel_purge_hours)).timestamp())}:R>",
                        inline=True
                    )
                    embed.set_footer(text=f"Auto-purge every {self.bot.config.request_channel_purge_hours} hours")
                    
                    await channel.send(embed=embed)
                    
                except Exception as e:
                    print(f"❌ Error purging channel in guild '{guild.name}': {e}")
            
            print(f"✅ Total purged {total_deleted} messages across {len(guilds_with_channel)} guilds")
            
        except Exception as e:
            print(f"❌ Error purging channels in all guilds: {e}")

    async def _send_purge_reminder(self, hours_left: int, target_guild=None):
        """Send a reminder about upcoming channel purge"""
        try:
            channel_name = self.bot.config.request_channel_name
            if not channel_name:
                return
            
            # Find the channel
            channel = None
            if target_guild:
                # Send reminder to specific guild's channel
                channel = discord.utils.get(target_guild.text_channels, name=channel_name)
            else:
                # Send reminder to all guilds' channels (for automatic reminders)
                for guild in self.bot.guilds:
                    channel = discord.utils.get(guild.text_channels, name=channel_name)
                    if channel:
                        break
            
            if not channel:
                return
            
            # Determine reminder frequency
            if hours_left == 1:
                # Send reminder every 15 minutes for the last hour
                reminder_text = "⚠️ **Channel will be purged in 1 hour!**"
                color = discord.Color.red()
            else:
                # Send hourly reminder
                reminder_text = f"⏰ **Channel will be purged in {hours_left} hours**"
                color = discord.Color.orange()
            
            embed = discord.Embed(
                title="🕐 Purge Reminder",
                description=reminder_text,
                color=color
            )
            
            if hours_left == 1:
                embed.add_field(
                    name="📢 Reminder Frequency",
                    value="You'll receive a reminder every 15 minutes until purge",
                    inline=False
                )
            
            embed.add_field(
                name="💡 Save Important Info",
                value="Make sure to save any important information before the purge",
                inline=False
            )
            
            embed.set_footer(text=f"Auto-purge every {self.bot.config.request_channel_purge_hours} hours")
            
            await channel.send(embed=embed)
            
        except Exception as e:
            print(f"❌ Error sending purge reminder: {e}")

    async def _send_purge_reminder_to_all_guilds(self, hours_left: int):
        """Send a reminder about upcoming channel purge to all guilds that have the channel"""
        try:
            channel_name = self.bot.config.request_channel_name
            if not channel_name:
                return
            
            # Find all guilds that have the channel
            guilds_with_channel = []
            for guild in self.bot.guilds:
                channel = discord.utils.get(guild.text_channels, name=channel_name)
                if channel:
                    guilds_with_channel.append((guild, channel))
            
            if not guilds_with_channel:
                print(f"❌ Channel '{channel_name}' not found in any guild")
                return
            
            # Determine reminder frequency
            if hours_left == 1:
                # Send reminder every 15 minutes for the last hour
                reminder_text = "⚠️ **Channel will be purged in 1 hour!**"
                color = discord.Color.red()
            else:
                # Send hourly reminder
                reminder_text = f"⏰ **Channel will be purged in {hours_left} hours**"
                color = discord.Color.orange()
            
            embed = discord.Embed(
                title="🕐 Purge Reminder",
                description=reminder_text,
                color=color
            )
            
            if hours_left == 1:
                embed.add_field(
                    name="📢 Reminder Frequency",
                    value="You'll receive a reminder every 15 minutes until purge",
                    inline=False
                )
            
            embed.add_field(
                name="💡 Save Important Info",
                value="Make sure to save any important information before the purge",
                inline=False
            )
            
            embed.set_footer(text=f"Auto-purge every {self.bot.config.request_channel_purge_hours} hours")
            
            # Send reminder to all guilds that have the channel
            for guild, channel in guilds_with_channel:
                try:
                    await channel.send(embed=embed)
                    print(f"✅ Sent purge reminder to guild '{guild.name}' channel '{channel_name}'")
                except Exception as e:
                    print(f"❌ Failed to send reminder to guild '{guild.name}': {e}")
            
        except Exception as e:
            print(f"❌ Error sending purge reminders to all guilds: {e}")

    async def _start_reminder_scheduler(self):
        """Start the reminder scheduler in a separate thread"""
        if not self.bot.config.request_channel_name or self.bot.config.request_channel_purge_hours is None:
            return
        
        # Check if auto-purge is disabled (0 hours)
        if self.bot.config.request_channel_purge_hours == 0:
            print(f"ℹ️ Reminder scheduler disabled for channel '{self.bot.config.request_channel_name}' (REQUEST_CHANNEL_PURGE_HOURS = 0)")
            return
        
        # Start reminder scheduler in a separate thread
        thread = threading.Thread(target=self._reminder_scheduler, daemon=True)
        thread.start()
        print(f"✅ Reminder scheduler started for channel '{self.bot.config.request_channel_name}'")

    def _reminder_scheduler(self):
        """Background thread for sending purge reminders"""
        pdt_tz = pytz.timezone('US/Pacific')
        
        while True:
            try:
                # Get current time in PDT
                now = datetime.datetime.now(pdt_tz)
                
                # Calculate next purge time
                next_purge = now.replace(hour=0, minute=0, second=0, microsecond=0)
                while next_purge <= now:
                    next_purge += datetime.timedelta(hours=self.bot.config.request_channel_purge_hours)
                
                # Calculate hours until next purge
                hours_until_purge = int((next_purge - now).total_seconds() / 3600)
                
                # Send reminders based on time remaining
                if hours_until_purge == 1:
                    # Send reminder every 15 minutes for the last hour
                    asyncio.run_coroutine_threadsafe(self._send_purge_reminder_to_all_guilds(1), self.bot.loop)
                    time.sleep(15 * 60)  # Wait 15 minutes
                elif hours_until_purge <= 12:
                    # Send hourly reminder
                    asyncio.run_coroutine_threadsafe(self._send_purge_reminder_to_all_guilds(hours_until_purge), self.bot.loop)
                    time.sleep(60 * 60)  # Wait 1 hour
                else:
                    # Sleep for a longer period
                    time.sleep(60 * 60)  # Wait 1 hour
                
            except Exception as e:
                print(f"❌ Error in reminder scheduler: {e}")
                time.sleep(60)  # Wait 1 minute before retrying


async def setup(bot):
    cog = Download_Commands(bot)
    await bot.add_cog(cog)
    
    # Start channel purge and reminder schedulers
    await cog._start_channel_purge_scheduler()
    await cog._start_reminder_scheduler()
