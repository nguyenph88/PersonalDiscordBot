import discord
from utils.default import CustomContext
from discord.ext import commands
from utils.data import DiscordBot
from utils import http
import asyncio


class Download_Commands(commands.Cog):
    def __init__(self, bot):
        self.bot: DiscordBot = bot
    
    # Global wait time for API calls (in seconds)
    API_WAIT_TIME = 5

    # global loop time to run the magnet_check_id command
    MAGNET_CHECK_ID_LOOP_TIME = 3
    
    # Global wait time for user reactions (in seconds)
    REACTION_WAIT_TIME = 15

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
        await ctx.send("Available commands:\n`!AD status` - Check API authentication\n`!AD download <link>` - Unlock/download a link\n`!AD magnet_upload <magnet_uri>` - Upload magnet link to AllDebrid and get Magnet ID\n`!AD magnet_get <magnet_uri>` - Complete workflow: upload magnet and check status\n`!AD magnet_check_id <magnet_id>` - Check magnet status and information\n`!AD magnet_get_files <magnet_id>` - Get all download files and links\n`!AD supported_host <name>` - Check if a service is supported\n`!AD supported_hosts` - List all supported services\n`!AD history <number>` - Get recent download history")

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
                                value=f"`!AD magnet_check_id {magnet_id}`",
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
                                value=f"Use `!AD magnet_check_id {magnet_id}` when you're ready",
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
                                
                                # Call the magnet_check_id function
                                await self.magnet_check_id(ctx, str(magnet_id))
                                
                            except asyncio.TimeoutError:
                                # No reaction within timeout period
                                timeout_embed = discord.Embed(
                                    title="⏰ Time's up!",
                                    description="You can check the magnet status manually anytime using:",
                                    color=discord.Color.orange()
                                )
                                timeout_embed.add_field(
                                    name="🔍 Manual Status Check",
                                    value=f"`!AD magnet_check_id {magnet_id}`",
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
    async def magnet_check_id(self, ctx: CustomContext, magnet_id: str):
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
                
                for loop_count in range(self.MAGNET_CHECK_ID_LOOP_TIME + 1):
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
                            if loop_count < self.MAGNET_CHECK_ID_LOOP_TIME - 1:
                                await ctx.send(f"⏳ **Attempt {loop_count + 1}/{self.MAGNET_CHECK_ID_LOOP_TIME}:** Magnet not ready yet. Waiting {self.API_WAIT_TIME} seconds before next check...")
                                await asyncio.sleep(self.API_WAIT_TIME)

                            # if last loop, send error message
                            if loop_count == self.MAGNET_CHECK_ID_LOOP_TIME:
                                await ctx.send(f"⏳ **Attempt {loop_count}/{self.MAGNET_CHECK_ID_LOOP_TIME}:** Magnet not ready yet. Printing the magnet data...")
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
                    
                    # add magnet_check_id command to the embed
                    if status_lower != "ready":
                        embed.add_field(name="🔍 Check Magnet Status (again later)", value=f"- Use `!AD magnet_check_id {magnet_id}`\n- Don't complain, use a magnet with many seeders to get a good download :)", inline=False)
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
                            value="`!AD download <file_link>`\n*(Use the links from Step 1)*",
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
                        next_steps_embed.set_footer(text="Links will expire in 24 hours")
                        
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
                            # Create embed with magnet files information
                            embed = discord.Embed(
                                title="📁 Magnet Files Available",
                                description=f"**Magnet ID:** `{magnet_id}`",
                                color=discord.Color.green()
                            )
                            
                            embed.add_field(name="📋 Total Files", value=f"{len(magnet_links)} files", inline=True)
                            
                            # Show all files with download links
                            files_display = ""
                            for i, link in enumerate(magnet_links, 1):
                                file_name = link.get('n', 'Unknown')
                                file_size = self._format_file_size(link.get('s', 'Unknown'))
                                download_link = link.get('l', 'No link available')
                                
                                # Truncate long filenames
                                display_name = self._truncate_text(file_name, 40)
                                
                                files_display += f"**{i}.** {display_name}\n"
                                files_display += f"   📏 Size: {file_size}\n"
                                files_display += f"   🔗 Link: {download_link}\n\n"
                            
                            embed.add_field(name="📋 Files & Download Links", value=files_display, inline=False)
                            
                            embed.set_footer(text=f"Magnet ID: {magnet_id}")
                            await ctx.send(embed=embed)
                            
                            # Send additional message with download instructions
                            download_instructions_embed = discord.Embed(
                                title="🔗 Download Instructions",
                                description="To request direct download links for any of these files, use the commands below:",
                                color=discord.Color.blue()
                            )
                            
                            # Create download commands for each file
                            download_commands = ""

                            download_instructions_embed.add_field(
                                name="💡 How to Download",
                                value="1. Click on any command below to copy it\n2. Paste it in the chat and press Enter\n3. The bot will provide you with a direct download link",
                                inline=False
                            )

                            for i, link in enumerate(magnet_links, 1):
                                file_name = link.get('n', 'Unknown')
                                download_link = link.get('l', 'No link available')
                                
                                # Truncate long filenames for display
                                display_name = self._truncate_text(file_name, 100)
                                
                                download_commands += f"**{i}.** `!AD download {download_link}`\n"
                                download_commands += f"   📁 File: {display_name}\n\n"
                            
                            download_instructions_embed.add_field(
                                name="📋 Download Commands",
                                value=download_commands,
                                inline=False
                            )
                        
                            download_instructions_embed.add_field(
                                name="⚠️ Important Notes",
                                value="• Links will expire in 24 hours\n• You can download files one at a time\n• Some files in the magnet are trash or virus files - use your own judgement\n• Commands are in code blocks for easy copying",
                                inline=False
                            )
                            
                            download_instructions_embed.set_footer(text=f"Magnet ID: {magnet_id} | Total Files: {len(magnet_links)}")
                            await ctx.send(embed=download_instructions_embed)
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

    @AD.command()
    async def magnet_get(self, ctx: CustomContext, *, magnet_uri: str):
        """ Complete workflow: upload magnet URI, get ID, check status """
        if not magnet_uri:
            await ctx.send("❌ **Error:** Please provide a magnet URI")
            return
        
        magnet_uri = magnet_uri.strip()
        if not magnet_uri.startswith('magnet:?'):
            await ctx.send("❌ **Error:** Please provide a valid magnet URI starting with `magnet:?`")
            return
        
        async with ctx.channel.typing():
            try:
                api_key = await self._check_api_authentication()
                headers = {'Authorization': f'Bearer {api_key}'}
                
                # Step 1: Upload magnet and get ID
                upload_data = {'magnets[]': magnet_uri}
                upload_response = await self._make_api_request(
                    'https://api.alldebrid.com/v4/magnet/upload',
                    headers=headers,
                    method="POST",
                    data=upload_data
                )
                
                upload_result = upload_response.response
                if upload_result.get('status') != 'success':
                    error_msg = upload_result.get('error', {}).get('message', 'Unknown error')
                    embed = self._create_error_embed("❌ Magnet Upload Failed", f"**Error:** {error_msg}")
                    embed.add_field(name="🔗 Original Magnet", value=f"```{magnet_uri}```", inline=False)
                    await ctx.send(embed=embed)
                    return

                magnet_data = upload_result.get('data', {})
                magnets = magnet_data.get('magnets', [])

                if not magnets:
                    embed = self._create_error_embed("❌ Magnet Upload Failed", "No magnet data returned")
                    embed.add_field(name="🔗 Original Magnet", value=f"```{magnet_uri}```", inline=False)
                    await ctx.send(embed=embed)
                    return
                
                # The magnets data is a list containing a dictionary
                magnet_info = magnets[0]  # Get the first magnet from the list
                magnet_id = magnet_info.get('id')
                
                if not magnet_id:
                    embed = self._create_error_embed("❌ Magnet Upload Failed", "No magnet ID returned")
                    embed.add_field(name="🔗 Original Magnet", value=f"```{magnet_uri}```", inline=False)
                    await ctx.send(embed=embed)
                    return
                
                # Step 2: Check magnet status
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
                        magnet_data = status_result.get('data', {}).get('magnets', {})
                        
                        if magnet_data:
                            # Extract magnet information from the correct structure
                            #magnet_name = magnet_data.get('name', 'Unknown')
                            magnet_status = magnet_data.get('status', 'Unknown')
                            magnet_progress = 100 if magnet_status == 'Ready' else 0
                            
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
                            embed.add_field(name="📊 Progress", value=f"{magnet_progress}%", inline=True)
                            
                            # Status with emoji (case-insensitive comparison)
                            status_lower = magnet_status.lower()
                            status_emoji = "✅" if status_lower == "ready" else "⏳" if status_lower == "downloading" else "❌"
                            embed.add_field(name="🔄 Status", value=f"{status_emoji} {magnet_status.title()}", inline=True)
                            
                            # Add links if available
                            if magnet_links:
                                embed.add_field(name="🔗 Links", value=f"{len(magnet_links)} files available", inline=True)
                                
                                # Show first few links with download links
                                if len(magnet_links) <= 5:
                                    links_display = "\n".join([f"• {link.get('n', 'Unknown')} ({self._format_file_size(link.get('s', 'Unknown'))})\n  🔗 {link.get('l', 'No link available')}" for link in magnet_links])
                                else:
                                    links_display = "\n".join([f"• {link.get('n', 'Unknown')} ({self._format_file_size(link.get('s', 'Unknown'))})\n  🔗 {link.get('l', 'No link available')}" for link in magnet_links[:5]])
                                    links_display += f"\n... and {len(magnet_links) - 5} more files"
                                
                                embed.add_field(name="📋 Files", value=links_display, inline=False)
                            else:
                                embed.add_field(name="📋 Files", value="No files available yet", inline=False)
                            
                            embed.set_footer(text=f"Magnet ID: {magnet_id}")
                            await ctx.send(embed=embed)
                        else:
                            embed = self._create_error_embed("❌ Magnet Not Found", f"No magnet found with ID: `{magnet_id}`")
                            await ctx.send(embed=embed)
                    else:
                        error_msg = status_result.get('error', {}).get('message', 'Unknown error')
                        embed = self._create_error_embed("❌ Magnet Status Check Failed", f"**Error:** {error_msg}")
                        embed.add_field(name="🔗 Magnet ID", value=f"`{magnet_id}`", inline=False)
                        await ctx.send(embed=embed)
                        
                except ValueError:
                    await ctx.send("❌ **Error:** Invalid magnet ID format")
                    
            except Exception as e:
                error_embed = self._create_error_embed("❌ Error", str(e))
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
        
        embed.set_footer(text="Link will expire in 24 hours")
        
        if message_to_edit:
            await message_to_edit.edit(embed=embed)
        else:
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Download_Commands(bot))
