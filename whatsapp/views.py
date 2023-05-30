import json
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from twilio.rest import Client
from .models import AdminUser, Game, Player
from twilio.request_validator import RequestValidator
from functools import wraps
import os
from django.views.decorators.http import require_POST
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import time

GUIDE_MESSAGE = """Command not recognized. See a list of Player Commands and Admin Commands by typing:
"/playercommands"
"/admincommands"
"""

CREATE_GAME_TEMPLATE_MESSAGE = """/create
Location: 160 Columbus Ave, New York, NY 10023
Start Date: 5/25/2023
Start Time: 18:00
Minimum Players: 6
Maximum Players: 11"""

EDIT_GAME_TEMPLATE_MESSAGE = """/edit
Game ID: {}
Location: {}
Start Date: {}
Start Time: {}
Minimum Players: {}
Maximum Players: {}"""

CREATED_GAME_MESSAGE = """GameID: {}
Location: {}
Start Date: {}
Start Time: {}
Minimum Players: {}
Maximum Players: {}

To Join the Game, reply "/in {}" privately to this message.
To Leave the Game, reply "/out {}" privately to this message.
"""

ADMIN_COMMANDS_MESSAGE1="""
-"/template" : Gives the Admin the /create game template to copy with some dummy data.

-"/create" : Allows a user to create a new game. After this command, you should send message for game info.

-"/delete" : Allows a user to delete a game.

-"/kick (GameID) (Phone Number)" : Allows an admin to remove a player from the player list/wait list of a game and moves them to out list.

-"/block (GameID) (Phone Number)" : Allows an admin to kick a player from a game, and block them from rejoining the game.

-"/unblock (GameID) (Phone Number)" : Allows an admin to unblock a player from a game, and allows them to rejoin the game.

-"/add (GameID) (Phone Number)" : Allows an admin to add a player to a game, adds the player to the player list if there's a spot, and the waitlist if it's already a full game.

"""
ADMIN_COMMANDS_MESSAGE2 = """
-"/playerlist (GameID) (Phone Number)" : Allows an admin to manually add a player to a games player list (Even if Full). If the player is currently on the waitlist, they will be moved to the player list. Overrides Max Players.

-"/waitlist (GameID) (Phone Number)" : Allows an admin to manually add a player to a games wait list. If the player is currently on the playerlist, they will be moved to the waitlist.

-"/outlist (GameID) (Phone Number)" : Allows an admin to manually add a player to the Out List. If they are currently on the player list, wait list, or not even in the game, they will be added/moved to the Out List.

-"/invite (GameID) (Phone Number)" :  Sends an invite message with game info to a phone number.

-"/edit (GameID)" : Allows Admins to edit an existing game's details.

-"/admin (GameID) (Phone Number)" : Allows an admin to give admin powers to a phone number for that game.

-"/removeadmin (GameID) (Phone Number)" : Allows an admin to remove admin powers from a phone number for that game. Can not be used on the original creator of the game.

"""

PLAYER_COMMANDS_MESSAGE = """
-"/info (GameID)" : Displays All Game Info Including Player List & Waitlist

-"/joinedgames" : Shows all upcoming games that the player has already joined

-"/in (GameID)" : Adds player to a game they are not currently added to. Adds the player to the Player List if it is not full, and if it is full, adds the player to the Wait List.

-"/out (GameID)" : Removes player from a game they were signed up for. Moves player to the Out List of that game, and will update the Player and Wait List for the other players if applicable. Also moves up players from Wait List to take the players spot if the player was on the Player List and there are players waiting on the Wait List.

-"/gamelist" :  Shows List of games available to the player.

"""

ADD_PLAYERLIST_MESSAGE = """Game ID: {}
Location: {}
Start Date: {}
Start Time: {}
Minimum Players: {}
Maximum Players: {}

You have been added to Game!

To Leave Game, reply "/out {}" to this message."""

WAITLIST_MESSAGE = """Game ID: {}
Location: {}
Start Date: {}
Start Time: {}
Minimum Players: {}
Maximum Players: {}

Maximum Player Limit Reached! You have been successfully added to Game

To Leave Game, reply "/out {}" privately to this message.
"""

MAXIMUM_MESSAGE = """Game ID: {}
Location: {}
Start Date: {}
Start Time: {}
Minimum Players: {}
Maximum Players: {}

To Join Game, reply "/in {}" privately to this message.
To Leave Game, reply "/out {}" privately to this message.

Maximum Player Limit Reached! Players may still join Game.

Player List ({})
"""

