from twilio.rest import Client
from .models import AdminUser, Game, Player
import os
from datetime import datetime

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

-"/delete (GameID)" : Allows a user to delete a game.

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
    adminlist, location, start_date, start_time, min_players, max_players, playerlist, waitlist, outlist = get_game_info(game_id)
    if len(playerlist) >= min_players:
        INFO_MESSAGE = GAMEINFO_MESSAGE.format(game_id, "✅", len(playerlist), max_players, location, start_date, start_time, min_players, max_players, game_id, game_id)
    else:
        INFO_MESSAGE = GAMEINFO_MESSAGE.format(game_id, "❌", len(playerlist), min_players, location, start_date, start_time, min_players, max_players, game_id, game_id)
        
    INFO_MESSAGE += f"\nAdmin List({len(adminlist)})"
    for phone_number, username in adminlist.items():
        INFO_MESSAGE += f"{username} : {phone_number}\n"
        
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
