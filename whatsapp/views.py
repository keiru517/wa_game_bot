import json
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .models import AdminUser, Game, Player
from twilio.request_validator import RequestValidator
from functools import wraps
import os
from django.views.decorators.http import require_POST
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
from .bot_util import *



def index(request):
    return render(request, 'index.html')

def validate_twilio_request(f):
    """Validates that incoming requests genuinely originated from Twilio"""
    @wraps(f)
    def decorated_function(request, *args, **kwargs):
        # Create an instance of the RequestValidator class
        validator = RequestValidator(os.environ.get('TWILIO_AUTH_TOKEN'))

        # Validate the request using its URL, POST data,
        # and X-TWILIO-SIGNATURE header
        request_valid = validator.validate(
            request.build_absolute_uri(),
            request.POST,
            request.META.get('HTTP_X_TWILIO_SIGNATURE', ''))

        # Continue processing the request if it's valid, return a 403 error if
        # it's not
        if request_valid:
            return f(request, *args, **kwargs)
        else:
            return HttpResponseForbidden()
    return decorated_function

@require_POST
@csrf_exempt
@validate_twilio_request
def incoming_message(request):
    """Twilio Messaging URL - receives incoming messages from Twilio"""
    # Create a new TwiML response
    resp = MessagingResponse()

    # <Message> a text back to the person who texted us
    message = request.POST['Body']
    message = message.replace('  ', ' ').strip()
    wa_id = request.POST.get('From', '').replace('whatsapp:', '').replace('+', '')
    wa_username = request.POST.get('ProfileName', '')
    
    message_list = message.split(' ')
    message_type = len(message_list)
    action = message_list[0].lower().strip()
    if message_type == 1:
        if action == '/admincommands':
            resp.message(ADMIN_COMMANDS_MESSAGE1)
            resp.message(ADMIN_COMMANDS_MESSAGE2) 
        elif action == '/playercommands':
            resp.message(PLAYER_COMMANDS_MESSAGE)  
        elif action == '/template':
            resp.message(CREATE_GAME_TEMPLATE_MESSAGE)
            return HttpResponse(resp)

        elif action == '/joinedgames':
            my_games = get_my_games(wa_id)
            if len(my_games) > 0:
                MYGAME_MESSAGE = f"""Your Upcoming Games ({len(my_games)}):\n
                """
                for my_game in my_games:
                    _, location, start_date, start_time, min_players, max_players, playerlist, waitlist, outlist = get_game_info(my_game.game.id)
                    if len(playerlist) == max_players:
                        MYGAME_MESSAGE += f"\nGame ID: {my_game.game.id}\nGame Status: ({max_players} Players)\nStart Date: {start_date}\nStart Time: {start_time}\nLocation: {location}\n"
                    elif len(playerlist) < min_players:
                        MYGAME_MESSAGE += f"\nGame ID: {my_game.game.id}\nGame Status: ❌({len(playerlist)}/{min_players})\nStart Date: {start_date}\nStart Time: {start_time}\nLocation: {location}\n"
                    elif len(playerlist) >= min_players:
                        MYGAME_MESSAGE += f"\nGame ID: {my_game.game.id}\nGame Status: ✅({len(playerlist)}/{max_players})\nStart Date: {start_date}\nStart Time: {start_time}\nLocation: {location}\n"
                        
                    resp.message(MYGAME_MESSAGE)
                    MYGAME_MESSAGE = f""
            else:
                MYGAME_MESSAGE = """There is no game you joined! You can join "/in (GameID)"."""
                resp.message(MYGAME_MESSAGE)   
                
        elif action == '/gamelist':
            games = get_all_games()
            MYGAME_MESSAGE=f"""
            """
            if len(games) > 0:
                for game in games:
                    _, location, start_date, start_time, min_players, max_players, playerlist, waitlist, outlist = get_game_info(game.id)
                    MYGAME_MESSAGE = f"\nGame ID: {game.id}\nGame Status: ({len(playerlist)}/{min_players} Players)\nStart Date: {start_date}\nStart Time: {start_time}\nLocation: {location}\n"
                    resp.message(MYGAME_MESSAGE)
            else:
                resp.message('There is no games available. You can create your own game.')
        else:
            resp.message(GUIDE_MESSAGE)
        return HttpResponse(resp)
    elif message_type == 2:
        game_id = message_list[1].strip()
        try:
            adminlist, location, start_date, start_time, min_players, max_players, playerlist, waitlist, outlist = get_game_info(game_id)
            # if the player is the admin of this game
            if action == '/edit':
                if wa_id in adminlist:
                    resp.message('Send edit message with this format')
                    resp.message(EDIT_GAME_TEMPLATE_MESSAGE.format(game_id, location, start_date, start_time, min_players, max_players))
                else:
                    resp.message('You are not the admin of this game!')
            elif action == '/delete':
                if wa_id in adminlist:
                    result = delete_game(game_id)
                    if result:
                        resp.message(f"You have successfully removed game {game_id}!")
                    else:
                        resp.message("Please insert correct GameID")
            # if the player is not the admin of this game
            elif action == '/info':
                # INFO_MESSAGE = GAMEINFO_MESSAGE.format(game_id,len(playerlist), max_players, location, start_date, start_time, min_players, max_players, game_id, game_id)
                
                # INFO_MESSAGE += f"\nPlayer List({len(playerlist)}):\n"
                # for phone_number, username in playerlist.items():
                #     INFO_MESSAGE += f"{username} : {phone_number}\n"
                
                # INFO_MESSAGE += f"\nWait List({len(waitlist)}):\n"
                # for phone_number, username in waitlist.items():
                #     INFO_MESSAGE += f"{username} : {phone_number}\n"

                # INFO_MESSAGE += f"\nOut List({len(outlist)}):\n"
                # for phone_number, username in outlist.items():
                #     INFO_MESSAGE += f"{username} : {phone_number}\n"
                
                # resp.message(INFO_MESSAGE)
                info_message = display_gameinfo(game_id)
                resp.message(info_message)
            elif action == '/in':
                
                if is_new_player(game_id, wa_id) or is_outlist_player(game_id, wa_id):
                    if not is_expired(game_id):
                    # join the game
                        if len(playerlist) < max_players:
                            add_playerlist(game_id, wa_username, wa_id)
                            # send notification to the admin
                            for admin_number, _ in adminlist.items():
                                notify_message(f"Player {wa_username} has joined the playerlist of game {game_id}.", admin_number)
                            # resp.message(ADD_PLAYERLIST_MESSAGE.format(game_id, location, start_date, start_time, min_players, max_players, game_id))
                            
                            info_message = display_gameinfo(game_id)
                            resp.message(info_message)
                        # join the waitlist
                        else:
                            # overflow the maximum limit
                            if len(playerlist) > max_players:
                                add_waitlist(game_id, wa_username, phone_number)
                                for admin_number, _ in adminlist.items():
                                    notify_message(f"Player {wa_username} has joined the waitlist of game {game_id}.", admin_number)
                                resp.message(WAITLIST_MESSAGE.format(game_id, location, start_date, start_time, min_players, max_players, game_id))
                            
                            # reached to maximum limit
                            else:
                                LOCAL_MAXIMUM_MESSAGE = MAXIMUM_MESSAGE.format(game_id, location, start_date, start_time, min_players, max_players, game_id, game_id, max_players)
                                count = 1
                                # add playerlist to the message
                                for number, name in playerlist.items():
                                    LOCAL_MAXIMUM_MESSAGE += "\t\n" + str(count) + ".  " + name + ": " + number
                                    count += 1
                                    
                                LOCAL_MAXIMUM_MESSAGE += '\nWaitlist(0)'
                                # notify the admin that the game has maximum players to the admin
                                for admin_number, _ in adminlist.items():
                                    notify_message(f'Game {game_id} has maximum players!', admin_number)
                                resp.message(LOCAL_MAXIMUM_MESSAGE)
                    else:
                        resp.message(f"The Game ID: {game_id} has been expired. You can't join.")
                elif is_blocked_player(game_id, wa_id):
                    resp.message('You are blocked to this game.')
                else:
                    resp.message('You have already joined this game.')                    
            
            elif action == '/out':
                result = remove_playerlist(game_id, wa_id)
                # if you are in the playerlist or waitlist
                if result:
                    # notify the admin that a player has left the game
                    for admin_number, _ in adminlist.items():
                        notify_message(f'Player {wa_username}:{wa_id} has left the game {game_id}.', admin_number)
                    # resp.message(REMOVE_MESSAGE.format(game_id, location, start_date, start_date, min_players, max_players))

                    # Send message to the first user in the waitlist
                    waitlist_name, waitlist_number = check_waitlist(game_id)
                    # if there is a play in the waitlist
                    if len(waitlist_number) > 0:
                        # message = client.messages.create(
                        #     from_=f'whatsapp:{twilio_number}',
                        #     body=ADD_PLAYERLIST_FROM_WAITLIST_MESSAGE.format(game_id, location, start_date, start_time, min_players, max_players, game_id),
                        #     to=f'whatsapp:{waitlist_number}'
                        # )
                        notify_message(ADD_PLAYERLIST_FROM_WAITLIST_MESSAGE.format(game_id, location, start_date, start_time, min_players, max_players, game_id), waitlist_number)
                        # notify the admin that a player has been moved from the waitlist to the playerlist
                        for admin_number, _ in adminlist.items():
                            notify_message(f'A player {waitlist_name}:{wa_username} has been added to the playerlist.', admin_number)
                    # if waitlist is 0
                    else:
                        pass
                else:
                    resp.message(f"You are not in the playerlist of the Game ID:{game_id}")
                info_message = display_gameinfo(game_id)
                resp.message(info_message)
            else:
                resp.message(GUIDE_MESSAGE)
        except:
            resp.message(GUIDE_MESSAGE)
        return HttpResponse(resp)
    elif message_type == 3:
        game_id = message_list[1]
        phone_number = message_list[2]
        try:
            adminlist, location, start_date, start_time, min_players, max_players, playerlist, waitlist, outlist = get_game_info(game_id)
            # if the player is the admin of this game
            if wa_id in adminlist:
                if action == '/kick':
                    try:
                        kick(game_id, phone_number)
                        resp.message(f'You have successfully removed {playerlist[phone_number]}: {phone_number} from game {game_id}!')
                    except:
                        resp.message('Please make sure the GameID or phone number.')
                elif action == '/block':
                    try:
                        block(game_id, phone_number)
                        resp.message(f'You have successfully blocked {phone_number} for game {game_id}!')
                    except:
                        resp.message('Please make sure the GameID or phone number are correct.')                    
                elif action == '/unblock':
                    try:
                        unblock(game_id, phone_number)
                        resp.message(f'You have successfully unblocked {phone_number} for game {game_id}.')
                    except:
                        resp.message('Please make sure the GameID or phone number are correct.')                    
                elif action == '/add':
                    try:
                        add(game_id, phone_number)
                    except:
                        resp.message('Please make sure the GameID or phone number are correct.')                    
                elif action == '/playerlist':
                    try:
                        insert_playerlist(game_id, phone_number)
                    except:
                        resp.message('Please make sure the GameID or phone number are correct.')                    
                elif action == '/waitlist':
                    try:
                        insert_waitlist(game_id, phone_number)
                    except:
                        resp.message('Please make sure the GameID or phone number are correct.')                    
                elif action == '/outlist':
                    try:
                        insert_outlist(game_id, phone_number)
                    except:
                        resp.message('Please make sure the GameID or phone number are correct.')                    
                elif action == '/invite':
                    try:
                        resp.message(GAMEINFO_MESSAGE.format(game_id, len(playerlist), max_players, location, start_date, start_time, min_players, max_players, game_id, game_id), phone_number)
                        notify_message(f'You have successfully invited {phone_number} to game {game_id}!',wa_id)
                    except:
                        resp.message('Please make sure the GameID or phone number are correct.')                    
                elif action == '/admin':
                    try:
                        add_admin(game_id, phone_number)
                        resp.message(f'You have Successfully given Admin powers to {phone_number} for Game {game_id}!')
                    except:
                        resp.message('Please make sure the GameID or phone number are correct.')                    
                elif action == '/removeadmin':
                    try:
                        remove_admin(game_id, phone_number)
                        resp.message(f'You have Successfully removed Admin powers to {phone_number} for Game {game_id}!')
                    except:
                        resp.message('Please make sure the GameID or phone number are correct.')                    
                else:
                    resp.message(GUIDE_MESSAGE)
                info_message = display_gameinfo(game_id)
                resp.message(info_message)
            else:
                resp.message(f"You are not the admin of the game {game_id}.")
        except:
            resp.message(GUIDE_MESSAGE)
        finally:
            return HttpResponse(resp)
    else:
        message_list = message.split('\n')
        print(message_list)
        if message_list[0] == '/create':
            if len(message_list) == 6:
                location = message_list[1].split(':')[1].strip()
                start_date = message_list[2].split(':')[1].strip()
                start_time = message_list[3].split(':')[1].strip() + ":" + message_list[3].split(':')[2].strip()
                min_players = message_list[4].split(':')[1].strip()
                max_players = message_list[5].split(':')[1].strip()
                print("================", start_date, len(start_date))
                print("================", start_time, len(start_time))

                id = insert_game(wa_id, wa_username, location, start_date, start_time, min_players, max_players)

                # this should be sent to the group
                resp.message(CREATED_GAME_MESSAGE.format(id, location, start_date, start_time, min_players, max_players, id, id))            
            else:
                resp.message(CREATE_GAME_TEMPLATE_MESSAGE)
        elif message_list[0] == '/edit':
            if len(message_list) == 7:
                game_id = message_list[1].split(':')[1]
                location = message_list[2].split(':')[1]
                start_date = message_list[3].split(':')[1]
                start_time = message_list[4].split(':')[1] + ":" + message_list[4].split(':')[2]
                min_players = message_list[5].split(':')[1]
                max_players = message_list[6].split(':')[1]
                
                adminlist, _, _, _, _, _, _, _, _ = get_game_info(game_id)
                # if the player is the admin of this game
                if wa_id in adminlist:
                    edit_game(game_id, location, start_date, start_time, min_players, max_players)
                    resp.message('')
                else:
                    resp.message('You are not the admin of this game!')
                
        else:
            resp.message(GUIDE_MESSAGE)
        return HttpResponse(resp)
    
    