GAMEINFO_MESSAGE = """Game ID: {}
Game Status: {}({}/{} Players)
Location: {}
Start Date: {}
Start Time: {}
Minimum Players: {}
Maximum Players: {}

To Join Game, reply "/in {}" privately to this message.

To Leave Game, reply "/out {}" to this message.
"""

REMOVE_MESSAGE = """Game ID: {}
Location: {}
Start Date: {}
Start Time: {}
Minimum Players: {}
Maximum Players: {}

You have been successfully removed from the Game!
"""

ADD_PLAYERLIST_FROM_WAITLIST_MESSAGE = """Game ID: {}
Location: {}
Start Date: {}
Start Time: {}
Minimum Players: {}
Maximum Players: {}

A player has dropped out! You have been added to Game!

To Leave Game, reply "/out {}" to this message.
"""

account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
twilio_number = os.environ.get('TWILIO_NUMBER')
client = Client(account_sid, auth_token)
openai_api_key = os.environ.get('OPENAI_API_KEY')

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
                        message = client.messages.create(
                            from_=f'whatsapp:{twilio_number}',
                            body=ADD_PLAYERLIST_FROM_WAITLIST_MESSAGE.format(game_id, location, start_date, start_time, min_players, max_players, game_id),
                            to=f'whatsapp:{waitlist_number}'
                        )
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
    
    
# Send notify message to a phone_number with message
def notify_message(message, phone_number):
    message = client.messages.create(
        from_=f'whatsapp:{twilio_number}',
        body=message,
        to=f'whatsapp:{phone_number}'
    )

def is_admin(phone_number):
    admin = AdminUser.objects.filter(phone_number=phone_number)
    if len(admin) > 0:
        return True
    else:
        return False

def is_expired(game_id):
    # return is_expired
    game = Game.objects.get(id=game_id)
    input_format = "%m/%d/%Y %H:%M"
    dt = datetime.strptime(game.start_date + " " + game.start_time, input_format)
    
    output_format = "%Y-%m-%d %H:%M"
    start_time = dt.strftime(output_format)
    cur_time = datetime.now().strftime(output_format)
    if start_time > cur_time:
        return False
    # elif start_time == cur_time:
    #     return False, True
    else:
        return True
    
    

def insert_game(phone_number, username, location, start_date, start_time, min_players, max_players):
    newGame = Game()
    newGame.phone_number = phone_number
    newGame.username = username
    newGame.location = location.strip()
    newGame.start_date = start_date.strip()
    newGame.start_time = start_time.strip()
    newGame.min_players = min_players.strip()
    newGame.max_players = max_players.strip()
    newGame.save()
    
    newAdmin = AdminUser()
    newAdmin.game = Game.objects.get(id=newGame.id)
    newAdmin.phone_number = phone_number
    newAdmin.username = username
    newAdmin.save()
    
    return newGame.id


def edit_game(game_id, location, start_date, start_time, min_players, max_players):
    game = Game.objects.get(id=game_id)
    prev_max_players = game.max_players
    
    game.location = location
    game.start_date = start_date
    game.start_time = start_time 
    game.min_players = min_players
    game.max_players = max_players
    game.save()
    
    max_players = int(max_players)
    # handle players based on the change of the maximum players
    # if maximum players has increased
    if max_players > prev_max_players:
        # number of the players should be moved to the playerlist
        diff = max_players - prev_max_players
        # find players in the waitlist of the game
        players = Player.objects.filter(game=game_id, is_waitlist=True).order_by('joined_at')
        count = 0
        if len(players) >= diff:
            count = diff
        else:
            count = len(players)
        
        for player in players[:count]:
            player.is_waitlist = False
            player.is_playerlist = True
            player.joined_at = datetime.now()
            player.save()
            notify_message(f'You are moved to the playerlist of game {game_id}!', player.phone_number)
                
    elif max_players < prev_max_players:
        # number of players should be moved to waitlist
        diff = prev_max_players - max_players
        players = Player.objects.filter(game=game_id, is_playerlist=True).order_by('joined_at')
        if len(players) > max_players:
            for player in players[max_players-len(players):]:
                player.is_playerlist = False
                player.is_waitlist = True
                player.joined_at = datetime.now()
                player.save()
                notify_message(f'You are moved to the waitlist of game {game_id}!', player.phone_number)
    
    
