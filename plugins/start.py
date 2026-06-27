@Client.on_message(filters.command('start') & filters.private)
@force_sub
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id

    # 1. Add user if not present
    present = await client.mongodb.present_user(user_id)
    if not present:
        try:
            await client.mongodb.add_user(user_id)
        except Exception as e:
            client.LOGGER(__name__, client.name).warning(f"Error adding a user:\n{e}")

    # 2. Check if banned
    is_banned = await client.mongodb.is_banned(user_id)
    if is_banned:
        return await message.reply("**You have been banned from using this bot!**")

    text = message.text
    if len(text) > 7:
        try:
            original_payload = text.split(" ", 1)[1]
            base64_string = original_payload
            is_verification = False

            # Custom logic to catch verification return
            if base64_string.startswith("verify_"):
                base64_string = base64_string.replace("verify_", "")
                is_verification = True
            elif base64_string.startswith("yu3elk"):
                base64_string = base64_string[6:-1]
                
        except IndexError:
            return await message.reply("Invalid command format.")

        # 3. Check premium and verification status
        is_user_pro = await client.mongodb.is_pro(user_id)
        is_verified = await client.mongodb.check_verify_status(user_id)

        # 4. Handle Verification completion
        if is_verification:
            await client.mongodb.set_verify_status(user_id)
            is_verified = True
            await message.reply("✅ **Verification Successful!**\n\nYou can now download files directly for the next 24 hours without seeing any ads.")

        # 5. Check if shortner is enabled
        shortner_enabled = getattr(client, 'shortner_enabled', True)

        # 6. If user is NOT premium, NOT verified, AND shortner is enabled, send short URL
        if not is_user_pro and user_id != OWNER_ID and not is_verified and shortner_enabled:
            try:
                # Generate link pointing back to bot with 'verify_' prefix
                verify_payload = f"verify_{base64_string}"
                short_link = get_short(f"https://t.me/{client.username}?start={verify_payload}", client)
            except Exception as e:
                client.LOGGER(__name__, client.name).warning(f"Shortener failed: {e}")
                return await message.reply("Couldn't generate short link.")

            short_photo = client.messages.get("SHORT_PIC", "")
            short_caption = client.messages.get("SHORT_MSG", "Get your file here:")
            tutorial_link = getattr(client, 'tutorial_link', "https://t.me/How_to_Download_7x/26")

            await client.send_photo(
                chat_id=message.chat.id,
                photo=short_photo,
                caption=short_caption,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("• ᴏᴘᴇɴ ʟɪɴᴋ", url=short_link),
                        InlineKeyboardButton("ᴛᴜᴛᴏʀɪᴀʟ •", url=tutorial_link)
                    ],
                    [
                        InlineKeyboardButton(" • ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ •", url="https://t.me/Premium_Fliix/21")
                    ]
                ])
            )
            return  # Stop here, force user to verify

        # 7. Decode and prepare file IDs (User is verified/premium, proceed to send file)
        try:
            string = await decode(base64_string)
            argument = string.split("-")
            ids = []
            source_channel_id = None

            if len(argument) == 3:
                encoded_start = int(argument[1])
                encoded_end = int(argument[2])
                
                primary_multiplier = abs(client.db)
                start_primary = int(encoded_start / primary_multiplier)
                end_primary = int(encoded_end / primary_multiplier)
                
                if encoded_start % primary_multiplier == 0 and encoded_end % primary_multiplier == 0:
                    source_channel_id = client.db
                    start = start_primary
                    end = end_primary
                else:
                    db_channels = getattr(client, 'db_channels', {})
                    for channel_id_str in db_channels.keys():
                        channel_id = int(channel_id_str)
                        channel_multiplier = abs(channel_id)
                        start_test = int(encoded_start / channel_multiplier)
                        end_test = int(encoded_end / channel_multiplier)
                        
                        if encoded_start % channel_multiplier == 0 and encoded_end % channel_multiplier == 0:
                            source_channel_id = channel_id
                            start = start_test
                            end = end_test
                            break
                    
                    if source_channel_id is None:
                        source_channel_id = client.db
                        start = start_primary
                        end = end_primary
                
                ids = range(start, end + 1) if start <= end else list(range(start, end - 1, -1))

            elif len(argument) == 2:
                encoded_msg = int(argument[1])
                
                if hasattr(client, 'db_channel') and client.db_channel:
                    primary_multiplier = abs(client.db_channel.id)
                    msg_id_primary = int(encoded_msg / primary_multiplier)
                    
                    if encoded_msg % primary_multiplier == 0:
                        source_channel_id = client.db_channel.id
                        ids = [msg_id_primary]
                    else:
                        db_channels = getattr(client, 'db_channels', {})
                        for channel_id_str in db_channels.keys():
                            channel_id = int(channel_id_str)
                            channel_multiplier = abs(channel_id)
                            msg_id_test = int(encoded_msg / channel_multiplier)
                            
                            if encoded_msg % channel_multiplier == 0:
                                source_channel_id = channel_id
                                ids = [msg_id_test]
                                break
                        
                        if source_channel_id is None:
                            source_channel_id = client.db_channel.id if hasattr(client, 'db_channel') else client.db
                            ids = [msg_id_primary]
                else:
                    source_channel_id = client.db
                    ids = [int(encoded_msg / abs(client.db))]

        except Exception as e:
            client.LOGGER(__name__, client.name).warning(f"Error decoding base64: {e}")
            return await message.reply("⚠️ Invalid or expired link.")

        # 8. Get messages from the specific source channel
        temp_msg = await message.reply("Wait A Sec..")
        messages = []

        try:
            if source_channel_id:
                try:
                    msgs = await client.get_messages(
                        chat_id=source_channel_id,
                        message_ids=list(ids)
                    )
                    valid_msgs = [msg for msg in msgs if msg is not None]
                    messages.extend(valid_msgs)
                    
                    if len(valid_msgs) < len(list(ids)):
                        missing_ids = [mid for mid in ids if mid not in {msg.id for msg in valid_msgs}]
                        if missing_ids:
                            additional_messages = await get_messages(client, missing_ids)
                            messages.extend(additional_messages)
                except Exception as e:
                    messages = await get_messages(client, ids)
            else:
                messages = await get_messages(client, ids)
        except Exception as e:
            await temp_msg.edit_text("Something went wrong!")
            return

        if not messages:
            return await temp_msg.edit("Couldn't find the files in the database.")
        await temp_msg.delete()

        yugen_msgs = []
        for msg in messages:
            caption = (
                client.messages.get('CAPTION', '').format(
                    previouscaption=msg.caption.html if msg.caption else msg.document.file_name
                ) if bool(client.messages.get('CAPTION', '')) and bool(msg.document)
                else ("" if not msg.caption else msg.caption.html)
            )
            reply_markup = msg.reply_markup if not client.disable_btn else None

            try:
                copied_msg = await msg.copy(
                    chat_id=message.from_user.id,
                    caption=caption,
                    reply_markup=reply_markup,
                    protect_content=client.protect
                )
                yugen_msgs.append(copied_msg)
            except FloodWait as e:
                await asyncio.sleep(e.x)
                copied_msg = await msg.copy(
                    chat_id=message.from_user.id,
                    caption=caption,
                    reply_markup=reply_markup,
                    protect_content=client.protect
                )
                yugen_msgs.append(copied_msg)
            except Exception as e:
                pass

        # 9. Auto delete timer
        if messages and client.auto_del > 0:
            transfer_link = original_payload
            asyncio.create_task(batch_auto_del_notification(
                bot_username=client.username,
                messages=yugen_msgs,
                delay_time=client.auto_del,
                transfer_link=transfer_link,
                chat_id=message.from_user.id,
                client=client
            ))
        return

    # 10. Normal start message
    else:
        buttons = [[InlineKeyboardButton("Help", callback_data="about"), InlineKeyboardButton("Close", callback_data='close')]]
        if user_id in client.admins:
            buttons.insert(0, [InlineKeyboardButton("⛩️ ꜱᴇᴛᴛɪɴɢꜱ ⛩️", callback_data="settings")])

        photo = client.messages.get("START_PHOTO", "")
        start_caption = client.messages.get('START', 'Welcome, {mention}').format(
            first=message.from_user.first_name,
            last=message.from_user.last_name,
            username=None if not message.from_user.username else '@' + message.from_user.username,
            mention=message.from_user.mention,
            id=message.from_user.id
        )

        if photo:
            await client.send_photo(
                chat_id=message.chat.id,
                photo=photo,
                caption=start_caption,
                message_effect_id=MSG_EFFECT,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        else:
            await client.send_message(
                chat_id=message.chat.id,
                text=start_caption,
                message_effect_id=MSG_EFFECT,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        return