def delete_game(game_id):
    game = Game.objects.get(id=game_id)
    if game:
        game.delete()
        return True 
    else:
        return False   

def kick(game_id, phone_number):
    player = Player.objects.get(game=game_id, phone_number=phone_number)
    player.is_playerlist = False
    player.is_waitlist = False
    player.is_outlist = True
    player.save()
    

def block(game_id, phone_number):
    player = Player.objects.get(game=game_id, phone_number=phone_number)
    player.is_blocked = True
    player.is_playerlist = False
    player.is_waitlist = False
    player.is_outlist = False
    player.save()


def unblock(game_id, phone_number):
    player = Player.objects.get(game=game_id, phone_number=phone_number)
    player.is_blocked = False
    player.save()
    
# Allows an admin to add a player to a game, adds the player to the player list if there’s a spot, and the waitlist if it’s already a full game.
def add(game_id, phone_number):
    game = Game.objects.get(id=game_id)
    max_players = game.max_players
    players = Player.objects.filter(game=game_id, is_playerlist=True)
    # if the maximum limit is not reached and new player
    if is_new_player(game_id, phone_number):
        if len(players) < max_players:
            add_playerlist(game_id, "added player", phone_number)
        else:
            add_waitlist(game_id, 'added player', phone_number)
        notify_message(f'You have successfully added {phone_number} to game {game_id}.', game.phone_number)
    else:
        notify_message(f"{phone_number} has already been joined the game {game_id}", game.phone_number)
 

def insert_playerlist(game_id, phone_number):
    game = Game.objects.get(id=game_id)
    player = Player.objects.get(game=game_id, phone_number=phone_number)
    # if the player is in the game
    if player:
        player.is_playerlist = True
        player.is_waitlist = False
        player.is_outlist = False
        player.joined_at = datetime.now()
        player.save()
    else:
        add_playerlist(game_id, 'player', phone_number)
    notify_message(f'You have successfully added {phone_number} to {game_id}\'s Player List!', game.phone_number)
 

def insert_waitlist(game_id, phone_number):
    game = Game.objects.get(id=game_id)
    player = Player.objects.get(game=game_id, phone_number=phone_number)
    # if the player is in the game
    if player:
        player.is_playerlist = False
        player.is_waitlist = True
        player.is_outlist = False
        player.joined_at = datetime.now()
        player.save()
    else:
        add_waitlist(game_id, 'player', phone_number)
    notify_message(f'You have successfully added {phone_number} to {game_id}\'s Wait List!', game.phone_number)
 

def insert_outlist(game_id, phone_number):
    game = Game.objects.get(id=game_id)
    player = Player.objects.get(game=game_id, phone_number=phone_number)
    # if the player is in the game
    if player:
        player.is_playerlist = False
        player.is_waitlist = False
        player.is_outlist = True
        player.joined_at = datetime.now()
        player.save()
    else:
        add_outlist(game_id, 'player', phone_number)
    notify_message(f'You have successfully added {phone_number} to {game_id}\'s Out List!', game.phone_number)

    

def get_game_info(game_id):
    # get game info with game_id from games table
    game = Game.objects.get(id=game_id)
    
    if game:
        phone_number = game.phone_number
        username = game.username
        location = game.location
        start_date = game.start_date
        start_time = game.start_time
        min_players = game.min_players
        max_players = game.max_players

        admins = AdminUser.objects.filter(game=game_id)
        players = Player.objects.filter(game=game_id, is_playerlist=True).order_by('joined_at')
        waits = Player.objects.filter(game=game_id, is_waitlist=True).order_by('joined_at')
        outs = Player.objects.filter(game=game_id, is_outlist=True).order_by('joined_at')
        
        adminlist = {}
        for admin in admins:
            adminlist[admin.phone_number] = admin.username
        
        playerlist = {}
        for player in players:
            playerlist[player.phone_number] = player.username
        
        waitlist = {}
        for wait in waits:
            waitlist[wait.phone_number] = wait.username

        outlist = {}
        for out in outs:
            outlist[out.phone_number] = out.username
            
        return adminlist, location, start_date, start_time, min_players, max_players, playerlist, waitlist, outlist
    else:
        return [], [], [], [], [], [], [], [], []


def get_all_games():
    games = Game.objects.all().order_by('-created_at')
    available_games = [game for game in games if not is_expired(game.id)]
    return available_games

def get_my_games(phone_number):
    my_games = Player.objects.filter(phone_number=phone_number)
    return my_games




def is_new_player(game_id, phone_number):
    # return True if player is new to this game
    player = Player.objects.filter(phone_number=phone_number, game=game_id).exists()
    return not player
 
    
def is_blocked_player(game_id, phone_number):
    blocked = Player.objects.filter(phone_number=phone_number, game=game_id, is_blocked=True)
    if len(blocked) > 0:
        return True
    else:
        return False

def is_outlist_player(game_id, phone_number):
    # return True if player is new to this game
    player = Player.objects.get(phone_number=phone_number, game=game_id)
    
    if player:
        if player.is_outlist and not player.is_blocked:
            player.delete()
            return True
        else:
            return False
    else:   
        return False   


# return playerlist
def get_playerlist(id):
    return {'Tom Sandoval':'132456', 'Jack Mason': '4567891', 'Tony':'789465'}

# add number to the playerlist
def add_playerlist(id, username, phone_number):
    newPlayer = Player()
    newPlayer.game = Game.objects.get(id=id)
    newPlayer.username = username
    newPlayer.phone_number = phone_number
    newPlayer.is_playerlist = True
    newPlayer.is_waitlist = False
    newPlayer.is_outlist = False
    newPlayer.joined_at = datetime.now()
    newPlayer.save()

# add number to the waitlist
def add_waitlist(id, username, phone_number):
    newPlayer = Player()
    newPlayer.game = Game.objects.get(id=id)
    newPlayer.username = username
    newPlayer.phone_number = phone_number
    newPlayer.is_playerlist = False
    newPlayer.is_waitlist = True
    newPlayer.is_outlist = False
    newPlayer.save()
    

# add number to the outlist
def add_outlist(id, username, phone_number):
    newPlayer = Player()
    newPlayer.game = Game.objects.get(id=id)
    newPlayer.username = username
    newPlayer.phone_number = phone_number
    newPlayer.is_playerlist = False
    newPlayer.is_waitlist = False
    newPlayer.is_outlist = True
    newPlayer.save()


def get_waitlist(id):
    return {'Tom Sandoval':'132456', 'Jack Mason': '4567891', 'Tony':'789465'}

# remove number from the waitlist
def remove_playerlist(game_id, phone_number):
    player = Player.objects.get(game=game_id, phone_number=phone_number)
    if player:
        player.is_playerlist = False
        player.is_waitlist = False
        player.is_outlist = True
        player.save()
        
        return True
    else:
        return False
    


def check_waitlist(game_id):
    # find waitlist from the players table with game_id and sort them
    waitlist = Player.objects.filter(game=game_id, is_waitlist=True).order_by('joined_at')
    if len(waitlist) > 0:
        waitlist[0].is_playerlist = True
        waitlist[0].is_waitlist = False
        return waitlist[0].username, waitlist[0].phone_number
    else:
        return [], []

def display_gameinfo(game_id):
    admin_number, location, start_date, start_time, min_players, max_players, playerlist, waitlist, outlist = get_game_info(game_id)
    if len(playerlist) >= min_players:
        INFO_MESSAGE = GAMEINFO_MESSAGE.format(game_id, "✅", len(playerlist), max_players, location, start_date, start_time, min_players, max_players, game_id, game_id)
    else:
        INFO_MESSAGE = GAMEINFO_MESSAGE.format(game_id, "❌", len(playerlist), min_players, location, start_date, start_time, min_players, max_players, game_id, game_id)
        
    INFO_MESSAGE += f"\nPlayer List({len(playerlist)}):\n"
    for phone_number, username in playerlist.items():
        INFO_MESSAGE += f"{username} : {phone_number}\n"
    
    INFO_MESSAGE += f"\nWait List({len(waitlist)}):\n"
    for phone_number, username in waitlist.items():
        INFO_MESSAGE += f"{username} : {phone_number}\n"

    INFO_MESSAGE += f"\nOut List({len(outlist)}):\n"
    for phone_number, username in outlist.items():
        INFO_MESSAGE += f"{username} : {phone_number}\n"
    
    return INFO_MESSAGE
    
def add_admin(game_id, phone_number):
    newAdmin = AdminUser()
    newAdmin.game = Game.objects.get(id=game_id)
    newAdmin.username = 'admin'
    newAdmin.phone_number = phone_number
    newAdmin.save()

    
def remove_admin(game_id, phone_number):
    admin = AdminUser.objects.filter(game=game_id, phone_number=phone_number)
    admin.delete()

    pass